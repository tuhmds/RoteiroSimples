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
            "funcao f(n: inteiro) -> inteiro {\n"
            " seja x = n\n x = x / 2\n retorne x\n}\n"
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
