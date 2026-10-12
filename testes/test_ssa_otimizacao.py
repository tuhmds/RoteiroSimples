"""RS 0.13: SSA aplicada ao backend, DCE e verificacao semantica por plataforma."""
import os
import random
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))
from compilador.parser import analisar_programa
from compilador.ir import construir_ir
from compilador.cfg import construir_cfg
from compilador.ssa import construir_ssa
from compilador.ssa_baixamento import planejar_copias_phi, formatar_copias_phi
from backend import compilar
from tamanho_codigo import tamanho_codigo_elf


def executar(programa, nivel, entrada=''):
    alvo = 'windows' if sys.platform == 'win32' else 'linux'
    with tempfile.TemporaryDirectory() as pasta:
        arquivo = Path(pasta)/('codigo.exe' if alvo == 'windows' else 'codigo')
        arquivo.write_bytes(compilar(programa, alvo, otimizar=nivel > 0, nivel=nivel))
        if alvo == 'linux':
            arquivo.chmod(0o755)
        retorno = subprocess.run([str(arquivo)], input=entrada,
                                 capture_output=True, encoding='utf-8', timeout=5)
    return retorno.returncode, retorno.stdout, retorno.stderr


class TestesSSA013(unittest.TestCase):
    def test_phi_constante_gera_litteral_no_backend(self):
        fonte = '''inicio {
            seja x = 0
            seja cond = 1
            se cond { x = 7
            } senao { x = 7
            }
            escreva(x)
        }'''
        # O parser exige instrucao de abertura na sua propria linha.
        fonte = '''inicio {
            seja x = 0
            seja cond = 1
            se cond {
                x = 7
            } senao {
                x = 7
            }
            escreva(x)
        }'''
        programa = analisar_programa(fonte)
        ir2 = construir_ir(programa, True, 2)
        ir3 = construir_ir(programa, True, 3)
        self.assertEqual(ir2.instrucoes[-1].argumentos[0].operacao, 'var')
        self.assertEqual((ir3.instrucoes[-1].argumentos[0].operacao,
                          ir3.instrucoes[-1].argumentos[0].valor), ('numero', 7))
        self.assertFalse(any(i.operacao == 'atribua' and i.argumentos[0] == 'x'
                             for i in ir3.instrucoes))
        for alvo in ('linux', 'windows'):
            with self.subTest(alvo=alvo):
                novo = compilar(programa, alvo, True, 3)
                anterior = compilar(programa, alvo, True, 2)
                if alvo == 'linux':
                    self.assertLess(tamanho_codigo_elf(novo),
                                    tamanho_codigo_elf(anterior))
                else:
                    self.assertLess(len(novo), len(anterior) + 1)
        if sys.platform in ('linux', 'win32'):
            self.assertEqual(executar(programa, 3)[1], '7\n')

    def test_phi_diferente_nao_usa_constante_arbitraria(self):
        fonte = '''inicio {
            seja escolha = 0
            seja x = 3
            leia(escolha)
            se escolha {
                x = 7
            } senao {
                x = 9
            }
            escreva(x)
        }'''
        programa = analisar_programa(fonte)
        ir = construir_ir(programa, True, 3)
        self.assertEqual(ir.instrucoes[-1].argumentos[0].operacao, 'var')
        if sys.platform in ('linux', 'win32'):
            for entrada, esperado in [('0\n', '9\n'), ('1\n', '7\n')]:
                with self.subTest(entrada=entrada):
                    self.assertEqual(executar(programa, 3, entrada)[1], esperado)

    def test_plano_arestas_para_phi(self):
        fonte = '''inicio {
            seja x = 0
            seja y = 1
            se y {
                x = 4
            } senao {
                x = 5
            }
            escreva(x)
        }'''
        p = analisar_programa(fonte)
        ssa = construir_ssa(construir_cfg(construir_ir(p, False, 0)))
        planos = planejar_copias_phi(ssa)
        destino = next(phi.destino for b in ssa.blocos.values()
                       for phi in b.phis.values() if phi.variavel == 'x')
        copias = [c for c in planos.values() for c in c]
        self.assertEqual(sum(c.destino == destino for c in copias), 2)
        self.assertIn('copias paralelas', formatar_copias_phi(ssa))

    def test_laco_phi_em_retroaresta_e_pare_continue(self):
        programa = analisar_programa('''inicio {
            seja soma = 0
            para i de 1 ate 5 {
                se i == 3 {
                    continue
                }
                se i == 5 {
                    pare
                }
                soma = soma + i
            }
            escreva(soma)
        }''')
        ssa = construir_ssa(construir_cfg(construir_ir(programa, True, 3)))
        self.assertTrue(planejar_copias_phi(ssa))
        if sys.platform in ('linux', 'win32'):
            self.assertEqual(executar(programa, 3)[1], '7\n')

    def test_nao_remove_atribuicao_com_erro(self):
        fonte = '''inicio {
            seja n = 9223372036854775807
            seja perdido = n + 1
            escreva(999)
        }'''
        programa = analisar_programa(fonte)
        ir = construir_ir(programa, True, 3)
        self.assertTrue(any(i.operacao == 'atribua' and i.argumentos[0] == 'perdido'
                            for i in ir.instrucoes))
        if sys.platform in ('linux', 'win32'):
            zero = executar(programa, 0)
            tres = executar(programa, 3)
            self.assertEqual(zero, tres)
            self.assertEqual(zero[0], 1)
            self.assertNotIn('999', ''.join(zero[1:]))

    def test_nunca_elimina_leia_ou_erro_divisao(self):
        fonte = '''inicio {
            seja a = 0
            seja descartado = 10
            leia(a)
            descartado = 5 / a
            escreva(77)
        }'''
        programa = analisar_programa(fonte)
        ir = construir_ir(programa, True, 3)
        self.assertTrue(any(i.operacao == 'leia_int' for i in ir.instrucoes))
        self.assertTrue(any(i.operacao == 'atribua' and i.argumentos[0] == 'descartado'
                            for i in ir.instrucoes))
        if sys.platform in ('linux', 'win32'):
            for texto in ('0\n', '2\n', 'abc\n', ''):
                with self.subTest(texto=texto):
                    self.assertEqual(executar(programa, 2, texto), executar(programa, 3, texto))

    def test_equivalencia_plataforma_deterministica(self):
        if sys.platform not in ('win32', 'linux'):
            self.skipTest('Somente Windows e Linux')
        cenarios = [
            ('''inicio {
            seja n = 0
            enquanto n < 5 {
                n = n + 1
            }
            escreva(n)
            }''', ''),
            ('''inicio {
            seja a = -9223372036854775808
            escreva(a)
            }''', ''),
            ('''inicio {
            seja a = 7
            seja b = 0
            escreva(a / b)
            }''', ''),
            ('''inicio {
            seja n = 0
            leia(n)
            se n < 3 {
                escreva(4)
            } senao {
                escreva(8)
            }
            }''', '10\n'),
        ]
        for fonte, entrada in cenarios:
            p = analisar_programa(fonte)
            with self.subTest(fonte=fonte[:35]):
                base = executar(p, 2, entrada)
                self.assertEqual(base, executar(p, 3, entrada))

    def test_equivalencia_aleatoria(self):
        if sys.platform not in ('win32', 'linux'):
            self.skipTest('Somente Windows e Linux')
        aleatorio = random.Random(12013)
        for i in range(40):
            a = aleatorio.randint(-50, 50)
            b = aleatorio.randint(-50, 50)
            p = analisar_programa(f'''inicio {{
                seja x = {a}
                seja y = {b}
                seja cond = x < y
                se cond {{
                    x = x + 1
                }} senao {{
                    y = y - 1
                }}
                escreva(x)
                escreva(y)
                escreva(x * y)
            }}''')
            with self.subTest(i=i):
                self.assertEqual(executar(p, 2), executar(p, 3))

    def test_comando_mostrar_plano_ssa(self):
        with tempfile.TemporaryDirectory() as pasta:
            base = Path(pasta)
            fonte = base/'fonte.rts'
            destino = base/'codigo.exe'
            fonte.write_text('''inicio {
            seja x = 1
            se x {
                x = 2
            } senao {
                x = 3
            }
            escreva(x)
            }''', encoding='utf-8')
            p = subprocess.run([sys.executable, str(RAIZ/'compilar.py'), str(fonte),
                                '--alvo', 'windows', '-O', '3', '--mostrar-copias-phi',
                                '-o', str(destino)], capture_output=True, text=True, timeout=15)
            self.assertEqual(p.returncode, 0, p.stderr)
            self.assertIn('copias paralelas', p.stdout)
            self.assertTrue(destino.read_bytes().startswith(b'MZ'))


if __name__ == '__main__':
    unittest.main()
