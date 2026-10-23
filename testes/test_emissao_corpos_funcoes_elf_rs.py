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
             "inicio {\n seja r = f(8) / 0\n}", 240),
            ("funcao zero(n: inteiro) -> inteiro {\n retorne n - n\n}\n"
             "inicio {\n seja r = 9 % zero(5)\n}", 240),
            ("funcao f(n: inteiro) -> inteiro {\n retorne n / 0\n}\n"
             "inicio {\n seja r = f(13)\n}", 240),
            ("funcao f(n: inteiro) -> inteiro {\n retorne n\n}\n"
             "inicio {\n seja r = f(0) / 0\n}", 240),
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
             "inicio {\n seja r = f(8) / 0\n}", 240, "RS: divisao por zero\n"),
            ("funcao zero(n: inteiro) -> inteiro {\n retorne n - n\n}\n"
             "inicio {\n seja r = 9 % zero(5)\n}", 240, "RS: divisao por zero\n"),
            ("funcao minimo() -> inteiro {\n"
             " retorne -8 * 1024 * 1024 * 1024 * 1024 * 1024 * 1024\n}\n"
             "inicio {\n seja r = minimo() / -1\n}", 241, "RS: estouro na divisao\n"),
            ("funcao f(n: inteiro) -> inteiro {\n retorne n\n}\n" +
             "\n" * 10 +
             "inicio {\n            seja resultado = f(10) / 0\n}", 240, "RS: divisao por zero\n"),
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
            " seja x = n\n se x > 0 {\n seja y = 4\n }\n"
            " retorne x\n}\n inicio { seja r = f(1) }",
            "funcao f(n: inteiro) -> inteiro {\n"
            " seja x = n\n enquanto x > 0 {\n x = x - 1\n }\n"
            " retorne 1000000001\n}\n inicio { seja r = f(1) }",
            "funcao a() -> inteiro {\n"
            " seja x = b()\n retorne x\n}\n"
            "funcao b() -> inteiro {\n retorne 1\n}\n"
            "inicio { seja r = a() }",
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


if __name__ == "__main__":
    unittest.main()
