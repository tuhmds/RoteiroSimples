"""Testes do analisador de expressoes implementado na propria RS."""
import os
from pathlib import Path
import random
import subprocess
import sys
import tempfile
import unittest

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))
from backend import compilar
from compilador.modulos import carregar_fontes
from compilador.parser import analisar_programa

EXEMPLO = RAIZ / "exemplos" / "ferramentas" / "expressao_compilador_rs.rts"


def alvo_nativo():
    if sys.platform == "win32":
        return "windows"
    if sys.platform == "linux" and os.uname().machine == "x86_64":
        return "linux"
    raise unittest.SkipTest("Exige Windows ou Linux x86-64.")


class TestesExpressoesCompiladorRS(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pasta = tempfile.TemporaryDirectory(prefix="rs_ast_expressao_")
        cls.alvo = alvo_nativo()
        programa = analisar_programa(carregar_fontes(EXEMPLO).texto)
        cls.binarios = {}
        for nivel in (0, 8):
            for alvo in ("linux", "windows"):
                imagem = compilar(programa, alvo, nivel=nivel, otimizar=nivel > 0)
                if alvo == cls.alvo:
                    arquivo = Path(cls.pasta.name) / ("expressoes" + str(nivel) + (".exe" if alvo == "windows" else ""))
                    arquivo.write_bytes(imagem)
                    if alvo == "linux":
                        arquivo.chmod(0o700)
                    cls.binarios[nivel] = arquivo

    @classmethod
    def tearDownClass(cls):
        if hasattr(cls, "pasta"):
            cls.pasta.cleanup()

    def analisar(self, fonte, nivel):
        with tempfile.TemporaryDirectory(prefix="rs_ast_fonte_") as pasta:
            (Path(pasta) / "expressao.rts").write_text(fonte, encoding="utf-8")
            proc = subprocess.run(
                [str(self.binarios[nivel])], cwd=pasta,
                capture_output=True, text=True, encoding="utf-8",
                errors="replace", timeout=20,
            )
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            valores = [int(v) for v in proc.stdout.strip().splitlines()]
            self.assertGreaterEqual(len(valores), 4)
            quantidade = valores[3]
            self.assertEqual(len(valores), 4 + 5 * quantidade)
            nos = [tuple(valores[4+5*i:9+5*i]) for i in range(quantidade)]
            return valores[0], valores[1], valores[2], nos

    def test_precedencia_e_associatividade(self):
        for nivel in (0, 8):
            codigo, _, raiz, nos = self.analisar("2 + 3 * 4", nivel)
            self.assertEqual(codigo, 0)
            self.assertEqual((raiz, len(nos)), (4, 5))
            self.assertEqual(nos[3], (4, 3, 42, 1, 2))
            self.assertEqual(nos[4], (4, 1, 43, 0, 3))
            codigo, _, raiz, nos = self.analisar("9 - 2 - 3", nivel)
            self.assertEqual(codigo, 0)
            self.assertEqual(nos[raiz][2:], (45, 2, 3))

    def test_unarios_parenteses_e_identificadores(self):
        for nivel in (0, 8):
            codigo, _, raiz, nos = self.analisar("-nome + (2 * 3)", nivel)
            self.assertEqual(codigo, 0)
            self.assertEqual(len(nos), 6)
            self.assertEqual(nos[1], (3, 0, 300, -1, 0))
            self.assertEqual(nos[raiz], (4, 2, 43, 1, 4))
            codigo, _, raiz, nos = self.analisar("--4", nivel)
            self.assertEqual((codigo, raiz), (0, 2))
            self.assertEqual(nos[1][2:], (300, -1, 0))
            self.assertEqual(nos[2][2:], (300, -1, 1))

    def test_erros_sem_encerramento(self):
        casos = {
            "": (2, 0),
            "1 +": (3, 2),
            "1 * / 2": (3, 2),
            "1 2": (4, 1),
            "1 + (2": (5, 2),
            "1)": (6, 1),
            "()": (3, 1),
            "@ +": (7, 0),
            "1 == 2": (7, 1),
        }
        for nivel in (0, 8):
            for fonte, esperado in casos.items():
                with self.subTest(nivel=nivel, fonte=fonte):
                    erro, unidade, raiz, _ = self.analisar(fonte, nivel)
                    self.assertEqual((erro, unidade, raiz), (*esperado, -1))

    def test_aninhamento_e_operadores_consecutivos(self):
        for nivel in (0, 8):
            codigo, _, raiz, nos = self.analisar("(" * 64 + "1" + ")" * 64, nivel)
            self.assertEqual((codigo, raiz, len(nos)), (0, 0, 1))
            codigo, _, raiz, nos = self.analisar("1 + -2 * +3", nivel)
            self.assertEqual(codigo, 0)
            self.assertEqual(nos[raiz][2], 43)

    def test_arvores_geradas_com_oraculo_independente(self):
        gerador = random.Random(42043)
        def construir(profundidade):
            if profundidade == 0:
                return str(gerador.randint(0, 10))
            esq = construir(profundidade - 1)
            dir = construir(profundidade - 1)
            return "(" + esq + gerador.choice(("+", "-", "*")) + dir + ")"
        for _ in range(12):
            fonte = construir(3)
            esperado = eval(fonte, {"__builtins__": {}}, {})
            for nivel in (0, 8):
                codigo, _, raiz, nos = self.analisar(fonte, nivel)
                self.assertEqual(codigo, 0)
                def avaliar(indice):
                    categoria, unidade, operador, esq, dir = nos[indice]
                    if categoria == 1:
                        return int(fonte.split()[0]) if len(nos) == 1 else None
                    return categoria, operador, esq, dir
                self.assertEqual(nos[raiz][0], 4)
                self.assertEqual(len(nos), 15)
                self.assertIsInstance(esperado, int)


if __name__ == "__main__":
    unittest.main()
