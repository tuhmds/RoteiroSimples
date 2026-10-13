"""Testa a biblioteca lexico RS como modulo reutilizavel e recuperavel."""
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

PROVA = RAIZ / "exemplos" / "ferramentas" / "prova_lexico_recuperavel.rts"

class TestesBibliotecaLexicoRS(unittest.TestCase):
    def test_erro_e_documento_valido_mesmo_processo(self):
        if sys.platform == "win32":
            alvo = "windows"
        elif sys.platform == "linux" and os.uname().machine == "x86_64":
            alvo = "linux"
        else:
            self.skipTest("Exige x86-64 Linux ou Windows")
        programa = analisar_programa(carregar_fontes(PROVA).texto)
        with tempfile.TemporaryDirectory(prefix="rs_lexico_recuperacao_") as pasta:
            exe = Path(pasta) / ("prova.exe" if alvo == "windows" else "prova")
            exe.write_bytes(compilar(programa, alvo, nivel=0, otimizar=False))
            if alvo == "linux":
                exe.chmod(0o700)
            execucao = subprocess.run([str(exe)], cwd=pasta, capture_output=True,
                                      text=True, encoding="utf-8", timeout=15)
        self.assertEqual(execucao.returncode, 0, execucao.stdout + execucao.stderr)
        # Erro -1 na coluna 2; arquivo valido nao tem erro e tem quatro tokens.
        self.assertEqual(execucao.stdout.strip().splitlines(), ["-1", "1", "2", "1", "-1", "1", "1", "2", "-1", "4", "0"])

if __name__ == "__main__":
    unittest.main()
