"""Testes O0/O8 do emprestimo read-only de buffers dinamicos e fixos ELF64."""
import unittest
from testes import test_emissao_corpos_funcoes_elf_rs as base_corpos


class TestesEmprestimoBytesELF(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        base_corpos.TestesCorposFuncoesELFRS.setUpClass()
        cls.gerador = base_corpos.TestesCorposFuncoesELFRS("test_buffers_bytes_nativos_e_leituras_o0_o8")

    @classmethod
    def tearDownClass(cls):
        base_corpos.TestesCorposFuncoesELFRS.tearDownClass()

    def gerar(self, fonte, nivel, limite_memoria=None):
        return self.gerador.gerar(fonte, nivel, limite_memoria=limite_memoria)

    def test_leitura_sem_copia_e_encadeamento(self):
        casos = (
            (
                "funcao ler(d: emprestimo[bytes]) -> inteiro {\n"
                " retorne d[1] + tamanho(d)\n}\n"
                "inicio {\n seja d: bytes = criar_bytes(128)\n"
                " d[1] = 70\n seja r = ler(d)\n}", 198
            ),
            (
                "funcao ler(d: emprestimo[bytes], i: inteiro) -> inteiro {\n"
                " retorne d[i] + tamanho(d)\n}\n"
                "funcao encaminhar(d: emprestimo[bytes], i: inteiro) -> inteiro {\n"
                " retorne ler(d, i)\n}\n"
                "inicio {\n seja d: bytes = criar_bytes(4)\n"
                " d[3] = 87\n seja r = encaminhar(d, 3)\n}", 91
            ),
            (
                "funcao ler(d: emprestimo[bytes]) -> inteiro {\n"
                " retorne d[0]\n}\n"
                "inicio {\n seja d: bytes = criar_bytes(3)\n"
                " d[0] = 22\n seja r = ler(d)\n"
                " d[0] = 99\n r = r + d[0]\n}", 121
            ),
            (
                "funcao ler(n: inteiro, d: emprestimo[bytes]) -> inteiro {\n"
                " retorne n + d[0]\n}\n"
                "inicio {\n seja d: bytes = criar_bytes(2)\n"
                " d[0] = 22\n seja r = ler(17, d)\n}", 39
            ),
            (
                "funcao ler(d: emprestimo[bytes]) -> inteiro {\n"
                " retorne tamanho(d)\n}\n"
                "inicio {\n seja d: bytes = criar_bytes(0)\n"
                " seja r = ler(d)\n}", 0
            ),
            (
                "funcao ler(d: emprestimo[bytes]) -> inteiro {\n"
                " retorne d[0]\n}\n"
                "inicio {\n seja d: bytes = criar_bytes(2)\n"
                " liberar_bytes(d)\n seja r = ler(d)\n}", 23
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

    def test_rejeitar_mutacao_desalocacao_e_escapes(self):
        casos = (
            (18, "funcao f(d: emprestimo[bytes]) -> inteiro {\n"
             " liberar_bytes(d)\n retorne 1\n}\n"
             "inicio { seja d: bytes = criar_bytes(2)\n seja r = f(d) }"),
            (18, "funcao f(d: emprestimo[bytes]) -> inteiro {\n"
             " d[0] = 3\n retorne 1\n}\n"
             "inicio { seja d: bytes = criar_bytes(2)\n seja r = f(d) }"),
            (18, "funcao f(d: emprestimo[bytes]) -> inteiro {\n"
             " retorne d\n}\n"
             "inicio { seja d: bytes = criar_bytes(2)\n seja r = f(d) }"),
            (18, "funcao f(d: emprestimo[bytes]) -> inteiro {\n"
             " retorne d + 1\n}\n"
             "inicio { seja d: bytes = criar_bytes(2)\n seja r = f(d) }"),
            (18, "funcao f(n: inteiro) -> inteiro { retorne n }\n"
             "inicio { seja d: bytes = criar_bytes(2)\n seja r = f(d) }"),
            (18, "funcao f(d: emprestimo[bytes]) -> inteiro { retorne tamanho(d) }\n"
             "inicio { seja n = 7\n seja r = f(n) }"),
            (18, "funcao f(d: emprestimo[bytes]) -> inteiro { retorne tamanho(d) }\n"
             "inicio { seja d: bytes = criar_bytes(2)\n seja r = f(d[0]) }"),
            (2, "funcao f(d: bytes) -> inteiro { retorne 1 }\n"
             "inicio { seja r = f(1) }"),
        )
        for nivel in (0, 8):
            for esperado, fonte in casos:
                with self.subTest(nivel=nivel, erro=esperado):
                    codigo, dados, status = self.gerar(fonte, nivel)
                    self.assertEqual(codigo, esperado)
                    self.assertIsNone(dados)
                    self.assertIsNone(status)

    def test_emprestimo_fixo_e_reemprestimo_sem_copia(self):
        casos = (
            (
                "funcao ler(d: emprestimo[bytes]) -> inteiro {\n"
                " retorne d[0] + d[2] + tamanho(d)\n}\n"
                'inicio { seja d: bytes = "ABC"\n seja r = ler(d) }', 135,
            ),
            (
                "funcao ler(d: emprestimo[bytes]) -> inteiro { retorne d[1] }\n"
                "funcao repassar(d: emprestimo[bytes]) -> inteiro { retorne ler(d) }\n"
                'inicio { seja d: bytes = "XYZ"\n d[1] = 19\n'
                " seja r = repassar(d) }", 19,
            ),
            (
                "funcao ler(d: emprestimo[bytes]) -> inteiro { retorne tamanho(d) }\n"
                'inicio { seja d: bytes = ""\n seja r = ler(d) }', 0,
            ),
            (
                "funcao ler(d: emprestimo[bytes]) -> inteiro { retorne d[1] }\n"
                'inicio { seja d: bytes = "é"\n seja r = ler(d) }', 169,
            ),
            (
                "funcao ler(d: emprestimo[bytes]) -> inteiro { retorne d[0] }\n"
                'inicio { seja d: bytes = "A"\n seja r = ler(d)\n'
                " d[0] = 42\n r = r + d[0] }", 107,
            ),
            (
                "funcao ler(d: emprestimo[bytes]) -> inteiro { retorne d[0] }\n"
                'inicio { seja a: bytes = "A"\n seja v = 3\n'
                ' seja b: bytes = "Z"\n seja r = ler(a) + ler(b) + v }', 158,
            ),
            (
                "funcao ler(d: emprestimo[bytes]) -> inteiro { retorne d[3] }\n"
                'inicio { seja d: bytes = "ABC"\n seja r = ler(d) }', 23,
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

    def test_emprestimo_fixo_em_escopo_interno(self):
        fonte = (
            "funcao ler(d: emprestimo[bytes]) -> inteiro { retorne d[0] }\n"
            "inicio { seja r = 0\n"
            ' se 1 == 1 { seja d: bytes = "B"\n r = ler(d) }\n'
            " r = r\n}"
        )
        for nivel in (0, 8):
            with self.subTest(nivel=nivel):
                codigo, dados, status = self.gerar(fonte, nivel)
                self.assertEqual(codigo, 0)
                self.assertIsNotNone(dados)
                if status is not None:
                    self.assertEqual(status, 66)

    def test_fixo_nao_pode_ser_devolvido_ou_liberado_pelo_emprestado(self):
        casos = (
            "funcao ler(d: emprestimo[bytes]) -> inteiro { d[0] = 5\n retorne 1 }\n"
            'inicio { seja d: bytes = "A"\n seja r = ler(d) }',
            "funcao ler(d: emprestimo[bytes]) -> inteiro { liberar_bytes(d)\n retorne 1 }\n"
            'inicio { seja d: bytes = "A"\n seja r = ler(d) }',
            "funcao ler(d: emprestimo[bytes]) -> inteiro { retorne d }\n"
            'inicio { seja d: bytes = "A"\n seja r = ler(d) }',
        )
        for nivel in (0, 8):
            for fonte in casos:
                with self.subTest(nivel=nivel):
                    codigo, dados, status = self.gerar(fonte, nivel)
                    self.assertEqual(codigo, 18)
                    self.assertIsNone(dados)
                    self.assertIsNone(status)

    def test_repeticao_emprestada_sem_transferencia(self):
        fonte = (
            "funcao ler(d: emprestimo[bytes]) -> inteiro { retorne d[0] }\n"
            "inicio { seja d: bytes = criar_bytes(1048576)\n"
            " d[0] = 7\n seja i = 0\n seja r = 0\n"
            " enquanto i < 300 { r = r + ler(d)\n i = i + 1 }\n"
            " r = r\n}"
        )
        for nivel in (0, 8):
            codigo, dados, status = self.gerar(
                fonte, nivel, limite_memoria=96 * 1024 * 1024
            )
            self.assertEqual(codigo, 0)
            if status is not None:
                self.assertEqual(status, 7 * 300 % 256)
