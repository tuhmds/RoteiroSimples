"""IR e emissao unificada de funcoes, chamadas, atribuicoes e fluxo ELF64."""
import os
from pathlib import Path
import random
import struct
import subprocess
import sys
import tempfile
import unittest

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))
from backend import compilar
from compilador.modulos import carregar_fontes
from compilador.parser import analisar_programa

FERRAMENTA = RAIZ / "exemplos" / "ferramentas" / "compilador_corpos_funcoes_elf_rs.rts"


def alvo_local():
    if sys.platform == "win32":
        return "windows"
    if sys.platform == "linux" and os.uname().machine == "x86_64":
        return "linux"
    raise unittest.SkipTest("Exige Windows ou Linux x86-64")


class TestesCorposFuncoesELFRS(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pasta = tempfile.TemporaryDirectory(prefix="rs_corpos_elf_")
        cls.alvo = alvo_local()
        programa = analisar_programa(carregar_fontes(FERRAMENTA).texto)
        cls.ferramentas = {}
        for nivel in (0, 8):
            for alvo in ("linux", "windows"):
                imagem = compilar(programa, alvo, nivel=nivel, otimizar=nivel > 0)
                if alvo == cls.alvo:
                    destino = Path(cls.pasta.name) / (
                        f"emissor_corpos_{nivel}" + (".exe" if alvo == "windows" else "")
                    )
                    destino.write_bytes(imagem)
                    if alvo == "linux":
                        destino.chmod(0o700)
                    cls.ferramentas[nivel] = destino

    @classmethod
    def tearDownClass(cls):
        if hasattr(cls, "pasta"):
            cls.pasta.cleanup()

    def gerar(self, fonte, nivel):
        with tempfile.TemporaryDirectory(prefix="rs_codigo_corpos_") as pasta:
            raiz = Path(pasta)
            (raiz / "codigo_fonte.rts").write_text(fonte, encoding="utf-8")
            proc = subprocess.run(
                [str(self.ferramentas[nivel])], cwd=raiz, timeout=30,
                capture_output=True, text=True, encoding="utf-8", errors="replace",
            )
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            saida = [int(v) for v in proc.stdout.splitlines()]
            self.assertIn(len(saida), (2, 3))
            arquivo = raiz / "resultado_corpos_elf"
            if saida[0] != 0:
                self.assertFalse(arquivo.exists())
                return saida[0], None, None
            self.assertEqual(len(saida), 3)
            dados = arquivo.read_bytes()
            self.assertEqual(len(dados), saida[2])
            self.assertEqual(dados[:7], b"\x7fELF\x02\x01\x01")
            cabecalho = struct.unpack_from("<HHIQQQIHHHHHH", dados, 16)
            self.assertEqual(cabecalho[0:3], (2, 62, 1))
            self.assertEqual(cabecalho[3], 0x400078)
            segmento = struct.unpack_from("<IIQQQQQQ", dados, 64)
            self.assertEqual(segmento, (1, 5, 0, 0x400000, 0x400000, len(dados), len(dados), 4096))
            self.assertEqual(dados[120:127], bytes((85, 72, 137, 229, 72, 129, 236)))
            self.assertIn(bytes((232,)), dados[127:])
            self.assertIn(bytes((201, 195)), dados[127:])
            if "se " in fonte or "enquanto " in fonte:
                self.assertIn(bytes((72, 57, 200, 15)), dados[127:])
            if "enquanto " in fonte:
                self.assertIn(bytes((233,)), dados[127:])
            status = None
            if self.alvo == "linux":
                arquivo.chmod(0o700)
                status = subprocess.run([str(arquivo)], cwd=raiz, timeout=4).returncode
            return 0, dados, status

    def test_corpos_de_funcao_com_locais_se_e_retorno_antecipado(self):
        casos = (
            ("funcao soma(a: inteiro, b: inteiro) -> inteiro {\n"
             " seja x = a + b\n retorne x\n}\n"
             "inicio {\n seja resultado = soma(3, 8)\n}", 11),
            ("funcao sinal(x: inteiro) -> inteiro {\n"
             " se x < 0 {\n retorne -1\n }\n"
             " se x == 0 {\n retorne 0\n }\n retorne 1\n}\n"
             "inicio {\n seja n = sinal(-4)\n}", 255),
            ("funcao sinal(x: inteiro) -> inteiro {\n"
             " se x < 0 {\n retorne -1\n }\n"
             " se x == 0 {\n retorne 0\n }\n retorne 1\n}\n"
             "inicio {\n seja n = sinal(0)\n}", 0),
            ("funcao sinal(x: inteiro) -> inteiro {\n"
             " se x < 0 {\n retorne -1\n }\n"
             " se x == 0 {\n retorne 0\n }\n retorne 1\n}\n"
             "inicio {\n seja n = sinal(7)\n}", 1),
            ("funcao conta(n: inteiro) -> inteiro {\n"
             " seja x = 0\n enquanto x < n {\n x = x + 1\n }\n"
             " retorne x\n}\n"
             "inicio {\n seja r = conta(9)\n}", 9),
            ("funcao conta(n: inteiro) -> inteiro {\n"
             " seja x = 0\n enquanto x < n {\n"
             " se x == 3 {\n retorne 60\n }\n"
             " x = x + 1\n }\n retorne x\n}\n"
             "inicio {\n seja r = conta(9)\n}", 60),
            ("funcao conta(n: inteiro) -> inteiro {\n"
             " seja x = 0\n enquanto x < n {\n"
             " se x == 3 {\n retorne 60\n }\n"
             " x = x + 1\n }\n retorne x\n}\n"
             "inicio {\n seja r = conta(2)\n}", 2),
            ("funcao anterior(x: inteiro) -> inteiro {\n retorne x - 1\n}\n"
             "funcao posterior(n: inteiro) -> inteiro {\n"
             " seja y = anterior(n)\n"
             " enquanto y < n + 2 {\n y = y + 1\n }\n"
             " retorne y\n}\n"
             "inicio {\n seja k = posterior(7)\n}", 9),
            ("funcao dobro(n: inteiro) -> inteiro {\n retorne n * 2\n}\n"
             "funcao soma(a: inteiro, b: inteiro) -> inteiro {\n"
             " seja x = dobro(a)\n"
             " se b > 0 {\n x = x + b\n }\n"
             " retorne x\n}\n"
             "inicio {\n seja k = soma(11, 5)\n}", 27),
        )
        for nivel in (0, 8):
            for fonte, esperado in casos:
                with self.subTest(nivel=nivel, fonte=fonte):
                    codigo, dados, status = self.gerar(fonte, nivel)
                    self.assertEqual(codigo, 0)
                    self.assertIn(bytes((201, 195)), dados[127:])
                    if status is not None:
                        self.assertEqual(status, esperado % 256)

    def test_codigo_inalcancavel_apos_retorne(self):
        casos = (
            ("funcao f(n: inteiro) -> inteiro {\n retorne n\n n = n + 1\n}\n"
             "inicio {\n seja r = f(1)\n}", 10),
            ("funcao f(n: inteiro) -> inteiro {\n retorne n\n retorne n + 1\n}\n"
             "inicio {\n seja r = f(2)\n}", 10),
            ("funcao f(n: inteiro) -> inteiro {\n seja x = n\n"
             " retorne x\n x = x + 2\n}\n"
             "inicio {\n seja r = f(3)\n}", 10),
            ("funcao f(n: inteiro) -> inteiro {\n"
             " se n > 0 {\n retorne n\n n = n + 2\n }\n"
             " retorne 0\n}\n inicio {\n seja r = f(1)\n}", 10),
            ("funcao f(n: inteiro) -> inteiro {\n"
             " enquanto n > 0 {\n retorne n\n n = n - 1\n }\n"
             " retorne 0\n}\n inicio {\n seja r = f(1)\n}", 10),
            ("funcao f(n: inteiro) -> inteiro {\n"
             " se n > 0 {\n se n > 1 {\n retorne n\n n = n - 1\n }\n }\n"
             " retorne 0\n}\n inicio {\n seja r = f(1)\n}", 10),
        )
        for nivel in (0, 8):
            for fonte, esperado in casos:
                with self.subTest(nivel=nivel, fonte=fonte):
                    codigo, arquivo, resultado = self.gerar(fonte, nivel)
                    self.assertEqual(codigo, esperado)
                    self.assertIsNone(arquivo)
                    self.assertIsNone(resultado)

    def test_caminho_sem_retorno_final(self):
        casos = (
            "funcao f(n: inteiro) -> inteiro {\n seja x = n + 1\n}\n"
            "inicio {\n seja r = f(3)\n}",
            "funcao f(n: inteiro) -> inteiro {\n"
            " se n > 0 {\n retorne n\n }\n}\n"
            "inicio {\n seja r = f(3)\n}",
            "funcao f(n: inteiro) -> inteiro {\n"
            " enquanto n > 0 {\n retorne n\n }\n}\n"
            "inicio {\n seja r = f(3)\n}",
            "funcao f(n: inteiro) -> inteiro {\n"
            " se n > 0 {\n retorne n\n }\n n = n + 1\n}\n"
            "inicio {\n seja r = f(3)\n}",
        )
        for nivel in (0, 8):
            for fonte in casos:
                with self.subTest(nivel=nivel, fonte=fonte):
                    codigo, arquivo, resultado = self.gerar(fonte, nivel)
                    self.assertEqual(codigo, 11)
                    self.assertIsNone(arquivo)
                    self.assertIsNone(resultado)

    def test_retorno_antecipado_nao_bloqueia_bloco_externo(self):
        casos = (
            ("funcao f(n: inteiro) -> inteiro {\n"
             " se n > 0 {\n retorne 7\n }\n"
             " n = n + 3\n retorne n\n}\n"
             "inicio {\n seja r = f(2)\n}", 7),
            ("funcao f(n: inteiro) -> inteiro {\n"
             " se n > 0 {\n retorne 7\n }\n"
             " n = n + 3\n retorne n\n}\n"
             "inicio {\n seja r = f(-2)\n}", 1),
            ("funcao f(n: inteiro) -> inteiro {\n"
             " enquanto n > 0 {\n retorne 8\n }\n"
             " retorne n\n}\n"
             "inicio {\n seja r = f(4)\n}", 8),
            ("funcao f(n: inteiro) -> inteiro {\n"
             " enquanto n > 0 {\n retorne 8\n }\n"
             " retorne n\n}\n"
             "inicio {\n seja r = f(0)\n}", 0),
            ("funcao f(n: inteiro) -> inteiro {\n"
             " se n > 0 {\n"
             "  se n > 1 {\n retorne 10\n }\n"
             " n = n + 1\n }\n"
             " retorne n\n}\n"
             "inicio {\n seja r = f(1)\n}", 2),
            ("funcao f(n: inteiro) -> inteiro {\n"
             " se n > 0 {\n"
             "  se n > 1 {\n retorne 10\n }\n"
             " n = n + 1\n }\n"
             " retorne n\n}\n"
             "inicio {\n seja r = f(3)\n}", 10),
        )
        for nivel in (0, 8):
            for fonte, esperado in casos:
                with self.subTest(nivel=nivel, fonte=fonte):
                    codigo, arquivo, resultado = self.gerar(fonte, nivel)
                    self.assertEqual(codigo, 0)
                    self.assertIsNotNone(arquivo)
                    if resultado is not None:
                        self.assertEqual(resultado, esperado)

    def test_indice_do_primeiro_comando_inalcancavel(self):
        fonte = ("funcao f(n: inteiro) -> inteiro {\n"
                 " retorne n\n n = n + 1\n}\n"
                 "inicio {\n seja r = f(1)\n}")
        for nivel in (0, 8):
            with self.subTest(nivel=nivel):
                with tempfile.TemporaryDirectory(prefix="rs_caminho_retorno_") as pasta:
                    raiz = Path(pasta)
                    (raiz / "codigo_fonte.rts").write_text(fonte, encoding="utf-8")
                    processo = subprocess.run(
                        [str(self.ferramentas[nivel])], cwd=raiz, timeout=30,
                        capture_output=True, text=True, encoding="utf-8", errors="replace",
                    )
                    self.assertEqual(processo.returncode, 0, processo.stderr)
                    valores = [int(v) for v in processo.stdout.splitlines()]
                    self.assertEqual(len(valores), 2)
                    self.assertEqual(valores[0], 10)
                    self.assertGreater(valores[1], 0)
                    self.assertFalse((raiz / "resultado_corpos_elf").exists())

    def test_retorno_direto_de_chamada(self):
        casos = (
            ("funcao aumentar(n: inteiro) -> inteiro {\n retorne n + 1\n}\n"
             "funcao encaminhar(x: inteiro) -> inteiro {\n retorne aumentar(x)\n}\n"
             "inicio {\n seja resultado = encaminhar(11)\n}", 12),
            ("funcao base() -> inteiro {\n retorne 7\n}\n"
             "funcao encaminhar() -> inteiro {\n retorne base()\n}\n"
             "inicio {\n seja resultado = encaminhar()\n}", 7),
            ("funcao soma(a: inteiro, b: inteiro) -> inteiro {\n retorne a + b\n}\n"
             "funcao responder(x: inteiro) -> inteiro {\n retorne soma(x, 5)\n}\n"
             "inicio {\n seja resultado = responder(10)\n}", 15),
            ("funcao negativo(n: inteiro) -> inteiro {\n retorne 0 - n\n}\n"
             "funcao decidir(n: inteiro) -> inteiro {\n"
             " se n > 0 {\n retorne negativo(n)\n }\n"
             " retorne n\n}\n"
             "inicio {\n seja resultado = decidir(3)\n}", 253),
        )
        for nivel in (0, 8):
            for fonte, esperado in casos:
                with self.subTest(nivel=nivel, fonte=fonte):
                    codigo, dados, status = self.gerar(fonte, nivel)
                    self.assertEqual(codigo, 0)
                    self.assertIn(bytes((232,)), dados[127:])  # call rel32
                    self.assertIn(bytes((201, 195)), dados[127:])  # leave; ret
                    if status is not None:
                        self.assertEqual(status, esperado)

    def test_retorno_direto_invalido(self):
        fontes = (
            "funcao f(n: inteiro) -> inteiro {\n retorne inexistente(n)\n}\n"
            "inicio { seja r = f(2) }",
            "funcao base(n: inteiro) -> inteiro {\n retorne n\n}\n"
            "funcao f() -> inteiro {\n retorne base()\n}\n"
            "inicio { seja r = f() }",
        )
        for nivel in (0, 8):
            for fonte in fontes:
                with self.subTest(nivel=nivel, fonte=fonte):
                    codigo, dados, status = self.gerar(fonte, nivel)
                    self.assertNotEqual(codigo, 0)
                    self.assertIsNone(dados)
                    self.assertIsNone(status)

    def test_diagnosticos_semanticos_de_chamadas(self):
        casos = (
            (12, "funcao base(n: inteiro) -> inteiro {\n retorne n\n}\n"
             "inicio {\n seja r = inexistente(2)\n}"),
            (12, "funcao base(n: inteiro) -> inteiro {\n retorne n\n}\n"
             "inicio {\n seja r = base(inexistente(3))\n}"),
            (12, "funcao base(n: inteiro) -> inteiro {\n retorne desconhecida(n)\n}\n"
             "inicio {\n seja r = base(2)\n}"),
            (13, "funcao soma(a: inteiro, b: inteiro) -> inteiro {\n retorne a + b\n}\n"
             "inicio {\n seja r = soma(1)\n}"),
            (13, "funcao soma(a: inteiro, b: inteiro) -> inteiro {\n retorne a + b\n}\n"
             "inicio {\n seja r = soma(1, 2, 3)\n}"),
            (13, "funcao sem() -> inteiro {\n retorne 7\n}\n"
             "inicio {\n seja r = sem(1)\n}"),
            (13, "funcao sem() -> inteiro {\n retorne 7\n}\n"
             "inicio {\n seja r = sem(sem())\n}"),
            (14, "funcao primeira() -> inteiro {\n retorne segunda()\n}\n"
             "funcao segunda() -> inteiro {\n retorne primeira()\n}\n"
             "inicio {\n seja r = primeira()\n}"),
            (14, "funcao primeira(n: inteiro) -> inteiro {\n retorne primeira(n)\n}\n"
             "inicio {\n seja r = primeira(7)\n}"),
            (15, "funcao f(n: inteiro) -> inteiro {\n retorne n\n}\n"
             "inicio {\n seja r = f(, 1)\n}"),
            (15, "funcao f(n: inteiro) -> inteiro {\n retorne n\n}\n"
             "inicio {\n seja r = f(1,)\n}"),
            (15, "funcao f(n: inteiro) -> inteiro {\n retorne n\n}\n"
             "inicio {\n seja r = f(1,,2)\n}"),
        )
        for nivel in (0, 8):
            for esperado, fonte in casos:
                with self.subTest(nivel=nivel, erro=esperado, fonte=fonte):
                    codigo, dados, status = self.gerar(fonte, nivel)
                    self.assertEqual(codigo, esperado)
                    self.assertIsNone(dados)
                    self.assertIsNone(status)

    def test_assinaturas_restringem_tipos_a_inteiro(self):
        invalidos = (
            "funcao f(n: real) -> inteiro {\n retorne n\n}\n"
            "inicio {\n seja r = f(1)\n}",
            "funcao f(n: inteiro) -> real {\n retorne n\n}\n"
            "inicio {\n seja r = f(1)\n}",
            "funcao f(n: texto) -> inteiro {\n retorne 1\n}\n"
            "inicio {\n seja r = f(1)\n}",
        )
        for nivel in (0, 8):
            for fonte in invalidos:
                with self.subTest(nivel=nivel, fonte=fonte):
                    codigo, dados, status = self.gerar(fonte, nivel)
                    self.assertEqual(codigo, 2)
                    self.assertIsNone(dados)
                    self.assertIsNone(status)

    def test_indice_da_chamada_com_quantidade_incorreta(self):
        fonte = ("funcao soma(a: inteiro, b: inteiro) -> inteiro {\n"
                 " retorne a + b\n}\n"
                 "inicio {\n seja r = soma(1)\n}")
        for nivel in (0, 8):
            with self.subTest(nivel=nivel):
                with tempfile.TemporaryDirectory(prefix="rs_chamada_assinatura_") as pasta:
                    raiz = Path(pasta)
                    (raiz / "codigo_fonte.rts").write_text(fonte, encoding="utf-8")
                    resultado = subprocess.run(
                        [str(self.ferramentas[nivel])], cwd=raiz, timeout=30,
                        capture_output=True, text=True, encoding="utf-8", errors="replace",
                    )
                    self.assertEqual(resultado.returncode, 0, resultado.stderr)
                    linhas = [int(v) for v in resultado.stdout.splitlines()]
                    self.assertEqual(len(linhas), 2)
                    self.assertEqual(linhas[0], 13)
                    self.assertGreater(linhas[1], 0)
                    self.assertFalse((raiz / "resultado_corpos_elf").exists())

    def test_chamadas_aninhadas_nos_argumentos(self):
        casos = (
            ("funcao dobro(n: inteiro) -> inteiro {\n retorne n * 2\n}\n"
             "funcao soma(a: inteiro, b: inteiro) -> inteiro {\n retorne a + b\n}\n"
             "funcao calcular(n: inteiro) -> inteiro {\n"
             " retorne soma(dobro(n), soma(2, 3))\n}\n"
             "inicio {\n seja r = calcular(5)\n}", 15),
            ("funcao base() -> inteiro {\n retorne 7\n}\n"
             "funcao soma(a: inteiro, b: inteiro) -> inteiro {\n retorne a + b\n}\n"
             "inicio {\n seja r = soma(base(), base())\n}", 14),
            ("funcao dobro(n: inteiro) -> inteiro {\n retorne n * 2\n}\n"
             "funcao soma(a: inteiro, b: inteiro) -> inteiro {\n retorne a + b\n}\n"
             "inicio {\n seja r = soma(dobro(2 + 3), dobro(4))\n}", 18),
            ("funcao dobro(n: inteiro) -> inteiro {\n retorne n * 2\n}\n"
             "funcao soma(a: inteiro, b: inteiro) -> inteiro {\n retorne a + b\n}\n"
             "funcao calcular(x: inteiro) -> inteiro {\n"
             " se x > 1 {\n retorne soma(dobro(x), 6)\n }\n"
             " retorne soma(1, 2)\n}\n"
             "inicio {\n seja r = calcular(4)\n}", 14),
        )
        for nivel in (0, 8):
            for fonte, esperado in casos:
                with self.subTest(nivel=nivel, fonte=fonte):
                    codigo, dados, status = self.gerar(fonte, nivel)
                    self.assertEqual(codigo, 0)
                    self.assertGreaterEqual(dados[127:].count(bytes((232,))), 2)
                    if status is not None:
                        self.assertEqual(status, esperado)

    def test_chamadas_aninhadas_invalidas(self):
        fontes = (
            "funcao f(n: inteiro) -> inteiro {\n retorne n + 1\n}\n"
            "inicio {\n seja r = f(f(2), 3)\n}",
            "funcao f(n: inteiro) -> inteiro {\n retorne n + 1\n}\n"
            "inicio {\n seja r = f(f(2),)\n}",
            "funcao f(n: inteiro) -> inteiro {\n retorne n + 1\n}\n"
            "inicio {\n seja r = f(nao_existe(2))\n}",
            "funcao f(n: inteiro) -> inteiro {\n retorne n + 1\n}\n"
            "inicio {\n seja r = f(f(2)) ** 1\n}",
            "funcao f(n: inteiro) -> inteiro {\n retorne n + 1\n}\n"
            "inicio {\n seja r = f(f(2)) (3)\n}",
        )
        fontes += (
            "funcao f(n: inteiro) -> inteiro {\n retorne n + 1\n}\n"
            "inicio {\n seja r = " + "f(" * 10 + "1" + ")" * 10 + "\n}",
        )
        for nivel in (0, 8):
            for fonte in fontes:
                with self.subTest(nivel=nivel, fonte=fonte):
                    codigo, dados, status = self.gerar(fonte, nivel)
                    self.assertNotEqual(codigo, 0)
                    self.assertIsNone(dados)
                    self.assertIsNone(status)

    def test_chamadas_misturadas_com_aritmetica(self):
        casos = (
            ("funcao f(n: inteiro) -> inteiro {\n retorne n + 1\n}\n"
             "inicio {\n seja r = f(f(2)) + 1\n}", 5),
            ("funcao dobro(n: inteiro) -> inteiro {\n retorne n * 2\n}\n"
             "funcao calcular(n: inteiro) -> inteiro {\n retorne dobro(n) + 1\n}\n"
             "inicio {\n seja r = calcular(3)\n}", 7),
            ("funcao dobro(n: inteiro) -> inteiro {\n retorne n * 2\n}\n"
             "funcao soma(a: inteiro, b: inteiro) -> inteiro {\n retorne a + b\n}\n"
             "funcao calcular(n: inteiro) -> inteiro {\n retorne soma(dobro(n) + 1, 4)\n}\n"
             "inicio {\n seja r = calcular(3)\n}", 11),
            ("funcao soma(a: inteiro, b: inteiro) -> inteiro {\n retorne a + b\n}\n"
             "inicio {\n seja r = soma(3, 4) * 2 - 1\n}", 13),
            ("funcao soma(a: inteiro, b: inteiro) -> inteiro {\n retorne a + b\n}\n"
             "inicio {\n seja r = (soma(3, 4) + 5) * 2\n}", 24),
            ("funcao dobro(n: inteiro) -> inteiro {\n retorne n * 2\n}\n"
             "inicio {\n seja r = dobro(3) + dobro(4) * 2\n}", 22),
            ("funcao dobro(n: inteiro) -> inteiro {\n retorne n * 2\n}\n"
             "funcao calcular(n: inteiro) -> inteiro {\n retorne -(dobro(n) + 1)\n}\n"
             "inicio {\n seja r = calcular(3)\n}", 249),
            ("funcao dobro(n: inteiro) -> inteiro {\n retorne n * 2\n}\n"
             "inicio {\n seja r = dobro(8) - 4 - 2\n}", 10),
            ("funcao dobro(n: inteiro) -> inteiro {\n retorne n * 2\n}\n"
             "inicio {\n seja r = dobro(-2) + 3\n}", 255),
        )
        for nivel in (0, 8):
            for fonte, esperado in casos:
                with self.subTest(nivel=nivel, fonte=fonte):
                    codigo, dados, status = self.gerar(fonte, nivel)
                    self.assertEqual(codigo, 0)
                    self.assertIn(bytes((232,)), dados[127:])
                    if status is not None:
                        self.assertEqual(status, esperado)

    def test_chamadas_com_operadores_invalidas(self):
        fontes = (
            "funcao dobro(n: inteiro) -> inteiro {\n retorne n * 2\n}\n"
            "inicio {\n seja r = dobro(3) ** 2\n}",
            "funcao dobro(n: inteiro) -> inteiro {\n retorne n * 2\n}\n"
            "inicio {\n seja r = dobro(3) +\n}",
            "funcao dobro(n: inteiro) -> inteiro {\n retorne n * 2\n}\n"
            "inicio {\n seja r = dobro(3) * desconhecida(2)\n}",
            "funcao dobro(n: inteiro) -> inteiro {\n retorne n * 2\n}\n"
            "inicio {\n seja r = dobro(3) + (2 * 4\n}",
        )
        for nivel in (0, 8):
            for fonte in fontes:
                with self.subTest(nivel=nivel, fonte=fonte):
                    codigo, dados, status = self.gerar(fonte, nivel)
                    self.assertNotEqual(codigo, 0)
                    self.assertIsNone(dados)
                    self.assertIsNone(status)

    def test_divisao_e_resto_signed64(self):
        casos = (
            ("funcao metade(n: inteiro) -> inteiro {\n retorne n / 2\n}\n"
             "inicio {\n seja r = metade(15)\n}", 7),
            ("funcao dobro(n: inteiro) -> inteiro {\n retorne n * 2\n}\n"
             "inicio {\n seja r = dobro(19) / 5\n}", 7),
            ("funcao dobro(n: inteiro) -> inteiro {\n retorne n * 2\n}\n"
             "inicio {\n seja r = dobro(19) % 5\n}", 3),
            ("funcao base(n: inteiro) -> inteiro {\n retorne n\n}\n"
             "inicio {\n seja r = (base(-17) / 5) + 10\n}", 7),
            ("funcao base(n: inteiro) -> inteiro {\n retorne n\n}\n"
             "inicio {\n seja r = base(-17) % 5\n}", 254),
            ("funcao base(n: inteiro) -> inteiro {\n retorne n\n}\n"
             "inicio {\n seja r = base(17) % -5\n}", 2),
            ("funcao f(n: inteiro) -> inteiro {\n retorne n / 2\n}\n"
             "inicio {\n seja r = f(9) + 1\n}", 5),
            ("funcao soma(a: inteiro, b: inteiro) -> inteiro {\n retorne a + b\n}\n"
             "inicio {\n seja r = (soma(8, 3) / 2) + (soma(3, 4) % 3)\n}", 6),
        )
        for nivel in (0, 8):
            for fonte, esperado in casos:
                with self.subTest(nivel=nivel, fonte=fonte):
                    codigo, dados, status = self.gerar(fonte, nivel)
                    self.assertEqual(codigo, 0)
                    self.assertIn(bytes((72, 153, 72, 247, 249)), dados)
                    if status is not None:
                        self.assertEqual(status, esperado % 256)

    def test_divisao_protegida_contra_zero_e_overflow(self):
        casos = (
            ("funcao f(n: inteiro) -> inteiro {\n retorne n + 1\n}\n"
             "inicio {\n seja r = f(8) / (f(1) - f(1))\n}", 240),
            ("funcao zero(n: inteiro) -> inteiro {\n retorne n - n\n}\n"
             "inicio {\n seja r = 9 % zero(5)\n}", 240),
            ("funcao f(n: inteiro) -> inteiro {\n retorne n / (n - n)\n}\n"
             "inicio {\n seja r = f(13)\n}", 240),
            ("funcao f(n: inteiro) -> inteiro {\n retorne n\n}\n"
             "inicio {\n seja r = f(0) / (f(1) - f(1))\n}", 240),
            ("funcao minimo() -> inteiro {\n"
             " retorne -8 * 1024 * 1024 * 1024 * 1024 * 1024 * 1024\n}\n"
             "inicio {\n seja r = minimo() / -1\n}", 241),
            ("funcao f(n: inteiro) -> inteiro {\n retorne n\n}\n"
             "inicio {\n seja r = f(-8) / -1\n}", 8),
            ("funcao f(n: inteiro) -> inteiro {\n retorne n\n}\n"
             "inicio {\n seja r = f(0) / -1\n}", 0),
        )
        for nivel in (0, 8):
            for fonte, esperado in casos:
                with self.subTest(nivel=nivel, fonte=fonte):
                    codigo, dados, status = self.gerar(fonte, nivel)
                    self.assertEqual(codigo, 0)
                    # test rcx,rcx; jne +12 e IDIV com extensao signed64.
                    self.assertIn(bytes((72, 133, 201, 15, 133)), dados)
                    self.assertIn(bytes((72, 153, 72, 247, 249)), dados)
                    if status is not None:
                        self.assertEqual(status, esperado)

    def test_diagnosticos_divisao_em_stderr(self):
        if self.alvo != "linux":
            return
        casos = (
            ("funcao f(n: inteiro) -> inteiro {\n retorne n\n}\n"
             "inicio {\n seja r = f(8) / (f(1) - f(1))\n}", 240, "RS: divisao por zero\n"),
            ("funcao zero(n: inteiro) -> inteiro {\n retorne n - n\n}\n"
             "inicio {\n seja r = 9 % zero(5)\n}", 240, "RS: divisao por zero\n"),
            ("funcao minimo() -> inteiro {\n"
             " retorne -8 * 1024 * 1024 * 1024 * 1024 * 1024 * 1024\n}\n"
             "inicio {\n seja r = minimo() / -1\n}", 241, "RS: estouro na divisao\n"),
            ("funcao f(n: inteiro) -> inteiro {\n retorne n\n}\n" +
             "\n" * 10 +
             "inicio {\n            seja resultado = f(10) / (f(1) - f(1))\n}", 240, "RS: divisao por zero\n"),
            ("funcao retorna(n: inteiro) -> inteiro {\n retorne n\n}\n"
             "inicio {\n seja r = retorna(240)\n}", 240, ""),
            ("funcao retorna(n: inteiro) -> inteiro {\n retorne n\n}\n"
             "inicio {\n seja r = retorna(241)\n}", 241, ""),
            ("funcao f(n: inteiro) -> inteiro {\n retorne n\n}\n"
             "inicio {\n seja r = f(-12) / -5\n}", 2, ""),
        )
        for nivel in (0, 8):
            for fonte, esperado, diagnostico in casos:
                with self.subTest(nivel=nivel, fonte=fonte):
                    with tempfile.TemporaryDirectory(prefix="rs_diagnostico_elf_") as pasta:
                        raiz = Path(pasta)
                        (raiz / "codigo_fonte.rts").write_text(fonte, encoding="utf-8")
                        gerador = subprocess.run(
                            [str(self.ferramentas[nivel])], cwd=raiz, timeout=30,
                            capture_output=True, text=True, encoding="utf-8", errors="replace",
                        )
                        self.assertEqual(gerador.returncode, 0, gerador.stderr)
                        self.assertEqual(int(gerador.stdout.splitlines()[0]), 0)
                        arquivo = raiz / "resultado_corpos_elf"
                        arquivo.chmod(0o700)
                        processo = subprocess.run(
                            [str(arquivo)], cwd=raiz, timeout=4,
                            capture_output=True, text=True, encoding="utf-8", errors="replace",
                        )
                        self.assertEqual(processo.returncode, esperado)
                        if diagnostico:
                            local_operador = fonte.find(" / ")
                            if local_operador < 0:
                                local_operador = fonte.find(" % ")
                            self.assertGreaterEqual(local_operador, 0)
                            local_operador += 1
                            linha = fonte.count("\n", 0, local_operador) + 1
                            coluna = local_operador - fonte.rfind("\n", 0, local_operador)
                            diagnostico = diagnostico.rstrip("\n") + f" (linha {linha}, coluna {coluna})\n"
                        self.assertEqual(processo.stderr, diagnostico)
                        self.assertEqual(processo.stdout, "")

    def test_rejeita_divisao_constante_zero_em_funcoes_e_chamadas(self):
        invalidos = (
            "funcao f(n: inteiro) -> inteiro {\n retorne n\n}\n"
            "inicio {\n seja r = f(8) / 0\n}",
            "funcao f(n: inteiro) -> inteiro {\n retorne n\n}\n"
            "inicio {\n seja r = f(8) % (8 - 8)\n}",
            "funcao f(n: inteiro) -> inteiro {\n retorne n / (6 - 6)\n}\n"
            "inicio {\n seja r = f(8)\n}",
            "funcao f(n: inteiro) -> inteiro {\n retorne n\n}\n"
            "inicio {\n seja r = f(9 / (2 - 2))\n}",
            "funcao f(n: inteiro) -> inteiro {\n retorne n\n}\n"
            "inicio {\n seja r = f(4) + 7 / (10 / 20)\n}",
            "funcao f(n: inteiro) -> inteiro {\n retorne n\n}\n"
            "inicio {\n seja r = 2\n se f(4) / 0 > r {\n r = 5\n }\n}",
            "funcao f(n: inteiro) -> inteiro {\n retorne n\n}\n"
            "inicio {\n seja r = 2\n enquanto f(4) % (3 - 3) > r {\n r = 5\n }\n}",
        )
        for nivel in (0, 8):
            for fonte in invalidos:
                with self.subTest(nivel=nivel, fonte=fonte):
                    codigo, dados, status = self.gerar(fonte, nivel)
                    self.assertEqual(codigo, 9)
                    self.assertIsNone(dados)
                    self.assertIsNone(status)

    def test_divisores_dinamicos_em_funcoes_preservados(self):
        casos = (
            ("funcao f(n: inteiro) -> inteiro {\n retorne n\n}\n"
             "inicio {\n seja r = f(8) / (f(3) - f(1))\n}", 4),
            ("funcao f(n: inteiro) -> inteiro {\n retorne n\n}\n"
             "inicio {\n seja x = 2\n seja r = f(8) % x\n}", 0),
            ("funcao f(n: inteiro) -> inteiro {\n retorne n\n}\n"
             "inicio {\n seja r = f(8) / (f(3) - f(3))\n}", 240),
        )
        for nivel in (0, 8):
            for fonte, esperado in casos:
                with self.subTest(nivel=nivel, fonte=fonte):
                    codigo, dados, status = self.gerar(fonte, nivel)
                    self.assertEqual(codigo, 0)
                    self.assertIsNotNone(dados)
                    if status is not None:
                        self.assertEqual(status, esperado)

    def test_predicados_com_chamadas_diretas_e_compostas(self):
        casos = (
            ("funcao dobro(n: inteiro) -> inteiro {\n retorne n * 2\n}\n"
             "funcao teste(n: inteiro) -> inteiro {\n"
             " se dobro(n) > 10 {\n retorne 17\n }\n retorne 3\n}\n"
             "inicio {\n seja r = teste(6)\n}", 17),
            ("funcao dobro(n: inteiro) -> inteiro {\n retorne n * 2\n}\n"
             "funcao teste(n: inteiro) -> inteiro {\n"
             " se dobro(n) > 10 {\n retorne 17\n }\n retorne 3\n}\n"
             "inicio {\n seja r = teste(2)\n}", 3),
            ("funcao f(n: inteiro) -> inteiro {\n retorne n + 1\n}\n"
             "inicio {\n seja x = 3\n"
             " enquanto f(x) < 8 {\n x = x + 1\n }\n"
             " seja r = x\n}", 7),
            ("funcao f(n: inteiro) -> inteiro {\n retorne n - 1\n}\n"
             "inicio {\n seja x = 0\n"
             " enquanto x + 2 <= f(9) {\n x = x + 1\n }\n"
             " seja r = x\n}", 7),
            ("funcao f(n: inteiro) -> inteiro {\n retorne n + 1\n}\n"
             "inicio {\n seja x = 0\n"
             " se f(3) * 2 == (f(5) + 2) {\n x = 91\n }\n"
             " seja r = x\n}", 91),
            ("funcao f(n: inteiro) -> inteiro {\n retorne n - 3\n}\n"
             "funcao g(n: inteiro) -> inteiro {\n retorne f(n) * 2\n}\n"
             "inicio {\n seja x = 4\n"
             " se g(5) != f(5) {\n x = g(8) + 1\n }\n"
             " seja r = x\n}", 11),
            ("funcao f(n: inteiro) -> inteiro {\n retorne n + 1\n}\n"
             "inicio {\n seja x = 3\n"
             " se f(x) % 2 == 0 {\n x = x + 19\n }\n"
             " seja r = x\n}", 22),
        )
        for nivel in (0, 8):
            for fonte, esperado in casos:
                with self.subTest(nivel=nivel, fonte=fonte):
                    codigo, dados, status = self.gerar(fonte, nivel)
                    self.assertEqual(codigo, 0)
                    self.assertIn(bytes((72, 57, 200, 15)), dados[127:])
                    if status is not None:
                        self.assertEqual(status, esperado)

    def test_predicados_com_chamadas_invalidas(self):
        fontes = (
            "funcao f(n: inteiro) -> inteiro {\n retorne n + 1\n}\n"
            "inicio {\n seja x = 0\n se f(2) >= desconhecida(3) {\n x = 1\n }\n}",
            "funcao f(n: inteiro) -> inteiro {\n retorne n + 1\n}\n"
            "inicio {\n seja x = 0\n se f() > 0 {\n x = 1\n }\n}",
            "funcao f(n: inteiro) -> inteiro {\n retorne n + 1\n}\n"
            "inicio {\n seja x = 0\n se f(3) > f(2) > 0 {\n x = 1\n }\n}",
            "funcao f(n: inteiro) -> inteiro {\n retorne n + 1\n}\n"
            "inicio {\n seja x = 0\n se f(3) + > 1 {\n x = 1\n }\n}",
        )
        for nivel in (0, 8):
            for fonte in fontes:
                with self.subTest(nivel=nivel, fonte=fonte):
                    codigo, dados, status = self.gerar(fonte, nivel)
                    self.assertNotEqual(codigo, 0)
                    self.assertIsNone(dados)
                    self.assertIsNone(status)

    def test_programas_diferenciais_sem_recursao(self):
        rng = random.Random(42061)
        for _ in range(10):
            limite = rng.randrange(1, 13)
            passo = rng.randrange(1, 5)
            fonte = (
                "funcao somatorio(limite: inteiro, passo: inteiro) -> inteiro {\n"
                " seja i = 0\n seja soma = 0\n"
                " enquanto i < limite {\n"
                " i = i + 1\n soma = soma + i * passo\n"
                " }\n retorne soma\n}\n"
                "inicio {\n"
                f" seja r = somatorio({limite}, {passo})\n"
                "}"
            )
            esperado = sum(i * passo for i in range(1, limite + 1)) % 256
            for nivel in (0, 8):
                codigo, _, status = self.gerar(fonte, nivel)
                self.assertEqual(codigo, 0)
                if status is not None:
                    self.assertEqual(status, esperado)

    def test_rejeita_falta_de_retorno_ciclos_e_erros(self):
        fontes = (
            "",
            "inicio {\n seja x = 2\n}",
            "funcao f(n: inteiro) -> inteiro {\n"
            " seja x = n + 1\n}\n inicio { seja r = f(2) }",
            "funcao f(n: inteiro) -> inteiro {\n"
            " se n > 0 {\n retorne n\n }\n}\n"
            "inicio { seja r = f(1) }",
            "funcao f(n: inteiro) -> inteiro {\n retorne f(n)\n}\n"
            "inicio { seja r = f(1) }",
            "funcao f(n: inteiro) -> inteiro {\n"
            " seja a = f(n)\n retorne a\n}\n"
            "inicio { seja r = f(1) }",
            "funcao f(n: inteiro) -> inteiro {\n"
            " seja x = n\n retorne x\n"
            " escreva(x)\n}\n inicio { seja r = f(2) }",
            "funcao f(n: inteiro) -> inteiro {\n"
            " seja x = n\n enquanto x > 0 {\n x = x - 1\n }\n"
            " retorne 1000000001\n}\n inicio { seja r = f(1) }",
            "funcao f(n: inteiro) -> inteiro {\n"
            " seja x = n\n retorne x + desconhecido\n}\n"
            "inicio { seja r = f(3) }",
        )
        for nivel in (0, 8):
            for fonte in fontes:
                with self.subTest(nivel=nivel, fonte=fonte):
                    codigo, dados, retorno = self.gerar(fonte, nivel)
                    self.assertNotEqual(codigo, 0)
                    self.assertIsNone(dados)
                    self.assertIsNone(retorno)



    def test_retorno_exaustivo_se_senao_sem_retorne_final(self):
        casos = (
            ("funcao escolha(n: inteiro) -> inteiro {\n"
             " se n > 0 {\n retorne 31\n } senao {\n retorne 43\n }\n"
             "}\n inicio { seja r = escolha(6) }", 31),
            ("funcao escolha(n: inteiro) -> inteiro {\n"
             " se n > 0 {\n retorne 31\n } senao {\n retorne 43\n }\n"
             "}\n inicio { seja r = escolha(-6) }", 43),
            ("funcao escolha(n: inteiro) -> inteiro {\n"
             " se n > 0 {\n"
             " se n > 10 {\n retorne 7\n } senao {\n retorne 8\n }\n"
             " } senao {\n retorne 9\n }\n"
             "}\n inicio { seja r = escolha(3) }", 8),
            ("funcao escolha(n: inteiro) -> inteiro {\n"
             " se n > 0 {\n"
             " se n > 10 {\n retorne 7\n } senao {\n retorne 8\n }\n"
             " } senao {\n retorne 9\n }\n"
             "}\n inicio { seja r = escolha(-3) }", 9),
            ("funcao triplo(n: inteiro) -> inteiro {\n retorne n * 3\n}\n"
             "funcao escolha(n: inteiro) -> inteiro {\n"
             " se n > 0 {\n retorne triplo(n)\n"
             " } senao {\n retorne 5\n }\n"
             "}\n inicio { seja r = escolha(4) }", 12),
        )
        for nivel in (0, 8):
            for fonte, esperado in casos:
                with self.subTest(nivel=nivel, esperado=esperado, fonte=fonte):
                    codigo, dados, status = self.gerar(fonte, nivel)
                    self.assertEqual(codigo, 0)
                    self.assertIsNotNone(dados)
                    if status is not None:
                        self.assertEqual(status, esperado)

    def test_retorno_exaustivo_rejeita_inalcancavel(self):
        casos = (
            "funcao escolha(n: inteiro) -> inteiro {\n"
            " se n > 0 {\n retorne 1\n } senao {\n retorne 2\n }\n"
            " retorne 3\n}\n inicio { seja r = escolha(3) }",
            "funcao escolha(n: inteiro) -> inteiro {\n"
            " se n > 0 {\n retorne 1\n } senao {\n retorne 2\n }\n"
            " n = n + 1\n retorne n\n}\n inicio { seja r = escolha(3) }",
            "funcao escolha(n: inteiro) -> inteiro {\n"
            " se n > 0 {\n"
            " se n > 1 {\n retorne 1\n } senao {\n retorne 2\n }\n"
            " n = n + 1\n"
            " } senao {\n retorne 3\n }\n"
            " retorne 4\n}\n inicio { seja r = escolha(3) }",
        )
        for nivel in (0, 8):
            for fonte in casos:
                with self.subTest(nivel=nivel, fonte=fonte):
                    codigo, dados, status = self.gerar(fonte, nivel)
                    self.assertEqual(codigo, 10)
                    self.assertIsNone(dados)
                    self.assertIsNone(status)

    def test_retorno_exaustivo_conserva_caminhos_sem_retorno(self):
        casos = (
            "funcao f(n: inteiro) -> inteiro {\n"
            " se n > 0 {\n retorne 1\n } senao {\n n = n + 1\n }\n"
            "}\n inicio { seja r = f(2) }",
            "funcao f(n: inteiro) -> inteiro {\n"
            " enquanto n > 0 {\n"
            " se n > 1 {\n retorne 1\n } senao {\n retorne 2\n }\n"
            " }\n}\n inicio { seja r = f(2) }",
            "funcao f(n: inteiro) -> inteiro {\n"
            " se n > 0 {\n"
            " se n > 1 {\n retorne 1\n }\n"
            " } senao {\n retorne 2\n }\n"
            "}\n inicio { seja r = f(2) }",
        )
        for nivel in (0, 8):
            for fonte in casos:
                with self.subTest(nivel=nivel, fonte=fonte):
                    codigo, dados, status = self.gerar(fonte, nivel)
                    self.assertEqual(codigo, 11)
                    self.assertIsNone(dados)
                    self.assertIsNone(status)

    def test_senao_em_funcoes_e_inicio(self):
        # Ambos os niveis geram o mesmo ELF funcional para os dois ramos.
        casos = (
            ("funcao escolha(n: inteiro) -> inteiro {\n"
             " seja r = 0\n"
             " se n > 0 {\n r = 17\n } senao {\n r = 9\n }\n"
             " retorne r\n}\n"
             "inicio {\n seja r = escolha(3)\n}", 17),
            ("funcao escolha(n: inteiro) -> inteiro {\n"
             " seja r = 0\n"
             " se n > 0 {\n r = 17\n } senao {\n r = 9\n }\n"
             " retorne r\n}\n"
             "inicio {\n seja r = escolha(-3)\n}", 9),
            ("funcao escolha(n: inteiro) -> inteiro {\n"
             " se n < 0 {\n retorne 41\n } senao {\n retorne 42\n }\n"
             "}\n"
             "inicio {\n seja r = escolha(-2)\n}", 41),
            ("funcao escolha(n: inteiro) -> inteiro {\n"
             " se n < 0 {\n retorne 41\n } senao {\n retorne 42\n }\n"
             "}\n"
             "inicio {\n seja r = escolha(2)\n}", 42),
            ("funcao soma(n: inteiro) -> inteiro {\n"
             " seja i = 0\n seja r = 0\n"
             " enquanto i < n {\n"
             " se i % 2 == 0 {\n r = r + 3\n"
             " } senao {\n r = r + 5\n }\n"
             " i = i + 1\n }\n"
             " retorne r\n}\n"
             "inicio {\n seja r = soma(4)\n}", 16),
            ("funcao dobro(n: inteiro) -> inteiro {\n retorne n * 2\n}\n"
             "inicio {\n seja r = 0\n"
             " se dobro(3) >= 6 {\n r = 7\n"
             " } senao {\n r = 13\n }\n}", 7),
            ("funcao dobro(n: inteiro) -> inteiro {\n retorne n * 2\n}\n"
             "inicio {\n seja r = 0\n"
             " se dobro(2) >= 6 {\n r = 7\n"
             " } senao {\n r = 13\n }\n}", 13),
            ("funcao ramo(n: inteiro) -> inteiro {\n"
             " seja r = 0\n"
             " se n > 0 {\n"
             " se n > 9 {\n r = 6\n } senao {\n r = 4\n }\n"
             " } senao {\n r = 2\n }\n retorne r\n}\n"
             "inicio {\n seja r = ramo(6)\n}", 4),
        )
        for nivel in (0, 8):
            for fonte, esperado in casos:
                with self.subTest(nivel=nivel, esperado=esperado, fonte=fonte):
                    codigo, dados, status = self.gerar(fonte, nivel)
                    self.assertEqual(codigo, 0)
                    self.assertIn(bytes((233,)), dados[127:])
                    if status is not None:
                        self.assertEqual(status, esperado)

    def test_senao_invalido_nao_gera_elf(self):
        invalidos = (
            "funcao f(n: inteiro) -> inteiro {\n"
            " seja r = 0\n enquanto n > 0 {\n n = n - 1\n"
            " } senao {\n r = 4\n }\n retorne r\n}\n"
            "inicio { seja x = f(2) }",
            "funcao f(n: inteiro) -> inteiro {\n"
            " seja r = 0\n se n > 0 {\n r = 1\n"
            " } senao {\n r = 2\n } senao {\n r = 3\n }\n"
            " retorne r\n}\n inicio { seja x = f(2) }",
            "funcao f(n: inteiro) -> inteiro {\n"
            " seja r = 0\n se n > 0 {\n r = 1\n"
            " } senao r = 2\n retorne r\n}\n inicio { seja x = f(2) }",
            "funcao f(n: inteiro) -> inteiro {\n"
            " seja r = 0\n senao {\n r = 1\n }\n"
            " retorne r\n}\n inicio { seja x = f(2) }",
        )
        for nivel in (0, 8):
            for fonte in invalidos:
                with self.subTest(nivel=nivel, fonte=fonte):
                    codigo, dados, status = self.gerar(fonte, nivel)
                    self.assertNotEqual(codigo, 0)
                    self.assertIsNone(dados)
                    self.assertIsNone(status)


    def test_chamadas_futuras_sem_ciclo(self):
        casos = (
            ("funcao a() -> inteiro {\n retorne b()\n}\n"
             "funcao b() -> inteiro {\n retorne 7\n}\n"
             "inicio { seja r = a() }", 7),
            ("funcao a(n: inteiro) -> inteiro {\n retorne b(n + 2)\n}\n"
             "funcao b(x: inteiro) -> inteiro {\n retorne x * 3\n}\n"
             "inicio { seja r = a(4) }", 18),
            ("funcao a(n: inteiro) -> inteiro {\n retorne b(n)\n}\n"
             "funcao b(n: inteiro) -> inteiro {\n retorne c(n) + 1\n}\n"
             "funcao c(n: inteiro) -> inteiro {\n retorne n * 2\n}\n"
             "inicio { seja r = a(8) }", 17),
            ("funcao base(n: inteiro) -> inteiro {\n retorne n - 1\n}\n"
             "funcao primeira(n: inteiro) -> inteiro {\n retorne ultima(n) + 1\n}\n"
             "funcao ultima(n: inteiro) -> inteiro {\n retorne base(n) * 2\n}\n"
             "inicio { seja r = primeira(5) }", 9),
            ("funcao selecionar(n: inteiro) -> inteiro {\n"
             " se depois(n) > 5 {\n retorne 11\n } senao {\n retorne 22\n }\n"
             "}\n"
             "funcao depois(n: inteiro) -> inteiro {\n retorne n + 1\n}\n"
             "inicio { seja r = selecionar(5) }", 11),
            ("funcao soma(n: inteiro) -> inteiro {\n"
             " seja i = 0\n enquanto i < proximo(n) {\n i = i + 1\n }\n"
             " retorne i\n}\n"
             "funcao proximo(n: inteiro) -> inteiro {\n retorne n + 2\n}\n"
             "inicio { seja r = soma(3) }", 5),
            ("funcao calcular(n: inteiro) -> inteiro {\n"
             " retorne juntar(dobro(n), n + 1)\n}\n"
             "funcao dobro(n: inteiro) -> inteiro {\n retorne n * 2\n}\n"
             "funcao juntar(a: inteiro, b: inteiro) -> inteiro {\n retorne a + b\n}\n"
             "inicio { seja r = calcular(5) }", 16),
        )
        for nivel in (0, 8):
            for fonte, esperado in casos:
                with self.subTest(nivel=nivel, fonte=fonte):
                    codigo, dados, status = self.gerar(fonte, nivel)
                    self.assertEqual(codigo, 0)
                    self.assertIsNotNone(dados)
                    if status is not None:
                        self.assertEqual(status, esperado)

    def test_ciclos_indiretos_e_chamadas_futuras_invalidas(self):
        casos = (
            (14, "funcao a() -> inteiro {\n retorne b()\n}\n"
             "funcao b() -> inteiro {\n retorne a()\n}\n"
             "inicio { seja r = a() }"),
            (14, "funcao a(n: inteiro) -> inteiro {\n retorne b(n)\n}\n"
             "funcao b(n: inteiro) -> inteiro {\n retorne c(n)\n}\n"
             "funcao c(n: inteiro) -> inteiro {\n retorne a(n)\n}\n"
             "inicio { seja r = a(1) }"),
            (14, "funcao a(n: inteiro) -> inteiro {\n"
             " se n > 0 {\n retorne b(n)\n }\n retorne 0\n}\n"
             "funcao b(n: inteiro) -> inteiro {\n"
             " se n > 0 {\n retorne a(n)\n }\n retorne 1\n}\n"
             "inicio { seja r = a(0) }"),
            (13, "funcao a() -> inteiro {\n retorne b(1)\n}\n"
             "funcao b() -> inteiro {\n retorne 3\n}\n"
             "inicio { seja r = a() }"),
            (12, "funcao a() -> inteiro {\n retorne inexistente()\n}\n"
             "funcao b() -> inteiro {\n retorne 3\n}\n"
             "inicio { seja r = a() }"),
        )
        for nivel in (0, 8):
            for esperado, fonte in casos:
                with self.subTest(nivel=nivel, esperado=esperado, fonte=fonte):
                    codigo, dados, status = self.gerar(fonte, nivel)
                    self.assertEqual(codigo, esperado)
                    self.assertIsNone(dados)
                    self.assertIsNone(status)

    def test_indice_token_ciclo_indireto(self):
        fonte = ("funcao alfa() -> inteiro {\n retorne beta()\n}\n"
                 "funcao beta() -> inteiro {\n retorne alfa()\n}\n"
                 "inicio { seja r = alfa() }")
        for nivel in (0, 8):
            with self.subTest(nivel=nivel):
                with tempfile.TemporaryDirectory(prefix="rs_ciclo_elf_") as pasta:
                    raiz = Path(pasta)
                    (raiz / "codigo_fonte.rts").write_text(fonte, encoding="utf-8")
                    processo = subprocess.run(
                        [str(self.ferramentas[nivel])], cwd=raiz, timeout=30,
                        capture_output=True, text=True, encoding="utf-8", errors="replace",
                    )
                    self.assertEqual(processo.returncode, 0, processo.stderr)
                    valores = [int(v) for v in processo.stdout.splitlines()]
                    self.assertEqual(len(valores), 2)
                    self.assertEqual(valores[0], 14)
                    self.assertGreater(valores[1], 0)
                    self.assertFalse((raiz / "resultado_corpos_elf").exists())


    def test_pare_continue_em_lacos_elf_o0_o8(self):
        casos = (
            ("funcao somar(n: inteiro) -> inteiro {\n"
             " seja i = 0\n seja total = 0\n"
             " enquanto i < n {\n"
             " i = i + 1\n"
             " se i % 2 == 0 {\n continue\n }\n"
             " total = total + i\n"
             " }\n retorne total\n}\n"
             "inicio { seja resultado = somar(6) }", 9),
            ("funcao interromper(n: inteiro) -> inteiro {\n"
             " seja i = 0\n"
             " enquanto i < n {\n"
             " se i == 4 {\n pare\n }\n"
             " i = i + 1\n }\n retorne i\n}\n"
             "inicio { seja resultado = interromper(10) }", 4),
            ("funcao contar(n: inteiro) -> inteiro {\n"
             " seja i = 0\n seja j = 0\n seja total = 0\n"
             " enquanto i < n {\n"
             " j = 0\n"
             " enquanto j < 4 {\n"
             " j = j + 1\n"
             " se j == 2 {\n pare\n }\n"
             " total = total + 1\n"
             " }\n i = i + 1\n"
             " }\n retorne total\n}\n"
             "inicio { seja resultado = contar(3) }", 3),
            ("funcao contar(n: inteiro) -> inteiro {\n"
             " seja i = 0\n seja j = 0\n seja total = 0\n"
             " enquanto i < n {\n"
             " j = 0\n i = i + 1\n"
             " enquanto j < 3 {\n"
             " j = j + 1\n"
             " se j == 2 {\n continue\n }\n"
             " total = total + 1\n"
             " }\n"
             " }\n retorne total\n}\n"
             "inicio { seja resultado = contar(3) }", 6),
            ("funcao identidade(n: inteiro) -> inteiro {\n retorne n\n}\n"
             "inicio {\n"
             " seja i = 0\n seja resultado = 0\n"
             " enquanto i < identidade(6) {\n"
             " i = i + 1\n"
             " se i % 2 == 0 {\n continue\n } senao {\n"
             " resultado = resultado + i\n }\n"
             " }\n resultado = identidade(resultado)\n}", 9),
            ("funcao identidade(n: inteiro) -> inteiro {\n retorne n\n}\n"
             "inicio {\n seja resultado = 0\n"
             " enquanto resultado < 9 {\n"
             " resultado = resultado + 1\n"
             " se resultado == 5 {\n pare\n }\n"
             " }\n resultado = identidade(resultado)\n}", 5),
        )
        for nivel in (0, 8):
            for fonte, esperado in casos:
                with self.subTest(nivel=nivel, esperado=esperado, fonte=fonte):
                    codigo, dados, status = self.gerar(fonte, nivel)
                    self.assertEqual(codigo, 0)
                    self.assertIn(bytes((233,)), dados[127:])
                    if status is not None:
                        self.assertEqual(status, esperado)

    def test_pare_continue_invalidos_e_inalcancaveis(self):
        casos = (
            (16, "funcao f() -> inteiro {\n retorne 1\n}\n"
             "inicio {\n seja r = 0\n pare\n}"),
            (16, "funcao f() -> inteiro {\n retorne 1\n}\n"
             "inicio {\n seja r = 0\n continue\n}"),
            (16, "funcao f(n: inteiro) -> inteiro {\n"
             " pare\n retorne n\n}\n"
             "inicio { seja r = f(1) }"),
            (16, "funcao f(n: inteiro) -> inteiro {\n"
             " se n > 0 {\n continue\n }\n retorne n\n}\n"
             "inicio { seja r = f(1) }"),
            (16, "funcao f() -> inteiro {\n retorne 1\n}\n"
             "inicio { seja r = 0\n enquanto r < 3 {\n pare 2\n }\n}"),
            (16, "funcao f() -> inteiro {\n retorne 1\n}\n"
             "inicio { seja r = 0\n enquanto r < 3 {\n continue 1\n }\n}"),
            (10, "funcao f(n: inteiro) -> inteiro {\n"
             " enquanto n > 0 {\n pare\n n = n - 1\n }\n"
             " retorne n\n}\n inicio { seja r = f(3) }"),
            (10, "funcao f(n: inteiro) -> inteiro {\n"
             " enquanto n > 0 {\n continue\n n = n - 1\n }\n"
             " retorne n\n}\n inicio { seja r = f(3) }"),
        )
        for nivel in (0, 8):
            for esperado, fonte in casos:
                with self.subTest(nivel=nivel, esperado=esperado, fonte=fonte):
                    codigo, dados, status = self.gerar(fonte, nivel)
                    self.assertEqual(codigo, esperado)
                    self.assertIsNone(dados)
                    self.assertIsNone(status)


    def test_escopos_locais_de_bloco_elf_o0_o8(self):
        casos = (
            ("funcao f(n: inteiro) -> inteiro {\n"
             " seja r = 1\n"
             " se n > 0 {\n seja t = n + 2\n r = t + 4\n }\n"
             " retorne r\n}\n inicio { seja r = f(5) }", 11),
            ("funcao f(n: inteiro) -> inteiro {\n"
             " seja r = 1\n"
             " se n > 0 {\n seja t = n + 2\n r = t + 4\n }\n"
             " retorne r\n}\n inicio { seja r = f(-3) }", 1),
            ("funcao f(n: inteiro) -> inteiro {\n"
             " seja r = 0\n"
             " se n > 0 {\n seja t = 10\n r = t\n"
             " } senao {\n seja t = 20\n r = t\n }\n"
             " retorne r\n}\n inicio { seja r = f(4) }", 10),
            ("funcao f(n: inteiro) -> inteiro {\n"
             " seja r = 0\n"
             " se n > 0 {\n seja t = 10\n r = t\n"
             " } senao {\n seja t = 20\n r = t\n }\n"
             " retorne r\n}\n inicio { seja r = f(-4) }", 20),
            ("funcao f(n: inteiro) -> inteiro {\n"
             " seja r = 7\n se n > 0 {\n"
             " seja r = 19\n r = r + 1\n }\n retorne r\n"
             "}\n inicio { seja r = f(2) }", 7),
            ("funcao f(n: inteiro) -> inteiro {\n"
             " seja r = 7\n se n > 0 {\n"
             " seja r = 19\n r = r + 1\n }\n retorne r\n"
             "}\n inicio { seja r = f(-2) }", 7),
            ("funcao f(n: inteiro) -> inteiro {\n"
             " seja i = 0\n seja r = 0\n"
             " enquanto i < n {\n"
             " seja parte = i + 2\n r = r + parte\n i = i + 1\n"
             " }\n retorne r\n}\n inicio { seja r = f(3) }", 9),
            ("funcao f(n: inteiro) -> inteiro {\n"
             " seja v = 4\n seja r = 0\n"
             " se n > 0 {\n seja v = 3\n"
             " se n > 1 {\n seja v = 8\n r = v\n }\n"
             " r = r + v\n }\n retorne r + v\n"
             "}\n inicio { seja r = f(2) }", 15),
            ("funcao f(n: inteiro) -> inteiro {\n"
             " seja r = 0\n se n > 0 {\n"
             " seja n = 10\n r = n\n }\n retorne r + n\n"
             "}\n inicio { seja r = f(3) }", 13),
            ("funcao f(n: inteiro) -> inteiro {\n"
             " seja r = 0\n"
             " se n > 0 {\n seja t = 3\n r = t\n }\n"
             " se r > 0 {\n seja t = 9\n r = r + t\n }\n"
             " retorne r\n}\n inicio { seja r = f(2) }", 12),
            ("funcao f(n: inteiro) -> inteiro {\n"
             " seja x = n\n se x > 0 {\n seja y = 4\n }\n"
             " retorne x\n}\n inicio { seja r = f(1) }", 1),
            ("funcao identidade(n: inteiro) -> inteiro {\n retorne n\n}\n"
             "inicio {\n seja r = 1\n se r > 0 {\n"
             " seja interno = 5\n r = interno + 2\n }\n"
             " r = identidade(r)\n}", 7),
        )
        for nivel in (0, 8):
            for fonte, esperado in casos:
                with self.subTest(nivel=nivel, esperado=esperado, fonte=fonte):
                    codigo, dados, status = self.gerar(fonte, nivel)
                    self.assertEqual(codigo, 0)
                    self.assertIsNotNone(dados)
                    if status is not None:
                        self.assertEqual(status, esperado)

    def test_escopos_locais_rejeitam_uso_fora_do_bloco_e_duplicidade(self):
        casos = (
            (7, "funcao f(n: inteiro) -> inteiro {\n"
             " seja r = 0\n se n > 0 {\n seja x = 2\n r = x\n }\n"
             " retorne x\n}\n inicio { seja r = f(1) }"),
            (7, "funcao f(n: inteiro) -> inteiro {\n"
             " seja r = 0\n se n > 0 {\n seja x = 2\n r = x\n"
             " } senao {\n r = x\n }\n"
             " retorne r\n}\n inicio { seja r = f(1) }"),
            (7, "funcao f(n: inteiro) -> inteiro {\n"
             " seja i = 0\n enquanto i < n {\n"
             " seja x = i\n i = i + 1\n }\n"
             " retorne x\n}\n inicio { seja r = f(2) }"),
            (5, "funcao f(n: inteiro) -> inteiro {\n"
             " seja i = 0\n enquanto i < n {\n"
             " seja x = i\n i = i + 1\n }\n"
             " x = 3\n retorne i\n}\n inicio { seja r = f(2) }"),
            (4, "funcao f(n: inteiro) -> inteiro {\n"
             " seja r = 0\n se n > 0 {\n"
             " seja x = 1\n seja x = 2\n r = x\n }\n"
             " retorne r\n}\n inicio { seja r = f(2) }"),
            (4, "funcao f(n: inteiro) -> inteiro {\n"
             " seja r = 1\n seja r = 2\n retorne r\n"
             "}\n inicio { seja r = f(2) }"),
            (4, "funcao f(n: inteiro) -> inteiro {\n"
             " seja n = 4\n retorne n\n"
             "}\n inicio { seja r = f(2) }"),
        )
        for nivel in (0, 8):
            for esperado, fonte in casos:
                with self.subTest(nivel=nivel, esperado=esperado, fonte=fonte):
                    codigo, dados, status = self.gerar(fonte, nivel)
                    self.assertEqual(codigo, esperado)
                    self.assertIsNone(dados)
                    self.assertIsNone(status)


    def test_declaracoes_tipadas_inteiro_em_funcoes_e_inicio(self):
        casos = (
            ("funcao dobro(n: inteiro) -> inteiro {\n"
             " seja resultado: inteiro = n * 2\n"
             " retorne resultado\n}\n"
             "inicio { seja saida: inteiro = dobro(7) }", 14),
            ("funcao escolher(n: inteiro) -> inteiro {\n"
             " seja resultado: inteiro = 0\n"
             " se n > 0 {\n"
             " seja valor: inteiro = n + 4\n resultado = valor\n"
             " } senao {\n"
             " seja valor: inteiro = 20\n resultado = valor\n"
             " }\n retorne resultado\n}\n"
             "inicio { seja saida: inteiro = escolher(3) }", 7),
            ("funcao escolher(n: inteiro) -> inteiro {\n"
             " seja resultado: inteiro = 0\n"
             " se n > 0 {\n"
             " seja valor: inteiro = n + 4\n resultado = valor\n"
             " } senao {\n"
             " seja valor: inteiro = 20\n resultado = valor\n"
             " }\n retorne resultado\n}\n"
             "inicio { seja saida: inteiro = escolher(-3) }", 20),
            ("funcao somar(n: inteiro) -> inteiro {\n"
             " seja i: inteiro = 0\n"
             " seja total: inteiro = 0\n"
             " enquanto i < n {\n"
             " seja parcela: inteiro = i + 2\n"
             " total = total + parcela\n i = i + 1\n"
             " }\n retorne total\n}\n"
             "inicio { seja saida: inteiro = somar(4) }", 14),
            ("funcao calcular(n: inteiro) -> inteiro {\n"
             " seja valor: inteiro = n\n"
             " se n > 0 {\n"
             " seja valor: inteiro = 11\n"
             " valor = valor + 1\n"
             " }\n retorne valor\n}\n"
             "inicio { seja saida: inteiro = calcular(5) }", 5),
            ("funcao base(n: inteiro) -> inteiro {\n"
             " seja x: inteiro = n + 1\n retorne x\n}\n"
             "funcao executar(n: inteiro) -> inteiro {\n"
             " seja x: inteiro = base(n)\n"
             " retorne x + 2\n}\n"
             "inicio { seja saida: inteiro = executar(5) }", 8),
            ("funcao base(n: inteiro) -> inteiro {\n"
             " seja x: inteiro = n + 1\n retorne x\n}\n"
             "inicio {\n"
             " seja saida: inteiro = base(2)\n"
             " se saida > 0 {\n"
             " seja parcial: inteiro = saida + 2\n"
             " saida = parcial\n }\n"
             " saida = base(saida)\n}", 6),
        )
        for nivel in (0, 8):
            for fonte, esperado in casos:
                with self.subTest(nivel=nivel, fonte=fonte):
                    codigo, dados, status = self.gerar(fonte, nivel)
                    self.assertEqual(codigo, 0)
                    self.assertIsNotNone(dados)
                    if status is not None:
                        self.assertEqual(status, esperado)

    def test_declaracoes_tipadas_rejeitam_tipos_e_sintaxe_incorretos(self):
        casos = (
            (2, "funcao f() -> inteiro {\n"
             " seja x: real = 2\n retorne x\n}\n"
             "inicio { seja r = f() }"),
            (2, "funcao f() -> inteiro {\n"
             " seja x: texto = 2\n retorne x\n}\n"
             "inicio { seja r = f() }"),
            (2, "funcao f() -> inteiro {\n"
             " seja x: lista[inteiro] = 2\n retorne x\n}\n"
             "inicio { seja r = f() }"),
            (17, "funcao f() -> inteiro {\n retorne 1\n}\n"
             "inicio { seja r: bytes = f() }"),
            (3, "funcao f() -> inteiro {\n"
             " seja x: inteiro 2\n retorne x\n}\n"
             "inicio { seja r = f() }"),
            (3, "funcao f() -> inteiro {\n"
             " seja x: inteiro: inteiro = 2\n retorne x\n}\n"
             "inicio { seja r = f() }"),
            (3, "funcao f() -> inteiro {\n"
             " seja x: inteiro = 2\n x: inteiro = 3\n retorne x\n}\n"
             "inicio { seja r = f() }"),
        )
        for nivel in (0, 8):
            for esperado, fonte in casos:
                with self.subTest(nivel=nivel, esperado=esperado, fonte=fonte):
                    codigo, dados, status = self.gerar(fonte, nivel)
                    self.assertEqual(codigo, esperado)
                    self.assertIsNone(dados)
                    self.assertIsNone(status)


    def test_buffers_bytes_nativos_e_leituras_o0_o8(self):
        casos = (
            ("funcao f() -> inteiro {\n"
             ' seja dados: bytes = "ABC"\n'
             " retorne dados[0]\n}\n"
             "inicio { seja r = f() }", 65),
            ("funcao f() -> inteiro {\n"
             ' seja dados: bytes = "ABC"\n'
             " retorne dados[2]\n}\n"
             "inicio { seja r = f() }", 67),
            ("funcao f() -> inteiro {\n"
             ' seja dados: bytes = "ABC"\n'
             " retorne tamanho(dados)\n}\n"
             "inicio { seja r = f() }", 3),
            ("funcao f() -> inteiro {\n"
             ' seja dados: bytes = ""\n'
             " retorne tamanho(dados)\n}\n"
             "inicio { seja r = f() }", 0),
            ("funcao f() -> inteiro {\n"
             ' seja dados: bytes = "0123456789abcdefghijklmnopqrstuv"\n'
             " retorne dados[31]\n}\n"
             "inicio { seja r = f() }", ord("v")),
            ("funcao f(n: inteiro) -> inteiro {\n"
             ' seja dados: bytes = "ABC"\n'
             " retorne dados[n]\n}\n"
             "inicio { seja r = f(1) }", 66),
            ("funcao f(n: inteiro) -> inteiro {\n"
             ' seja dados: bytes = "ABC"\n'
             " retorne dados[n + 1] + tamanho(dados)\n}\n"
             "inicio { seja r = f(1) }", 70),
            ("funcao f() -> inteiro {\n"
             ' seja dados: bytes = "ABC"\n'
             " retorne dados[0] + dados[2]\n}\n"
             "inicio { seja r = f() }", 132),
            ("funcao f() -> inteiro {\n"
             ' seja dados: bytes = "Ação"\n'
             " retorne dados[1]\n}\n"
             "inicio { seja r = f() }", 195),
            ("funcao f(n: inteiro) -> inteiro {\n"
             " seja valor: inteiro = n\n"
             ' se n > 0 {\n seja dados: bytes = "Z"\n'
             " valor = dados[0]\n }\n"
             " retorne valor\n}\n"
             "inicio { seja r = f(1) }", 90),
            ("funcao f() -> inteiro {\n"
             ' seja dados: bytes = "A"\n'
             ' se dados[0] > 64 {\n retorne tamanho(dados) + dados[0]\n }\n'
             " retorne 0\n}\n"
             "inicio { seja r = f() }", 66),
            ("funcao f() -> inteiro {\n"
             ' seja dados: bytes = "XYZ"\n'
             " seja i: inteiro = 0\n seja total: inteiro = 0\n"
             " enquanto i < tamanho(dados) {\n"
             " total = total + dados[i]\n i = i + 1\n"
             " }\n retorne total\n}\n"
             "inicio { seja r = f() }", 267 % 256),
            ("funcao f() -> inteiro {\n retorne 1\n}\n"
             'inicio { seja dados: bytes = "AB"\n'
             " seja r: inteiro = f()\n"
             " r = dados[0] + tamanho(dados)\n}", 67),
        )
        for nivel in (0, 8):
            for fonte, esperado in casos:
                with self.subTest(nivel=nivel, esperado=esperado, fonte=fonte):
                    codigo, dados, status = self.gerar(fonte, nivel)
                    self.assertEqual(codigo, 0)
                    self.assertIsNotNone(dados)
                    if status is not None:
                        self.assertEqual(status, esperado % 256)

    def test_buffers_bytes_nativos_indice_fora_do_limite(self):
        fontes = (
            ("funcao f() -> inteiro {\n"
             ' seja dados: bytes = "ABC"\n retorne dados[3]\n}\n'
             "inicio { seja r = f() }"),
            ("funcao f() -> inteiro {\n"
             ' seja dados: bytes = "ABC"\n retorne dados[-1]\n}\n'
             "inicio { seja r = f() }"),
            ("funcao f(n: inteiro) -> inteiro {\n"
             ' seja dados: bytes = "ABC"\n retorne dados[n]\n}\n'
             "inicio { seja r = f(100) }"),
            ("funcao f() -> inteiro {\n"
             ' seja dados: bytes = ""\n retorne dados[0]\n}\n'
             "inicio { seja r = f() }"),
        )
        for nivel in (0, 8):
            for fonte in fontes:
                with self.subTest(nivel=nivel, fonte=fonte):
                    codigo, dados, status = self.gerar(fonte, nivel)
                    self.assertEqual(codigo, 0)
                    self.assertIsNotNone(dados)
                    if status is not None:
                        self.assertEqual(status, 23)

    def test_buffers_bytes_nativos_diagnosticos_e_escopos(self):
        casos = (
            (17, "funcao f() -> inteiro {\n"
             ' seja dados: bytes = "0123456789abcdefghijklmnopqrstuvw"\n'
             " retorne 0\n}\n inicio { seja r = f() }"),
            (17, "funcao f() -> inteiro {\n"
             ' seja dados: bytes = "A\\\\n"\n'
             " retorne 0\n}\n inicio { seja r = f() }"),
            (17, "funcao f() -> inteiro {\n"
             " seja dados: bytes = 42\n"
             " retorne 0\n}\n inicio { seja r = f() }"),
            (17, "funcao f() -> inteiro {\n"
             ' seja dados: bytes = "A" + "B"\n'
             " retorne 0\n}\n inicio { seja r = f() }"),
            (18, "funcao f() -> inteiro {\n"
             ' seja dados: bytes = "A"\n dados = 9\n'
             " retorne 0\n}\n inicio { seja r = f() }"),
            (7, "funcao f() -> inteiro {\n"
             ' se 1 > 0 {\n seja dados: bytes = "A"\n }\n'
             " retorne dados[0]\n}\n inicio { seja r = f() }"),
        )
        for nivel in (0, 8):
            for esperado, fonte in casos:
                with self.subTest(nivel=nivel, erro=esperado, fonte=fonte):
                    codigo, dados, status = self.gerar(fonte, nivel)
                    self.assertEqual(codigo, esperado)
                    self.assertIsNone(dados)
                    self.assertIsNone(status)


    def test_bytes_escrita_e_dinamicos_mmap_o0_o8(self):
        casos = (
            ("funcao f() -> inteiro {\n"
             ' seja dados: bytes = "ABC"\n'
             " dados[1] = 90\n"
             " retorne dados[0] + dados[1] + dados[2]\n"
             "}\n inicio { seja r = f() }", 65 + 90 + 67),
            ("funcao f() -> inteiro {\n"
             ' seja dados: bytes = "ABC"\n'
             " seja i: inteiro = 0\n"
             " dados[i + 2] = 120\n"
             " retorne dados[2]\n"
             "}\n inicio { seja r = f() }", 120),
            ("funcao f() -> inteiro {\n"
             " seja dados: bytes = criar_bytes(128)\n"
             " dados[120] = 201\n"
             " seja r = dados[120] + tamanho(dados)\n"
             " liberar_bytes(dados)\n"
             " retorne r\n"
             "}\n inicio { seja r = f() }", (201 + 128) % 256),
            ("funcao f() -> inteiro {\n"
             " seja dados: bytes = criar_bytes(0)\n"
             " seja r = tamanho(dados)\n"
             " liberar_bytes(dados)\n"
             " retorne r\n"
             "}\n inicio { seja r = f() }", 0),
            ("funcao f() -> inteiro {\n"
             " seja dados: bytes = criar_bytes(65537)\n"
             " dados[65536] = 255\n"
             " seja r = dados[65536] + dados[0]\n"
             " liberar_bytes(dados)\n"
             " retorne r\n"
             "}\n inicio { seja r = f() }", 255),
            ("funcao f(n: inteiro) -> inteiro {\n"
             " seja dados: bytes = criar_bytes(n + 2)\n"
             " dados[n] = n + 30\n"
             " seja r = dados[n] + tamanho(dados)\n"
             " liberar_bytes(dados)\n retorne r\n"
             "}\n inicio { seja r = f(10) }", 52),
            ("funcao f() -> inteiro {\n"
             " seja i: inteiro = 0\n seja total: inteiro = 0\n"
             " enquanto i < 3 {\n"
             " seja dados: bytes = criar_bytes(64)\n"
             " dados[i] = i + 65\n"
             " total = total + dados[i]\n"
             " liberar_bytes(dados)\n"
             " i = i + 1\n }\n"
             " retorne total\n"
             "}\n inicio { seja r = f() }", (65 + 66 + 67) % 256),
            ("funcao f() -> inteiro {\n"
             " seja i: inteiro = 1\n"
             " se i > 0 {\n"
             " seja dados: bytes = criar_bytes(i + 40)\n"
             " dados[i + 32] = 200\n"
             " i = dados[i + 32]\n"
             " liberar_bytes(dados)\n"
             " }\n retorne i\n"
             "}\n inicio { seja r = f() }", 200),
            ("funcao f() -> inteiro {\n"
             " seja dados: bytes = criar_bytes(4)\n"
             " dados[0] = 255\n"
             " seja r = dados[0]\n"
             " liberar_bytes(dados)\n"
             " retorne r\n"
             "}\n inicio { seja r = f() }", 255),
        )
        for nivel in (0, 8):
            for fonte, esperado in casos:
                with self.subTest(nivel=nivel, fonte=fonte, esperado=esperado):
                    codigo, dados, status = self.gerar(fonte, nivel)
                    self.assertEqual(codigo, 0)
                    self.assertIsNotNone(dados)
                    if status is not None:
                        self.assertEqual(status, esperado % 256)

    def test_bytes_dinamicos_erros_de_limites_propriedade_e_valor(self):
        casos = (
            ("funcao f() -> inteiro {\n"
             " seja dados: bytes = criar_bytes(-1)\n"
             " liberar_bytes(dados)\n retorne 0\n"
             "}\n inicio { seja r = f() }", 24),
            ("funcao f() -> inteiro {\n"
             " seja dados: bytes = criar_bytes(1048577)\n"
             " liberar_bytes(dados)\n retorne 0\n"
             "}\n inicio { seja r = f() }", 24),
            ("funcao f() -> inteiro {\n"
             " seja dados: bytes = criar_bytes(2)\n"
             " dados[2] = 10\n liberar_bytes(dados)\n retorne 0\n"
             "}\n inicio { seja r = f() }", 23),
            ("funcao f() -> inteiro {\n"
             " seja dados: bytes = criar_bytes(2)\n"
             " dados[-1] = 10\n liberar_bytes(dados)\n retorne 0\n"
             "}\n inicio { seja r = f() }", 23),
            ("funcao f() -> inteiro {\n"
             ' seja dados: bytes = "ABC"\n'
             " dados[0] = 256\n retorne 0\n"
             "}\n inicio { seja r = f() }", 23),
            ("funcao f() -> inteiro {\n"
             " seja dados: bytes = criar_bytes(2)\n"
             " dados[0] = -1\n liberar_bytes(dados)\n retorne 0\n"
             "}\n inicio { seja r = f() }", 23),
            ("funcao f() -> inteiro {\n"
             " seja dados: bytes = criar_bytes(2)\n"
             " liberar_bytes(dados)\n"
             " retorne dados[0]\n"
             "}\n inicio { seja r = f() }", 23),
            ("funcao f() -> inteiro {\n"
             " seja dados: bytes = criar_bytes(2)\n"
             " liberar_bytes(dados)\n"
             " liberar_bytes(dados)\n retorne 0\n"
             "}\n inicio { seja r = f() }", 25),
        )
        for nivel in (0, 8):
            for fonte, esperado in casos:
                with self.subTest(nivel=nivel, esperado=esperado, fonte=fonte):
                    codigo, dados, status = self.gerar(fonte, nivel)
                    self.assertEqual(codigo, 0)
                    self.assertIsNotNone(dados)
                    if status is not None:
                        self.assertEqual(status, esperado)

    def test_bytes_dinamicos_sintaxe_e_tipos_invalidos(self):
        casos = (
            (18, "funcao f() -> inteiro {\n"
             " seja a = 1\n a[0] = 65\n retorne 0\n"
             "}\n inicio { seja r = f() }"),
            (18, "funcao f() -> inteiro {\n"
             ' seja a: bytes = "ABC"\n'
             " liberar_bytes(a)\n retorne 0\n"
             "}\n inicio { seja r = f() }"),
            (18, "funcao f() -> inteiro {\n"
             " seja a: bytes = criar_bytes(5)\n"
             " a = 10\n liberar_bytes(a)\n retorne 0\n"
             "}\n inicio { seja r = f() }"),
            (5, "funcao f() -> inteiro {\n"
             " liberar_bytes(a)\n retorne 0\n"
             "}\n inicio { seja r = f() }"),
            (3, "funcao f() -> inteiro {\n"
             ' seja a: bytes = "ABC"\n'
             " a[] = 1\n retorne 0\n"
             "}\n inicio { seja r = f() }"),
            (17, "funcao f() -> inteiro {\n"
             " seja a: bytes = criar_bytes()\n"
             " retorne 0\n"
             "}\n inicio { seja r = f() }"),
        )
        for nivel in (0, 8):
            for esperado, fonte in casos:
                with self.subTest(nivel=nivel, esperado=esperado, fonte=fonte):
                    codigo, dados, status = self.gerar(fonte, nivel)
                    self.assertEqual(codigo, esperado)
                    self.assertIsNone(dados)
                    self.assertIsNone(status)


if __name__ == "__main__":
    unittest.main()
