"""RS 0.32: listas dinâmicas com propriedade única, memória nativa e tempo de vida."""
from pathlib import Path
import os
import subprocess
import sys
import tempfile
import unittest

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))
from compilador.parser import analisar_programa
from compilador.erros import ErroCompilacao


def executar(codigo, entrada=None):
    if sys.platform not in ('win32', 'linux') or (
            sys.platform == 'linux' and os.uname().machine != 'x86_64'):
        raise unittest.SkipTest('Requer Windows/Linux x86-64.')
    with tempfile.TemporaryDirectory() as pasta:
        fonte = Path(pasta) / 'principal.rts'
        fonte.write_text(codigo, encoding='utf-8')
        alvo = 'windows' if sys.platform == 'win32' else 'linux'
        saida = Path(pasta) / ('programa.exe' if alvo == 'windows' else 'programa')
        proc = subprocess.run(
            [sys.executable, str(RAIZ/'compilar.py'), str(fonte),
             '--alvo', alvo, '-O', '8', '-o', str(saida)],
            capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=30)
        if proc.returncode:
            raise AssertionError(proc.stderr + proc.stdout)
        return subprocess.run([str(saida)], input=entrada, capture_output=True,
                              text=True, encoding='utf-8', errors='replace', timeout=15)


class TestesListasDinamicas(unittest.TestCase):
    def test_crescimento_automatico_e_valores(self):
        fonte = """inicio {
            seja valores: lista[]
            escreva(tamanho(valores))
            escreva(capacidade(valores))
            para i de 0 ate 999 {
                adicione(valores, i * 2)
            }
            escreva(tamanho(valores))
            escreva(valores[0])
            escreva(valores[99])
            escreva(valores[999])
            valores[99] = -15
            escreva(valores[99])
            escreva(capacidade(valores))
        }"""
        resultado = executar(fonte)
        self.assertEqual(resultado.returncode, 0, resultado.stderr + resultado.stdout)
        linhas = resultado.stdout.splitlines()
        self.assertEqual(linhas[:6], ['0','0','1000','0','198','1998'])
        self.assertEqual(linhas[6], '-15')
        self.assertGreaterEqual(int(linhas[7]), 1000)

    def test_remocao_limpeza_e_reuso(self):
        fonte = """inicio {
            seja dados: lista[]
            adicione(dados, 10)
            adicione(dados, 20)
            remova_ultimo(dados)
            escreva(tamanho(dados))
            escreva(dados[0])
            limpe_lista(dados)
            escreva(tamanho(dados))
            adicione(dados, 99)
            escreva(dados[0])
        }"""
        resultado=executar(fonte)
        self.assertEqual((resultado.returncode, resultado.stdout),(0,'1\n10\n0\n99\n'))

    def test_propriedade_em_funcoes_e_reentrancia(self):
        fonte = """funcao somar(n: inteiro) -> inteiro {
            seja valores: lista[]
            seja total = 0
            para i de 0 ate 100 {
                adicione(valores, n + i)
            }
            para k de 0 ate 100 {
                total = total + valores[k]
            }
            retorne total
        }
        inicio {
            escreva(somar(0))
            escreva(somar(1))
            escreva(somar(2))
        }"""
        resultado = executar(fonte)
        self.assertEqual((resultado.returncode, resultado.stdout),(0,'5050\n5151\n5252\n'))

    def test_liberacao_explicita_e_segunda_liberacao_rejeitada(self):
        fonte = """inicio {
            seja colecao: lista[]
            adicione(colecao, 10)
            libere(colecao)
            escreva(123)
        }"""
        resultado=executar(fonte)
        self.assertEqual((resultado.returncode, resultado.stdout),(0,'123\n'))
        for comando in ('libere(colecao)', 'adicione(colecao, 42)', 'escreva(tamanho(colecao))',
                        'escreva(colecao[0])', 'remova_ultimo(colecao)'):
            fonte = """inicio {
                seja colecao: lista[]
                adicione(colecao, 10)
                libere(colecao)
                """+comando+"\n}"
            with self.subTest(comando=comando):
                r=executar(fonte)
                self.assertNotEqual(r.returncode,0)
                self.assertIn('liber',r.stdout.lower()+r.stderr.lower())

    def test_indices_invalidos(self):
        for expressao in ('colecao[0]', 'colecao[-1]', 'colecao[2]'):
            fonte="""inicio {
                seja colecao: lista[]
                adicione(colecao, 8)
                escreva("""+expressao+""")
            }"""
            if expressao == 'colecao[0]':
                r=executar(fonte)
                self.assertEqual((r.returncode,r.stdout),(0,'8\n'))
            else:
                r=executar(fonte)
                self.assertNotEqual(r.returncode,0)
                self.assertIn('indice', (r.stdout+r.stderr).lower().replace('í','i'))

    def test_ler_indice_existente(self):
        fonte="""inicio {
            seja colecao: lista[]
            adicione(colecao, 0)
            leia(colecao[0])
            escreva(colecao[0])
        }"""
        r=executar(fonte,'123\n')
        self.assertEqual((r.returncode,r.stdout),(0,'123\n'))

    def test_remover_lista_vazia_falha(self):
        r=executar("""inicio {
            seja colecao: lista[]
            remova_ultimo(colecao)
        }""")
        self.assertNotEqual(r.returncode,0)

    def test_proibir_copia_e_emprestimo_implicitos(self):
        proibidos=[
            """inicio {
                seja a: lista[]
                seja b = a
            }""",
            """inicio {
                seja a: lista[]
                seja b: lista[]
                a = b
            }""",
            """funcao receber(a: lista[]) -> inteiro {
                retorne 1
            }
            inicio {
                escreva(1)
            }""",
            """inicio {
                para i de 0 ate 3 {
                    seja colecao: lista[]
                    adicione(colecao, i)
                }
            }""",
        ]
        for fonte in proibidos:
            with self.subTest(fonte=fonte):
                with self.assertRaises(ErroCompilacao):
                    analisar_programa(fonte)

    def test_lista_fixa_preservada(self):
        fonte="""inicio {
            seja fixa: lista[3]
            fixa[0] = 10
            fixa[2] = 30
            escreva(tamanho(fixa))
            escreva(fixa[2])
            seja movel: lista[]
            adicione(movel, 77)
            escreva(movel[0])
        }"""
        r=executar(fonte)
        self.assertEqual((r.returncode,r.stdout),(0,'3\n30\n77\n'))

if __name__ == '__main__':
    unittest.main()
