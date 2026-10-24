"""Regressao de escapes ASCII/JSON em buffers bytes fixos do emissor ELF RS.

Os testes compilam o emissor escrito em RS usando o bootstrap de
desenvolvimento e executam os ELF64 gerados em Linux x86-64.
"""
import unittest
from testes import test_emissao_corpos_funcoes_elf_rs as base_corpos


class TestesEscapesBytesFixosELF(unittest.TestCase):
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

    def test_escapes_simples_com_comprimento_decodificado(self):
        casos = (
            (r"A\nB", 13),
            (r"A\tB", 12),
            (r"A\rB", 16),
            (r"A\\B", 95),
            (r"A\"B", 37),
            (r"A\/B", 50),
            (r"A\bB", 11),
            (r"A\fB", 15),
            ("Ação", 201),
        )
        for nivel in (0, 8):
            for literal, esperado in casos:
                fonte = (
                    "funcao f() -> inteiro {\n"
                    f' seja dados: bytes = "{literal}"\n'
                    " retorne dados[1] + tamanho(dados)\n}\n"
                    "inicio { seja r = f() }"
                )
                with self.subTest(nivel=nivel, literal=literal):
                    codigo, arquivo, status = self.gerar(fonte, nivel)
                    self.assertEqual(codigo, 0)
                    self.assertIsNotNone(arquivo)
                    if status is not None:
                        self.assertEqual(status, esperado)

    def test_limite_32_aplica_apos_decodificacao(self):
        literal = r"\n" * 32
        for nivel in (0, 8):
            fonte = (
                "funcao f() -> inteiro {\n"
                f' seja dados: bytes = "{literal}"\n'
                " retorne dados[31] + tamanho(dados)\n}\n"
                "inicio { seja r = f() }"
            )
            with self.subTest(nivel=nivel):
                codigo, arquivo, status = self.gerar(fonte, nivel)
                self.assertEqual(codigo, 0)
                self.assertIsNotNone(arquivo)
                if status is not None:
                    self.assertEqual(status, 42)

    def test_escapes_invalidos_ou_buffer_maior_rejeitados(self):
        casos = (r"A\qB", r"A\u00E9", r"\n" * 33)
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

    def test_escapes_de_buffer_fixo_emprestado(self):
        fonte = (
            "funcao ler(d: emprestimo[bytes]) -> inteiro {\n"
            " retorne d[1] + tamanho(d)\n}\n"
            'inicio { seja d: bytes = "A\\tB"\n'
            " seja r = ler(d) }"
        )
        for nivel in (0, 8):
            with self.subTest(nivel=nivel):
                codigo, arquivo, status = self.gerar(fonte, nivel)
                self.assertEqual(codigo, 0)
                self.assertIsNotNone(arquivo)
                if status is not None:
                    self.assertEqual(status, 12)


if __name__ == "__main__":
    unittest.main()
