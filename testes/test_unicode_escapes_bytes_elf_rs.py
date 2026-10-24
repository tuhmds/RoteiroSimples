"""Testes de caracteres Unicode nos literais bytes do emissor ELF64 em RS.

Compila o emissor via bootstrap de desenvolvimento e testa seu resultado
nativo nos niveis O0/O8 em Linux. Escapes invalidos sao rejeitados
antes da emissao do codigo executavel.
"""
import unittest

from testes import test_emissao_corpos_funcoes_elf_rs as base_corpos


class TestesEscapesUnicodeBytesELF(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        base_corpos.TestesCorposFuncoesELFRS.setUpClass()
        cls.gerador = base_corpos.TestesCorposFuncoesELFRS(
            "test_buffers_bytes_nativos_e_leituras_o0_o8"
        )

    @classmethod
    def tearDownClass(cls):
        base_corpos.TestesCorposFuncoesELFRS.tearDownClass()

    def gerar(self, fonte, nivel):
        return self.gerador.gerar(fonte, nivel)

    def test_unicode_e_utf8_decodificados_sem_truncamento(self):
        casos = (
            (r"\u0041", 0, 66),
            (r"\u0000", 0, 1),
            (r"A\u00e9", 2, 172),
            (r"\u00E9", 0, 197),
            (r"\u4E2D", 1, 187),
            (r"\uD83D\uDE00", 3, 132),
            (r"\uD800\uDC00", 1, 148),
            (r"\uDBFF\uDFFF", 0, 248),
            (r"\u0061\u0062", 1, 100),
            (r"\uD83D\uDE00\u0000", 4, 5),
            ("Ação" + r"\u00E9", 6, 175),
        )
        for nivel in (0, 8):
            for literal, indice, esperado in casos:
                fonte = (
                    "funcao f() -> inteiro {\n"
                    f' seja dados: bytes = "{literal}"\n'
                    f" retorne dados[{indice}] + tamanho(dados)\n"
                    "}\n inicio { seja r = f() }"
                )
                with self.subTest(nivel=nivel, literal=literal, indice=indice):
                    codigo, arquivo, status = self.gerar(fonte, nivel)
                    self.assertEqual(codigo, 0)
                    self.assertIsNotNone(arquivo)
                    if status is not None:
                        self.assertEqual(status, esperado)

    def test_limite_aplicado_a_bytes_unicode_codificados(self):
        casos = (
            (r"\u00E9" * 16, 0, 227),
            (r"\uD83D\uDE00" * 8, 0, 16),
            (r"\u00E9" * 16 + "A", 17, None),
            (r"\uD83D\uDE00" * 9, 17, None),
        )
        for nivel in (0, 8):
            for literal, codigo_esperado, status_esperado in casos:
                fonte = (
                    "funcao f() -> inteiro {\n"
                    f' seja dados: bytes = "{literal}"\n'
                    " retorne dados[0] + tamanho(dados)\n"
                    "}\n inicio { seja r = f() }"
                )
                with self.subTest(nivel=nivel, tamanho_fonte=len(literal)):
                    codigo, arquivo, status = self.gerar(fonte, nivel)
                    self.assertEqual(codigo, codigo_esperado)
                    if codigo_esperado:
                        self.assertIsNone(arquivo)
                        self.assertIsNone(status)
                    else:
                        self.assertIsNotNone(arquivo)
                        if status is not None:
                            self.assertEqual(status, status_esperado)

    def test_substitutos_solitarios_incompletos_e_hex_invalido(self):
        casos = (
            r"\u", r"\u0", r"\u000", r"\u00G0",
            r"\uD800", r"\uDFFF", r"\uDE00",
            r"\uD800\u0041", r"\uD800A",
            r"\uD800\uDC0G", r"\uD800\uDC",
        )
        for nivel in (0, 8):
            for literal in casos:
                fonte = (
                    "funcao f() -> inteiro {\n"
                    f' seja dados: bytes = "{literal}"\n'
                    " retorne 0\n}\n inicio { seja r = f() }"
                )
                with self.subTest(nivel=nivel, literal=literal):
                    codigo, arquivo, status = self.gerar(fonte, nivel)
                    self.assertEqual(codigo, 17)
                    self.assertIsNone(arquivo)
                    self.assertIsNone(status)

    def test_unicode_emprestado_em_cadeia(self):
        fonte = (
            "funcao consultar(d: emprestimo[bytes]) -> inteiro {\n"
            " retorne d[0] + d[3] + tamanho(d)\n}\n"
            "funcao encaminhar(d: emprestimo[bytes]) -> inteiro {\n"
            " retorne consultar(d)\n}\n"
            'inicio { seja d: bytes = "\\uD83D\\uDE00"\n'
            " seja resultado = encaminhar(d) }"
        )
        for nivel in (0, 8):
            with self.subTest(nivel=nivel):
                codigo, arquivo, status = self.gerar(fonte, nivel)
                self.assertEqual(codigo, 0)
                self.assertIsNotNone(arquivo)
                if status is not None:
                    self.assertEqual(status, 116)


if __name__ == "__main__":
    unittest.main()
