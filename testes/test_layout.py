"""RS 0.15: propriedades e compatibilidade do novo layout SSA."""
import os
from pathlib import Path
import random
import subprocess
import sys
import tempfile
import unittest

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))
from compilador.ir import construir_ir, programa_para_backend
from compilador.parser import analisar_programa
from backend import compilar
from backend.ssa_x86_64 import construir_backend_ssa, emissor_ssa, planejar_layout
from backend.x86_64 import montar_codigo


class TestesLayout(unittest.TestCase):
    def executar(self, fonte, nivel, entrada=''):
        if sys.platform not in ('win32', 'linux'):
            self.skipTest('Windows ou Linux x86-64')
        if sys.platform == 'linux' and os.uname().machine != 'x86_64':
            self.skipTest('Linux x86-64')
        alvo = 'windows' if sys.platform == 'win32' else 'linux'
        binario = compilar(analisar_programa(fonte), alvo, nivel=nivel)
        with tempfile.TemporaryDirectory() as pasta:
            arq = Path(pasta) / ('programa.exe' if alvo == 'windows' else 'programa')
            arq.write_bytes(binario)
            if alvo == 'linux':
                arq.chmod(0o755)
            r = subprocess.run([str(arq)], input=entrada, text=True,
                               capture_output=True, encoding='utf-8', timeout=12)
        return (r.returncode, r.stdout, r.stderr)

    def test_layout_deterministico_e_cobertura(self):
        prog = analisar_programa((RAIZ/'exemplos'/'registradores.rts').read_text(encoding='utf-8'))
        ssa, _ = construir_backend_ssa(construir_ir(prog, nivel=3))
        ordem = planejar_layout(ssa)
        self.assertEqual(ordem[0], ssa.cfg.entrada)
        self.assertEqual(set(ordem), {bid for bid, bloco in ssa.blocos.items() if bloco.alcancavel})
        self.assertEqual(len(ordem), len(set(ordem)))
        self.assertEqual(ordem, planejar_layout(ssa))

    def test_saltos_realmente_eliminados(self):
        prog = analisar_programa((RAIZ/'exemplos'/'decisoes.rts').read_text(encoding='utf-8'))
        ir = construir_ir(prog, nivel=3)
        ssa, aloc = construir_backend_ssa(ir)
        legado = programa_para_backend(ir)
        legado.variaveis = {f'slot{i}': i for i in range(aloc.vagas_pilha + 1)}
        def saltos(nivel):
            g, _ = montar_codigo(legado, False, emissor_ssa(ir, ssa, aloc, otimizar_layout=(nivel==5)))
            return sum(1 for pos, label in g.pendencias
                       if label.startswith('ssa_') and pos > 0 and g.codigo[pos-1] == 0xE9)
        self.assertLess(saltos(5), saltos(4))

    def test_exemplos_equivalentes(self):
        for caminho in sorted((RAIZ/'exemplos').glob('*.rts')):
            fonte = caminho.read_text(encoding='utf-8')
            entrada = '21\n' if caminho.stem == 'entrada' else ''
            with self.subTest(programa=caminho.name):
                self.assertEqual(self.executar(fonte, 4, entrada), self.executar(fonte, 5, entrada))

    def test_juncoes_phi_com_entrada(self):
        fonte = '''inicio {
            seja a = 0
            seja b = 17
            leia(a)
            se a > 0 {
                b = b + a
            } senao {
                b = b - a
            }
            escreva(b)
        }'''
        for entrada in ('0\n', '15\n', '-15\n'):
            with self.subTest(entrada=entrada):
                self.assertEqual(self.executar(fonte, 4, entrada), self.executar(fonte, 5, entrada))

    def test_lacos_overflow_e_divisao_zero(self):
        fontes = (
            '''inicio {
              para i de 9223372036854775806 ate 9223372036854775807 {
                escreva(i)
              }
              escreva(i)
            }''',
            '''inicio {
              para i de -9223372036854775807 ate -9223372036854775808 passo -1 {
                escreva(i)
              }
              escreva(i)
            }''',
            '''inicio {
              seja a = 9223372036854775807
              escreva(a + 1)
            }''',
            '''inicio {
              seja a = 0
              escreva(10 / a)
            }''',
            '''inicio {
              seja total = 0
              para i de 1 ate 12 {
                se i == 7 {
                  continue
                }
                total = total + i
                se i == 10 {
                  pare
                }
              }
              escreva(total)
            }''',
        )
        for fonte in fontes:
            with self.subTest(fonte=fonte[:70]):
                self.assertEqual(self.executar(fonte, 4), self.executar(fonte, 5))

    def test_25_programas_gerados(self):
        aleatorio = random.Random(150)
        for indice in range(25):
            limite = aleatorio.randint(3, 25)
            modulo = aleatorio.randint(2, 8)
            a = aleatorio.randint(1, 9)
            b = aleatorio.randint(1, 9)
            fonte = f'''inicio {{
                seja i = 0
                seja x = 0
                enquanto i < {limite} {{
                    se i % {modulo} == 0 {{
                        x = x + {a}
                    }} senao {{
                        x = x - {b}
                    }}
                    i = i + 1
                }}
                escreva(x)
            }}'''
            with self.subTest(caso=indice):
                self.assertEqual(self.executar(fonte, 4), self.executar(fonte, 5))


if __name__ == '__main__':
    unittest.main()
