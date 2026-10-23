"""Testes reais da biblioteca de fatias de bytes escrita na propria RS."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

from backend import compilar
from compilador.modulos import carregar_fontes
from compilador.parser import analisar_programa

FERRAMENTA = RAIZ / "exemplos" / "ferramentas" / "inspecionar_fatias_bytes_rs.rts"


def alvo_local():
    if sys.platform == "win32":
        return "windows"
    if sys.platform == "linux" and os.uname().machine == "x86_64":
        return "linux"
    raise unittest.SkipTest("Exige Windows ou Linux x86-64")


class TestesFatiasBytesRS(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.arquivos = tempfile.TemporaryDirectory(prefix="rs_fatias_bytes_")
        cls.alvo = alvo_local()
        programa = analisar_programa(carregar_fontes(FERRAMENTA).texto)
        cls.executaveis = {}
        for nivel in (0, 8):
            nome = f"fatias_bytes_{nivel}" + (".exe" if cls.alvo == "windows" else "")
            caminho = Path(cls.arquivos.name) / nome
            caminho.write_bytes(
                compilar(programa, cls.alvo, nivel=nivel, otimizar=nivel > 0)
            )
            if cls.alvo == "linux":
                caminho.chmod(0o700)
            cls.executaveis[nivel] = caminho

    @classmethod
    def tearDownClass(cls):
        if hasattr(cls, "arquivos"):
            cls.arquivos.cleanup()

    def executar(self, dados, nivel):
        with tempfile.TemporaryDirectory(prefix="rs_fatia_entrada_") as pasta:
            raiz = Path(pasta)
            (raiz / "dados.bin").write_bytes(dados)
            processo = subprocess.run(
                [str(self.executaveis[nivel])],
                cwd=raiz,
                timeout=20,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
            self.assertEqual(
                processo.returncode, 0, processo.stdout + processo.stderr
            )
            valores = [int(linha) for linha in processo.stdout.splitlines()]
            self.assertEqual(len(valores), 13, valores)
            return valores

    @staticmethod
    def esperado(dados, codigo_utf8=0, posicao_utf8=None):
        tamanho = len(dados)
        metade = tamanho // 2
        if posicao_utf8 is None:
            posicao_utf8 = tamanho
        return [
            tamanho,
            metade,
            tamanho - metade,
            int(dados[:metade] == dados[metade:]),
            1,   # subfatia fiel aos bytes da segunda metade
            1,   # recortar alem do fim
            1,   # inicio negativo
            1,   # subfatia alem do fim
            0 if dados else 2,   # primeiro byte
            dados[0] if dados else 0,
            2,   # leitura no indice == tamanho
            codigo_utf8,
            posicao_utf8,
        ]

    def test_fatias_binarias_zero_limites_e_textos_utf8(self):
        casos = (
            b"",
            b"\x00",
            b"\x00\x00",
            b"abab",
            b"abcdef",
            bytes(range(256)),
            ("Olá, mundo — ação 😃" * 3).encode("utf-8"),
            b"\x00\x7f\x01\x00\x7f\x01",
        )
        for nivel in (0, 8):
            for dados in casos:
                with self.subTest(nivel=nivel, dados=dados[:30]):
                    self.assertEqual(self.executar(dados, nivel), self.esperado(dados))

    def test_diagnosticos_utf8_estritos_com_offsets(self):
        casos = (
            (b"\x80", 1, 0),
            (b"\xc0\xaf", 1, 0),
            (b"\xf5\x80\x80\x80", 1, 0),
            (b"\xf0\x90\x80", 2, 0),
            (b"\xe2A\x80", 3, 0),
            (b"\xe0\x80\x80", 4, 0),
            (b"\xed\xa0\x80", 5, 0),
            (b"\xf4\x90\x80\x80", 6, 0),
            (b"texto\x00\xfffinal", 1, 6),
            ("ação".encode("utf-8") + b"\xe2\x82", 2, 6),
        )
        for nivel in (0, 8):
            for dados, codigo, posicao in casos:
                with self.subTest(nivel=nivel, dados=dados):
                    self.assertEqual(
                        self.executar(dados, nivel),
                        self.esperado(dados, codigo, posicao),
                    )


if __name__ == "__main__":
    unittest.main()
