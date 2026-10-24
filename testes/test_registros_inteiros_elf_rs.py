"""Regressao de registros locais no emissor ELF64 escrito em RS.

Escopo: ate 8 registros de 1 a 8 campos inteiro, somente locais.
O bootstrap Python constroi o emissor RS; o emissor produz ELF64.
"""
import unittest
from testes import test_emissao_corpos_funcoes_elf_rs as base_corpos


TIPO_PONTO = "tipo Ponto {\n x: inteiro\n y: inteiro\n}\n"


class TestesRegistrosInteirosELFRS(unittest.TestCase):
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

    def test_registros_locais_e_expressao_com_campos(self):
        casos = (
            (TIPO_PONTO +
             "funcao calcular() -> inteiro {\n"
             " seja p: Ponto\n"
             " p.x = 12\n p.y = -4\n"
             " retorne p.x + p.y\n}\n"
             "inicio { seja r = calcular() }", 8),
            (TIPO_PONTO +
             "funcao calcular() -> inteiro {\n"
             " seja p: Ponto\n"
             " retorne p.x + p.y\n}\n"
             "inicio { seja r = calcular() }", 0),
            (TIPO_PONTO +
             "funcao calcular(n: inteiro) -> inteiro {\n"
             " seja p: Ponto\n"
             " p.x = n * 2\n p.y = p.x + 3\n"
             " retorne p.y + p.x\n}\n"
             "inicio { seja r = calcular(5) }", 23),
            (TIPO_PONTO +
             "funcao calcular() -> inteiro {\n"
             " seja p: Ponto\n"
             " p.x = 1\n"
             " se p.x == 1 {\n p.y = 30\n }\n"
             " retorne p.y\n}\n"
             "inicio { seja r = calcular() }", 30),
            (TIPO_PONTO +
             "funcao calcular() -> inteiro {\n"
             " seja p: Ponto\n"
             " seja i = 0\n"
             " enquanto i < 8 {\n p.x = p.x + 3\n i = i + 1\n }\n"
             " retorne p.x\n}\n"
             "inicio { seja r = calcular() }", 24),
            (TIPO_PONTO +
             "funcao calcular() -> inteiro {\n"
             " seja p: Ponto\n"
             " p.x = 2\n"
             " se p.x == 2 {\n"
             " seja p: Ponto\n p.x = 50\n }\n"
             " retorne p.x\n}\n"
             "inicio { seja r = calcular() }", 2),
            (TIPO_PONTO +
             "funcao calcular() -> inteiro {\n"
             " seja p: Ponto\n p.x = 20\n p.y = 4\n"
             " retorne p.x / p.y + p.y\n}\n"
             "inicio { seja r = calcular() }", 9),
        )
        for nivel in (0, 8):
            for fonte, esperado in casos:
                with self.subTest(nivel=nivel, esperado=esperado):
                    codigo, arquivo, status = self.gerar(fonte, nivel)
                    self.assertEqual(codigo, 0)
                    self.assertIsNotNone(arquivo)
                    if status is not None:
                        self.assertEqual(status, esperado)

    def test_multiplos_tipos_com_campos_diferentes(self):
        fonte = (
            "tipo Ponto {\n x: inteiro\n y: inteiro\n}\n"
            "tipo Marca {\n etiqueta: inteiro\n nivel: inteiro\n flag: inteiro\n}\n"
            "funcao calcular() -> inteiro {\n"
            " seja p: Ponto\n seja m: Marca\n"
            " p.x = 6\n m.etiqueta = 2\n m.nivel = 7\n"
            " m.flag = p.x * m.nivel\n"
            " retorne m.flag + m.etiqueta\n}\n"
            "inicio { seja r = calcular() }"
        )
        for nivel in (0, 8):
            codigo, arquivo, status = self.gerar(fonte, nivel)
            self.assertEqual(codigo, 0)
            self.assertIsNotNone(arquivo)
            if status is not None:
                self.assertEqual(status, 44)

    def test_registro_no_inicio(self):
        fonte = (
            TIPO_PONTO +
            "funcao identidade(x: inteiro) -> inteiro { retorne x }\n"
            "inicio {\n"
            " seja p: Ponto\n"
            " p.x = 37\n p.y = 4\n"
            " seja r = identidade(p.x) + p.y\n}"
        )
        for nivel in (0, 8):
            codigo, arquivo, status = self.gerar(fonte, nivel)
            self.assertEqual(codigo, 0)
            self.assertIsNotNone(arquivo)
            if status is not None:
                self.assertEqual(status, 41)

    def test_diagnosticos_de_esquemas_e_campos(self):
        casos = (
            (2, "tipo Ponto {\n x: texto\n}\n"
             "funcao f() -> inteiro { retorne 1 }\n inicio { seja r = f() }"),
            (4, "tipo Ponto {\n x: inteiro\n x: inteiro\n}\n"
             "funcao f() -> inteiro { retorne 1 }\n inicio { seja r = f() }"),
            (4, "tipo Ponto {\n x: inteiro\n}\n"
             "tipo Ponto {\n y: inteiro\n}\n"
             "funcao f() -> inteiro { retorne 1 }\n inicio { seja r = f() }"),
            (2, TIPO_PONTO +
             "funcao f() -> inteiro {\n"
             " seja p: Desconhecido\n retorne 0\n}\n"
             "inicio { seja r = f() }"),
            (2, TIPO_PONTO +
             "funcao f() -> inteiro {\n"
             " seja p: Ponto = 1\n retorne 0\n}\n"
             "inicio { seja r = f() }"),
            (5, TIPO_PONTO +
             "funcao f() -> inteiro {\n"
             " seja p: Ponto\n retorne p.inexistente\n}\n"
             "inicio { seja r = f() }"),
            (18, TIPO_PONTO +
             "funcao f() -> inteiro {\n"
             " seja p: Ponto\n retorne p\n}\n"
             "inicio { seja r = f() }"),
            (18, TIPO_PONTO +
             "funcao f() -> inteiro {\n"
             " seja p: Ponto\n p = 3\n retorne 0\n}\n"
             "inicio { seja r = f() }"),
            (18, TIPO_PONTO +
             "funcao f() -> inteiro {\n"
             " seja x = 3\n x.campo = 5\n retorne 0\n}\n"
             "inicio { seja r = f() }"),
            (5, TIPO_PONTO +
             "funcao f() -> inteiro {\n"
             " seja p: Ponto\n p.inexistente = 3\n retorne 0\n}\n"
             "inicio { seja r = f() }"),
            (5, TIPO_PONTO +
             "funcao f() -> inteiro {\n"
             " se 1 == 1 {\n seja p: Ponto\n p.x = 4\n }\n"
             " retorne p.x\n}\n inicio { seja r = f() }"),
        )
        for nivel in (0, 8):
            for esperado, fonte in casos:
                with self.subTest(nivel=nivel, esperado=esperado):
                    codigo, arquivo, status = self.gerar(fonte, nivel)
                    self.assertEqual(codigo, esperado)
                    self.assertIsNone(arquivo)
                    self.assertIsNone(status)


if __name__ == "__main__":
    unittest.main()
