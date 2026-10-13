"""Resultados com donos, propagação e compatibilidade por execução nativa."""
from pathlib import Path
import sys
import tempfile
import unittest

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))
from backend import compilar
from compilador.erros import ErroCompilacao
from compilador.modulos import carregar_fontes
from compilador.parser import analisar_programa
from testes.test_valores_dinamicos_rs042a import alvo_nativo, rodar

REGISTROS = '''tipo Interno {
    nome: texto
    marcas: lista[logico]
}
tipo Documento {
    interno: Interno
    conteudo: bytes
    codigo: inteiro
}
funcao criar_documento() -> Documento {
    seja documento: Documento
    copie(documento.interno.nome, "Ação RS")
    adicione(documento.interno.marcas, verdadeiro)
    adicione_byte(documento.conteudo, 0)
    adicione_byte(documento.conteudo, 255)
    documento.codigo = 17
    retorne mova(documento)
}
'''


class TestesResultadosProprietariosRS042G(unittest.TestCase):
    def verificar(self, fonte, esperado, niveis=(0, 8), erro=None):
        programa = analisar_programa(fonte)
        for nivel in niveis:
            with self.subTest(nivel=nivel):
                for alvo in ('windows', 'linux'):
                    imagem = compilar(programa, alvo, nivel=nivel, otimizar=nivel > 0)
                    if alvo == alvo_nativo():
                        resultado, _ = rodar(imagem)
                if erro:
                    self.assertEqual(resultado.returncode, 1, resultado.stdout + resultado.stderr)
                    self.assertIn(erro, resultado.stdout + resultado.stderr)
                    self.assertNotIn('INDEVIDO', resultado.stdout)
                else:
                    self.assertEqual((resultado.returncode, resultado.stdout), (0, esperado), resultado.stderr)

    def test_texto_utf8_sucesso_falha_e_extracao_nove_niveis(self):
        fonte = '''funcao criar(escolha: logico) -> resultado[texto] {
    se escolha == falso {
        retorne falha[texto](7)
    }
    seja titulo: texto
    copie(titulo, "Ação RS")
    retorne sucesso[texto](mova(titulo))
}
inicio {
    seja aprovado: resultado[texto] = criar(verdadeiro)
    escreva(aprovado.valido)
    escreva(aprovado.codigo_erro)
    seja titulo = mova(aprovado.valor)
    escreva(titulo)
    escreva(caracteres(titulo))
    seja rejeitado = criar(falso)
    escreva(rejeitado.valido)
    escreva(rejeitado.codigo_erro)
    escreva(tamanho(rejeitado.valor))
}'''
        self.verificar(fonte, '1\n0\nAção RS\n7\n0\n7\n0\n', tuple(range(9)))

    def test_bytes_binarios_em_chamadas_aninhadas_nove_niveis(self):
        fonte = '''funcao criar() -> bytes {
    seja dados: bytes
    adicione_byte(dados, 0)
    adicione_byte(dados, 255)
    retorne mova(dados)
}
funcao encaminhar(resposta: resultado[bytes]) -> resultado[bytes] {
    retorne mova(resposta)
}
funcao consultar(resposta: resultado[bytes], numero: inteiro) -> inteiro {
    retorne resposta.valor[0] + resposta.valor[1] + numero
}
inicio {
    escreva(3 + consultar(encaminhar(sucesso[bytes](criar())), 4) * 2)
    seja rejeitado = encaminhar(falha[bytes](0))
    escreva(rejeitado.codigo_erro)
    escreva(tamanho(rejeitado.valor))
}'''
        self.verificar(fonte, '521\n2\n0\n', tuple(range(9)))

    def test_registro_aninhado_com_tres_donos_nove_niveis(self):
        fonte = REGISTROS + '''funcao criar() -> resultado[Documento] {
    retorne sucesso[Documento](criar_documento())
}
funcao encaminhar(resposta: resultado[Documento]) -> resultado[Documento] {
    propague resposta
    retorne mova(resposta)
}
inicio {
    seja resposta = encaminhar(criar())
    seja documento: Documento = mova(resposta.valor)
    escreva(documento.interno.nome)
    escreva(documento.interno.marcas[0])
    escreva(documento.conteudo[1])
    escreva(documento.codigo)
    seja rejeitado = falha[Documento](12)
    escreva(rejeitado.codigo_erro)
    escreva(tamanho(rejeitado.valor.interno.nome))
    escreva(tamanho(rejeitado.valor.conteudo))
    escreva(tamanho(rejeitado.valor.interno.marcas))
}'''
        self.verificar(fonte, 'Ação RS\n1\n255\n17\n12\n0\n0\n0\n', tuple(range(9)))

    def test_propague_falha_troca_tipo_de_retorno_e_preserva_codigo(self):
        fonte = REGISTROS + '''funcao consultar(escolha: logico) -> resultado[texto] {
    seja titulo: texto
    copie(titulo, "Descartado na falha")
    se escolha == falso {
        retorne falha[texto](-9)
    }
    retorne sucesso[texto](mova(titulo))
}
funcao conferir(escolha: logico) -> resultado[Documento] {
    seja local = criar_documento()
    seja resposta = consultar(escolha)
    propague resposta
    retorne sucesso[Documento](mova(local))
}
funcao informar() -> resultado[inteiro] {
    seja resposta = conferir(falso)
    propague resposta
    retorne sucesso[inteiro](1)
}
inicio {
    seja rejeitado = conferir(falso)
    escreva(rejeitado.valido)
    escreva(rejeitado.codigo_erro)
    seja aprovado = conferir(verdadeiro)
    escreva(aprovado.valor.codigo)
    seja simples = informar()
    escreva(simples.codigo_erro)
}'''
        self.verificar(fonte, '0\n-9\n17\n-9\n')

    def test_propague_resultado_copiavel_para_retorno_proprietario(self):
        fonte = '''funcao numero(escolha: logico) -> resultado[inteiro] {
    se escolha == falso {
        retorne falha[inteiro](21)
    }
    retorne sucesso[inteiro](17)
}
funcao converter(escolha: logico) -> resultado[bytes] {
    seja resposta = numero(escolha)
    propague resposta
    seja dados: bytes
    adicione_byte(dados, resposta.valor)
    retorne sucesso[bytes](mova(dados))
}
inicio {
    seja aprovado = converter(verdadeiro)
    escreva(aprovado.valor[0])
    seja rejeitado = converter(falso)
    escreva(rejeitado.codigo_erro)
}'''
        self.verificar(fonte, '17\n21\n')

    def test_loop_com_temporarios_sucesso_falha_pare_e_continue(self):
        fonte = '''funcao criar(numero: inteiro) -> resultado[bytes] {
    seja dados: bytes
    adicione_byte(dados, numero)
    se numero == 1 {
        retorne falha[bytes](10)
    }
    retorne sucesso[bytes](mova(dados))
}
funcao consultar(resposta: resultado[bytes]) -> inteiro {
    se resposta.valido {
        retorne resposta.valor[0]
    }
    retorne 0
}
inicio {
    seja soma = 0
    para indice de 0 ate 80 {
        seja resposta = criar(indice)
        se resposta.valido == falso {
            continue
        }
        se indice == 80 {
            pare
        }
        soma = soma + consultar(mova(resposta))
        soma = soma + consultar(criar(indice))
    }
    escreva(soma)
}'''
        self.verificar(fonte, '6318\n')

    def test_vazio_e_falha_sao_estados_diferentes_e_transportaveis(self):
        fonte = '''funcao encaminhar(resposta: resultado[texto]) -> resultado[texto] {
    retorne mova(resposta)
}
inicio {
    seja vazio: texto
    seja aprovado = encaminhar(sucesso[texto](mova(vazio)))
    seja rejeitado = encaminhar(falha[texto](0))
    escreva(aprovado.valido)
    escreva(tamanho(aprovado.valor))
    escreva(rejeitado.valido)
    escreva(tamanho(rejeitado.valor))
    escreva(rejeitado.codigo_erro)
}'''
        self.verificar(fonte, '1\n0\n0\n0\n2\n')

    def test_copia_explicita_do_conteudo_e_independente(self):
        fonte = '''inicio {
    seja titulo: texto
    copie(titulo, "RS")
    seja resposta = sucesso[texto](mova(titulo))
    seja copia: texto
    copie(copia, resposta.valor)
    junte(copia, "!")
    escreva(resposta.valor)
    escreva(copia)
    seja dados: bytes
    adicione_byte(dados, 255)
    seja binario = sucesso[bytes](mova(dados))
    seja outro: bytes
    copie(outro, binario.valor)
    outro[0] = 0
    escreva(binario.valor[0])
    escreva(outro[0])
}'''
        self.verificar(fonte, 'RS\nRS!\n255\n0\n')

    def test_payload_movido_nao_pode_ser_consumido_novamente(self):
        for comando in ('escreva(resposta.valor)', 'seja outro = mova(resposta.valor)', 'seja outro = mova(resposta)'):
            fonte = '''inicio {
    seja titulo: texto
    copie(titulo, "RS")
    seja resposta = sucesso[texto](mova(titulo))
    seja movido = mova(resposta.valor)
    ''' + comando + '\n    escreva("INDEVIDO")\n}'
            with self.subTest(comando=comando):
                self.verificar(fonte, '', erro='movimentacao ou liberacao')

    def test_resultado_parcial_nao_pode_ser_retornado(self):
        fonte = REGISTROS + '''funcao parcial() -> resultado[Documento] {
    seja resposta = sucesso[Documento](criar_documento())
    seja titulo = mova(resposta.valor.interno.nome)
    retorne mova(resposta)
}
inicio {
    seja resposta = parcial()
    escreva("INDEVIDO")
}'''
        self.verificar(fonte, '', erro='movimentacao ou liberacao')

    def test_recursao_com_resultado_respeita_orcamento_de_pilha(self):
        fonte = '''funcao repetir(resposta: resultado[texto], numero: inteiro) -> resultado[texto] {
    se numero == 0 {
        retorne mova(resposta)
    }
    retorne repetir(mova(resposta), numero - 1)
}
inicio {
    seja titulo: texto
    copie(titulo, "RS")
    seja recebido = repetir(sucesso[texto](mova(titulo)), 100)
    escreva(recebido.valor)
}'''
        self.verificar(fonte, 'RS\n')
        self.verificar(fonte.replace(')), 100)', ')), 100000)'), '', erro='limite seguro de pilha')

    def test_rejeita_copias_implicitas_em_construcao_argumentos_e_retornos(self):
        funcoes = '''funcao usar(resposta: resultado[texto]) -> inteiro {
    retorne tamanho(resposta.valor)
}
'''
        for corpo, mensagem in (
            ('seja resposta = sucesso[texto](titulo)', 'exige mova'),
            ('seja resposta = sucesso[texto](mova(titulo))\n    seja copia = resposta', 'copia implicita'),
            ('seja resposta = sucesso[texto](mova(titulo))\n    escreva(usar(resposta))', 'exige mova'),
            ('seja resposta = sucesso[texto](mova(titulo))\n    seja copia: resultado[texto] = resposta', 'exige mova'),
            ('seja resposta = sucesso[texto](mova(titulo))\n    escreva(resposta == resposta)', 'nao admite comparacao'),
        ):
            with self.subTest(corpo=corpo), self.assertRaisesRegex(ErroCompilacao, mensagem):
                analisar_programa(funcoes + 'inicio {\n    seja titulo: texto\n    ' + corpo + '\n}')
        with self.assertRaisesRegex(ErroCompilacao, 'retorno proprietario exige mova'):
            analisar_programa('''funcao errado(resposta: resultado[texto]) -> resultado[texto] {
    retorne resposta
}
inicio {
    escreva(1)
}''')

    def test_rejeita_donos_sobrepostos_e_emprestimo_junto_com_consumo(self):
        funcoes = '''funcao combinar(a: resultado[texto], b: texto) -> inteiro {
    retorne 1
}
funcao consultar(a: emprestimo[texto], b: resultado[texto]) -> inteiro {
    retorne 1
}
'''
        for chamada, mensagem in (
            ('combinar(mova(resposta), mova(resposta.valor))', 'mais de uma vez'),
            ('consultar(empreste(resposta.valor), mova(resposta))', 'emprestar e mover'),
        ):
            with self.subTest(chamada=chamada), self.assertRaisesRegex(ErroCompilacao, mensagem):
                analisar_programa(funcoes + 'inicio {\n    seja titulo: texto\n    seja resposta = sucesso[texto](mova(titulo))\n    escreva(' + chamada + ')\n}')

    def test_resultados_de_tipos_distintos_nao_se_confundem(self):
        with self.assertRaisesRegex(ErroCompilacao, 'tipo incompat'):
            analisar_programa('''inicio {
    seja titulo: texto
    seja resposta: resultado[bytes] = sucesso[texto](mova(titulo))
}''')

    def test_recursos_emprestimos_e_resultados_aninhados_continuam_restritos(self):
        for tipo in ('arquivo', 'emprestimo[texto]', 'resultado[texto]', 'lista[inteiro]'):
            with self.subTest(tipo=tipo), self.assertRaises(ErroCompilacao):
                analisar_programa('inicio {\n    seja resposta: resultado[' + tipo + ']\n    escreva(1)\n}')

    def test_biblioteca_demonstrativa_e_exemplo_nove_niveis(self):
        fonte = carregar_fontes(RAIZ / 'exemplos/aplicacoes/documento_resultado_rs042g.rts').texto
        self.verificar(fonte, '0\n1\nRelatório RS\n2\n0\n255\n', tuple(range(9)))

    def test_biblioteca_rejeita_limites_e_altera_titulo_sem_perder_conteudo(self):
        fonte = '''importe "padrao/documentos.rts" como documentos
funcao titulo() -> texto {
    seja valor: texto
    copie(valor, "Olá")
    retorne mova(valor)
}
funcao dados() -> bytes {
    seja valor: bytes
    adicione_byte(valor, 255)
    retorne mova(valor)
}
inicio {
    seja curto = documentos.criar(titulo(), dados(), 3, 1)
    escreva(curto.codigo_erro)
    seja grande = documentos.criar(titulo(), dados(), 4, 0)
    escreva(grande.codigo_erro)
    seja aprovado = documentos.criar(titulo(), dados(), 4, 1)
    seja alterado = documentos.alterar_titulo(mova(aprovado.valor), titulo(), 4)
    escreva(alterado.valor.titulo)
    escreva(alterado.valor.conteudo[0])
}'''
        with tempfile.TemporaryDirectory() as pasta:
            principal = Path(pasta) / 'principal.rts'
            principal.write_text(fonte, encoding='utf-8')
            self.verificar(carregar_fontes(principal).texto, '2\n3\nOlá\n255\n')

    def test_resultados_copiaveis_e_proprietarios_coexistem(self):
        fonte = '''tipo Valor {
    codigo: inteiro
}
funcao antigo() -> resultado[Valor] {
    seja valor: Valor
    valor.codigo = 17
    retorne sucesso[Valor](valor)
}
funcao fixo() -> resultado[texto[16]] {
    seja valor: texto[16]
    copie(valor, "Fixo")
    retorne sucesso[texto[16]](valor)
}
funcao novo() -> resultado[texto] {
    seja valor: texto
    copie(valor, "Dinâmico")
    retorne sucesso[texto](mova(valor))
}
inicio {
    seja original = antigo()
    seja copia = original
    copia.valor.codigo = 99
    escreva(original.valor.codigo)
    escreva(copia.valor.codigo)
    seja original_fixo = fixo()
    seja copia_fixa = original_fixo
    junte(copia_fixa.valor, "!")
    escreva(original_fixo.valor)
    escreva(copia_fixa.valor)
    seja dinamico = novo()
    escreva(dinamico.valor)
}'''
        self.verificar(fonte, '17\n99\nFixo\nFixo!\nDinâmico\n', tuple(range(9)))

    def test_atribuicao_implicita_do_payload_e_do_resultado_e_rejeitada(self):
        for comando, mensagem in (
            ('resposta.valor = titulo', 'campo proprietario nao pode receber atribuicao implicita'),
            ('seja outro = falha[texto](1)\n    outro = resposta', 'registro proprietario nao pode ser copiado'),
        ):
            with self.subTest(comando=comando), self.assertRaisesRegex(ErroCompilacao, mensagem):
                analisar_programa('''inicio {
    seja titulo: texto
    seja resposta = falha[texto](1)
    ''' + comando + '\n}')

    def test_erro_em_declaracao_mantem_localizacao_e_mensagem(self):
        fonte = '''tipo Caixa {
    campo: Desconhecido
}
inicio {
    seja resposta = falha[texto](1)
}'''
        with self.assertRaises(ErroCompilacao) as contexto:
            analisar_programa(fonte)
        self.assertIn('<codigo_rs>:2:', str(contexto.exception))
        self.assertIn('tipo de campo desconhecido', str(contexto.exception))
        self.assertNotIn('OrigemLinha(', str(contexto.exception))


if __name__ == '__main__':
    unittest.main()
