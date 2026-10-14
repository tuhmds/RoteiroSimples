"""RS 0.42O: gramática lógica, tipos estritos e travessias da frente."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from compilador.ast import formatar_ast
from compilador.erros import ErroCompilacao
from compilador.expressoes import Expressao
from compilador.lexico import tokens
from compilador.parser import analisar_programa
from compilador.semantica import ContextoSemantico


def fonte(corpo, definicoes=''):
    return definicoes + 'inicio {\n' + corpo + '\n}'


def expressao(texto, variaveis=None):
    return Expressao(tokens(texto, 1), 1, variaveis or {}, False).analisar()


class TestesLogicosParserRS042O(unittest.TestCase):
    def rejeitar(self, codigo, trecho):
        with self.assertRaisesRegex(ErroCompilacao, trecho):
            analisar_programa(codigo)

    def test_precedencia_comparacao_negacao_conjuncao_disjuncao(self):
        arvore = expressao('nao idade + 1 >= 18 e permitido ou falso',
                          {'idade': 0, 'permitido': 1})
        self.assertEqual(arvore, (
            'logica', 'ou',
            ('logica', 'e',
             ('nao', ('comparacao', '>=',
                      ('bin', '+', ('var', 'idade'), ('numero', 1)),
                      ('numero', 18))),
             ('var', 'permitido')),
            ('logico', 0)))
        self.assertEqual(expressao('verdadeiro ou falso e verdadeiro'), (
            'logica', 'ou', ('logico', 1),
            ('logica', 'e', ('logico', 0), ('logico', 1))))

    def test_associatividade_a_esquerda_e_nao_recursivo(self):
        for operador in ('e', 'ou'):
            with self.subTest(operador=operador):
                self.assertEqual(expressao(f'verdadeiro {operador} falso {operador} verdadeiro'), (
                    'logica', operador,
                    ('logica', operador, ('logico', 1), ('logico', 0)),
                    ('logico', 1)))
        self.assertEqual(expressao('nao nao verdadeiro'),
                         ('nao', ('nao', ('logico', 1))))
        self.assertEqual(expressao('(verdadeiro ou falso) e nao (1 < 2)'), (
            'logica', 'e', ('logica', 'ou', ('logico', 1), ('logico', 0)),
            ('nao', ('comparacao', '<', ('numero', 1), ('numero', 2)))))

    def test_declaracao_inferencia_retorno_e_condicoes(self):
        programa = analisar_programa(fonte('''seja idade = 20
seja permitido = verdadeiro
seja acesso: logico = permitido e idade >= 18
seja negado = nao acesso ou nao permitido
se acesso e nao negado {
 escreva(acesso)
}
enquanto negado e verdadeiro {
 pare
}
escreva(verificar(acesso))''', '''funcao verificar(valor: logico) -> logico {
 retorne nao valor ou valor e verdadeiro
}
'''))
        self.assertEqual(programa.tipos['acesso'], 'logico')
        self.assertEqual(programa.tipos['negado'], 'logico')
        self.assertEqual(programa.funcoes['verificar'].programa.instrucoes[0][1][0], 'logica')
        # O contrato antigo de condições inteiras permanece compatível.
        analisar_programa(fonte('se 1 {\n escreva(1)\n}\nenquanto 0 {\n pare\n}'))

    def test_expressoes_completas_em_argumentos_parenteses_e_indices(self):
        funcoes = '''funcao indice(valor: logico) -> inteiro {
 se valor {
  retorne 0
 } senao {
  retorne 1
 }
}
funcao confirmar(a: logico, b: logico) -> logico {
 retorne a e b
}
'''
        programa = analisar_programa(fonte('''seja itens: lista[2]
itens[indice(verdadeiro ou falso)] = 42
escreva(itens[indice(nao falso e verdadeiro)])
escreva(confirmar((verdadeiro ou falso), nao (2 == 3)))''', funcoes))
        consulta = programa.instrucoes[-2][1]
        self.assertEqual(consulta[2][2][0][0], 'logica')
        argumentos = programa.instrucoes[-1][1][2]
        self.assertEqual(tuple(arg[0] for arg in argumentos), ('logica', 'nao'))
        self.rejeitar(fonte('seja itens: lista[2]\nescreva(itens[verdadeiro ou falso])'),
                      'índice da lista deve ser inteiro')
        self.rejeitar('inclua matematica\n' + fonte('escreva(somar(verdadeiro e falso, 1))'),
                      'exige dois inteiros')

    def test_operandos_sao_logicos_sem_conversao_implicita(self):
        casos = (
            ('nao 0', 'operador nao exige logico'),
            ('nao 1', 'operador nao exige logico'),
            ('1 e verdadeiro', 'operador e exige dois logicos'),
            ('verdadeiro e 0', 'operador e exige dois logicos'),
            ('0 ou falso', 'operador ou exige dois logicos'),
            ('falso ou 1', 'operador ou exige dois logicos'),
            ('nao falso + 1', 'exige dois inteiros'),
        )
        for expr, trecho in casos:
            with self.subTest(expr=expr):
                self.rejeitar(fonte('escreva(' + expr + ')'), trecho)
        self.rejeitar(fonte('seja itens: lista[inteiro]\nescreva(falso e itens)'),
                      'operador e exige dois logicos')
        self.rejeitar(fonte('seja numero: inteiro = verdadeiro e falso'),
                      'esperava inteiro, recebeu logico')

    def test_lado_nao_executado_tambem_passa_por_validacao_estatica(self):
        casos = (
            ('falso e ausente', 'não foi declarada'),
            ('verdadeiro ou 123', 'exige dois logicos'),
            ('falso e confirmar(1)', 'argumento 1.*exige logico'),
            ('verdadeiro ou confirmar()', 'espera 1 argumentos'),
        )
        funcoes = 'funcao confirmar(valor: logico) -> logico {\n retorne valor\n}\n'
        for expr, trecho in casos:
            with self.subTest(expr=expr):
                self.rejeitar(fonte('escreva(' + expr + ')', funcoes), trecho)

    def test_palavras_reservadas_em_todos_os_nomes_controlados(self):
        for palavra in ('e', 'ou', 'nao'):
            casos = (
                fonte(f'seja {palavra} = verdadeiro'),
                fonte(f'se verdadeiro {{\n seja {palavra}: logico = falso\n}}'),
                fonte('escreva(1)', f'funcao {palavra}() -> logico {{\n retorne verdadeiro\n}}\n'),
                fonte('escreva(1)', f'funcao conferir({palavra}: logico) -> logico {{\n retorne verdadeiro\n}}\n'),
                fonte('escreva(1)', f'tipo {palavra} {{\n valor: inteiro\n}}\n'),
                fonte('escreva(1)', f'tipo Registro {{\n {palavra}: inteiro\n}}\n'),
                fonte(f'para {palavra} de 0 ate 1 {{\n escreva(1)\n}}'),
            )
            for codigo in casos:
                with self.subTest(palavra=palavra, codigo=codigo):
                    self.rejeitar(codigo, 'reservad|contador invalido')
            with self.assertRaisesRegex(ErroCompilacao, 'reservada'):
                ContextoSemantico().registrar(palavra, 'logico', 1)

    def test_expressoes_incompletas_ou_operadores_em_posicao_invalida(self):
        for expr in ('nao', 'verdadeiro e', 'falso ou', 'e verdadeiro',
                     'ou falso', 'verdadeiro e ou falso', '1 + nao verdadeiro',
                     'verdadeiro falso', '1 < 2 < 3', '(verdadeiro ou falso'):
            with self.subTest(expr=expr):
                self.rejeitar(fonte('escreva(' + expr + ')'), 'Linha 2, coluna')

    def test_origens_dos_operadores_e_formatacao_ast(self):
        texto = '  nao idade >= 18 e permitido ou falso'
        contexto = ContextoSemantico()
        contexto.registrar('idade', 'inteiro', 1)
        contexto.registrar('permitido', 'logico', 1)
        arvore, tipo = contexto.expressao_tipada(tokens(texto, 7), 7)
        self.assertEqual(tipo, 'logico')
        for no, palavra in ((arvore, 'ou'), (arvore[2], 'e permitido'),
                            (arvore[2][2], 'nao'), (arvore[2][2][1], '>=')):
            self.assertEqual((no.origem.linha, no.origem.coluna),
                             (7, texto.index(palavra) + 1))
        exibicao = formatar_ast(analisar_programa(fonte('escreva(nao verdadeiro e falso ou verdadeiro)')))
        self.assertEqual(exibicao.count('expressao:logica'), 2)
        self.assertEqual(exibicao.count('expressao:nao'), 1)
        self.assertEqual(exibicao.count('expressao:logico'), 3)

    def test_temporarios_compostos_e_textos_sao_preparados_dentro_da_logica(self):
        funcoes = '''funcao criar() -> lista[inteiro] {
 seja itens: lista[inteiro]
 retorne mova(itens)
}
funcao consumir(itens: lista[inteiro]) -> logico {
 retorne tamanho(itens) == 0
}
'''
        programa = analisar_programa(fonte('''seja a: texto
seja b: texto
escreva(nao (falso ou consumir(criar())))
escreva(falso ou nao (a == b))''', funcoes))
        argumento = programa.instrucoes[-2][1][1][3][2][0]
        self.assertEqual(argumento[0], 'temporario_composto')
        self.assertEqual(programa.tipos[argumento[1]], ('lista_dinamica', 'inteiro'))
        self.assertEqual(programa.instrucoes[-1][1][3][1][0], 'comparacao_texto')

    def test_conflitos_de_propriedade_nao_ficam_ocultos_em_argumentos_logicos(self):
        funcoes = '''funcao consumir(itens: lista[inteiro]) -> logico {
 retorne verdadeiro
}
funcao consultar(itens: emprestimo[lista[inteiro]]) -> logico {
 retorne verdadeiro
}
funcao combinar(a: logico, b: logico) -> logico {
 retorne a e b
}
'''
        casos = (
            ('combinar(falso e consumir(mova(itens)), nao consumir(mova(itens)))',
             'consumida mais de uma vez'),
            ('combinar(nao consumir(mova(itens)), verdadeiro ou consultar(empreste(itens)))',
             'emprestar e mover o mesmo dono'),
        )
        for expr, trecho in casos:
            with self.subTest(expr=expr):
                self.rejeitar(fonte('seja itens: lista[inteiro]\nescreva(' + expr + ')', funcoes), trecho)

    def test_recursao_e_campos_permanecem_visiveis_dentro_da_logica(self):
        programa = analisar_programa(fonte('''seja registro: Registro
registro.valido = verdadeiro
escreva(nao registro.valido ou verificar())''', '''tipo Registro {
 valido: logico
}
funcao verificar() -> logico {
 retorne falso e nao verificar()
}
'''))
        self.assertTrue(programa.funcoes['verificar'].recursiva)
        nome = programa.campos_registro['registro']['valido']
        self.assertEqual(programa.instrucoes[-1][1][2][1], ('var', nome))


if __name__ == '__main__':
    unittest.main()
