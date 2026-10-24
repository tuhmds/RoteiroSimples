"""Testes de lista[Registro] com campos inteiros no ELF64 emitido em RS."""
import unittest
from testes import test_emissao_corpos_funcoes_elf_rs as base_corpos


ESQUEMA = "tipo Ponto {\n x: inteiro\n y: inteiro\n}\n"


class TestesListasRegistrosELFRS(unittest.TestCase):
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

    def test_insercao_e_acesso_por_campo(self):
        casos = (
            (
                ESQUEMA +
                "funcao executar() -> inteiro {\n"
                " seja pontos: lista[Ponto]\n"
                " seja p: Ponto\n"
                " p.x = 7\n p.y = 11\n"
                " adicione(pontos, p)\n"
                " retorne pontos[0].x + pontos[0].y + tamanho(pontos)\n"
                "}\n inicio { seja r = executar() }", 19
            ),
            (
                ESQUEMA +
                "funcao executar() -> inteiro {\n"
                " seja pontos: lista[Ponto]\n"
                " retorne tamanho(pontos)\n"
                "}\n inicio { seja r = executar() }", 0
            ),
            (
                ESQUEMA +
                "funcao executar() -> inteiro {\n"
                " seja pontos: lista[Ponto]\n"
                " seja p: Ponto\n"
                " p.x = 8\n p.y = 7\n"
                " adicione(pontos, p)\n"
                " p.x = 44\n"
                " retorne pontos[0].x + p.x\n"
                "}\n inicio { seja r = executar() }", 52
            ),
            (
                ESQUEMA +
                "funcao executar() -> inteiro {\n"
                " seja pontos: lista[Ponto]\n"
                " seja p: Ponto\n p.x = 1\n p.y = 2\n"
                " adicione(pontos, p)\n"
                " pontos[0].x = 31\n"
                " pontos[0].y = pontos[0].x + 5\n"
                " retorne pontos[0].x + pontos[0].y\n"
                "}\n inicio { seja r = executar() }", 67
            ),
            (
                ESQUEMA +
                "funcao executar() -> inteiro {\n"
                " seja pontos: lista[Ponto]\n"
                " seja inteiros: lista[inteiro]\n"
                " seja p: Ponto\n p.x = 6\n"
                " adicione(inteiros, 10)\n"
                " adicione(pontos, p)\n"
                " retorne pontos[0].x + inteiros[0]\n"
                "}\n inicio { seja r = executar() }", 16
            ),
        )
        for nivel in (0, 8):
            for fonte, esperado in casos:
                with self.subTest(nivel=nivel, esperado=esperado):
                    codigo, arquivo, status = self.gerar(fonte, nivel)
                    self.assertEqual(codigo, 0)
                    self.assertIsNotNone(arquivo)
                    if status is not None:
                        self.assertEqual(status, esperado)

    def test_crescimento_remap_e_estruturas_contiguas(self):
        fonte = (
            "tipo Ponto {\n x: inteiro\n y: inteiro\n z: inteiro\n}\n"
            "funcao executar() -> inteiro {\n"
            " seja pontos: lista[Ponto]\n"
            " seja p: Ponto\n"
            " seja i = 0\n"
            " enquanto i < 133 {\n"
            " p.x = i\n p.y = i * 2\n p.z = i + 1\n"
            " adicione(pontos, p)\n"
            " i = i + 1\n"
            " }\n"
            " pontos[130].x = pontos[0].z + pontos[132].x\n"
            " retorne pontos[130].x + pontos[130].y + pontos[132].z + tamanho(pontos)\n"
            "}\n inicio { seja r = executar() }"
        )
        # (1 + 132) + 260 + 133 + 133 = 659 => status Linux 147.
        for nivel in (0, 8):
            codigo, arquivo, status = self.gerar(fonte, nivel)
            self.assertEqual(codigo, 0)
            self.assertIsNotNone(arquivo)
            if status is not None:
                self.assertEqual(status, 659 % 256)

    def test_indices_invalidos_sao_rejeitados_em_runtime(self):
        casos = (
            " retorne itens[0].x",
            " adicione(itens, p)\n retorne itens[-1].x",
            " adicione(itens, p)\n retorne itens[1].x",
            " adicione(itens, p)\n itens[1].y = 4\n retorne 0",
        )
        for nivel in (0, 8):
            for linhas in casos:
                fonte = (
                    ESQUEMA +
                    "funcao executar() -> inteiro {\n"
                    " seja itens: lista[Ponto]\n"
                    " seja p: Ponto\n"
                    + linhas + "\n}\n"
                    "inicio { seja r = executar() }"
                )
                with self.subTest(nivel=nivel, linhas=linhas):
                    codigo, arquivo, status = self.gerar(fonte, nivel)
                    self.assertEqual(codigo, 0)
                    self.assertIsNotNone(arquivo)
                    if status is not None:
                        self.assertEqual(status, 23)

    def test_tipos_incompativeis_e_campos_inexistentes(self):
        casos = (
            (2, ESQUEMA +
             "funcao executar() -> inteiro {\n"
             " seja itens: lista[Fantasma]\n retorne 0\n"
             "}\n inicio { seja r = executar() }"),
            (18, ESQUEMA +
             "funcao executar() -> inteiro {\n"
             " seja itens: lista[Ponto]\n"
             " adicione(itens, 1)\n retorne 0\n"
             "}\n inicio { seja r = executar() }"),
            (18, ESQUEMA +
             "tipo Outro {\n chave: inteiro\n}\n"
             "funcao executar() -> inteiro {\n"
             " seja itens: lista[Ponto]\n"
             " seja p: Outro\n"
             " adicione(itens, p)\n retorne 0\n"
             "}\n inicio { seja r = executar() }"),
            (5, ESQUEMA +
             "funcao executar() -> inteiro {\n"
             " seja itens: lista[Ponto]\n"
             " seja p: Ponto\n adicione(itens, p)\n"
             " retorne itens[0].inexistente\n"
             "}\n inicio { seja r = executar() }"),
            (5, ESQUEMA +
             "funcao executar() -> inteiro {\n"
             " seja itens: lista[Ponto]\n"
             " seja p: Ponto\n adicione(itens, p)\n"
             " itens[0].inexistente = 5\n retorne 0\n"
             "}\n inicio { seja r = executar() }"),
            (18, ESQUEMA +
             "funcao executar() -> inteiro {\n"
             " seja itens: lista[Ponto]\n"
             " seja p: Ponto\n adicione(itens, p)\n"
             " retorne itens[0]\n"
             "}\n inicio { seja r = executar() }"),
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
