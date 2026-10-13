"""Prova inicial do formato RSD com dois executaveis nativos independentes."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

from backend import compilar
from compilador.parser import analisar_programa
from compilador.modulos import carregar_fontes

GRAVADOR = RAIZ / "exemplos" / "dados_rs" / "prova_gravar.rts"
LEITOR = RAIZ / "exemplos" / "dados_rs" / "prova_ler.rts"


def plataforma():
    if sys.platform == "win32":
        return "windows"
    if sys.platform == "linux" and os.uname().machine == "x86_64":
        return "linux"
    raise unittest.SkipTest("Exige Windows ou Linux x86-64.")


class TestesDadosRSMiniatura(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.artefatos = tempfile.TemporaryDirectory(prefix="rs_dados_binarios_")
        cls.alvo = plataforma()
        cls.executaveis = []
        for caminho, nome in ((GRAVADOR, "gravador"), (LEITOR, "leitor")):
            programa = analisar_programa(carregar_fontes(caminho).texto)
            destino = Path(cls.artefatos.name) / (
                nome + (".exe" if cls.alvo == "windows" else "")
            )
            destino.write_bytes(
                compilar(programa, cls.alvo, nivel=0, otimizar=False)
            )
            if cls.alvo == "linux":
                destino.chmod(0o700)
            cls.executaveis.append(destino)
        with tempfile.TemporaryDirectory(prefix="rs_dados_original_") as pasta:
            gravacao = cls.rodar(cls.executaveis[0], pasta)
            if gravacao.returncode:
                raise AssertionError(gravacao.stdout + gravacao.stderr)
            cls.original = Path(pasta, "entregas.rsd").read_bytes()

    @classmethod
    def tearDownClass(cls):
        if hasattr(cls, "artefatos"):
            cls.artefatos.cleanup()

    @staticmethod
    def rodar(executavel, pasta):
        return subprocess.run(
            (str(executavel),), cwd=pasta,
            capture_output=True, text=True, encoding="utf-8",
            errors="replace", timeout=25,
        )

    def test_dois_executaveis_gravam_e_recuperam_100_registros(self):
        with tempfile.TemporaryDirectory(prefix="rs_dados_reinicio_") as pasta:
            gravador = self.rodar(self.executaveis[0], pasta)
            self.assertEqual(gravador.returncode, 0, gravador.stderr)
            self.assertEqual(gravador.stdout.strip().splitlines(), ["1616", "100"])
            leitor = self.rodar(self.executaveis[1], pasta)
            self.assertEqual(leitor.returncode, 0, leitor.stdout + leitor.stderr)
            self.assertEqual(leitor.stdout.strip().splitlines(), ["100", "50500"])

    def test_cabecalho_e_conteudo_little_endian(self):
        dados = self.original
        self.assertEqual(len(dados), 1616)
        self.assertEqual(dados[:4], b"RSDB")
        self.assertEqual(int.from_bytes(dados[4:8], "little"), 1)
        self.assertEqual(int.from_bytes(dados[8:16], "little"), 100)
        for indice in range(100):
            inicio = 16 + indice * 16
            codigo = int.from_bytes(dados[inicio:inicio + 8], "little")
            valor = int.from_bytes(dados[inicio + 8:inicio + 16], "little")
            self.assertEqual(codigo, indice + 1)
            self.assertEqual(valor, (indice + 1) * 10)

    def verificar_rejeicao(self, conteudo):
        with tempfile.TemporaryDirectory(prefix="rs_dados_corrompido_") as pasta:
            Path(pasta, "entregas.rsd").write_bytes(conteudo)
            resultado = self.rodar(self.executaveis[1], pasta)
            self.assertEqual(resultado.returncode, 3, resultado.stdout + resultado.stderr)
            self.assertIn("arquivo RSD invalido", resultado.stdout)

    def test_rejeita_tamanhos_incorretos(self):
        for tamanho in (0, 1, 7, 8, 15, 16, 1615):
            with self.subTest(tamanho=tamanho):
                self.verificar_rejeicao(self.original[:tamanho])
        self.verificar_rejeicao(self.original + b"\x00")

    def test_rejeita_cabecalho_contagem_e_registros_corrompidos(self):
        for deslocamento, valor in (
            (0, 0), (3, 0), (4, 2), (8, 99), (15, 128),
            (16, 9), (24, 27), (31, 128),
        ):
            with self.subTest(deslocamento=deslocamento):
                dados = bytearray(self.original)
                dados[deslocamento] = valor
                self.verificar_rejeicao(bytes(dados))


if __name__ == "__main__":
    unittest.main()
