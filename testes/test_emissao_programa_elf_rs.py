"""Confere a emissao de programa RS com variaveis para ELF x86-64."""
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

FERRAMENTA = RAIZ / "exemplos" / "ferramentas" / "compilador_programa_elf_rs.rts"


def alvo_local():
    if sys.platform == "win32":
        return "windows"
    if sys.platform == "linux" and os.uname().machine == "x86_64":
        return "linux"
    raise unittest.SkipTest("Exige Windows ou Linux x86-64")


class TestesEmissaoProgramaELFRS(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pasta = tempfile.TemporaryDirectory(prefix="rs_programa_elf_")
        cls.alvo = alvo_local()
        programa = analisar_programa(carregar_fontes(FERRAMENTA).texto)
        cls.ferramentas = {}
        for nivel in (0, 8):
            for alvo in ("linux", "windows"):
                imagem = compilar(programa, alvo, nivel=nivel, otimizar=nivel > 0)
                if alvo == cls.alvo:
                    destino = Path(cls.pasta.name) / (
                        f"emissor_programa_{nivel}" + (".exe" if alvo == "windows" else "")
                    )
                    destino.write_bytes(imagem)
                    if alvo == "linux":
                        destino.chmod(0o700)
                    cls.ferramentas[nivel] = destino

    @classmethod
    def tearDownClass(cls):
        if hasattr(cls, "pasta"):
            cls.pasta.cleanup()

    def emitir(self, codigo, nivel):
        with tempfile.TemporaryDirectory(prefix="rs_codigo_elf_") as pasta:
            raiz = Path(pasta)
            (raiz / "codigo_fonte.rts").write_text(codigo, encoding="utf-8")
            proc = subprocess.run(
                [str(self.ferramentas[nivel])],
                cwd=raiz, timeout=30, capture_output=True,
                text=True, encoding="utf-8", errors="replace",
            )
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            saida = [int(v) for v in proc.stdout.splitlines()]
            self.assertIn(len(saida), (2, 3))
            destino = raiz / "resultado_programa_elf"
            if saida[0] != 0:
                self.assertFalse(destino.exists())
                return saida[0], None, None
            self.assertEqual(len(saida), 3)
            dados = destino.read_bytes()
            self.assertEqual(len(dados), saida[2])
            self.assertEqual(dados[:7], b"\x7fELF\x02\x01\x01")
            cabecalho = struct.unpack_from("<HHIQQQIHHHHHH", dados, 16)
            self.assertEqual(cabecalho[0:3], (2, 62, 1))
            self.assertEqual(cabecalho[3], 0x400078)
            segmento = struct.unpack_from("<IIQQQQQQ", dados, 64)
            self.assertEqual(segmento, (1, 5, 0, 0x400000, 0x400000, len(dados), len(dados), 4096))
            self.assertEqual(dados[120:127], bytes((85, 72, 137, 229, 72, 129, 236)))
            self.assertEqual(dados[-7:], bytes((184, 60, 0, 0, 0, 15, 5)))
            codigo_saida = None
            if self.alvo == "linux":
                destino.chmod(0o700)
                codigo_saida = subprocess.run([str(destino)], cwd=raiz, timeout=10).returncode
            return 0, dados, codigo_saida

    def test_variaveis_e_referencias_reais(self):
        casos = {
            "inicio {\n seja a = 10\n seja b = a + 2 * 3\n}": 16,
            "inicio {\n seja a = 1\n seja b = a + 5\n seja c = b * (a + 3)\n}": 24,
            "inicio {\n seja um = 33\n seja dois = um - 100\n}": (-67) % 256,
            "inicio {\n seja x = -2\n seja y = x * -3\n}": 6,
            "inicio {\n seja a = 5\n seja b = a\n}": 5,
            "inicio {\n seja a = 1000000000\n seja b = a + 1\n}": (1000000001) % 256,
            "inicio { seja a = 1; seja b = a + 2; }": 3,
            "inicio {\n seja a = 7\n seja b = a + a * (a - 2)\n}": 42,
        }
        for nivel in (0, 8):
            for fonte, esperado in casos.items():
                with self.subTest(nivel=nivel, fonte=fonte):
                    codigo, imagem, retorno = self.emitir(fonte, nivel)
                    self.assertEqual(codigo, 0)
                    self.assertIsNotNone(imagem)
                    self.assertIn(bytes.fromhex("48 8b 85"), imagem)
                    self.assertIn(bytes.fromhex("48 89 85"), imagem)
                    if retorno is not None:
                        self.assertEqual(retorno, esperado)

    def test_gerado_com_oraculo_independente(self):
        r = random.Random(42057)
        for _ in range(16):
            a = r.randrange(0, 80)
            b = r.randrange(0, 70)
            c = r.randrange(0, 50)
            codigo = (
                "inicio {\n"
                f" seja base = {a} * {b}\n"
                f" seja soma = base + {c}\n"
                " seja final = (soma - base) * 3 + soma\n"
                "}"
            )
            esperado = ((a * b + c - a * b) * 3 + a * b + c) % 256
            for nivel in (0, 8):
                cod, _, retorno = self.emitir(codigo, nivel)
                self.assertEqual(cod, 0)
                if retorno is not None:
                    self.assertEqual(retorno, esperado)

    def test_rejeita_comandos_e_programas_incompletos(self):
        fontes = (
            "",
            "2 + 3",
            "inicio {}",
            "inicio {\n seja a = 1\n escreva(a)\n}",
            "inicio {\n escreva(1)\n seja a = 2\n}",
            "inicio {\n seja a = 1\n retorne a\n}",
            "inicio {\n seja a: inteiro = 1\n}",
            "inicio {\n seja a = 1\n a = 2\n}",
            "inicio {\n seja a = 1\n se verdadeiro { seja b = 2 }\n}",
            "inicio {\n seja a = 1\n}\ninicio {\n seja b = 2\n}",
            "funcao soma() -> inteiro { retorne 1 }\ninicio { seja x = soma() }",
            "inicio {\n seja a = 2\n seja a = 3\n}",
            "inicio {\n seja a = b + 1\n seja b = 1\n}",
            "inicio {\n seja a = 1 / 2\n}",
            "inicio {\n seja a = 1000000001\n}",
        )
        for nivel in (0, 8):
            for fonte in fontes:
                with self.subTest(nivel=nivel, fonte=fonte):
                    codigo, imagem, retorno = self.emitir(fonte, nivel)
                    self.assertNotEqual(codigo, 0)
                    self.assertIsNone(imagem)
                    self.assertIsNone(retorno)


if __name__ == "__main__":
    unittest.main()
