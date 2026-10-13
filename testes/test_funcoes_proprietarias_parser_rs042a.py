"""RS 0.42A.1: tipagem de transferências e funções com dono único."""
from pathlib import Path
import sys
import unittest

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))
from compilador.parser import analisar_programa
from compilador.erros import ErroCompilacao
from compilador.propriedade import eh_proprietario, PALAVRAS_DESCRITOR


FABRICA = """funcao criar() -> lista[inteiro] {
    seja itens: lista[inteiro]
    adicione(itens, 42)
    retorne mova(itens)
}
"""
CONSUMIDOR = """funcao consumir(itens: lista[inteiro]) -> inteiro {
    retorne itens[0]
}
"""


def fonte(inicio, funcoes=''):
    return funcoes + 'inicio {\n' + inicio + '\n}'


class TestesFuncoesProprietariasParserRS042A(unittest.TestCase):
    def rejeitar(self, codigo, trecho):
        with self.assertRaisesRegex(ErroCompilacao, trecho):
            analisar_programa(codigo)

    def test_fabrica_e_consumo_explicitamente_tipados(self):
        programa = analisar_programa(fonte('''seja primeiro: lista[inteiro] = criar()
seja segundo = mova(primeiro)
escreva(consumir(mova(segundo)))''', FABRICA + CONSUMIDOR))
        self.assertEqual(programa.tipos['segundo'], ('lista_dinamica', 'inteiro'))
        self.assertEqual([no[0] for no in programa.instrucoes], [
            'crie_lista_dinamica', 'receba_valor_dinamico',
            'crie_lista_dinamica', 'receba_valor_dinamico', 'imprima_num'])
        self.assertEqual(programa.funcoes['criar'].programa.instrucoes[-1],
                         ('retorne', ('mova_valor_dinamico', 'itens')))

    def test_resultado_fresco_reserva_descritor_proprietario_temporario(self):
        programa = analisar_programa(fonte('escreva(consumir(criar()))', FABRICA + CONSUMIDOR))
        argumento = programa.instrucoes[0][1][2][0]
        self.assertEqual(argumento[0], 'temporario_composto')
        nome = argumento[1]
        self.assertTrue(eh_proprietario(programa.tipos[nome]))
        self.assertEqual(PALAVRAS_DESCRITOR, 3)
        self.assertEqual(len([t for t in programa.tipos.values() if eh_proprietario(t)]), 1)
        self.assertEqual(argumento[2], ('chamada', 'criar', ()))

    def test_lista_vazia_como_alias_em_assinaturas_e_declaracao(self):
        funcoes = FABRICA.replace('lista[inteiro]', 'lista[]') + CONSUMIDOR.replace('lista[inteiro]', 'lista[]')
        programa = analisar_programa(fonte('seja itens: lista[] = criar()\nescreva(consumir(mova(itens)))', funcoes))
        self.assertEqual(programa.funcoes['criar'].retorno, ('lista_dinamica', 'inteiro'))
        self.assertEqual(programa.funcoes['consumir'].parametros[0][1], ('lista_dinamica', 'inteiro'))

    def test_retorno_encadeado_e_tipo_logico(self):
        codigo = '''funcao criar() -> lista[logico] {
 seja itens: lista[logico]
 adicione(itens, verdadeiro)
 retorne mova(itens)
}
funcao encaminhar() -> lista[logico] {
 retorne criar()
}
inicio {
 seja valores = encaminhar()
 escreva(valores[0])
}'''
        programa = analisar_programa(codigo)
        self.assertEqual(programa.tipos['valores'], ('lista_dinamica', 'logico'))
        self.assertEqual(programa.funcoes['encaminhar'].programa.instrucoes[-1][1][0], 'chamada')

    def test_dono_nu_nao_pode_ser_parametro_nem_retornado(self):
        self.rejeitar(fonte('seja itens: lista[inteiro]\nescreva(consumir(itens))', CONSUMIDOR), 'mova.*dono unico')
        self.rejeitar(FABRICA.replace('retorne mova(itens)', 'retorne itens') + fonte('escreva(1)'), 'retorno proprietario exige mova')

    def test_dono_nu_nao_pode_ser_copiado_em_declaracao(self):
        for declaracao in ('seja copia = origem', 'seja copia: lista[inteiro] = origem'):
            with self.subTest(declaracao=declaracao):
                self.rejeitar(fonte('seja origem: lista[inteiro]\n' + declaracao), 'dono unico.*copiar')

    def test_dono_existente_nao_admite_atribuicao(self):
        self.rejeitar(fonte('''seja origem: lista[inteiro]
seja destino: lista[inteiro]
destino = mova(origem)'''), 'dono unico.*atribuicao')

    def test_mova_exige_variavel_proprietaria_simples(self):
        for codigo in ('seja numero = 1\nseja destino = mova(numero)',
                       'seja fixa: lista[2]\nseja destino = mova(fixa)',
                       'seja destino = mova(criar())'):
            with self.subTest(codigo=codigo):
                self.rejeitar(fonte(codigo, FABRICA), 'mova|esperava')

    def test_comparacao_direta_de_donos_nao_e_permitida(self):
        for operador in ('==', '!=', '<'):
            with self.subTest(operador=operador):
                self.rejeitar(fonte('seja a: lista[inteiro]\nseja b: lista[inteiro]\nescreva(a ' + operador + ' b)'),
                              'dono unico.*comparacao')

    def test_consumo_duplicado_direto_e_aninhado(self):
        funcoes = CONSUMIDOR + '''funcao combinar(a: inteiro, b: inteiro) -> inteiro {
 retorne a + b
}
funcao dois(a: lista[inteiro], b: lista[inteiro]) -> inteiro {
 retorne tamanho(a) + tamanho(b)
}
'''
        for chamada in ('dois(mova(itens), mova(itens))',
                        'combinar(consumir(mova(itens)), consumir(mova(itens)))'):
            with self.subTest(chamada=chamada):
                self.rejeitar(fonte('seja itens: lista[inteiro]\nescreva(' + chamada + ')', funcoes),
                              'consumida mais de uma vez')

    def test_mistura_emprestimo_e_consumo_em_ambas_ordens(self):
        funcoes = CONSUMIDOR + '''funcao consultar(itens: emprestimo[lista[inteiro]]) -> inteiro {
 retorne tamanho(itens)
}
funcao combinar(a: inteiro, b: inteiro) -> inteiro {
 retorne a + b
}
funcao misturar(a: emprestimo[lista[inteiro]], b: lista[inteiro]) -> inteiro {
 retorne tamanho(a) + tamanho(b)
}
funcao inversa(a: lista[inteiro], b: emprestimo[lista[inteiro]]) -> inteiro {
 retorne tamanho(a) + tamanho(b)
}
'''
        chamadas = ('misturar(empreste(itens), mova(itens))',
                    'inversa(mova(itens), empreste(itens))',
                    'combinar(consultar(empreste(itens)), consumir(mova(itens)))',
                    'combinar(consumir(mova(itens)), consultar(empreste(itens)))')
        for chamada in chamadas:
            with self.subTest(chamada=chamada):
                self.rejeitar(fonte('seja itens: lista[inteiro]\nescreva(' + chamada + ')', funcoes),
                              'emprestar e mover o mesmo dono')

    def test_donos_distintos_e_multiplos_emprestimos_permanecem_validos(self):
        funcoes = '''funcao misturar(a: emprestimo[lista[inteiro]], b: lista[inteiro]) -> inteiro {
 retorne tamanho(a) + tamanho(b)
}
funcao consultar(a: emprestimo[lista[inteiro]], b: emprestimo[lista[inteiro]]) -> inteiro {
 retorne tamanho(a) + tamanho(b)
}
'''
        programa = analisar_programa(fonte('''seja a: lista[inteiro]
seja b: lista[inteiro]
escreva(consultar(empreste(a), empreste(a)))
escreva(misturar(empreste(a), mova(b)))''', funcoes))
        self.assertEqual(len(programa.funcoes), 2)

    def test_emprestimo_nao_pode_escapar_nem_virar_dono(self):
        self.rejeitar(fonte('seja itens: lista[inteiro]\nseja alias = empreste(itens)'), 'emprestimo.*variavel local')
        self.rejeitar('''funcao escapar(itens: emprestimo[lista[inteiro]]) -> emprestimo[lista[inteiro]] {
 retorne itens
}
inicio {
 escreva(1)
}''', 'nao pode ser retornado')
        self.rejeitar('''funcao mover(itens: emprestimo[lista[inteiro]]) -> lista[inteiro] {
 retorne mova(itens)
}
inicio {
 escreva(1)
}''', 'mova.*proprietaria')

    def test_tipos_dos_elementos_precisam_coincidir(self):
        self.rejeitar(fonte('seja itens: lista[logico]\nescreva(consumir(mova(itens)))', CONSUMIDOR),
                      'argumento 1.*exige')
        self.rejeitar(fonte('seja itens: lista[logico] = criar()', FABRICA), 'tipo incompat')

    def test_recursao_em_acrescimos_indices_e_retornos_proprietarios(self):
        corpos = ('seja itens: lista[inteiro]\nadicione(itens, f())\nretorne 0',
                  'seja itens: lista[inteiro]\nadicione(itens, 0)\nretorne itens[f()]',
                  'seja dados: bytes[2]\nadicione_byte(dados, 0)\nretorne dados[f()]')
        for corpo in corpos:
            with self.subTest(corpo=corpo):
                programa = analisar_programa('funcao f() -> inteiro {\n' + corpo + '\n}\ninicio {\n escreva(f())\n}')
                self.assertTrue(programa.funcoes['f'].recursiva)
        programa = analisar_programa('''funcao criar() -> lista[inteiro] {
 retorne criar()
}
inicio {
 seja itens = criar()
}''')
        self.assertTrue(programa.funcoes['criar'].recursiva)

    def test_acrescimo_aceita_chamadas_com_argumentos_aninhados(self):
        funcoes = CONSUMIDOR + '''funcao somar(a: inteiro, b: inteiro) -> inteiro {
 retorne a + b
}
'''
        programa = analisar_programa(fonte('''seja origem: lista[inteiro]
seja destino: lista[inteiro]
adicione(destino, somar(consumir(mova(origem)), 1))
escreva(tamanho(destino))''', funcoes))
        self.assertEqual(programa.instrucoes[2][0], 'adicione_lista_dinamica')


if __name__ == '__main__':
    unittest.main()
