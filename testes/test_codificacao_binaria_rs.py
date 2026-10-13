"""Codificacao e leitura recuperaveis nas bibliotecas da propria RS."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))
from compilador.modulos import carregar_fontes
from compilador.parser import analisar_programa
from backend import compilar

PROVA = RAIZ / "exemplos" / "dados_rs" / "prova_codificacao_recuperavel.rts"

class TestesCodificacaoBinariaRS(unittest.TestCase):
    def test_erros_recuperaveis_e_limites_em_execucao_nativa(self):
        if sys.platform == "win32":
            alvo = "windows"
        elif sys.platform == "linux" and os.uname().machine == "x86_64":
            alvo = "linux"
        else:
            self.skipTest("Exige Windows/Linux x86-64")
        programa = analisar_programa(carregar_fontes(PROVA).texto)
        for nivel in (0, 8):
            with self.subTest(nivel=nivel), tempfile.TemporaryDirectory(prefix="rs_binarios_") as pasta:
                exe = Path(pasta) / ("codificacao.exe" if alvo == "windows" else "codificacao")
                exe.write_bytes(compilar(programa, alvo, nivel=nivel))
                if alvo == "linux":
                    exe.chmod(0o700)
                r = subprocess.run([str(exe)], cwd=pasta, capture_output=True,
                                   text=True, encoding="utf-8", timeout=15)
                self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
                self.assertEqual(r.stdout.strip().splitlines(), [
                    "1", "2", "1", "2", "1", "3", "4294967295", "9223372036854775807"
                ])

if __name__ == "__main__":
    unittest.main()
