"""Verifica a primeira biblioteca sintatica escrita na propria RS."""
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

FERRAMENTA = RAIZ / "exemplos" / "ferramentas" / "estrutura_compilador_rs.rts"


def alvo_nativo():
    if sys.platform == "win32":
        return "windows"
    if sys.platform == "linux" and os.uname().machine == "x86_64":
        return "linux"
    raise unittest.SkipTest("Requer Windows/Linux x86-64.")


class TestesEstruturaCompiladorRS(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pasta = tempfile.TemporaryDirectory(prefix="rs_estrutura_")
        cls.alvo = alvo_nativo()
        programa = analisar_programa(carregar_fontes(FERRAMENTA).texto)
        cls.binarios = {}
        for nivel in (0, 8):
            for alvo in ("linux", "windows"):
                imagem = compilar(programa, alvo, nivel=nivel, otimizar=nivel > 0)
                if alvo == cls.alvo:
                    caminho = Path(cls.pasta.name) / ("analisador_" + str(nivel) + (".exe" if alvo == "windows" else ""))
                    caminho.write_bytes(imagem)
                    if alvo == "linux":
                        caminho.chmod(0o700)
                    cls.binarios[nivel] = caminho

    @classmethod
    def tearDownClass(cls):
        if hasattr(cls, "pasta"):
            cls.pasta.cleanup()

    def analisar(self, texto, nivel):
        with tempfile.TemporaryDirectory(prefix="rs_entrada_") as pasta:
            Path(pasta, "entrada.rts").write_bytes(texto.encode("utf-8"))
            processo = subprocess.run(
                [str(self.binarios[nivel])], cwd=pasta, capture_output=True,
                text=True, encoding="utf-8", errors="replace", timeout=20,
            )
            self.assertEqual(processo.returncode, 0, processo.stdout + processo.stderr)
            valores = [int(x) for x in processo.stdout.strip().splitlines()]
            self.assertGreaterEqual(len(valores), 3)
            quantidade = valores[2]
            self.assertEqual(len(valores), 3 + 4 * quantidade)
            pares = [tuple(valores[3 + i * 4:7 + i * 4]) for i in range(quantidade)]
            return valores[0], valores[1], pares

    def test_aninhamento_produz_indices_e_profundidade(self):
        fonte = "inicio { escreva(1 + (2 * 3)) }"
        esperado = (0, 13, [(6, 10, 40, 2), (3, 11, 40, 1), (1, 12, 123, 0)])
        for nivel in (0, 8):
            self.assertEqual(self.analisar(fonte, nivel), esperado)

    def test_strings_e_comentarios_nao_viram_delimitadores(self):
        fonte = 'inicio { escreva("} ) ]") // } ) ]\n escreva(2) }'
        for nivel in (0, 8):
            erro, _, pares = self.analisar(fonte, nivel)
            self.assertEqual(erro, 0)
            self.assertEqual(len(pares), 3)
            self.assertEqual([p[2] for p in pares], [40, 40, 123])

    def test_erros_recuperaveis_com_indice_exato(self):
        casos = [
            ("inicio { escreva(1 }", 3, 5),
            ("inicio { escreva(1)) }", 2, 6),
            ("inicio { escreva(1)", 4, 1),
            ("inicio { escreva(@) }", 1, 4),
            (")", 2, 0),
        ]
        for nivel in (0, 8):
            for fonte, erro, indice in casos:
                with self.subTest(nivel=nivel, fonte=fonte):
                    resultado = self.analisar(fonte, nivel)
                    self.assertEqual(resultado[:2], (erro, indice))

    def test_profundidade_com_varios_blocos(self):
        fonte = "inicio { " + "se verdadeiro { " * 48 + "} " * 49
        for nivel in (0, 8):
            erro, _, pares = self.analisar(fonte, nivel)
            self.assertEqual(erro, 0)
            self.assertEqual(len(pares), 49)
            self.assertEqual(pares[0][3], 48)
            self.assertEqual(pares[-1][3], 0)

    def test_fonte_vazia(self):
        for nivel in (0, 8):
            self.assertEqual(self.analisar("", nivel), (0, 0, []))


if __name__ == "__main__":
    unittest.main()
