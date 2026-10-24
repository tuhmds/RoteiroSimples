"""Regressao de 32 funcoes no emissor ELF64 escrito em RoteiroSimples.

O compilador de desenvolvimento inicializa o emissor; a compilacao
efetiva dos programas abaixo e realizada pelo codigo do emissor em RS.
"""
import unittest

from testes import test_emissao_corpos_funcoes_elf_rs as base_corpos


class TestesTrintaDuasFuncoesELFRS(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        base_corpos.TestesCorposFuncoesELFRS.setUpClass()
        cls.gerador = base_corpos.TestesCorposFuncoesELFRS(
            "test_corpos_de_funcao_com_locais_se_e_retorno_antecipado"
        )

    @classmethod
    def tearDownClass(cls):
        base_corpos.TestesCorposFuncoesELFRS.tearDownClass()

    def gerar(self, fonte, nivel):
        return self.gerador.gerar(fonte, nivel)

    @staticmethod
    def cadeia(quantidade, invertida=False, ciclo=False):
        linhas = []
        for indice in range(quantidade):
            nome = f"etapa_{indice:02d}"
            if ciclo and indice == quantidade - 1:
                corpo = "retorne etapa_00(x) + 1"
            elif indice == quantidade - 1:
                corpo = "retorne x + 1"
            else:
                corpo = f"retorne etapa_{indice + 1:02d}(x) + 1"
            linhas.append(
                f"funcao {nome}(x: inteiro) -> inteiro {{\\n"
                f" {corpo}\\n"
                "}\\n"
            )
        if invertida:
            linhas.reverse()
        return "".join(linhas) + "inicio {\\n seja resultado = etapa_00(7)\\n}"

    def test_trinta_duas_funcoes_chamadas_para_frente_e_para_tras(self):
        for nivel in (0, 8):
            for invertida in (False, True):
                fonte = self.cadeia(32, invertida=invertida)
                with self.subTest(nivel=nivel, invertida=invertida):
                    codigo, dados, status = self.gerar(fonte, nivel)
                    self.assertEqual(codigo, 0)
                    self.assertIsNotNone(dados)
                    if status is not None:
                        self.assertEqual(status, 39)

    def test_trinta_duas_funcoes_com_emprestimo_no_fim(self):
        funcoes = []
        for indice in range(31):
            funcoes.append(
                f"funcao reserva_{indice:02d}() -> inteiro {{\\n"
                f" retorne {indice}\\n"
                "}\\n"
            )
        funcoes.append(
            "funcao consultar(dados: emprestimo[bytes]) -> inteiro {\\n"
            " retorne dados[0] + tamanho(dados)\\n"
            "}\\n"
        )
        fonte = (
            "".join(funcoes)
            + 'inicio {\\n seja dados: bytes = "ABC"\\n'
            + " seja r = consultar(dados) + reserva_30()\\n}"
        )
        for nivel in (0, 8):
            with self.subTest(nivel=nivel):
                codigo, dados, status = self.gerar(fonte, nivel)
                self.assertEqual(codigo, 0)
                self.assertIsNotNone(dados)
                if status is not None:
                    self.assertEqual(status, 98)

    def test_trinta_e_tres_funcoes_geram_erro_de_limite(self):
        fonte = self.cadeia(33)
        for nivel in (0, 8):
            with self.subTest(nivel=nivel):
                codigo, dados, status = self.gerar(fonte, nivel)
                self.assertEqual(codigo, 2)
                self.assertIsNone(dados)
                self.assertIsNone(status)

    def test_ciclo_longo_com_vinte_e_quatro_funcoes_rejeitado(self):
        fonte = self.cadeia(24, invertida=True, ciclo=True)
        for nivel in (0, 8):
            with self.subTest(nivel=nivel):
                codigo, dados, status = self.gerar(fonte, nivel)
                self.assertEqual(codigo, 14)
                self.assertIsNone(dados)
                self.assertIsNone(status)


if __name__ == "__main__":
    unittest.main()
