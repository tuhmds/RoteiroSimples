"""Reconhecimento de declaracoes RS sem parser Python no programa compilado."""
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

EXEMPLO = RAIZ / "exemplos" / "ferramentas" / "declaracoes_compilador_rs.rts"


def alvo():
    if sys.platform == "win32":
        return "windows"
    if sys.platform == "linux" and os.uname().machine == "x86_64":
        return "linux"
    raise unittest.SkipTest("Exige Windows/Linux x86-64")


class TestesDeclaracoesCompiladorRS(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pasta = tempfile.TemporaryDirectory(prefix="rs_declaracoes_")
        cls.sistema = alvo()
        programa = analisar_programa(carregar_fontes(EXEMPLO).texto)
        cls.binarios = {}
        for nivel in (0, 8):
            for sistema in ("linux", "windows"):
                imagem = compilar(programa, sistema, nivel=nivel, otimizar=nivel > 0)
                if sistema == cls.sistema:
                    nome = Path(cls.pasta.name) / ("declaracoes_" + str(nivel) + (".exe" if sistema == "windows" else ""))
                    nome.write_bytes(imagem)
                    if sistema == "linux":
                        nome.chmod(0o700)
                    cls.binarios[nivel] = nome

    @classmethod
    def tearDownClass(cls):
        if hasattr(cls, "pasta"):
            cls.pasta.cleanup()

    def analisar(self, fonte, nivel):
        with tempfile.TemporaryDirectory(prefix="rs_fonte_declaracoes_") as pasta:
            (Path(pasta) / "codigo_fonte.rts").write_text(fonte, encoding="utf-8")
            p = subprocess.run(
                [str(self.binarios[nivel])], cwd=pasta, capture_output=True,
                text=True, encoding="utf-8", errors="replace", timeout=20,
            )
            self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
            dados = [int(n) for n in p.stdout.strip().splitlines()]
            self.assertGreaterEqual(len(dados), 3)
            self.assertEqual(len(dados), 3 + dados[2] * 5)
            itens = [tuple(dados[3+5*i:8+5*i]) for i in range(dados[2])]
            return dados[0], dados[1], itens

    def test_declaracoes_tipadas_inferidas_e_compostas(self):
        fonte = """inicio {
    seja numero = 12 + 3
    seja nome: texto = "RS"
    seja nomes: lista[texto]
    escreva(numero)
}"""
        for nivel in (0, 8):
            erro, _, itens = self.analisar(fonte, nivel)
            self.assertEqual(erro, 0)
            self.assertEqual(len(itens), 3)
            self.assertEqual(itens[0][1:3], (-1, -1))
            self.assertGreater(itens[0][4], itens[0][3])
            self.assertEqual(itens[1][2] - itens[1][1], 1)
            self.assertGreater(itens[1][4], itens[1][3])
            self.assertEqual(itens[2][2] - itens[2][1], 4)
            self.assertEqual(itens[2][3:], (-1, -1))

    def test_varias_declaracoes_em_uma_linha_e_aninhadas(self):
        fonte = 'funcao f() -> inteiro { seja a = 1; seja b = (2 + 3); retorne a + b }\ninicio { escreva("seja c = 4") }'
        for nivel in (0, 8):
            erro, _, itens = self.analisar(fonte, nivel)
            self.assertEqual((erro, len(itens)), (0, 2))

    def test_inicializador_multilinha_parentizado(self):
        fonte = 'inicio {\n seja conta = (1 +\n 2)\n escreva(conta)\n}'
        for nivel in (0, 8):
            erro, _, itens = self.analisar(fonte, nivel)
            self.assertEqual((erro, len(itens)), (0, 1))
            self.assertGreaterEqual(itens[0][4] - itens[0][3], 5)

    def test_erros_recuperaveis(self):
        casos = (
            ("seja", 2),
            ("inicio { seja 99 = 3 }", 2),
            ("inicio { seja valor: = 3 }", 3),
            ("inicio { seja valor = }", 4),
            ("inicio { seja valor }", 5),
            ("inicio { seja valor = 3", 1),
        )
        for nivel in (0, 8):
            for fonte, esperado in casos:
                with self.subTest(fonte=fonte, nivel=nivel):
                    erro, _, _ = self.analisar(fonte, nivel)
                    self.assertEqual(erro, esperado)

    def test_programa_sem_declaracoes(self):
        for nivel in (0, 8):
            self.assertEqual(self.analisar('inicio { escreva("seja") }', nivel)[::2], (0, []))


if __name__ == "__main__":
    unittest.main()
