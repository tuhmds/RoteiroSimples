"""Testes nativos do comando para da RS 0.5, em Windows e Linux."""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))
from sintaxe import analisar_programa, ErroCompilacao
from codigo_nativo import compilar


class TestesPara(unittest.TestCase):
    def executar_e_verificar(self, fonte, esperado):
        alvo = 'windows' if sys.platform == 'win32' else 'linux'
        if alvo == 'linux' and (sys.platform != 'linux' or os.uname().machine != 'x86_64'):
            self.skipTest('Requer processador x86-64')
        with tempfile.TemporaryDirectory() as pasta:
            arquivo = Path(pasta) / ('teste.exe' if alvo == 'windows' else 'teste')
            arquivo.write_bytes(compilar(analisar_programa(fonte), alvo))
            if alvo == 'linux':
                arquivo.chmod(0o755)
            resultado = subprocess.run([str(arquivo)], capture_output=True, encoding='utf-8', timeout=5)
        self.assertEqual(resultado.returncode, 0, resultado.stderr)
        self.assertEqual(resultado.stdout, esperado)

    def test_crescente_e_decrescente(self):
        self.executar_e_verificar("""inicio {
            para i de 1 ate 5 {
                escreva(i)
            }
            para j de 5 ate 1 passo -2 {
                escreva(j)
            }
        }""", "1\n2\n3\n4\n5\n5\n3\n1\n")

    def test_limites_inclusivos_e_zero_iteracoes(self):
        self.executar_e_verificar("""inicio {
            para i de 5 ate 1 {
                escreva(999)
            }
            para j de 1 ate 5 passo -1 {
                escreva(999)
            }
            para k de 4 ate 4 {
                escreva(k)
            }
        }""", "4\n")

    def test_continue_pare_e_aninhamento(self):
        self.executar_e_verificar("""inicio {
            seja soma = 0
            para i de 1 ate 5 {
                se i == 2 {
                    continue
                }
                se i == 5 {
                    pare
                }
                para j de 1 ate 3 {
                    se j == 2 {
                        continue
                    }
                    soma = soma + 1
                }
            }
            escreva(soma)
        }""", "6\n")

    def test_limite_reavaliado(self):
        self.executar_e_verificar("""inicio {
            seja limite = 5
            para i de 1 ate limite {
                escreva(i)
                limite = limite - 1
            }
        }""", "1\n2\n3\n")

    def test_limites_de_64_bits_sem_volta(self):
        self.executar_e_verificar("""inicio {
            para i de 9223372036854775806 ate 9223372036854775807 {
                escreva(i)
            }
            para j de -9223372036854775807 ate -9223372036854775808 passo -1 {
                escreva(j)
            }
        }""", "9223372036854775806\n9223372036854775807\n-9223372036854775807\n-9223372036854775808\n")

    def test_passo_invalido(self):
        for passo in ('0', '-0', 'i', '1+1', '9223372036854775808'):
            with self.subTest(passo=passo):
                fonte = 'inicio {\n para i de 1 ate 5 passo ' + passo + ' {\n escreva(i)\n }\n}'
                with self.assertRaisesRegex(ErroCompilacao, 'passo'):
                    analisar_programa(fonte)

    def test_contador_disponivel_apos_laco(self):
        self.executar_e_verificar('inicio {\n para n de 1 ate 2 {\n escreva(n)\n }\n escreva(n)\n}', '1\n2\n3\n')

    def test_palavras_sem_acentos(self):
        with self.assertRaisesRegex(ErroCompilacao, 'sem acentos'):
            analisar_programa('inicio {\n para índice de 1 ate 2 {\n escreva(1)\n }\n}')


if __name__ == '__main__':
    unittest.main()
