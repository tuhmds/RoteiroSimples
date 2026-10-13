"""Verifica o primeiro analisador lexico escrito na propria RS.

As comparacoes usam o lexer historico Python como referencia para o
subconjunto valido coberto neste marco. Nao declara paridade universal.
"""
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

from backend import compilar
from compilador.lexico import tokens
from compilador.modulos import carregar_fontes
from compilador.parser import analisar_programa


PROGRAMA = RAIZ / "exemplos" / "ferramentas" / "analisador_lexico_rs042c.rts"


def plataforma():
    if sys.platform == "win32":
        return "windows"
    if sys.platform == "linux" and os.uname().machine == "x86_64":
        return "linux"
    raise unittest.SkipTest("Exige Windows ou Linux em x86-64.")


def referencia(fonte):
    """Extrai classes, fatias em bytes e posicoes usando o lexer Python existente."""
    saida = []
    inicio_linha = 0
    for numero, linha_original in enumerate(fonte.splitlines(keepends=True), 1):
        linha = linha_original.rstrip("\r\n")
        for unidade in tokens(linha, numero):
            valor = str(unidade)
            coluna = unidade.origem.coluna
            inicio = inicio_linha + len(linha[:coluna - 1].encode("utf-8"))
            comprimento = len(valor.encode("utf-8"))
            if valor.startswith('"'):
                classe = 3
            elif valor in ("==", "!=", "<=", ">="):
                classe = 5
            elif valor.isascii() and valor.isdecimal():
                classe = 2
            elif re.fullmatch(r"[A-Za-z_][A-Za-z_0-9]*", valor):
                classe = 1
            else:
                classe = 4
            saida.append((classe, inicio, comprimento, numero, coluna))
        inicio_linha += len(linha_original.encode("utf-8"))
    return saida


class TestesLexicoEmRS(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pasta = tempfile.TemporaryDirectory(prefix="rs_lexico_inicial_")
        cls.alvo = plataforma()
        programa = analisar_programa(carregar_fontes(PROGRAMA).texto)
        cls.executavel = Path(cls.pasta.name) / (
            "analisador.exe" if cls.alvo == "windows" else "analisador"
        )
        cls.executavel.write_bytes(compilar(programa, cls.alvo, nivel=0, otimizar=False))
        if cls.alvo == "linux":
            cls.executavel.chmod(0o700)

    @classmethod
    def tearDownClass(cls):
        if hasattr(cls, "pasta"):
            cls.pasta.cleanup()

    def executar(self, fonte):
        # A ferramenta RS 0.42C inicial ainda nao recebe argumentos do processo.
        with tempfile.TemporaryDirectory(prefix="rs_lexico_arquivo_") as pasta:
            Path(pasta, "codigo_fonte.rts").write_bytes(fonte.encode("utf-8"))
            return subprocess.run(
                (str(self.executavel),), cwd=pasta,
                capture_output=True, text=True, encoding="utf-8",
                errors="replace", timeout=20,
            )

    def comparar(self, fonte):
        proc = self.executar(fonte)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        numeros = [int(v) for v in proc.stdout.strip().splitlines()]
        self.assertTrue(numeros, "A saida deveria conter a contagem.")
        quantidade = numeros[0]
        self.assertEqual(len(numeros) - 1, quantidade * 5)
        obtidos = [
            tuple(numeros[1 + 5 * i: 1 + 5 * (i + 1)])
            for i in range(quantidade)
        ]
        self.assertEqual(obtidos, referencia(fonte))
        # Verificacao independente dos offsets: nenhuma fatia sai da entrada.
        for classe, inicio, comprimento, linha, coluna in obtidos:
            self.assertGreaterEqual(inicio, 0)
            self.assertGreater(comprimento, 0)
            self.assertLessEqual(inicio + comprimento, len(fonte.encode("utf-8")))
            self.assertGreaterEqual(linha, 1)
            self.assertGreaterEqual(coluna, 1)

    def test_programa_completo(self):
        self.comparar(
            'tipo Pessoa {\n'
            '    idade: inteiro\n'
            '}\n'
            'funcao dobro(n: inteiro) -> inteiro {\n'
            '    retorne n * 2\n'
            '}\n'
            'inicio {\n'
            '    seja x = 5\n'
            '    se x >= 2 {\n'
            '        escreva(dobro(x))\n'
            '    }\n'
            '}\n'
        )

    def test_texto_utf8_com_escapes_e_comentarios(self):
        self.comparar(
            '// somente comentario\n'
            'inicio {\n'
            '    escreva("ação 😀 // nao e comentario") // comentario\n'
            '    escreva("aspas: \\" e barra: \\\\")\n'
            '    escreva("e\\tuma tabulacao")\n'
            '}\n'
        )

    def test_operadores_espacos_e_crlf(self):
        self.comparar(
            "inicio {\r\n"
            "\tse 10==10 {\r\n"
            "\t\tse 7!=8 {\r\n"
            "\t\t\tescreva(1<=2)\r\n"
            "\t\t}\r\n"
            "\t}\r\n"
            "}\r\n"
        )

    def test_fonte_vazia(self):
        self.comparar("")

    def test_caractere_invalido(self):
        for fonte in ("inicio { @ }\n", "inicio { seja ação = 3 }\n"):
            with self.subTest(fonte=fonte):
                processo = self.executar(fonte)
                self.assertEqual(processo.returncode, 2)
                self.assertIn("Erro lexico", processo.stdout)

    def test_texto_sem_fechamento(self):
        processo = self.executar('inicio {\n escreva("texto incompleto\n}\n')
        self.assertEqual(processo.returncode, 2)
        self.assertIn("aspas de fechamento", processo.stdout)


if __name__ == "__main__":
    unittest.main()
