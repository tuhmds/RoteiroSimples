"""Leitura de assinaturas de funcoes escrita em RS, executada nativamente."""
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

EXEMPLO = RAIZ / "exemplos" / "ferramentas" / "assinaturas_compilador_rs.rts"


def alvo_nativo():
    if sys.platform == "win32":
        return "windows"
    if sys.platform == "linux" and os.uname().machine == "x86_64":
        return "linux"
    raise unittest.SkipTest("Exige Windows/Linux x86-64")


class TestesAssinaturasCompiladorRS(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pasta = tempfile.TemporaryDirectory(prefix="rs_assinaturas_")
        cls.alvo = alvo_nativo()
        programa = analisar_programa(carregar_fontes(EXEMPLO).texto)
        cls.executaveis = {}
        for nivel in (0, 8):
            for alvo in ("windows", "linux"):
                binario = compilar(programa, alvo, nivel=nivel, otimizar=nivel > 0)
                if alvo == cls.alvo:
                    arquivo = Path(cls.pasta.name) / ("assinaturas_" + str(nivel) + (".exe" if alvo == "windows" else ""))
                    arquivo.write_bytes(binario)
                    if alvo == "linux":
                        arquivo.chmod(0o700)
                    cls.executaveis[nivel] = arquivo

    @classmethod
    def tearDownClass(cls):
        if hasattr(cls, "pasta"):
            cls.pasta.cleanup()

    def verificar(self, fonte, nivel):
        with tempfile.TemporaryDirectory(prefix="rs_fonte_assinaturas_") as pasta:
            (Path(pasta) / "codigo_fonte.rts").write_text(fonte, encoding="utf-8")
            processo = subprocess.run(
                [str(self.executaveis[nivel])], cwd=pasta,
                capture_output=True, text=True, encoding="utf-8",
                errors="replace", timeout=20,
            )
            self.assertEqual(processo.returncode, 0, processo.stdout + processo.stderr)
            valores = [int(v) for v in processo.stdout.strip().splitlines()]
            self.assertGreaterEqual(len(valores), 4)
            funcoes = valores[2]
            parametros = valores[3]
            self.assertEqual(len(valores), 4 + 9 * funcoes + 3 * parametros)
            assinaturas = [tuple(valores[4 + 9*i:13 + 9*i]) for i in range(funcoes)]
            inicio = 4 + 9 * funcoes
            parametros_lidos = [
                tuple(valores[inicio + 3*i:inicio + 3*i + 3])
                for i in range(parametros)
            ]
            return valores[:2], assinaturas, parametros_lidos

    def test_funcao_com_parametros_e_tipo_composto(self):
        fonte = (
            "publico funcao soma(a: inteiro, b: lista[inteiro]) -> resultado[inteiro] {\n"
            "    retorne sucesso[inteiro](0)\n}\n"
            "inicio { escreva(1) }\n"
        )
        for nivel in (0, 8):
            (erro, _), assinaturas, parametros = self.verificar(fonte, nivel)
            self.assertEqual(erro, 0)
            self.assertEqual(len(assinaturas), 1)
            self.assertEqual(len(parametros), 2)
            self.assertEqual(assinaturas[0][8], 2)
            self.assertLess(assinaturas[0][3], assinaturas[0][4])
            self.assertLess(assinaturas[0][5], assinaturas[0][6])
            self.assertEqual(parametros[0][2] - parametros[0][1], 1)
            self.assertEqual(parametros[1][2] - parametros[1][1], 4)

    def test_duas_funcoes_e_textos_nao_geram_assinaturas_extras(self):
        fonte = (
            'funcao dobro(n: inteiro) -> inteiro { retorne n * 2 }\n'
            'funcao triplo(n: inteiro) -> inteiro { retorne n * 3 }\n'
            'inicio { escreva("funcao fantasma() -> inteiro") }'
        )
        for nivel in (0, 8):
            (erro, _), assinaturas, parametros = self.verificar(fonte, nivel)
            self.assertEqual((erro, len(assinaturas), len(parametros)), (0, 2, 2))
            self.assertEqual([a[7:] for a in assinaturas], [(0, 1), (1, 1)])

    def test_erros_recuperaveis(self):
        casos = (
            ("funcao (n: inteiro) -> inteiro {}", 2),
            ("funcao f(n inteiro) -> inteiro {}", 4),
            ("funcao f(n: inteiro,) -> inteiro {}", 4),
            ("funcao f() inteiro {}", 5),
            ("funcao f() -> {}", 6),
            ("funcao f() -> inteiro", 7),
            ("funcao f() -> inteiro {", 1),
            ("funcao f() -> inteiro }", 1),
        )
        for nivel in (0, 8):
            for fonte, esperado in casos:
                with self.subTest(nivel=nivel, fonte=fonte):
                    (erro, _), _, _ = self.verificar(fonte, nivel)
                    self.assertEqual(erro, esperado)

    def test_programa_sem_funcoes(self):
        for nivel in (0, 8):
            (erro, _), assinaturas, parametros = self.verificar(
                'inicio { seja texto: texto = "funcao"\n escreva(texto) }',
                nivel,
            )
            self.assertEqual((erro, assinaturas, parametros), (0, [], []))


if __name__ == "__main__":
    unittest.main()
