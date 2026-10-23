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

FERRAMENTA = RAIZ / "exemplos" / "ferramentas" / "compilador_integrado_elf_rs.rts"


def alvo_local():
    if sys.platform == "win32":
        return "windows"
    if sys.platform == "linux" and os.uname().machine == "x86_64":
        return "linux"
    raise unittest.SkipTest("Exige Windows ou Linux x86-64")


class TestesEmissaoIntegradaELFRS(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pasta = tempfile.TemporaryDirectory(prefix="rs_integrado_elf_")
        cls.alvo = alvo_local()
        programa = analisar_programa(carregar_fontes(FERRAMENTA).texto)
        cls.ferramentas = {}
        for nivel in (0, 8):
            for alvo in ("linux", "windows"):
                imagem = compilar(programa, alvo, nivel=nivel, otimizar=nivel > 0)
                if alvo == cls.alvo:
                    destino = Path(cls.pasta.name) / (
                        f"emissor_integrado_{nivel}" + (".exe" if alvo == "windows" else "")
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
        with tempfile.TemporaryDirectory(prefix="rs_codigo_integrado_") as pasta:
            raiz = Path(pasta)
            (raiz / "codigo_fonte.rts").write_text(fonte, encoding="utf-8")
            proc = subprocess.run(
                [str(self.ferramentas[nivel])], cwd=raiz, timeout=30,
                capture_output=True, text=True, encoding="utf-8", errors="replace",
            )
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            saida = [int(v) for v in proc.stdout.splitlines()]
            self.assertIn(len(saida), (2, 3))
            arquivo = raiz / "resultado_integrado_elf"
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
            self.assertIn(bytes((72, 57, 200, 15)), dados[127:])
            self.assertIn(bytes((233,)), dados[127:])
            status = None
            if self.alvo == "linux":
                arquivo.chmod(0o700)
                status = subprocess.run([str(arquivo)], cwd=raiz, timeout=4).returncode
            return 0, dados, status

    def test_chamadas_condicionais_lacos_e_atribuicoes(self):
        casos = (
            ("funcao dobro(x: inteiro) -> inteiro {\n retorne x * 2\n}\n"
             "inicio {\n seja n = 0\n seja total = 0\n enquanto n < 4 {\n"
             " n = n + 1\n se n >= 2 {\n total = dobro(total + n)\n }\n }\n}", 36),
            ("funcao soma(a: inteiro, b: inteiro) -> inteiro {\n retorne a + b\n}\n"
             "inicio {\n seja n = 5\n seja total = 7\n se n < 2 {\n total = soma(100, 3)\n"
             " }\n enquanto n > 2 {\n n = n - 1\n total = soma(total, n)\n }\n}", 16),
            ("funcao quadrado(x: inteiro) -> inteiro {\n retorne x * x\n}\n"
             "inicio {\n seja n = 1\n seja total = 0\n enquanto n < 5 {\n"
             " total = quadrado(n)\n n = n + 1\n }\n}", 5),
            ("funcao constante() -> inteiro {\n retorne 9\n}\n"
             "inicio {\n seja n = 0\n enquanto n < 2 {\n"
             " n = constante()\n }\n}", 9),
            ("funcao negacao(x: inteiro) -> inteiro {\n retorne -x\n}\n"
             "inicio {\n seja x = -2\n se x < 0 {\n x = negacao(x)\n }\n"
             " enquanto x > 0 {\n x = x - 1\n }\n}", 0),
            ("funcao dois(x: inteiro, y: inteiro) -> inteiro {\n retorne x * y\n}\n"
             "inicio {\n seja n = 0\n seja total = 0\n enquanto n < 4 {\n"
             " n = n + 1\n se n == 3 {\n total = dois(n, 7)\n }\n"
             " se n == 4 {\n total = total + 1\n }\n }\n}", 22),
            ("funcao f(a: inteiro) -> inteiro {\n retorne a\n}\n"
             "inicio {\n seja x = f(1)\n"
             " se x > 0 {\n seja y = 2\n x = x + y\n }\n"
             " enquanto x < 4 {\n x = x + 1\n }\n}", 4),
        )
        for nivel in (0, 8):
            for fonte, esperado in casos:
                with self.subTest(nivel=nivel, fonte=fonte):
                    codigo, dados, status = self.gerar(fonte, nivel)
                    self.assertEqual(codigo, 0)
                    if status is not None:
                        self.assertEqual(status, esperado % 256)

    def test_geracao_pseudorrandomica_com_oraculo(self):
        rng = random.Random(42060)
        for _ in range(12):
            multiplicador = rng.randrange(1, 7)
            limite = rng.randrange(2, 9)
            fonte = (
                "funcao produto(x: inteiro, y: inteiro) -> inteiro {\n"
                " retorne x * y\n}\n"
                "inicio {\n seja n = 0\n seja total = 0\n"
                f" enquanto n < {limite} {{\n"
                " n = n + 1\n"
                f" total = produto(total + n, {multiplicador})\n"
                " }\n}"
            )
            esperado = 0
            for n in range(1, limite + 1):
                esperado = (esperado + n) * multiplicador
            for nivel in (0, 8):
                codigo, _, status = self.gerar(fonte, nivel)
                self.assertEqual(codigo, 0)
                if status is not None:
                    self.assertEqual(status, esperado % 256)

    def test_locais_tipados_no_emissor_integrado(self):
        casos = (
            ("funcao dobro(x: inteiro) -> inteiro {\n retorne x * 2\n}\n"
             "inicio {\n"
             " seja i: inteiro = 0\n"
             " seja total: inteiro = 0\n"
             " enquanto i < 4 {\n"
             " seja parcela: inteiro = i + 1\n"
             " total = total + parcela\n i = i + 1\n"
             " }\n total = dobro(total)\n}", 20),
            ("funcao dobro(x: inteiro) -> inteiro {\n retorne x * 2\n}\n"
             "inicio {\n"
             " seja total: inteiro = 1\n"
             " se total > 0 {\n"
             " seja total: inteiro = 10\n"
             " total = total + 1\n }\n"
             " seja contador: inteiro = 0\n"
             " enquanto contador < 2 {\n contador = contador + 1\n }\n"
             " total = dobro(total)\n}", 2),
        )
        for nivel in (0, 8):
            for fonte, esperado in casos:
                with self.subTest(nivel=nivel, fonte=fonte):
                    codigo, dados, status = self.gerar(fonte, nivel)
                    self.assertEqual(codigo, 0)
                    self.assertIsNotNone(dados)
                    if status is not None:
                        self.assertEqual(status, esperado)

    def test_locais_tipados_invalidos_no_emissor_integrado(self):
        casos = (
            (2, "funcao f(n: inteiro) -> inteiro {\n retorne n\n}\n"
             "inicio {\n seja x: real = f(1)\n}"),
            (2, "funcao f(n: inteiro) -> inteiro {\n retorne n\n}\n"
             "inicio {\n seja x: bytes = f(1)\n}"),
            (3, "funcao f(n: inteiro) -> inteiro {\n retorne n\n}\n"
             "inicio {\n seja x: inteiro 1\n}"),
        )
        for nivel in (0, 8):
            for erro, fonte in casos:
                with self.subTest(nivel=nivel, erro=erro, fonte=fonte):
                    codigo, dados, status = self.gerar(fonte, nivel)
                    self.assertEqual(codigo, erro)
                    self.assertIsNone(dados)
                    self.assertIsNone(status)

    def test_rejeita_gramatica_nao_suportada_sem_gravar(self):
        ruins = (
            "",
            "inicio {\n seja a = 2\n}",
            "funcao f(a: inteiro) -> inteiro {\n retorne a\n}\ninicio {}",
            "funcao f(a: inteiro) -> inteiro {\n retorne a\n}\n"
            "inicio {\n seja x = f(1)\n enquanto x > 0 {\n x = x - 1\n}",
            "funcao f(a: inteiro) -> inteiro {\n retorne a\n}\n"
            "inicio {\n seja x = f(1)\n senao { x = 2 }\n}",
            "funcao f(a: inteiro) -> inteiro {\n retorne a\n}\n"
            "inicio {\n seja x = f(1)\n se x < 2 {\n x = f(1,)\n }\n}",
            "funcao f(a: inteiro) -> inteiro {\n retorne a\n}\n"
            "inicio {\n seja x = f(1)\n se x < 2 {\n x = g(1)\n }\n}",
            "funcao f(a: inteiro) -> inteiro {\n retorne a\n}\n"
            "inicio {\n seja x = f(1)\n x = f(x) + 2\n}",
            "funcao f(a: inteiro) -> inteiro {\n retorne a\n}\n"
            "inicio {\n seja x = f(1)\n escreva(x)\n}",
            "funcao f(a: inteiro) -> inteiro {\n retorne a\n}\n"
            "inicio {\n seja x = f(1)\n x = x ** 2\n}",
            "funcao f(a: inteiro) -> inteiro {\n retorne a\n}\n"
            "inicio {\n seja x = f(1)\n x = 1000000001\n}",
            "funcao f(a: inteiro) -> inteiro {\n seja b = a * 2\n retorne b\n}\n"
            "inicio {\n seja x = f(1)\n}",
        )
        for nivel in (0, 8):
            for fonte in ruins:
                with self.subTest(nivel=nivel, fonte=fonte):
                    codigo, dados, status = self.gerar(fonte, nivel)
                    self.assertNotEqual(codigo, 0)
                    self.assertIsNone(dados)
                    self.assertIsNone(status)


if __name__ == "__main__":
    unittest.main()
