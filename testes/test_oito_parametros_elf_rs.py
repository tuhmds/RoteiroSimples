"""Regressao de oito parametros na ABI interna do emissor ELF64 escrito em RS.

O bootstrap Python so compila o emissor de desenvolvimento. Os programas
testados sao gerados pelo emissor em RS e executados como ELF64 no Linux.
"""
import unittest

from testes import test_emissao_corpos_funcoes_elf_rs as base_corpos


class TestesOitoParametrosELFRS(unittest.TestCase):
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

    def test_oito_inteiros_e_chamada_encadeada(self):
        fonte = (
            "funcao somar8(a: inteiro, b: inteiro, c: inteiro, d: inteiro, "
            "quinto: inteiro, f: inteiro, g: inteiro, h: inteiro) -> inteiro {\n"
            " retorne a + b + c + d + quinto + f + g + h\n}\n"
            "funcao passar8(a: inteiro, b: inteiro, c: inteiro, d: inteiro, "
            "quinto: inteiro, f: inteiro, g: inteiro, h: inteiro) -> inteiro {\n"
            " retorne somar8(a, b, c, d, quinto, f, g, h)\n}\n"
            "inicio { seja r = passar8(1, 2, 3, 4, 5, 6, 7, 8) }"
        )
        for nivel in (0, 8):
            with self.subTest(nivel=nivel):
                codigo, dados, status = self.gerar(fonte, nivel)
                self.assertEqual(codigo, 0)
                self.assertIsNotNone(dados)
                if status is not None:
                    self.assertEqual(status, 36)

    def test_emprestimo_na_quinta_posicao_e_reemprestimo(self):
        fonte = (
            "funcao ler8(a: inteiro, b: inteiro, c: inteiro, d: inteiro, "
            "dados: emprestimo[bytes], sexto: inteiro, f: inteiro, g: inteiro) -> inteiro {\n"
            " retorne a + b + c + d + dados[0] + sexto + f + g\n}\n"
            "funcao repassar8(a: inteiro, b: inteiro, c: inteiro, d: inteiro, "
            "dados: emprestimo[bytes], sexto: inteiro, f: inteiro, g: inteiro) -> inteiro {\n"
            " retorne ler8(a, b, c, d, dados, sexto, f, g)\n}\n"
            "inicio {\n"
            " seja dados: bytes = criar_bytes(32)\n"
            " dados[0] = 21\n"
            " seja r = repassar8(1, 2, 3, 4, dados, 5, 6, 7)\n"
            "}"
        )
        for nivel in (0, 8):
            with self.subTest(nivel=nivel):
                codigo, dados, status = self.gerar(fonte, nivel)
                self.assertEqual(codigo, 0)
                self.assertIsNotNone(dados)
                if status is not None:
                    self.assertEqual(status, 49)

    def test_nove_parametros_sao_rejeitados(self):
        fonte = (
            "funcao nove(a: inteiro, b: inteiro, c: inteiro, d: inteiro, "
            "quinto: inteiro, f: inteiro, g: inteiro, h: inteiro, i: inteiro) -> inteiro {\n"
            " retorne a\n}\n"
            "inicio { seja r = nove(1, 2, 3, 4, 5, 6, 7, 8, 9) }"
        )
        for nivel in (0, 8):
            with self.subTest(nivel=nivel):
                codigo, dados, status = self.gerar(fonte, nivel)
                self.assertEqual(codigo, 2)
                self.assertIsNone(dados)
                self.assertIsNone(status)

    def test_oito_parametros_com_sete_argumentos_sao_rejeitados(self):
        fonte = (
            "funcao oito(a: inteiro, b: inteiro, c: inteiro, d: inteiro, "
            "quinto: inteiro, f: inteiro, g: inteiro, h: inteiro) -> inteiro {\n"
            " retorne a\n}\n"
            "inicio { seja r = oito(1, 2, 3, 4, 5, 6, 7) }"
        )
        for nivel in (0, 8):
            with self.subTest(nivel=nivel):
                codigo, dados, status = self.gerar(fonte, nivel)
                self.assertEqual(codigo, 13)
                self.assertIsNone(dados)
                self.assertIsNone(status)


if __name__ == "__main__":
    unittest.main()
