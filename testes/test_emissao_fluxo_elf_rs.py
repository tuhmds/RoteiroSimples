"""Compila e executa ELF64 emitido em RS com saltos condicionais e lacos."""
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

FERRAMENTA = RAIZ / "exemplos" / "ferramentas" / "compilador_fluxo_elf_rs.rts"


def alvo_local():
    if sys.platform == "win32":
        return "windows"
    if sys.platform == "linux" and os.uname().machine == "x86_64":
        return "linux"
    raise unittest.SkipTest("Exige Windows ou Linux x86-64")


class TestesEmissaoFluxoELFRS(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pasta = tempfile.TemporaryDirectory(prefix="rs_fluxo_elf_")
        cls.alvo = alvo_local()
        programa = analisar_programa(carregar_fontes(FERRAMENTA).texto)
        cls.ferramentas = {}
        for nivel in (0, 8):
            for alvo in ("linux", "windows"):
                imagem = compilar(programa, alvo, nivel=nivel, otimizar=nivel > 0)
                if alvo == cls.alvo:
                    destino = Path(cls.pasta.name) / (
                        f"emissor_fluxo_{nivel}" + (".exe" if alvo == "windows" else "")
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
        with tempfile.TemporaryDirectory(prefix="rs_codigo_fluxo_") as pasta:
            raiz = Path(pasta)
            (raiz / "codigo_fonte.rts").write_text(fonte, encoding="utf-8")
            proc = subprocess.run(
                [str(self.ferramentas[nivel])], cwd=raiz, timeout=30,
                capture_output=True, text=True, encoding="utf-8", errors="replace",
            )
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            saida = [int(valor) for valor in proc.stdout.splitlines()]
            self.assertIn(len(saida), (2, 3))
            arquivo = raiz / "resultado_fluxo_elf"
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
            self.assertEqual(dados[-7:], bytes((184, 60, 0, 0, 0, 15, 5)))
            resultado = None
            if self.alvo == "linux":
                arquivo.chmod(0o700)
                resultado = subprocess.run([str(arquivo)], cwd=raiz, timeout=4).returncode
            return 0, dados, resultado

    def test_condicionais_comparacoes_assinadas(self):
        casos = (
            ("inicio {\n seja n = 2\n se n < 3 {\n n = n + 5\n }\n}", 7),
            ("inicio {\n seja n = 3\n se n < 3 {\n n = 99\n }\n}", 3),
            ("inicio {\n seja n = -1\n se n <= 0 {\n n = 11\n }\n}", 11),
            ("inicio {\n seja n = 8\n se n > 7 {\n n = n * 2\n }\n}", 16),
            ("inicio {\n seja n = 8\n se n >= 9 {\n n = 77\n }\n}", 8),
            ("inicio {\n seja n = 10\n se n == 10 {\n n = n + 1\n }\n}", 11),
            ("inicio {\n seja n = 10\n se n != 10 {\n n = 99\n }\n}", 10),
            ("inicio {\n seja n = 3\n se (n * 2) <= 6 {\n n = 19\n }\n}", 19),
            ("inicio {\n seja n = 3\n se n + 1 >= 4 {\n n = 23\n }\n}", 23),
            ("inicio {\n seja n = -5\n se n < 0 {\n n = -n\n }\n}", 5),
        )
        for nivel in (0, 8):
            for fonte, esperado in casos:
                with self.subTest(nivel=nivel, fonte=fonte):
                    codigo, dados, status = self.gerar(fonte, nivel)
                    self.assertEqual(codigo, 0)
                    self.assertIn(bytes((72, 57, 200, 15)), dados)
                    if status is not None:
                        self.assertEqual(status, esperado % 256)

    def test_divisao_e_resto_no_fluxo_sem_chamadas(self):
        casos = (
            ("inicio {\n seja a = -17\n a = a / 5\n}", 253),
            ("inicio {\n seja a = -17\n a = a % 5\n}", 254),
            ("inicio {\n seja a = 17\n a = a % -5\n}", 2),
            ("inicio {\n seja a = 8\n a = a / 2 * 3 + 1\n}", 13),
            ("inicio {\n seja a = 17\n se a / 3 == 5 {\n a = a % 3\n }\n}", 2),
        )
        for nivel in (0, 8):
            for fonte, esperado in casos:
                with self.subTest(nivel=nivel, fonte=fonte):
                    codigo, dados, status = self.gerar(fonte, nivel)
                    self.assertEqual(codigo, 0)
                    self.assertIn(bytes((72, 153, 72, 247, 249)), dados)
                    if status is not None:
                        self.assertEqual(status, esperado % 256)

    def test_lacos_e_aninhamentos(self):
        casos = (
            ("inicio {\n seja n = 0\n enquanto n < 5 {\n n = n + 1\n }\n}", 5),
            ("inicio {\n seja n = 8\n enquanto n < 4 {\n n = n + 1\n }\n}", 8),
            ("inicio {\n seja n = 5\n enquanto n > 0 {\n n = n - 1\n }\n}", 0),
            ("inicio {\n seja x = -4\n enquanto x < 0 {\n x = x + 1\n }\n}", 0),
            ("inicio {\n seja a = 0\n seja b = 0\n enquanto a < 3 {\n a = a + 1\n b = b + a\n }\n}", 6),
            ("inicio {\n seja n = 0\n enquanto n < 3 {\n se n == 1 {\n n = n + 2\n }\n se n < 1 {\n n = n + 1\n }\n }\n}", 3),
            ("inicio {\n seja n = 0\n seja total = 0\n enquanto n < 4 {\n seja_ignorado = 0\n }\n}", None),
        )
        for nivel in (0, 8):
            for fonte, esperado in casos:
                with self.subTest(nivel=nivel, fonte=fonte):
                    codigo, dados, status = self.gerar(fonte, nivel)
                    if esperado is None:
                        self.assertNotEqual(codigo, 0)
                    else:
                        self.assertEqual(codigo, 0)
                        self.assertIn(bytes((233,)), dados[127:])
                        if status is not None:
                            self.assertEqual(status, esperado % 256)

    def test_aleatorio_com_modelo_independente(self):
        gerador = random.Random(42058)
        for _ in range(12):
            incremento = gerador.randint(1, 6)
            limite = gerador.randint(3, 12)
            esperado = ((limite + incremento - 1) // incremento) * incremento
            fonte = (
                "inicio {\n"
                " seja posicao = 0\n"
                f" enquanto posicao < {limite} {{\n"
                f" posicao = posicao + {incremento}\n"
                " }\n"
                "}"
            )
            for nivel in (0, 8):
                codigo, _, status = self.gerar(fonte, nivel)
                self.assertEqual(codigo, 0)
                if status is not None:
                    self.assertEqual(status, esperado % 256)

    def test_rejeicoes_e_ausencia_de_saida_parcial(self):
        fontes = (
            "",
            "2+3",
            "inicio {}",
            "inicio { seja a = 3 } inicio { seja b = 2 }",
            "inicio { seja a = 1; seja a = 2; }",
            "inicio { a = 1 }",
            "inicio {\n seja a = 2\n seja b = x + 1\n}",
            "inicio {\n seja a = 1\n b = 2\n}",
            "inicio {\n seja a = 1\n se a < 2 {\n seja b = 3\n }\n}",
            "inicio {\n seja a = 1\n enquanto a < 2 {\n seja b = 3\n }\n}",
            "inicio {\n seja a = 1\n se a {\n a = 2\n }\n}",
            "inicio {\n seja a = 1\n se a + 1 < a + 2 > 0 {\n a = 2\n }\n}",
            "inicio {\n seja a = 1\n se a > 0 { a = 2 }\n senao { a = 3 }\n}",
            "inicio {\n seja a = 1\n escreva(a)\n}",
            "inicio {\n seja a = 1\n a = a ** 2\n}",
            "inicio {\n seja a = 1000000001\n}",
            "inicio {\n seja a = 1\n enquanto a < 3 {\n a = a + 1\n}",
            "funcao n() -> inteiro { retorne 1 } inicio { seja a = 2 }",
        )
        for nivel in (0, 8):
            for fonte in fontes:
                with self.subTest(nivel=nivel, fonte=fonte):
                    codigo, dados, status = self.gerar(fonte, nivel)
                    self.assertNotEqual(codigo, 0)
                    self.assertIsNone(dados)
                    self.assertIsNone(status)


if __name__ == "__main__":
    unittest.main()
