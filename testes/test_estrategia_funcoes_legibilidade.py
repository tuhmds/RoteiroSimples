"""Regressões do contrato de escolha do gerador para funções RS."""

import unittest
from unittest.mock import patch

from compilador.estrategia import EstrategiaFuncao, estrategias_funcoes


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


if __name__ == '__main__':
    unittest.main()
