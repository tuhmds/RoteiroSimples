"""Transferencia de registro proprietario inteiro e descarte seguro no backend."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))
from compilador.erros import ErroCompilacao
from compilador.parser import analisar_programa
from backend import compilar

EXEMPLO = RAIZ / "exemplos" / "aplicacoes" / "transferencia_registros_rs042e.rts"

FONTE_COMUM = """tipo Interno {
    nome: texto
}
tipo Caixa {
    interno: Interno
    conteudo: bytes
}
"""

class TestesTransferenciaRegistroRS042E(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if sys.platform == "win32":
            cls.alvo = "windows"
        elif sys.platform == "linux" and os.uname().machine == "x86_64":
            cls.alvo = "linux"
        else:
            raise unittest.SkipTest("Exige Windows ou Linux x86-64.")

    def executar(self, fonte, nivel=0):
        programa = analisar_programa(fonte)
        with tempfile.TemporaryDirectory(prefix="rs_movimento_registros_") as pasta:
            exe = Path(pasta) / ("prova.exe" if self.alvo == "windows" else "prova")
            exe.write_bytes(compilar(programa, self.alvo, nivel=nivel))
            if self.alvo == "linux":
                exe.chmod(0o700)
            return subprocess.run(
                (str(exe),), cwd=pasta, capture_output=True,
                text=True, encoding="utf-8", errors="replace", timeout=20,
            )

    def test_movimenta_agregados_aninhados_em_ambos_niveis(self):
        fonte = EXEMPLO.read_text(encoding="utf-8")
        for nivel in (0, 8):
            with self.subTest(nivel=nivel):
                r = self.executar(fonte, nivel)
                self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
                self.assertEqual(r.stdout.strip().splitlines(), [
                    "Origem RS", "65", "11", "42",
                    "Origem RS", "2", "42", "Origem RS", "65",
                ])

    def test_origem_ja_movida_nao_pode_ser_movida_novamente(self):
        fonte = FONTE_COMUM + """inicio {
    seja origem: Caixa
    seja destino: Caixa
    seja outro: Caixa
    copie(origem.interno.nome, "Vivo")
    mova(destino, origem)
    mova(outro, origem)
    escreva(100)
}"""
        r = self.executar(fonte)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("movimentacao ou liberacao", r.stdout + r.stderr,
                      f"Codigo de saida: {r.returncode}; saida: {r.stdout!r}; erro: {r.stderr!r}")

    def test_movimento_de_campo_composto_em_registro_mais_externo(self):
        fonte = FONTE_COMUM + """tipo Exterior {
    primeira: Caixa
    segunda: Caixa
}
inicio {
    seja conteiner: Exterior
    copie(conteiner.primeira.interno.nome, "Primeira")
    adicione_byte(conteiner.primeira.conteudo, 81)
    copie(conteiner.segunda.interno.nome, "Antiga")
    mova(conteiner.segunda, conteiner.primeira)
    escreva(conteiner.segunda.interno.nome)
    escreva(conteiner.segunda.conteudo[0])
}"""
        for nivel in (0, 8):
            with self.subTest(nivel=nivel):
                r = self.executar(fonte, nivel)
                self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
                self.assertEqual(r.stdout.strip().splitlines(), ["Primeira", "81"])

    def test_rejeita_movimento_incompativel_ou_copia(self):
        fontes = [
            FONTE_COMUM + """inicio {
    seja caixa: Caixa
    mova(caixa, caixa)
}""",
            FONTE_COMUM + """tipo Outra {
    nome: texto
}
inicio {
    seja caixa: Caixa
    seja outra: Outra
    mova(caixa, outra)
}""",
            FONTE_COMUM + """inicio {
    seja primeira: Caixa
    seja segunda: Caixa
    segunda = primeira
}""",
        ]
        for fonte in fontes:
            with self.subTest(fonte=fonte[-90:]), self.assertRaises(ErroCompilacao):
                analisar_programa(fonte)

if __name__ == "__main__":
    unittest.main()
