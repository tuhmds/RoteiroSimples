"""Contrato, separação de tipos e propriedade dos bytes dinâmicos."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend import compilar
from compilador.parser import analisar_programa
from compilador.erros import ErroCompilacao
from compilador.propriedade import (
    TIPO_BYTES_DINAMICOS, TIPO_BYTES_EMPRESTADOS, contrato_valor,
    passo_armazenamento, eh_bytes, eh_texto,
)
from compilador.estrategia import decidir_estrategia
from compilador.efeitos_programa import efeito_instrucao_arvore, efeito_expressao_arvore


class TestesBytesDinamicosParserRS042A(unittest.TestCase):
    def rejeitar(self, fonte, trecho=None):
        with self.assertRaisesRegex(ErroCompilacao, trecho or '.'):
            analisar_programa(fonte)

    def test_descritor_proprietario_e_emprestimo_compartilham_passo(self):
        for tipo, esperado in ((TIPO_BYTES_DINAMICOS, (3, False, True)),
                               (TIPO_BYTES_EMPRESTADOS, (1, False, False))):
            c = contrato_valor(tipo)
            self.assertEqual((c.palavras, c.pode_copiar, c.precisa_descartar), esperado)
            self.assertEqual(passo_armazenamento(tipo, {}), 1)
            self.assertTrue(eh_bytes(tipo))
            self.assertFalse(eh_texto(tipo))
        self.assertTrue(contrato_valor(('bytes', 17)).pode_copiar)

    def test_assinaturas_inferencia_indices_e_dois_geradores(self):
        p = analisar_programa('''funcao criar() -> bytes {
            seja dados: bytes
            adicione_byte(dados, 255)
            retorne mova(dados)
        }
        funcao encaminhar(dados: bytes) -> bytes {
            retorne mova(dados)
        }
        funcao consultar(dados: emprestimo[bytes]) -> inteiro {
            retorne dados[0] + tamanho(dados) + capacidade(dados)
        }
        inicio {
            seja dados = encaminhar(criar())
            seja outro: bytes = mova(dados)
            escreva(consultar(empreste(outro)))
        }''')
        self.assertEqual(p.tipos['outro'], TIPO_BYTES_DINAMICOS)
        for nivel in range(9):
            self.assertEqual(decidir_estrategia(p, nivel).gerador, 'conservador')
            for alvo in ('windows', 'linux'):
                self.assertTrue(compilar(p, alvo, nivel=nivel, otimizar=nivel > 0))

    def test_copias_implicitas_e_atribuicoes_rejeitadas(self):
        for comando in ('seja copia = dados', 'seja copia: bytes = dados',
                        'dados = outro', 'dados = mova(outro)'):
            self.rejeitar('inicio {\n seja dados: bytes\n seja outro: bytes\n' + comando + '\n}')
        self.rejeitar('funcao devolver(dados: bytes) -> bytes {\n retorne dados\n}\ninicio {\n escreva(1)\n}', 'retorno proprietario')

    def test_consumo_duplicado_e_emprestimo_com_movimentacao_rejeitados(self):
        cabecalho = '''funcao dois(a: bytes, b: bytes) -> inteiro {
            retorne 0
        }
        funcao consultar(a: emprestimo[bytes], b: bytes) -> inteiro {
            retorne 0
        }
        inicio {
            seja dados: bytes
'''
        self.rejeitar(cabecalho + 'escreva(dois(mova(dados), mova(dados)))\n}', 'mais de uma vez')
        self.rejeitar(cabecalho + 'escreva(consultar(empreste(dados), mova(dados)))\n}', 'emprestar e mover')

    def test_emprestimos_nao_escapam_nem_permitem_modificacao(self):
        for comando in ('adicione_byte(dados, 1)', 'dados[0] = 1', 'limpe(dados)',
                        'libere(dados)', 'copie(dados, outro)', 'junte(dados, outro)',
                        'seja local = dados', 'seja local = mova(dados)',
                        'carregue_arquivo("dados.bin", dados)'):
            self.rejeitar('funcao testar(dados: emprestimo[bytes], outro: emprestimo[bytes]) -> inteiro {\n'
                          + comando + '\n retorne 0\n}\ninicio {\n escreva(1)\n}')
        self.rejeitar('funcao escapar(dados: emprestimo[bytes]) -> emprestimo[bytes] {\n retorne dados\n}\ninicio {\n escreva(1)\n}', 'retornado')

    def test_texto_e_bytes_nao_admitem_conversao_implicita(self):
        for comando in ('seja copia: bytes = nome', 'seja copia: texto = dados',
                        'copie(dados, nome)', 'junte(dados, nome)', 'copie(nome, dados)',
                        'junte(nome, dados)', 'escreva(caracteres(dados))',
                        'escreva(byte_em(dados, 0))', 'seja copia: bytes = "texto"'):
            self.rejeitar('inicio {\n seja dados: bytes\n seja nome: texto\n' + comando + '\n}')

    def test_valores_dinamicos_em_registros_e_listas_continuam_pendentes(self):
        self.rejeitar('tipo Registro {\n dados: bytes\n}\ninicio {\n escreva(1)\n}')
        self.rejeitar('inicio {\n seja itens: lista[bytes]\n}')

    def test_indices_e_valores_exigem_inteiros(self):
        for comando in ('dados[falso] = 0', 'dados[0] = falso',
                        'escreva(dados[falso])', 'adicione_byte(dados, falso)'):
            self.rejeitar('inicio {\n seja dados: bytes\n' + comando + '\n}')

    def test_leia_de_indice_binario_rejeita_com_diagnostico_da_linguagem(self):
        for tipo in ('bytes', 'bytes[4]'):
            self.rejeitar('inicio {\n seja dados: ' + tipo + '\n leia(dados[0])\n}',
                          'leia nao admite indices de bytes')
        self.rejeitar('tipo Registro {\n dados: bytes[4]\n}\ninicio {\n seja item: Registro\n leia(item.dados[0])\n}',
                      'leia nao admite indices de bytes')

    def test_operacoes_binarias_preservam_barreiras_de_memoria_e_arquivos(self):
        e = efeito_instrucao_arvore(('modifique_bytes', 'junte', 'destino', ('buffer', 'origem', None)))
        self.assertEqual(e.leituras, frozenset(('destino', 'origem')))
        self.assertEqual(e.escritas, frozenset(('destino',)))
        self.assertIn('modificar:destino', e.propriedade)
        self.assertTrue(e.pode_falhar)
        e = efeito_instrucao_arvore(('carregue_bytes_dinamicos', 'dados.bin', 'destino'))
        self.assertTrue(e.arquivos and e.pode_falhar)
        self.assertIn('preencher:destino', e.propriedade)
        for tag in ('tamanho_bytes_dinamicos', 'capacidade_bytes_dinamicos', 'empreste_bytes_dinamicos'):
            e = efeito_expressao_arvore((tag, 'dados'))
            self.assertTrue(e.pode_falhar)
            self.assertEqual(e.leituras, frozenset(('dados',)))

    def test_comparacao_direta_de_descritores_continua_rejeitada(self):
        self.rejeitar('inicio {\n seja a: bytes\n seja b: bytes\n escreva(a == b)\n}')

    def test_arquivo_inteiro_aceita_bytes_fixos_e_dinamicos(self):
        p = analisar_programa('inicio {\n seja a: bytes[16]\n seja b: bytes\n carregue_arquivo("a.bin", a)\n grave_arquivo("b.bin", b)\n carregue_arquivo("b.bin", b)\n copie(b, a)\n copie(a, b)\n}')
        self.assertIn('carregue_bytes_dinamicos', [op[0] for op in p.instrucoes])
        for alvo in ('windows', 'linux'):
            self.assertTrue(compilar(p, alvo))


if __name__ == '__main__':
    unittest.main()
