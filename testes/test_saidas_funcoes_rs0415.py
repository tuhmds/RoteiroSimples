"""Diagnósticos fatais de tipos declarados somente dentro de funções RS."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))
from backend import compilar
from compilador.parser import analisar_programa

CASOS = (
    ("""funcao falhar() -> inteiro {
        seja linha: texto[2]
        copie(linha, "AB")
        junte(linha, "CD")
        retorne 0
    }
    inicio {
        escreva(falhar())
    }""", 'texto excede a capacidade'),
    ("""funcao falhar() -> inteiro {
        seja valores: lista[2]
        retorne valores[2]
    }
    inicio {
        escreva(falhar())
    }""", 'índice fora dos limites'),
)

class TestesSaidasFuncoesRS0415(unittest.TestCase):
    def test_tipos_exclusivos_da_funcao_compilam_nos_dois_alvos(self):
        for fonte, _ in CASOS:
            for alvo in ('windows', 'linux'):
                for nivel in (0, 4, 8):
                    with self.subTest(alvo=alvo, nivel=nivel, fonte=fonte):
                        imagem = compilar(analisar_programa(fonte), alvo,
                                          otimizar=nivel > 0, nivel=nivel)
                        self.assertTrue(imagem.startswith(
                            b'MZ' if alvo == 'windows' else b'\x7fELF'))

    def test_funcao_encerra_com_status_e_diagnostico_nativos(self):
        if sys.platform not in ('win32', 'linux') or (
                sys.platform == 'linux' and os.uname().machine != 'x86_64'):
            self.skipTest('Execução exige Windows ou Linux x86-64.')
        alvo = 'windows' if sys.platform == 'win32' else 'linux'
        with tempfile.TemporaryDirectory() as pasta:
            for indice, (fonte, mensagem) in enumerate(CASOS):
                for nivel in (0, 4, 8):
                    with self.subTest(caso=indice, nivel=nivel):
                        arquivo = Path(pasta) / (f'erro_{indice}_{nivel}' +
                                                ('.exe' if alvo == 'windows' else ''))
                        arquivo.write_bytes(compilar(analisar_programa(fonte), alvo,
                                                      otimizar=nivel > 0, nivel=nivel))
                        if alvo == 'linux':
                            arquivo.chmod(0o755)
                        resultado = subprocess.run([str(arquivo)], cwd=pasta,
                            capture_output=True, text=True, encoding='utf-8',
                            errors='replace', timeout=15)
                        self.assertEqual(resultado.returncode, 1, resultado.stderr)
                        self.assertIn(mensagem, resultado.stdout + resultado.stderr)

if __name__ == '__main__':
    unittest.main()
