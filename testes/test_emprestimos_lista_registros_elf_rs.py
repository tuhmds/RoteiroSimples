"""Emprestimo readonly de lista[Registro] no emissor ELF64 em RS.

Uma referencia transporta o descritor de uma lista dinamica. A funcao
receptora consulta campos e comprimento, sem copia e sem propriedade.
"""
import unittest

from testes import test_emissao_corpos_funcoes_elf_rs as base_corpos


PONTO = "tipo Ponto {\n x: inteiro\n y: inteiro\n}\n"
OUTRO = "tipo Outro {\n chave: inteiro\n}\n"


class TestesEmprestimosListasRegistrosELFRS(unittest.TestCase):
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

    def test_leitura_sem_copia_apos_remapeamento(self):
        casos = (
            (
                PONTO +
                "funcao ler(d: emprestimo[lista[Ponto]]) -> inteiro {\n"
                " retorne d[16].x + tamanho(d)\n}\n"
                "inicio {\n seja v: lista[Ponto]\n seja p: Ponto\n"
                " seja indice = 0\n enquanto indice < 17 {\n"
                " p.x = indice\n p.y = indice + 1\n"
                " adicione(v, p)\n indice = indice + 1\n }\n"
                " seja resultado = ler(v)\n}", 33
            ),
            (
                PONTO +
                "funcao ler(d: emprestimo[lista[Ponto]]) -> inteiro {\n"
                " retorne d[23].y + tamanho(d)\n}\n"
                "funcao encaminhar(d: emprestimo[lista[Ponto]]) -> inteiro {\n"
                " retorne ler(d) + d[0].x\n}\n"
                "inicio {\n seja v: lista[Ponto]\n seja p: Ponto\n"
                " seja indice = 0\n enquanto indice < 24 {\n"
                " p.x = indice\n p.y = indice + 1\n"
                " adicione(v, p)\n indice = indice + 1\n }\n"
                " seja resultado = encaminhar(v)\n}", 48
            ),
            (
                PONTO +
                "funcao ler(d: emprestimo[lista[Ponto]]) -> inteiro {\n"
                " retorne tamanho(d)\n}\n"
                "inicio {\n seja v: lista[Ponto]\n"
                " seja resultado = ler(v)\n}", 0
            ),
            (
                PONTO +
                "funcao somar(a: inteiro, d: emprestimo[lista[Ponto]], b: inteiro) -> inteiro {\n"
                " retorne a + d[8].y + tamanho(d) + b\n}\n"
                "inicio {\n seja v: lista[Ponto]\n seja p: Ponto\n"
                " seja indice = 0\n enquanto indice < 9 {\n"
                " p.y = indice * 2\n adicione(v, p)\n indice = indice + 1\n }\n"
                " seja resultado = somar(5, v, 7)\n}", 37
            ),
            (
                PONTO +
                "funcao ler(d: emprestimo[lista[Ponto]]) -> inteiro {\n"
                " retorne d[0].x + tamanho(d)\n}\n"
                "inicio {\n seja v: lista[Ponto]\n seja p: Ponto\n"
                " p.x = 4\n adicione(v, p)\n"
                " seja resultado = ler(v)\n"
                " v[0].x = 33\n"
                " resultado = resultado + v[0].x\n}", 38
            ),
        )
        for nivel in (0, 8):
            for fonte, esperado in casos:
                with self.subTest(nivel=nivel, esperado=esperado):
                    codigo, dados, status = self.gerar(fonte, nivel)
                    self.assertEqual(codigo, 0)
                    self.assertIsNotNone(dados)
                    if status is not None:
                        self.assertEqual(status, esperado)

    def test_diagnosticos_de_emprestimo_readonly(self):
        casos = (
            (18, PONTO +
             "funcao alterar(d: emprestimo[lista[Ponto]]) -> inteiro {\n"
             " d[0].x = 33\n retorne 0\n}\n"
             "inicio { seja v: lista[Ponto]\n seja r = alterar(v)\n}"),
            (18, PONTO +
             "funcao alterar(d: emprestimo[lista[Ponto]]) -> inteiro {\n"
             " seja p: Ponto\n adicione(d, p)\n retorne 0\n}\n"
             "inicio { seja v: lista[Ponto]\n seja r = alterar(v)\n}"),
            (18, PONTO +
             "funcao devolver(d: emprestimo[lista[Ponto]]) -> inteiro {\n"
             " retorne d\n}\n"
             "inicio { seja v: lista[Ponto]\n seja r = devolver(v)\n}"),
            (18, PONTO + OUTRO +
             "funcao ler(d: emprestimo[lista[Ponto]]) -> inteiro {\n"
             " retorne tamanho(d)\n}\n"
             "inicio { seja v: lista[Outro]\n seja r = ler(v)\n}"),
            (18, PONTO +
             "funcao ler(d: emprestimo[lista[Ponto]]) -> inteiro {\n"
             " retorne tamanho(d)\n}\n"
             "inicio { seja v: lista[inteiro]\n seja r = ler(v)\n}"),
            (18, PONTO +
             "funcao ler(d: emprestimo[lista[inteiro]]) -> inteiro {\n"
             " retorne tamanho(d)\n}\n"
             "inicio { seja v: lista[Ponto]\n seja r = ler(v)\n}"),
            (2, PONTO +
             "funcao ler(d: emprestimo[lista[Inexistente]]) -> inteiro {\n"
             " retorne 1\n}\n"
             "inicio { seja v: lista[Ponto]\n seja r = ler(v)\n}"),
            (18, PONTO +
             "funcao ler(d: emprestimo[lista[Ponto]]) -> inteiro {\n"
             " retorne tamanho(d)\n}\n"
             "funcao outro(d: emprestimo[lista[inteiro]]) -> inteiro {\n"
             " retorne ler(d)\n}\n"
             "inicio { seja v: lista[inteiro]\n seja r = outro(v)\n}"),
        )
        for nivel in (0, 8):
            for esperado, fonte in casos:
                with self.subTest(nivel=nivel, esperado=esperado):
                    codigo, dados, status = self.gerar(fonte, nivel)
                    self.assertEqual(codigo, esperado)
                    self.assertIsNone(dados)
                    self.assertIsNone(status)

    def test_indice_invalido_em_emprestimo_retorna_23(self):
        casos = (
            "retorne d[0].x",
            "retorne d[-1].y",
            "retorne d[1].x",
        )
        for nivel in (0, 8):
            for retorno in casos:
                fonte = (
                    PONTO +
                    "funcao ler(d: emprestimo[lista[Ponto]]) -> inteiro {\n"
                    " " + retorno + "\n}\n"
                    "inicio { seja v: lista[Ponto]\n"
                    " seja p: Ponto\n"
                    " adicione(v, p)\n"
                    " seja r = ler(v)\n}"
                )
                with self.subTest(nivel=nivel, retorno=retorno):
                    codigo, dados, status = self.gerar(fonte, nivel)
                    self.assertEqual(codigo, 0)
                    self.assertIsNotNone(dados)
                    if status is not None:
                        if retorno == "retorne d[0].x":
                            self.assertEqual(status, 0)
                        else:
                            self.assertEqual(status, 23)


if __name__ == "__main__":
    unittest.main()
