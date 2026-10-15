"""Regressões do contrato de escolha do gerador para funções RS."""

from copy import deepcopy
import unittest
from unittest.mock import patch

from compilador.estrategia import EstrategiaFuncao, estrategias_funcoes, percorrer


class TestesEstrategiaFuncoes(unittest.TestCase):
    def test_niveis_e_ativacao_preservam_decisao_do_gerador(self):
        classificacao = {
            'somar': (),
            'gravar': ('retorno fora do contrato inteiro/logico',),
        }

        for nivel in range(9):
            for otimizar in (False, True):
                with self.subTest(nivel=nivel, otimizar=otimizar):
                    with patch(
                        'compilador.estrategia.classificar_funcoes',
                        return_value=classificacao,
                    ):
                        funcoes = estrategias_funcoes(object(), nivel, otimizar)

                    ativo = otimizar and nivel > 0
                    gerador = (
                        'conservador' if not ativo else
                        'ssa' if nivel >= 4 else 'intermediario'
                    )
                    justificativas = () if ativo else ('otimização desativada',)
                    self.assertEqual(
                        funcoes,
                        (
                            EstrategiaFuncao(
                                'somar', True, gerador,
                                min(nivel, 3) if otimizar else 0,
                                justificativas,
                            ),
                            EstrategiaFuncao(
                                'gravar', False, 'conservador', 0,
                                ('retorno fora do contrato inteiro/logico',),
                            ),
                        ),
                    )

    def test_ordem_das_funcoes_reflete_ordem_das_declaracoes(self):
        classificacao = {'segunda': (), 'primeira': ()}
        with patch(
            'compilador.estrategia.classificar_funcoes',
            return_value=classificacao,
        ):
            funcoes = estrategias_funcoes(object(), 8, True)
        self.assertEqual([funcao.nome for funcao in funcoes], ['segunda', 'primeira'])

    def test_blocos_aninhados_preservam_ordem_e_identidade_das_instrucoes(self):
        primeira = ('imprima_num', ('numero', 1))
        segunda = ('imprima_num', ('numero', 2))
        terceira = ('imprima_num', ('numero', 3))
        ultima = ('retorne', ('numero', 4))
        repeticao = ('enquanto', ('logico', False), [primeira])
        contagem = ('para', 'indice', ('numero', 0), ('numero', 1), 1, [segunda])
        condicional = ('se', ('logico', False), [repeticao], [contagem, terceira])
        programa = [condicional, ultima]
        original = deepcopy(programa)

        instrucoes = list(percorrer(programa))

        esperadas = [condicional, repeticao, primeira, contagem, segunda, terceira, ultima]
        self.assertEqual(instrucoes, esperadas)
        for instrucao, esperada in zip(instrucoes, esperadas):
            self.assertIs(instrucao, esperada)
        self.assertEqual(programa, original)


if __name__ == '__main__':
    unittest.main()
