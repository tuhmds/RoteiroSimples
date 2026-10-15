"""Regressões das fronteiras e dos diagnósticos de funções escalares."""

import unittest

from compilador.ast import Funcao, Programa
from compilador.erros import ErroCompilacao
from compilador.funcoes_mistas import (
    chamadas_do_corpo, classificar_funcoes, construir_ir_funcoes,
)
from compilador.parser import analisar_programa
from compilador.ssa_funcoes import construir_ssa_funcoes


FONTE_GRUPO = '''funcao primeira(numero: inteiro) -> inteiro {
    retorne numero + 1
}
funcao segunda(numero: inteiro) -> inteiro {
    retorne primeira(numero) * 2
}
funcao recusada(numero: inteiro) -> inteiro {
    seja titulo: texto
    copie(titulo, "RS")
    retorne numero
}
inicio {
    escreva(segunda(3))
}'''


class TestesFuncoesMistasLegibilidade(unittest.TestCase):
    def test_chamadas_em_argumentos_e_expressoes_sao_unicas_e_ordenadas(self):
        corpo = Programa([
            ('retorne', ('chamada', 'externa', (
                ('chamada', 'interna', (('chamada', 'repetida', ()),)),
                ('neg', ('chamada', 'negada', ())),
                ('nao', ('chamada', 'negada_logica', ())),
                ('bin', '+', ('chamada', 'esquerda', ()),
                 ('chamada', 'direita', ())),
                ('comparacao', '==', ('chamada', 'comparada', ()),
                 ('chamada', 'repetida', ())),
                ('logica', 'e', ('chamada', 'logica_esquerda', ()),
                 ('chamada', 'logica_direita', ())),
                ('indice', 'valores', ('chamada', 'indice', ())),
            ))),
        ], {}, False, {})

        self.assertEqual(chamadas_do_corpo(corpo), (
            'comparada', 'direita', 'esquerda', 'externa', 'indice',
            'interna', 'logica_direita', 'logica_esquerda', 'negada',
            'negada_logica', 'repetida',
        ))

    def test_chamadas_em_ramos_lacos_e_apos_retorno_nao_sao_descartadas(self):
        corpo = Programa([
            ('se', ('chamada', 'condicao', ()),
             [('retorne', ('chamada', 'ramo_verdadeiro', ()))],
             [('retorne', ('chamada', 'ramo_falso', ()))]),
            ('enquanto', ('logico', 0), [
                ('imprima_num', ('chamada', 'laco_inacessivel', ())),
                ('se', ('logico', 0), [
                    ('retorne', ('chamada', 'ramo_inacessivel', ())),
                ], []),
            ]),
            ('para', 'indice', ('chamada', 'limite_inicial', ()),
             ('chamada', 'limite_final', ()), 1, [
                 ('imprima_num', ('chamada', 'laco_para', ())),
                 ('atribua_indice', 'valores',
                  ('chamada', 'posicao', ()), ('chamada', 'valor', ())),
                 ('leia_indice', 'valores', ('chamada', 'posicao', ())),
             ]),
            ('retorne', ('numero', 0)),
            ('atribua', 'numero', ('chamada', 'apos_retorno', ())),
        ], {}, False, {})

        self.assertEqual(chamadas_do_corpo(corpo), (
            'apos_retorno', 'condicao', 'laco_inacessivel', 'laco_para',
            'limite_final', 'limite_inicial', 'posicao', 'ramo_falso',
            'ramo_inacessivel', 'ramo_verdadeiro', 'valor',
        ))

    def test_ciclo_com_dependencia_recusada_contamina_todos_os_participantes(self):
        programa = Programa([], {}, False, {}, funcoes={
            'par': Funcao('par', (), 'inteiro', Programa([
                ('retorne', ('bin', '+', ('chamada', 'impar', ()),
                             ('chamada', 'bloqueada', ()))),
            ], {}, False, {})),
            'impar': Funcao('impar', (), 'inteiro', Programa([
                ('retorne', ('chamada', 'par', ())),
            ], {}, False, {})),
            'bloqueada': Funcao('bloqueada', (), 'inteiro', Programa([
                ('retorne', ('numero', 1)),
            ], {}, False, {'titulo': 'texto'})),
            'livre': Funcao('livre', (), 'inteiro', Programa([
                ('retorne', ('numero', 7)),
            ], {}, False, {})),
        })

        classificacao = classificar_funcoes(programa)

        self.assertEqual(tuple(classificacao), ('par', 'impar', 'bloqueada', 'livre'))
        self.assertEqual(classificacao, {
            'par': (
                'chamada fora do grupo escalar elegível: bloqueada',
                'chamada fora do grupo escalar elegível: impar',
            ),
            'impar': ('chamada fora do grupo escalar elegível: par',),
            'bloqueada': ('variáveis locais fora do contrato inteiro/logico',),
            'livre': (),
        })

    def test_motivos_preservam_ordem_das_restricoes_cobertura_e_dependencias(self):
        interna = Funcao('interna', (), 'inteiro', Programa([], {}, False, {}))
        restrita = Funcao('restrita', (('titulo', 'texto'),), 'texto', Programa([
            ('zeta_futura',),
            ('alfa_futura',),
            ('retorne', ('indice_bytes', 'dados', ('numero', 0))),
            ('imprima_num', ('byte_texto', 'titulo', ('numero', 0))),
        ], {}, False, {'titulo': 'texto'}, funcoes={'interna': interna}))
        desconhecida = Funcao('desconhecida', (), 'inteiro', Programa([
            ('retorne', ('bin', '+', ('chamada', 'zeta_ausente', ()),
                         ('chamada', 'alfa_ausente', ()))),
        ], {}, False, {}))
        dependente = Funcao('dependente', (), 'texto', Programa([
            ('retorne', ('bin', '+', ('chamada', 'restrita', ()),
                         ('chamada', 'desconhecida', ()))),
        ], {}, False, {}))
        programa = Programa([], {}, False, {}, funcoes={
            'restrita': restrita, 'desconhecida': desconhecida,
            'dependente': dependente,
        })

        self.assertEqual(classificar_funcoes(programa), {
            'restrita': (
                'funções aninhadas fora do contrato escalar',
                'retorno fora do contrato inteiro/logico',
                'parâmetros fora do contrato inteiro/logico',
                'variáveis locais fora do contrato inteiro/logico',
                'instrução ainda sem representação intermediária: alfa_futura',
                'instrução ainda sem representação intermediária: zeta_futura',
                'expressão ainda sem representação intermediária: byte_texto',
                'expressão ainda sem representação intermediária: indice_bytes',
            ),
            'desconhecida': (
                'chamada sem assinatura conhecida: alfa_ausente',
                'chamada sem assinatura conhecida: zeta_ausente',
            ),
            'dependente': (
                'retorno fora do contrato inteiro/logico',
                'chamada fora do grupo escalar elegível: desconhecida',
                'chamada fora do grupo escalar elegível: restrita',
            ),
        })

    def test_grupos_invalidos_preservam_mensagem_e_prioridade_das_verificacoes(self):
        programa = analisar_programa(FONTE_GRUPO)
        selecao_invalida = 'Grupo de funções IR contém função ausente ou não elegível.'
        grupo_incompleto = 'Grupo de funções IR não contém todas as funções chamadas.'
        casos = (
            ((), selecao_invalida),
            (('ausente',), selecao_invalida),
            (('primeira', 'primeira'), selecao_invalida),
            (('recusada',), selecao_invalida),
            (('segunda',), grupo_incompleto),
            (('segunda', 'ausente'), selecao_invalida),
            (('segunda', 'segunda'), selecao_invalida),
            (('segunda', 'recusada'), selecao_invalida),
        )
        for nomes, mensagem in casos:
            with self.subTest(nomes=nomes):
                with self.assertRaises(ErroCompilacao) as falha:
                    construir_ir_funcoes(programa, nomes)
                self.assertEqual(str(falha.exception), mensagem)

        for nivel in (-1, 4):
            with self.subTest(nivel=nivel):
                with self.assertRaises(ValueError) as falha:
                    construir_ir_funcoes(programa, ('segunda', 'ausente'), nivel=nivel)
                self.assertEqual(
                    str(falha.exception),
                    'A IR de funções escalares aceita níveis de 0 a 3.',
                )

    def test_ordem_de_selecao_invertida_preserva_grupo_valido_em_o0_e_o3(self):
        programa = analisar_programa(FONTE_GRUPO)
        original = analisar_programa(FONTE_GRUPO)
        for nivel in (0, 3):
            with self.subTest(nivel=nivel):
                grupo = construir_ir_funcoes(
                    programa, ('segunda', 'primeira'),
                    otimizar=nivel > 0, nivel=nivel,
                )
                self.assertEqual(tuple(grupo.funcoes), ('segunda', 'primeira'))
                for nome, funcao_ir in grupo.funcoes.items():
                    funcao = programa.funcoes[nome]
                    self.assertEqual(funcao_ir.nome, nome)
                    self.assertEqual(funcao_ir.parametros, funcao.parametros)
                    self.assertEqual(funcao_ir.retorno, funcao.retorno)
                self.assertTrue(construir_ssa_funcoes(grupo).validar())
                self.assertEqual(programa, original)


if __name__ == '__main__':
    unittest.main()
