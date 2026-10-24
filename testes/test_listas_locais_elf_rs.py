"""Testes de listas locais lista[inteiro] no emissor ELF64 escrito em RS.

Listas signed64 dinamicas via mmap/mremap: capacidade inicial de oito.
O codigo do emissor e escrito em RS e construido por bootstrap Python.
"""
import unittest
from testes import test_emissao_corpos_funcoes_elf_rs as base_corpos


class TestesListasLocaisELFRS(unittest.TestCase):
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

    def test_declaracao_adicao_leitura_e_comprimento(self):
        casos = (
            (
                "funcao executar() -> inteiro {\n"
                " seja valores: lista[inteiro]\n"
                " adicione(valores, 5)\n"
                " adicione(valores, 11)\n"
                " retorne valores[0] + valores[1] + tamanho(valores)\n}\n"
                "inicio { seja r = executar() }", 18
            ),
            (
                "funcao executar() -> inteiro {\n"
                " seja valores: lista[inteiro]\n"
                " retorne tamanho(valores)\n}\n"
                "inicio { seja r = executar() }", 0
            ),
            (
                "funcao executar(n: inteiro) -> inteiro {\n"
                " seja valores: lista[inteiro]\n"
                " adicione(valores, n)\n"
                " adicione(valores, n * -2)\n"
                " valores[0] = valores[1] + 20\n"
                " retorne valores[0]\n}\n"
                "inicio { seja r = executar(3) }", 14
            ),
            (
                "funcao executar() -> inteiro {\n"
                " seja valores: lista[inteiro]\n"
                " seja indice = 0\n"
                " enquanto indice < 8 {\n"
                " adicione(valores, indice * 2)\n"
                " indice = indice + 1\n"
                " }\n"
                " retorne valores[7] + tamanho(valores)\n}\n"
                "inicio { seja r = executar() }", 22
            ),
            (
                "funcao dobro(x: inteiro) -> inteiro { retorne x * 2 }\n"
                "funcao executar() -> inteiro {\n"
                " seja valores: lista[inteiro]\n"
                " adicione(valores, dobro(15))\n"
                " retorne valores[0]\n}\n"
                "inicio { seja r = executar() }", 30
            ),
            (
                "funcao executar() -> inteiro {\n"
                " seja primeira: lista[inteiro]\n"
                " seja numero = 7\n"
                " seja segunda: lista[inteiro]\n"
                " adicione(primeira, numero)\n"
                " adicione(segunda, -40)\n"
                " retorne primeira[0] - segunda[0] + tamanho(primeira)\n}\n"
                "inicio { seja r = executar() }", 48
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

    def test_lista_no_bloco_principal_e_escopos(self):
        fonte = (
            "funcao identidade(v: inteiro) -> inteiro { retorne v }\n"
            "inicio {\n"
            " seja r = 0\n"
            " se r == 0 {\n"
            " seja itens: lista[inteiro]\n"
            " adicione(itens, 23)\n"
            " r = identidade(itens[0])\n"
            " }\n"
            " r = r\n"
            "}"
        )
        for nivel in (0, 8):
            codigo, arquivo, status = self.gerar(fonte, nivel)
            self.assertEqual(codigo, 0)
            self.assertIsNotNone(arquivo)
            if status is not None:
                self.assertEqual(status, 23)

    def test_acesso_fora_de_limites_e_capacidade(self):
        casos = (
            " retorne valores[0]",
            " adicione(valores, 12)\n retorne valores[-1]",
            " adicione(valores, 12)\n retorne valores[1]",
            " adicione(valores, 12)\n valores[1] = 3\n retorne 0",

        )
        for nivel in (0, 8):
            for comandos in casos:
                fonte = (
                    "funcao executar() -> inteiro {\n"
                    " seja valores: lista[inteiro]\n"
                    + comandos + "\n}\n"
                    "inicio { seja r = executar() }"
                )
                with self.subTest(nivel=nivel, comandos=comandos):
                    codigo, arquivo, status = self.gerar(fonte, nivel)
                    self.assertEqual(codigo, 0)
                    self.assertIsNotNone(arquivo)
                    if status is not None:
                        self.assertEqual(status, 23)

    def test_crescimento_geometrico_preserva_valores(self):
        casos = (
            (9, 0, 9),
            (17, 8, 17),
            (65, 64, 65),
            (1000, 999, 1000),
            (4097, 4096, 4097),
        )
        for nivel in (0, 8):
            for tamanho, ultimo, esperado in casos:
                fonte = (
                    "funcao executar() -> inteiro {\n"
                    " seja valores: lista[inteiro]\n"
                    " seja indice = 0\n"
                    f" enquanto indice < {tamanho} {{\n"
                    " adicione(valores, indice)\n"
                    " indice = indice + 1\n"
                    " }\n"
                    f" retorne valores[{ultimo}] + tamanho(valores) - {tamanho - 1}\n"
                    "}\n inicio { seja r = executar() }"
                )
                with self.subTest(nivel=nivel, tamanho=tamanho):
                    codigo, arquivo, status = self.gerar(fonte, nivel)
                    self.assertEqual(codigo, 0)
                    self.assertIsNotNone(arquivo)
                    if status is not None:
                        self.assertEqual(status, esperado)

    def test_escrita_em_posicao_apos_remapeamento(self):
        fonte = (
            "funcao executar() -> inteiro {\n"
            " seja valores: lista[inteiro]\n"
            " seja indice = 0\n"
            " enquanto indice < 260 {\n"
            " adicione(valores, indice)\n"
            " indice = indice + 1\n"
            " }\n"
            " valores[0] = 55\n"
            " valores[129] = -70\n"
            " valores[259] = 99\n"
            " retorne valores[0] - valores[129] + valores[259]\n"
            "}\n inicio { seja r = executar() }"
        )
        for nivel in (0, 8):
            codigo, arquivo, status = self.gerar(fonte, nivel)
            self.assertEqual(codigo, 0)
            self.assertIsNotNone(arquivo)
            if status is not None:
                self.assertEqual(status, 224)

    def test_limite_de_um_mebibyte_por_lista(self):
        fonte = (
            "funcao executar() -> inteiro {\n"
            " seja valores: lista[inteiro]\n"
            " seja indice = 0\n"
            " enquanto indice < 131073 {\n"
            " adicione(valores, indice)\n"
            " indice = indice + 1\n"
            " }\n retorne tamanho(valores)\n"
            "}\n inicio { seja r = executar() }"
        )
        for nivel in (0, 8):
            with self.subTest(nivel=nivel):
                codigo, arquivo, status = self.gerar(fonte, nivel)
                self.assertEqual(codigo, 0)
                self.assertIsNotNone(arquivo)
                if status is not None:
                    self.assertEqual(status, 24)

    def test_liberacao_automatica_dentro_de_lacos(self):
        # A mesma posicao de pilha e ocupada muitas vezes: qualquer
        # mmap esquecido apos o fim da iteracao deve ser detectado
        # pelo limite de memoria virtual do processo nativo.
        fonte = (
            "funcao executar() -> inteiro {\n"
            " seja repeticao = 0\n"
            " seja soma = 0\n"
            " enquanto repeticao < 700 {\n"
            " seja valores: lista[inteiro]\n"
            " seja indice = 0\n"
            " enquanto indice < 8192 {\n"
            " adicione(valores, indice)\n"
            " indice = indice + 1\n"
            " }\n"
            " soma = soma + valores[8191]\n"
            " repeticao = repeticao + 1\n"
            " }\n"
            " retorne soma\n"
            "}\n inicio { seja r = executar() }"
        )
        for nivel in (0, 8):
            codigo, arquivo, status = self.gerar(
                fonte, nivel, limite_memoria=80 * 1024 * 1024
            )
            self.assertEqual(codigo, 0)
            self.assertIsNotNone(arquivo)
            if status is not None:
                self.assertEqual(status, (700 * 8191) % 256)

    def test_crescimento_e_escopos_com_pare_e_continue(self):
        fonte = (
            "funcao executar() -> inteiro {\n"
            " seja contador = 0\n"
            " enquanto contador < 20 {\n"
            " seja valores: lista[inteiro]\n"
            " adicione(valores, contador)\n"
            " contador = contador + 1\n"
            " se contador < 15 {\n continue\n }\n"
            " pare\n"
            " }\n retorne contador\n"
            "}\n inicio { seja r = executar() }"
        )
        for nivel in (0, 8):
            codigo, arquivo, status = self.gerar(fonte, nivel)
            self.assertEqual(codigo, 0)
            self.assertIsNotNone(arquivo)
            if status is not None:
                self.assertEqual(status, 15)

    def test_diagnosticos_tipagem_e_escopo(self):
        casos = (
            (18, "funcao executar() -> inteiro {\n"
             " seja n = 3\n adicione(n, 2)\n retorne n\n}\n"
             "inicio { seja r = executar() }"),
            (18, "funcao executar() -> inteiro {\n"
             " seja valores: lista[inteiro]\n"
             " retorne valores\n}\n inicio { seja r = executar() }"),
            (18, "funcao executar() -> inteiro {\n"
             " seja valores: lista[inteiro]\n"
             " valores = 3\n retorne 0\n}\n inicio { seja r = executar() }"),
            (2, "funcao executar() -> inteiro {\n"
             " seja valores: lista[texto]\n"
             " retorne 0\n}\n inicio { seja r = executar() }"),
            (2, "funcao executar() -> inteiro {\n"
             " seja valores: lista[inteiro] = 1\n"
             " retorne 0\n}\n inicio { seja r = executar() }"),
            (5, "funcao executar() -> inteiro {\n"
             " adicione(desconhecida, 1)\n"
             " retorne 0\n}\n inicio { seja r = executar() }"),
            (7, "funcao executar() -> inteiro {\n"
             " se 1 == 1 {\n seja valores: lista[inteiro]\n"
             " adicione(valores, 2)\n }\n"
             " retorne valores[0]\n}\n"
             "inicio { seja r = executar() }"),
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
