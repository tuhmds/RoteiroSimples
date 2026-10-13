"""Tipagem, propriedade e efeitos do texto UTF-8 dinâmico."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend import compilar
from compilador.parser import analisar_programa
from compilador.erros import ErroCompilacao
from compilador.propriedade import (
    TIPO_TEXTO_DINAMICO, TIPO_TEXTO_EMPRESTADO, contrato_valor, passo_armazenamento,
)
from compilador.estrategia import decidir_estrategia
from compilador.efeitos_programa import efeito_instrucao_arvore, efeito_expressao_arvore


class TestesTextoDinamicoParserRS042A(unittest.TestCase):
    def rejeitar(self, fonte, trecho=None):
        contexto = self.assertRaisesRegex(ErroCompilacao, trecho) if trecho else self.assertRaises(ErroCompilacao)
        with contexto:
            analisar_programa(fonte)

    def test_contrato_descritor_e_passos_compartilhados(self):
        texto = contrato_valor(TIPO_TEXTO_DINAMICO)
        emprestimo = contrato_valor(TIPO_TEXTO_EMPRESTADO)
        self.assertEqual((texto.palavras, texto.pode_copiar, texto.precisa_descartar), (3, False, True))
        self.assertEqual((emprestimo.palavras, emprestimo.pode_copiar, emprestimo.precisa_descartar), (1, False, False))
        self.assertEqual(passo_armazenamento(TIPO_TEXTO_DINAMICO, {}), 1)
        self.assertEqual(passo_armazenamento(('lista_dinamica', 'inteiro'), {}), 8)
        self.assertTrue(contrato_valor(('texto', 17)).pode_copiar)

    def test_assinaturas_inferencia_e_ambos_geradores(self):
        fonte = '''funcao criar() -> texto {
            seja nome: texto = "ação😀"
            retorne mova(nome)
        }
        funcao transferir(nome: texto) -> texto {
            retorne mova(nome)
        }
        funcao consultar(nome: emprestimo[texto]) -> inteiro {
            retorne caracteres(nome) + tamanho(nome) + capacidade(nome)
        }
        inicio {
            seja recebido = transferir(criar())
            seja outro: texto = mova(recebido)
            escreva(consultar(empreste(outro)))
        }'''
        p = analisar_programa(fonte)
        self.assertEqual(p.tipos['outro'], TIPO_TEXTO_DINAMICO)
        for nivel in range(9):
            self.assertEqual(decidir_estrategia(p, nivel).gerador, 'conservador')
            for alvo in ('windows', 'linux'):
                self.assertTrue(compilar(p, alvo, otimizar=nivel > 0, nivel=nivel))

    def test_copias_implicitas_e_reatribuicoes_rejeitadas(self):
        for comando in ('seja copia = nome', 'seja copia: texto = nome', 'nome = origem', 'nome = mova(origem)'):
            self.rejeitar('inicio {\n seja nome: texto\n seja origem: texto\n ' + comando + '\n}')
        self.rejeitar('''funcao devolver(nome: texto) -> texto {
            retorne nome
        }
        inicio {
            escreva(1)
        }''', 'retorno proprietario')

    def test_consumo_duplicado_e_mistura_com_emprestimo(self):
        cabecalho = '''funcao dois(a: texto, b: texto) -> inteiro {
            retorne 0
        }
        funcao consultar(a: emprestimo[texto], b: texto) -> inteiro {
            retorne 0
        }
        inicio {
            seja nome: texto
'''
        self.rejeitar(cabecalho + 'escreva(dois(mova(nome), mova(nome)))\n}', 'mais de uma vez')
        self.rejeitar(cabecalho + 'escreva(consultar(empreste(nome), mova(nome)))\n}', 'emprestar e mover')

    def test_emprestimos_nao_escapam_nem_sao_mutados(self):
        for comando in ('junte(nome, "x")', 'copie(nome, "x")', 'limpe(nome)', 'libere(nome)',
                        'seja local = nome', 'seja local = mova(nome)', 'nome = outro'):
            self.rejeitar('funcao testar(nome: emprestimo[texto], outro: emprestimo[texto]) -> inteiro {\n'
                          + comando + '\n retorne 0\n}\ninicio {\n escreva(1)\n}')
        self.rejeitar('''funcao escapar(nome: emprestimo[texto]) -> emprestimo[texto] {
            retorne nome
        }
        inicio {
            escreva(1)
        }''', 'retornado')

    def test_texto_e_binario_mantem_tipos_distintos(self):
        for comando in ('seja nome: texto = dados', 'copie(nome, dados)', 'junte(nome, dados)',
                        'escreva(caracteres(dados))', 'escreva(byte_em(dados, 0))'):
            self.rejeitar('inicio {\n seja dados: bytes[8]\n seja nome: texto\n' + comando + '\n}')
        self.rejeitar('inicio {\n seja nome: texto\n nome[0] = 65\n}')
        self.rejeitar('inicio {\n seja nome: texto\n escreva(nome[0])\n}')

    def test_donos_em_registros_e_listas_permanecem_rejeitados(self):
        self.rejeitar('tipo Pessoa {\n nome: texto\n}\ninicio {\n escreva(1)\n}')
        self.rejeitar('inicio {\n seja nomes: lista[texto]\n}')
        self.rejeitar('inicio {\n seja dados: bytes\n}')

    def test_passo_compartilhado_preserva_limite_historico_de_registros(self):
        campos = '\n'.join(f'campo{indice}: bytes[268000000]' for indice in range(10))
        fonte = 'tipo Grande {\n' + campos + '\n}\ninicio {\n seja dados: lista[Grande]\n}'
        p = analisar_programa(fonte)
        for alvo in ('windows', 'linux'):
            with self.assertRaisesRegex(ErroCompilacao, 'Largura do registro'):
                compilar(p, alvo)

    def test_comparacao_de_conteudo_tem_no_e_falha_explicitos(self):
        p = analisar_programa('inicio {\n seja a: texto\n seja b: texto[8]\n escreva(a == b)\n}')
        expressao = p.instrucoes[-1][1]
        self.assertEqual(expressao[0], 'comparacao_texto')
        e = efeito_expressao_arvore(expressao)
        self.assertTrue(e.pode_falhar)
        self.assertEqual(e.leituras, frozenset(('a', 'b')))
        self.rejeitar('inicio {\n seja a: texto\n seja b: texto\n escreva(a < b)\n}')

    def test_novas_operacoes_expoem_memoria_propriedade_e_falhas(self):
        e = efeito_instrucao_arvore(('modifique_texto_dinamico', 'junte', 'destino', ('buffer', 'origem', None)))
        self.assertEqual(e.leituras, frozenset(('destino', 'origem')))
        self.assertEqual(e.escritas, frozenset(('destino',)))
        self.assertTrue(e.pode_falhar)
        self.assertIn('modificar:destino', e.propriedade)
        e = efeito_instrucao_arvore(('carregue_texto_dinamico', 'nome.txt', 'destino'))
        self.assertTrue(e.arquivos and e.pode_falhar)
        self.assertIn('preencher:destino', e.propriedade)

    def test_literal_com_surrogate_isolado_e_rejeitado(self):
        self.rejeitar('inicio {\n seja nome: texto = "\\ud800"\n}', 'literal de texto')

    def test_funcoes_historicas_com_nome_de_consulta_continuam_validas(self):
        p = analisar_programa('''funcao caracteres(numero: inteiro) -> inteiro {
            retorne numero + 1
        }
        inicio {
            escreva(caracteres(7))
        }''')
        self.assertEqual(p.instrucoes[0][1][0], 'chamada')

    def test_consultas_nao_confundem_nomes_locais_com_funcoes(self):
        p = analisar_programa('''inicio {
            se verdadeiro {
                seja caracteres: texto = "é"
                escreva(caracteres(caracteres))
                escreva(byte_em(caracteres, 0))
            }
        }''')
        self.assertTrue(compilar(p, 'windows'))


if __name__ == '__main__':
    unittest.main()
