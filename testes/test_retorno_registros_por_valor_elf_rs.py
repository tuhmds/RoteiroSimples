"""Retorno de registros por valor no ELF64 gerado pelo compilador escrito em RS."""
import unittest
from testes import test_emissao_corpos_funcoes_elf_rs as base_corpos

TIPO = (
    "tipo Ponto {\n x: inteiro\n y: inteiro\n}\n"
)
ANINHADO = (
    TIPO +
    "tipo Amostra {\n id: inteiro\n ponto: Ponto\n flag: inteiro\n}\n"
)


class TestesRetornoRegistroPorValorELFRS(unittest.TestCase):
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

    def test_retorno_local_e_buffer_independente(self):
        casos = (
            (TIPO +
             "funcao criar() -> Ponto {\n"
             " seja p: Ponto\n"
             " p.x = 40\n p.y = 2\n retorne p\n"
             "}\n"
             "inicio {\n seja resultado: Ponto\n resultado = criar()\n"
             " seja soma = resultado.x + resultado.y\n}", 42),
            (TIPO +
             "funcao criar(n: inteiro) -> Ponto {\n"
             " seja p: Ponto\n p.x = n * 3\n p.y = -2\n"
             " retorne p\n}\n"
             "inicio {\n seja resultado: Ponto\n resultado = criar(7)\n"
             " seja soma = resultado.x + resultado.y\n}", 19),
            (TIPO +
             "funcao criar(a: inteiro, b: inteiro) -> Ponto {\n"
             " seja p: Ponto\n p.x = a\n p.y = b\n"
             " retorne p\n}\n"
             "inicio {\n seja resultado: Ponto\n resultado = criar(17, 5)\n"
             " seja soma = resultado.x + resultado.y\n}", 22),
            (ANINHADO +
             "funcao criar(id: inteiro) -> Amostra {\n"
             " seja a: Amostra\n"
             " a.id = id\n a.ponto.x = 11\n a.ponto.y = 7\n a.flag = 3\n"
             " retorne a\n}\n"
             "inicio {\n seja resultado: Amostra\n resultado = criar(5)\n"
             " seja soma = resultado.id + resultado.ponto.x + resultado.ponto.y + resultado.flag\n}", 26),
            (TIPO +
             "funcao criar(n: inteiro) -> Ponto {\n"
             " seja p: Ponto\n p.x = n\n p.y = 1\n retorne p\n}\n"
             "inicio {\n seja resultado: Ponto\n"
             " resultado = criar(12)\n"
             " resultado = criar(21)\n"
             " seja soma = resultado.x + resultado.y\n}", 22),
        )
        for nivel in (0, 8):
            for fonte, esperado in casos:
                with self.subTest(nivel=nivel, esperado=esperado):
                    codigo, imagem, status = self.gerar(fonte, nivel)
                    self.assertEqual(codigo, 0)
                    self.assertIsNotNone(imagem)
                    if status is not None:
                        self.assertEqual(status, esperado)

    def test_retorno_condicional_e_emprestimo_copiado(self):
        casos = (
            (TIPO +
             "funcao escolher(n: inteiro) -> Ponto {\n"
             " seja p: Ponto\n"
             " se n > 0 {\n"
             " p.x = n\n p.y = 1\n retorne p\n"
             " }\n p.x = 99\n p.y = 2\n retorne p\n}\n"
             "inicio {\n seja r: Ponto\n r = escolher(-1)\n"
             " seja soma = r.x + r.y\n}", 101),
            (TIPO +
             "funcao escolher(n: inteiro) -> Ponto {\n"
             " seja p: Ponto\n"
             " se n > 0 {\n"
             " p.x = n\n p.y = 1\n retorne p\n"
             " }\n p.x = 99\n p.y = 2\n retorne p\n}\n"
             "inicio {\n seja r: Ponto\n r = escolher(12)\n"
             " seja soma = r.x + r.y\n}", 13),
            (TIPO +
             "funcao copiar(origem: emprestimo[Ponto]) -> Ponto {\n"
             " retorne origem\n}\n"
             "inicio {\n seja fonte: Ponto\n fonte.x = 8\n fonte.y = 9\n"
             " seja destino: Ponto\n destino = copiar(fonte)\n"
             " destino.x = 13\n"
             " seja soma = fonte.x + destino.x + destino.y\n}", 30),
            (TIPO +
             "funcao copiar(origem: Ponto) -> Ponto {\n"
             " origem.x = origem.x + 10\n"
             " retorne origem\n}\n"
             "inicio {\n seja fonte: Ponto\n fonte.x = 8\n fonte.y = 9\n"
             " seja destino: Ponto\n destino = copiar(fonte)\n"
             " seja soma = fonte.x + destino.x + destino.y\n}", 35),
        )
        for nivel in (0, 8):
            for fonte, esperado in casos:
                with self.subTest(nivel=nivel, esperado=esperado):
                    codigo, imagem, status = self.gerar(fonte, nivel)
                    self.assertEqual(codigo, 0)
                    self.assertIsNotNone(imagem)
                    if status is not None:
                        self.assertEqual(status, esperado)

    def test_tipos_incompativeis_e_retorno_nao_estruturado(self):
        casos = (
            (18, TIPO +
             "funcao f() -> Ponto {\n retorne 3\n}\n"
             "inicio { seja p: Ponto\n p = f()\n}"),
            (18, TIPO +
             "funcao f() -> Ponto {\n seja p: Ponto\n retorne p.x\n}\n"
             "inicio { seja p: Ponto\n p = f()\n}"),
            (18, TIPO +
             "funcao f() -> Ponto {\n seja p: Ponto\n retorne p\n}\n"
             "inicio { seja n = f()\n}"),
            (18, TIPO +
             "funcao f() -> inteiro {\n retorne 3\n}\n"
             "inicio { seja p: Ponto\n p = f()\n}"),
            (18, ANINHADO +
             "funcao f() -> Amostra {\n seja a: Amostra\n retorne a\n}\n"
             "inicio { seja p: Ponto\n p = f()\n}"),
            (18, TIPO +
             "funcao f() -> Ponto {\n seja p: Ponto\n retorne p\n}\n"
             "inicio { seja p: Ponto\n p = 42\n}"),
            (18, TIPO +
             "funcao f() -> Ponto {\n seja p: Ponto\n retorne p\n}\n"
             "inicio { seja p: Ponto\n p = f() + 1\n}"),
            (2, TIPO +
             "funcao f() -> Inexistente {\n retorne 1\n}\n"
             "inicio { seja n = 1\n}"),
            (18, TIPO +
             "funcao f() -> Ponto {\n seja p: Ponto\n retorne p\n}\n"
             "inicio { seja n = f() + 2\n}"),
        )
        for nivel in (0, 8):
            for esperado, fonte in casos:
                with self.subTest(nivel=nivel, esperado=esperado):
                    codigo, imagem, status = self.gerar(fonte, nivel)
                    self.assertEqual(codigo, esperado)
                    self.assertIsNone(imagem)
                    self.assertIsNone(status)


if __name__ == "__main__":
    unittest.main()
