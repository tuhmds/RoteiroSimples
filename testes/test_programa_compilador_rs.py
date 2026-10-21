"""Testa AST integrada e resolucao lexical escritas em RoteiroSimples."""
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

EXEMPLO = RAIZ / "exemplos" / "ferramentas" / "programa_compilador_rs.rts"


def alvo_nativo():
    if sys.platform == "win32":
        return "windows"
    if sys.platform == "linux" and os.uname().machine == "x86_64":
        return "linux"
    raise unittest.SkipTest("Requer Windows/Linux x86-64")


class TestesProgramaCompiladorRS(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pasta = tempfile.TemporaryDirectory(prefix="rs_programa_compilador_")
        cls.alvo = alvo_nativo()
        programa = analisar_programa(carregar_fontes(EXEMPLO).texto)
        cls.executaveis = {}
        for nivel in (0, 8):
            for alvo in ("linux", "windows"):
                imagem = compilar(programa, alvo, nivel=nivel, otimizar=nivel > 0)
                if alvo == cls.alvo:
                    arquivo = Path(cls.pasta.name) / (
                        "programa_" + str(nivel) + (".exe" if alvo == "windows" else "")
                    )
                    arquivo.write_bytes(imagem)
                    if alvo == "linux":
                        arquivo.chmod(0o700)
                    cls.executaveis[nivel] = arquivo

    @classmethod
    def tearDownClass(cls):
        if hasattr(cls, "pasta"):
            cls.pasta.cleanup()

    def analisar(self, fonte, nivel):
        with tempfile.TemporaryDirectory(prefix="rs_fonte_programa_") as pasta:
            (Path(pasta) / "codigo_fonte.rts").write_text(fonte, encoding="utf-8")
            p = subprocess.run(
                [str(self.executaveis[nivel])], cwd=pasta, capture_output=True,
                text=True, encoding="utf-8", errors="replace", timeout=20,
            )
            self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
            numeros = [int(v) for v in p.stdout.strip().splitlines()]
            self.assertGreaterEqual(len(numeros), 5)
            erro, origem, ns, ni, nn = numeros[:5]
            self.assertEqual(len(numeros), 5 + 3 * ns + 4 * ni + 6 * nn)
            i = 5
            simbolos = [tuple(numeros[i+3*j:i+3*(j+1)]) for j in range(ns)]
            i += 3 * ns
            instrucoes = [tuple(numeros[i+4*j:i+4*(j+1)]) for j in range(ni)]
            i += 4 * ni
            nos = [tuple(numeros[i+6*j:i+6*(j+1)]) for j in range(nn)]
            return erro, origem, simbolos, instrucoes, nos

    def test_consolida_expressoes_e_resolve_referencias(self):
        fonte = "inicio {\n seja a = 10\n seja b = a + 2 * 3\n}"
        for nivel in (0, 8):
            erro, _, simbolos, instrucoes, nos = self.analisar(fonte, nivel)
            self.assertEqual(erro, 0)
            self.assertEqual([s[0] for s in simbolos], [1, 1])
            self.assertEqual(len(instrucoes), 2)
            self.assertEqual(len(nos), 6)
            self.assertEqual(nos[1][0], 2)
            self.assertEqual(nos[1][5], 0)
            self.assertEqual(instrucoes[1][3], 5)
            self.assertEqual(nos[5][3:5], (1, 4))
            self.assertEqual(nos[4][3:5], (2, 3))

    def test_sombreamento_e_volta_ao_escopo_externo(self):
        fonte = (
            "inicio {\n"
            " seja numero = 1\n"
            " se verdadeiro {\n"
            "  seja numero = 2\n"
            "  seja interno = numero + 3\n"
            " }\n"
            " seja externo = numero + 4\n"
            "}"
        )
        for nivel in (0, 8):
            erro, _, simbolos, instrucoes, nos = self.analisar(fonte, nivel)
            self.assertEqual(erro, 0)
            self.assertEqual(len(simbolos), 4)
            self.assertNotEqual(simbolos[0][2], simbolos[1][2])
            self.assertEqual(nos[instrucoes[2][3]][0], 4)
            self.assertEqual(nos[instrucoes[3][3]][0], 4)
            referencias = [no[5] for no in nos if no[0] == 2]
            self.assertEqual(referencias, [1, 0])

    def test_parametros_e_funcoes_em_escopos_distintos(self):
        fonte = (
            "funcao dobro(valor: inteiro) -> inteiro {\n"
            " seja novo = valor * 2\n"
            " retorne novo\n"
            "}\n"
            "inicio {\n seja entrada = 1\n}"
        )
        for nivel in (0, 8):
            erro, _, simbolos, instrucoes, nos = self.analisar(fonte, nivel)
            self.assertEqual(erro, 0)
            self.assertEqual([s[0] for s in simbolos], [2, 3, 1, 1])
            self.assertEqual(nos[0][0], 2)
            self.assertEqual(nos[0][5], 1)
            self.assertEqual(len(instrucoes), 2)

    def test_rejeita_simbolos_duplicados(self):
        casos = [
            ("inicio {\n seja a = 1\n seja a = 2\n}", 6),
            ("funcao f(a: inteiro, a: inteiro) -> inteiro { retorne a }", 5),
            ("funcao f() -> inteiro { retorne 1 }\nfuncao f() -> inteiro { retorne 2 }", 4),
            ("funcao f(a: inteiro) -> inteiro {\n seja a = 2\n retorne a\n}", 6),
        ]
        for nivel in (0, 8):
            for fonte, codigo in casos:
                with self.subTest(fonte=fonte, nivel=nivel):
                    erro, origem, _, _, _ = self.analisar(fonte, nivel)
                    self.assertEqual(erro, codigo)
                    self.assertGreaterEqual(origem, 0)

    def test_rejeita_referencia_futura_ou_fora_do_escopo(self):
        casos = (
            "inicio {\n seja a = b + 1\n seja b = 2\n}",
            "inicio {\n se verdadeiro {\n seja a = 1\n }\n seja b = a + 2\n}",
            "funcao f(a: inteiro) -> inteiro {\n seja b = a + 1\n retorne b\n}\n"
            "inicio {\n seja c = a + 1\n}",
        )
        for nivel in (0, 8):
            for fonte in casos:
                with self.subTest(fonte=fonte, nivel=nivel):
                    erro, origem, _, _, _ = self.analisar(fonte, nivel)
                    self.assertEqual(erro, 7)
                    self.assertGreaterEqual(origem, 0)

    def test_rejeita_tipo_ou_operador_nao_suportado(self):
        casos = [
            ("inicio {\n seja a: texto = \"oi\"\n}", 8),
            ("funcao f(a: texto) -> inteiro { retorne 1 }", 8),
            ("funcao f(a: inteiro) -> texto { retorne \"oi\" }", 8),
        ]
        for nivel in (0, 8):
            for fonte, codigo in casos:
                with self.subTest(fonte=fonte, nivel=nivel):
                    self.assertEqual(self.analisar(fonte, nivel)[0], codigo)
            erro, _, _, _, _ = self.analisar("inicio {\n seja a = 1 == 1\n}", nivel)
            self.assertEqual(erro, 27)

    def test_estrutura_invalida_e_fonte_vazia(self):
        for nivel in (0, 8):
            self.assertEqual(self.analisar("inicio {", nivel)[0], 1)
            self.assertEqual(self.analisar("", nivel)[0], 0)

    def test_declaracoes_aninhadas_nao_duplicam_escopo_pai(self):
        fonte = (
            "inicio {\n"
            " seja a = 1\n"
            " se verdadeiro {\n seja a = a + 2\n }\n"
            "}"
        )
        for nivel in (0, 8):
            erro, _, simbolos, _, nos = self.analisar(fonte, nivel)
            self.assertEqual(erro, 0)
            self.assertEqual(len(simbolos), 2)
            referencias = [no[5] for no in nos if no[0] == 2]
            self.assertEqual(referencias, [0])


if __name__ == "__main__":
    unittest.main()
