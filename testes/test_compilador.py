import os
import struct
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))
from sintaxe import ErroCompilacao, analisar_programa
from codigo_nativo import compilar


class TestesRS(unittest.TestCase):
    def test_analisador_entende_prioridade_e_biblioteca(self):
        p = analisar_programa('inclua matematica\ninício {\n seja a = 3 + 4 * 2\n escreva(somar(a, 2))\n}')
        self.assertEqual(list(p.variaveis), ['a'])
        self.assertEqual(p.instrucoes[0][2], ('bin', '+', ('numero', 3), ('bin', '*', ('numero', 4), ('numero', 2))))

    def test_importacao_obrigatoria(self):
        with self.assertRaisesRegex(ErroCompilacao, 'inclua matematica'):
            analisar_programa('início {\n escreva(somar(1, 2))\n}')

    def test_variavel_inexistente(self):
        with self.assertRaisesRegex(ErroCompilacao, 'não foi declarada'):
            analisar_programa('início {\n escreva(valor)\n}')

    def test_sem_linguagem_estrangeira_ou_texto_desconhecido(self):
        with self.assertRaisesRegex(ErroCompilacao, 'Linha 2'):
            analisar_programa('início {\n print("Oi")\n}')

    def test_linha_e_comentario_em_string(self):
        p = analisar_programa('início {\n escreva("https://exemplo.br") // válido\n}')
        self.assertEqual(p.instrucoes, [('texto', 'https://exemplo.br\n')])

    def test_linux_executa_textos_e_matematica(self):
        if sys.platform != 'linux' or os.uname().machine != 'x86_64':
            self.skipTest('Execução nativa requer Linux x86-64')
        fonte = '''inclua matematica
início {
  seja a = 2
  seja b = 7
  escreva("Olá, RS!")
  escreva(somar(a, b))
  escreva(subtrair(a, b))
  escreva(multiplicar(a, b))
  escreva(dividir(-17, 5))
  escreva(resto(-17, 5))
  escreva(1 + 2 * (3 + 4))
  a = -42
  escreva(a)
  escreva(0)
  escreva(-9223372036854775808)
}'''
        executado = self.executar_linux(fonte)
        self.assertEqual(executado.returncode, 0)
        self.assertEqual(executado.stdout, 'Olá, RS!\n9\n-5\n14\n-3\n-2\n15\n-42\n0\n-9223372036854775808\n')

    def test_linux_divisao_por_zero(self):
        if sys.platform != 'linux' or os.uname().machine != 'x86_64':
            self.skipTest('Execução nativa requer Linux x86-64')
        programa = 'inclua matematica\ninício {\n seja x = 0\n escreva(dividir(10, x))\n}'
        r = self.executar_linux(programa)
        self.assertEqual(r.returncode, 1)
        self.assertIn('divisão por zero', r.stderr)

    def test_linux_estouro_divisao(self):
        if sys.platform != 'linux' or os.uname().machine != 'x86_64':
            self.skipTest('Execução nativa requer Linux x86-64')
        programa = 'início {\n escreva(-9223372036854775808 / -1)\n}'
        r = self.executar_linux(programa)
        self.assertEqual(r.returncode, 1)
        self.assertIn('fora do limite', r.stderr)

    def test_comparacoes_precedencia_e_decisoes(self):
        fonte = """início {
            seja a = 4
            seja b = 7
            se a + 3 == b {
                escreva("igual")
            } senão {
                escreva("diferente")
            }
        }"""
        programa = analisar_programa(fonte)
        self.assertEqual(programa.instrucoes[2][0], 'se')
        self.assertEqual(programa.instrucoes[2][1][0], 'comparacao')

    def test_variavel_local_no_bloco_rejeitada(self):
        fonte = 'início {\n se 1 == 1 {\n seja x = 1\n }\n}'
        with self.assertRaisesRegex(ErroCompilacao, 'declare variáveis antes'):
            analisar_programa(fonte)

    def test_linux_decisoes_e_comparacoes(self):
        if sys.platform != 'linux' or os.uname().machine != 'x86_64':
            self.skipTest('Requer Linux x86-64')
        fonte = """início {
            seja x = 17
            seja y = 18
            se x >= y {
                escreva("adulto")
            } senão {
                escreva("menor")
            }
            se (3 + 4 * 2) == 11 {
                escreva("onze")
            }
            se x < y {
                se y != 0 {
                    escreva(1)
                }
            }
            escreva(x >= y)
            escreva(x <= y)
            escreva(x > y)
            escreva(x == y)
            escreva(x != y)
        }"""
        r = self.executar_linux(fonte)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout, 'menor\nonze\n1\n0\n1\n0\n0\n1\n')

    def test_parser_lacos_aninhados(self):
        fonte = """início {
            seja i = 0
            enquanto i < 3 {
                i = i + 1
                se i == 2 {
                    continue
                }
                se i == 3 {
                    pare
                }
            }
        }"""
        programa = analisar_programa(fonte)
        self.assertEqual(programa.instrucoes[1][0], 'enquanto')
        self.assertEqual(programa.instrucoes[1][2][1][2][0], ('continue',))

    def test_pare_e_continue_fora_do_laco_rejeitados(self):
        for palavra in ('pare', 'continue'):
            with self.subTest(palavra=palavra):
                fonte = f'início {{\n {palavra}\n}}'
                with self.assertRaisesRegex(ErroCompilacao, 'só pode ser usado'):
                    analisar_programa(fonte)
                fonte_condicional = f'início {{\n se 1 {{\n {palavra}\n }}\n}}'
                with self.assertRaisesRegex(ErroCompilacao, 'só pode ser usado'):
                    analisar_programa(fonte_condicional)

    def test_variavel_no_laco_rejeitada(self):
        fonte = 'início {\n enquanto 1 {\n seja numero = 5\n }\n}'
        with self.assertRaisesRegex(ErroCompilacao, 'declare variáveis antes'):
            analisar_programa(fonte)

    def test_linux_repeticao_continue_e_pare(self):
        if sys.platform != 'linux' or os.uname().machine != 'x86_64':
            self.skipTest('Requer Linux x86-64')
        fonte = """início {
            seja contador = 0
            seja soma = 0
            enquanto contador < 7 {
                contador = contador + 1
                se contador == 3 {
                    continue
                }
                se contador == 6 {
                    pare
                }
                soma = soma + contador
            }
            escreva(soma)
            escreva(contador)
            enquanto 0 {
                escreva("não deve aparecer")
            }
        }"""
        r = self.executar_linux(fonte)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout, '12\n6\n')

    def test_linux_lacos_aninhados(self):
        if sys.platform != 'linux' or os.uname().machine != 'x86_64':
            self.skipTest('Requer Linux x86-64')
        fonte = """início {
            seja i = 0
            seja j = 0
            seja total = 0
            enquanto i < 3 {
                j = 0
                enquanto j < 4 {
                    j = j + 1
                    se j == 2 {
                        continue
                    }
                    se j == 4 {
                        pare
                    }
                    total = total + 1
                }
                i = i + 1
            }
            escreva(total)
        }"""
        r = self.executar_linux(fonte)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout, '6\n')

    def test_windows_lacos_quando_disponivel(self):
        if sys.platform != 'win32':
            self.skipTest('Requer Windows real')
        fonte = """início {
            seja i = 0
            seja total = 0
            enquanto i < 5 {
                i = i + 1
                se i == 2 {
                    continue
                }
                total = total + i
                se i == 4 {
                    pare
                }
            }
            escreva(total)
        }"""
        with tempfile.TemporaryDirectory() as d:
            exe = Path(d) / 'lacos.exe'
            exe.write_bytes(compilar(analisar_programa(fonte), 'windows'))
            r = subprocess.run([str(exe)], capture_output=True, encoding='utf-8', timeout=5)
            self.assertEqual(r.returncode, 0)
            self.assertEqual(r.stdout, '8\n')

    def test_windows_pe_e_contem_importacoes(self):
        p = analisar_programa('inclua matematica\ninício {\n escreva(dividir(20, 4))\n}')
        exe = compilar(p, 'windows')
        self.assertEqual(exe[:2], b'MZ')
        pos = struct.unpack_from('<I', exe, 0x3c)[0]
        self.assertEqual(exe[pos:pos+4], b'PE\0\0')
        self.assertEqual(struct.unpack_from('<H', exe, pos+4)[0], 0x8664)
        for nome in [b'KERNEL32.dll', b'WriteFile', b'ExitProcess', b'GetStdHandle']:
            self.assertIn(nome, exe)

    def test_windows_decisoes_quando_disponivel(self):
        if sys.platform != 'win32':
            self.skipTest('Requer Windows real')
        fonte = """início {
            seja idade = 17
            seja limite = 18
            se idade >= limite {
                escreva("adulto")
            } senão {
                escreva("menor")
            }
            escreva(idade < limite)
        }"""
        with tempfile.TemporaryDirectory() as d:
            exe = Path(d) / 'decisoes.exe'
            exe.write_bytes(compilar(analisar_programa(fonte), 'windows'))
            r = subprocess.run([str(exe)], capture_output=True, encoding='utf-8', timeout=5)
            self.assertEqual(r.returncode, 0)
            self.assertEqual(r.stdout, 'menor\n1\n')

    def test_windows_execucao_quando_disponivel(self):
        if sys.platform != 'win32':
            self.skipTest('Requer Windows real')
        fonte = 'inclua matematica\ninício {\n escreva(multiplicar(7, 6))\n}'
        with tempfile.TemporaryDirectory() as d:
            exe = Path(d) / 'teste.exe'
            exe.write_bytes(compilar(analisar_programa(fonte), 'windows'))
            r = subprocess.run([str(exe)], capture_output=True, encoding='utf-8', timeout=5)
            self.assertEqual(r.returncode, 0)
            self.assertEqual(r.stdout, '42\n')

    @staticmethod
    def executar_linux(fonte):
        with tempfile.TemporaryDirectory() as d:
            programa = Path(d) / 'teste'
            programa.write_bytes(compilar(analisar_programa(fonte), 'linux'))
            programa.chmod(0o755)
            return subprocess.run([str(programa)], capture_output=True, encoding='utf-8', timeout=5)


if __name__ == '__main__':
    unittest.main()
