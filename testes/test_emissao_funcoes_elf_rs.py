"""Verifica chamadas x86-64 reais produzidas por emissor escrito em RS."""
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

FERRAMENTA = RAIZ / "exemplos" / "ferramentas" / "compilador_funcoes_elf_rs.rts"


def alvo_local():
    if sys.platform == "win32":
        return "windows"
    if sys.platform == "linux" and os.uname().machine == "x86_64":
        return "linux"
    raise unittest.SkipTest("Exige Windows ou Linux x86-64")


class TestesEmissaoFuncoesELFRS(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pasta = tempfile.TemporaryDirectory(prefix="rs_funcoes_elf_")
        cls.alvo = alvo_local()
        programa = analisar_programa(carregar_fontes(FERRAMENTA).texto)
        cls.ferramentas = {}
        for nivel in (0, 8):
            for alvo in ("linux", "windows"):
                imagem = compilar(programa, alvo, nivel=nivel, otimizar=nivel > 0)
                if alvo == cls.alvo:
                    destino = Path(cls.pasta.name) / (
                        f"emissor_funcoes_{nivel}" + (".exe" if alvo == "windows" else "")
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
        with tempfile.TemporaryDirectory(prefix="rs_fonte_funcoes_") as pasta:
            raiz = Path(pasta)
            (raiz / "codigo_fonte.rts").write_text(fonte, encoding="utf-8")
            proc = subprocess.run(
                [str(self.ferramentas[nivel])], cwd=raiz, timeout=30,
                capture_output=True, text=True, encoding="utf-8", errors="replace",
            )
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            saida = [int(v) for v in proc.stdout.splitlines()]
            self.assertIn(len(saida), (2, 3))
            arquivo = raiz / "resultado_funcoes_elf"
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
            status = None
            if self.alvo == "linux":
                arquivo.chmod(0o700)
                status = subprocess.run([str(arquivo)], cwd=raiz, timeout=4).returncode
            return 0, dados, status

    def test_retorno_parametros_e_varias_funcoes(self):
        fontes = (
            ("funcao sete() -> inteiro {\n retorne 7\n}\ninicio {\n seja n = sete()\n}", 7),
            ("funcao dobro(x: inteiro) -> inteiro {\n retorne x * 2\n}\ninicio {\n seja n = dobro(11)\n}", 22),
            ("funcao soma(a: inteiro, b: inteiro) -> inteiro {\n retorne a + b\n}\ninicio {\n seja n = soma(3, 8)\n}", 11),
            ("funcao diferenca(a: inteiro, b: inteiro) -> inteiro {\n retorne a - b\n}\ninicio {\n seja n = diferenca(2, 14)\n}", -12),
            ("funcao calcula(a: inteiro, b: inteiro, c: inteiro, d: inteiro) -> inteiro {\n retorne a + b * c - d\n}\ninicio {\n seja n = calcula(3, 4, 5, 6)\n}", 17),
            ("funcao um() -> inteiro {\n retorne 4\n}\nfuncao dois(x: inteiro, y: inteiro) -> inteiro {\n retorne x * y\n}\ninicio {\n seja a = um()\n seja b = dois(a + 2, a * 3)\n}", 72),
            ("funcao dobro(x: inteiro) -> inteiro {\n retorne x + x\n}\ninicio {\n seja base = 5\n seja y = dobro(base + 3 * 4)\n}", 34),
            ("funcao passar(x: inteiro) -> inteiro {\n retorne x\n}\ninicio {\n seja base = 99\n seja y = passar(base)\n}", 99),
            ("funcao negativo(x: inteiro) -> inteiro {\n retorne -x\n}\ninicio {\n seja n = negativo(-6)\n}", 6),
            ("funcao tres() -> inteiro {\n retorne 3;\n}\ninicio {\n seja um = tres(); seja dois = um + 2;\n}", 5),
        )
        for nivel in (0, 8):
            for fonte, esperado in fontes:
                with self.subTest(nivel=nivel, fonte=fonte):
                    codigo, dados, retorno = self.gerar(fonte, nivel)
                    self.assertEqual(codigo, 0)
                    self.assertIn(bytes((232,)), dados)
                    if retorno is not None:
                        self.assertEqual(retorno, esperado % 256)

    def test_aleatorio_oraculo_independente(self):
        rng = random.Random(42059)
        for _ in range(14):
            a, b = rng.randrange(0, 100), rng.randrange(0, 100)
            esperado = (a * 3 - b * 2) % 256
            fonte = (
                "funcao calcula(x: inteiro, y: inteiro) -> inteiro {\n"
                " retorne x * 3 - y * 2\n"
                "}\n"
                "inicio {\n"
                f" seja resultado = calcula({a}, {b})\n"
                "}"
            )
            for nivel in (0, 8):
                codigo, _, retorno = self.gerar(fonte, nivel)
                self.assertEqual(codigo, 0)
                if retorno is not None:
                    self.assertEqual(retorno, esperado)

    def test_rejeita_entradas_fora_do_subconjunto(self):
        ruins = (
            "",
            "inicio {\n seja a = 2\n}",
            "funcao f() -> inteiro {\n retorne 1\n}\ninicio {}",
            "funcao f(a: texto) -> inteiro {\n retorne 1\n}\ninicio {\n seja x = f(1)\n}",
            "funcao f() -> texto {\n retorne 1\n}\ninicio {\n seja x = f()\n}",
            "funcao f(a: inteiro, a: inteiro) -> inteiro {\n retorne a\n}\ninicio {\n seja x = f(1, 2)\n}",
            "funcao f() -> inteiro {\n retorne 1\n}\nfuncao f() -> inteiro {\n retorne 2\n}\ninicio {\n seja x = f()\n}",
            "funcao f(a: inteiro) -> inteiro {\n retorne a\n}\ninicio {\n seja x = f()\n}",
            "funcao f(a: inteiro) -> inteiro {\n retorne a\n}\ninicio {\n seja x = f(1,)\n}",
            "funcao f(a: inteiro) -> inteiro {\n retorne a\n}\ninicio {\n seja x = f(1, 2)\n}",
            "funcao f() -> inteiro {\n retorne 1\n}\ninicio {\n seja x = g()\n}",
            "funcao f() -> inteiro {\n retorne 1\n}\ninicio {\n seja x = f()\n escreva(x)\n}",
            "funcao f() -> inteiro {\n retorne 1\n}\ninicio {\n seja x = f()\n x = 3\n}",
            "funcao f() -> inteiro {\n retorne 1\n}\ninicio {\n seja x = f()\n se x > 0 { x = 2 }\n}",
            "funcao f(x: inteiro) -> inteiro {\n retorne f(x)\n}\ninicio {\n seja x = f(1)\n}",
            "funcao f(x: inteiro) -> inteiro {\n seja y = x + 1\n retorne y\n}\ninicio {\n seja x = f(1)\n}",
            "funcao f(a: inteiro, b: inteiro, c: inteiro, d: inteiro, e: inteiro) -> inteiro {\n retorne a\n}\ninicio {\n seja x = f(1,2,3,4,5)\n}",
            "funcao f(x: inteiro) -> inteiro {\n retorne x\n}\ninicio {\n seja a = 1\n seja b = f(a) + 2\n}",
        )
        for nivel in (0, 8):
            for fonte in ruins:
                with self.subTest(nivel=nivel, fonte=fonte):
                    codigo, dados, retorno = self.gerar(fonte, nivel)
                    self.assertNotEqual(codigo, 0)
                    self.assertIsNone(dados)
                    self.assertIsNone(retorno)


if __name__ == "__main__":
    unittest.main()
