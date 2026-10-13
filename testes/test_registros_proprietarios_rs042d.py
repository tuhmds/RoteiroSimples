"""Registros locais com campos proprietarios, sem copia superficial insegura."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))
from compilador.parser import analisar_programa
from compilador.erros import ErroCompilacao
from backend import compilar

EXEMPLO = RAIZ / "exemplos" / "aplicacoes" / "registro_com_proprietarios_rs042d.rts"
CABECALHO = """tipo Documento {
    titulo: texto
    conteudo: bytes
    numeros: lista[inteiro]
}
"""

class TestesRegistroProprietarioRS042D(unittest.TestCase):
    def test_exemplo_nativo_com_campos_move_e_escopo(self):
        fonte = EXEMPLO.read_text(encoding="utf-8")
        programa = analisar_programa(fonte)
        self.assertEqual(programa.registros["Documento"][0][1], ('texto_dinamico', 'utf8'))
        for nivel in (0, 8):
            if sys.platform == "win32":
                alvo = "windows"
            elif sys.platform == "linux" and os.uname().machine == "x86_64":
                alvo = "linux"
            else:
                self.skipTest("Exige Windows/Linux x86-64")
            with self.subTest(nivel=nivel), tempfile.TemporaryDirectory(prefix="rs_dono_registro_") as pasta:
                exe = Path(pasta) / ("exemplo.exe" if alvo == "windows" else "exemplo")
                exe.write_bytes(compilar(programa, alvo, nivel=nivel))
                if alvo == "linux":
                    exe.chmod(0o700)
                r = subprocess.run([str(exe)], cwd=pasta, capture_output=True,
                                   text=True, encoding="utf-8", timeout=20)
                self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
                self.assertEqual(r.stdout.strip().splitlines(),
                                 ["Relatorio RS", "2", "65", "2", "30", "2", "90", "1", "2"])

    def test_rejeita_copias_indiretas_e_colecoes_sem_transferencia(self):
        entradas = [
            CABECALHO + """inicio {
  seja origem: Documento
  seja destino: Documento = origem
}""",
            CABECALHO + """inicio {
  seja origem: Documento
  seja destino: Documento
  destino = origem
}""",
            CABECALHO + """inicio {
  seja origem: Documento
  seja documentos: lista[Documento]
  adicione(documentos, origem)
}""",
            CABECALHO + """funcao usar(x: Documento) -> inteiro {
  retorne 1
}
inicio {
  seja documento: Documento
  escreva(usar(documento))
}""",
            CABECALHO + """funcao devolver() -> Documento {
  seja documento: Documento
  retorne documento
}
inicio {
  escreva(1)
}""",
            CABECALHO + """inicio {
  seja origem: Documento
  seja destino: Documento
  origem.titulo = destino.titulo
}""",
        ]
        for fonte in entradas:
            with self.subTest(fonte=fonte[:70]), self.assertRaises(ErroCompilacao):
                analisar_programa(fonte)

    def test_retorno_antecipado_e_descarte_de_campos_em_funcao(self):
        fonte = """tipo Caixa {
  texto_livre: texto
  conteudo: bytes
}
funcao verificar(escolha: inteiro) -> inteiro {
  seja caixa: Caixa
  copie(caixa.texto_livre, "abc")
  adicione_byte(caixa.conteudo, 90)
  se escolha == 1 {
    retorne tamanho(caixa.conteudo)
  }
  retorne caracteres(caixa.texto_livre)
}
inicio {
  escreva(verificar(1))
  escreva(verificar(0))
}"""
        programa = analisar_programa(fonte)
        if sys.platform == "win32":
            alvo = "windows"
        elif sys.platform == "linux" and os.uname().machine == "x86_64":
            alvo = "linux"
        else:
            self.skipTest("Exige Windows/Linux x86-64")
        with tempfile.TemporaryDirectory(prefix="rs_registro_retorno_") as pasta:
            exe = Path(pasta) / ("retorno.exe" if alvo == "windows" else "retorno")
            exe.write_bytes(compilar(programa, alvo, nivel=8))
            if alvo == "linux":
                exe.chmod(0o700)
            r = subprocess.run([str(exe)], cwd=pasta, capture_output=True,
                               text=True, encoding="utf-8", timeout=20)
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            self.assertEqual(r.stdout.strip().splitlines(), ["1", "3"])

    def test_registro_aninhado_preserva_descritor_do_campo(self):
        fonte = """tipo Interno {
  nome: texto
}
tipo Externo {
  interno: Interno
}
inicio {
  seja grupo: Externo
  copie(grupo.interno.nome, "Exemplo")
  escreva(grupo.interno.nome)
}"""
        programa = analisar_programa(fonte)
        if sys.platform == "win32":
            alvo = "windows"
        elif sys.platform == "linux" and os.uname().machine == "x86_64":
            alvo = "linux"
        else:
            self.skipTest("Exige Windows/Linux x86-64")
        with tempfile.TemporaryDirectory(prefix="rs_registro_aninhado_") as pasta:
            exe = Path(pasta) / ("aninhado.exe" if alvo == "windows" else "aninhado")
            exe.write_bytes(compilar(programa, alvo, nivel=8))
            if alvo == "linux":
                exe.chmod(0o700)
            r = subprocess.run([str(exe)], cwd=pasta, capture_output=True,
                               text=True, encoding="utf-8", timeout=20)
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            self.assertEqual(r.stdout.strip(), "Exemplo")

    def test_registro_simples_e_valor_copiavel(self):
        fonte = """tipo Pessoa {
  idade: inteiro
}
inicio {
  seja primeira: Pessoa
  primeira.idade = 20
  seja segunda: Pessoa = primeira
  escreva(segunda.idade)
}"""
        programa = analisar_programa(fonte)
        self.assertTrue(programa.instrucoes)

if __name__ == "__main__":
    unittest.main()
