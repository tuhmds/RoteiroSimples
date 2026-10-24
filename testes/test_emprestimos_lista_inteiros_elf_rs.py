"""Regressao de emprestimo readonly de lista[inteiro] no emissor ELF64 RS."""
import unittest
from testes import test_emissao_corpos_funcoes_elf_rs as base_corpos


class TestesEmprestimoListaInteirosELFRS(unittest.TestCase):
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

    def test_emprestimo_sem_copia_apos_mremap(self):
        casos = (
            (
                "funcao ler(d: emprestimo[lista[inteiro]]) -> inteiro {\n"
                " retorne d[16] + tamanho(d)\n}\n"
                "inicio {\n seja v: lista[inteiro]\n"
                " seja indice = 0\n"
                " enquanto indice < 17 {\n"
                " adicione(v, indice)\n indice = indice + 1\n }\n"
                " seja r = ler(v)\n}", 33
            ),
            (
                "funcao ler(d: emprestimo[lista[inteiro]]) -> inteiro {\n"
                " retorne d[16] + tamanho(d)\n}\n"
                "funcao encaminhar(d: emprestimo[lista[inteiro]]) -> inteiro {\n"
                " retorne ler(d) + 1\n}\n"
                "inicio {\n seja v: lista[inteiro]\n"
                " seja indice = 0\n"
                " enquanto indice < 17 {\n"
                " adicione(v, indice)\n indice = indice + 1\n }\n"
                " seja r = encaminhar(v)\n}", 34
            ),
            (
                "funcao ler(d: emprestimo[lista[inteiro]]) -> inteiro {\n"
                " retorne tamanho(d)\n}\n"
                "inicio { seja v: lista[inteiro]\n"
                " seja r = ler(v)\n}", 0
            ),
            (
                "funcao somar(a: inteiro, d: emprestimo[lista[inteiro]], b: inteiro) -> inteiro {\n"
                " retorne a + d[8] + tamanho(d) + b\n}\n"
                "inicio {\n seja v: lista[inteiro]\n"
                " seja indice = 0\n enquanto indice < 9 {\n"
                " adicione(v, indice)\n indice = indice + 1\n }\n"
                " seja r = somar(5, v, 7)\n}", 29
            ),
            (
                "funcao consultar(d: emprestimo[lista[inteiro]]) -> inteiro {\n"
                " retorne d[0] + tamanho(d)\n}\n"
                "inicio { seja v: lista[inteiro]\n"
                " adicione(v, 4)\n"
                " seja r = consultar(v)\n"
                " v[0] = 33\n"
                " r = r + v[0]\n}", 38
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

    def test_bloqueia_escrita_insercao_e_fuga_do_emprestimo(self):
        casos = (
            (
                "funcao mexer(d: emprestimo[lista[inteiro]]) -> inteiro {\n"
                " d[0] = 1\n retorne 0\n}\n"
                "inicio { seja v: lista[inteiro]\n"
                " adicione(v, 4)\n seja r = mexer(v)\n}", 18
            ),
            (
                "funcao mexer(d: emprestimo[lista[inteiro]]) -> inteiro {\n"
                " adicione(d, 1)\n retorne 0\n}\n"
                "inicio { seja v: lista[inteiro]\n"
                " seja r = mexer(v)\n}", 18
            ),
            (
                "funcao mexer(d: emprestimo[lista[inteiro]]) -> inteiro {\n"
                " retorne d\n}\n"
                "inicio { seja v: lista[inteiro]\n"
                " seja r = mexer(v)\n}", 18
            ),
            (
                "funcao ler(d: emprestimo[lista[inteiro]]) -> inteiro {\n"
                " retorne tamanho(d)\n}\n"
                "inicio { seja v: bytes = \"ABC\"\n"
                " seja r = ler(v)\n}", 18
            ),
            (
                "funcao ler(d: emprestimo[bytes]) -> inteiro {\n"
                " retorne tamanho(d)\n}\n"
                "inicio { seja v: lista[inteiro]\n"
                " seja r = ler(v)\n}", 18
            ),
            (
                "funcao ler(d: emprestimo[lista[texto]]) -> inteiro {\n"
                " retorne 0\n}\n"
                "inicio { seja v: lista[inteiro]\n"
                " seja r = ler(v)\n}", 2
            ),
        )
        for nivel in (0, 8):
            for fonte, esperado in casos:
                with self.subTest(nivel=nivel, esperado=esperado):
                    codigo, arquivo, status = self.gerar(fonte, nivel)
                    self.assertEqual(codigo, esperado)
                    self.assertIsNone(arquivo)
                    self.assertIsNone(status)

    def test_indice_invalido_emprestado_retorna_23(self):
        fonte = (
            "funcao consultar(d: emprestimo[lista[inteiro]]) -> inteiro {\n"
            " retorne d[4]\n}\n"
            "inicio { seja v: lista[inteiro]\n"
            " adicione(v, 1)\n"
            " seja r = consultar(v)\n}"
        )
        for nivel in (0, 8):
            codigo, arquivo, status = self.gerar(fonte, nivel)
            self.assertEqual(codigo, 0)
            self.assertIsNotNone(arquivo)
            if status is not None:
                self.assertEqual(status, 23)


if __name__ == "__main__":
    unittest.main()
