"""RS 0.14: lowering SSA, ciclos paralelos, alocacao e regressao multiplataforma."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

from backend import compilar
from backend.ssa_x86_64 import copias_paralelas, construir_backend_ssa
from compilador.alocacao import Local, alocar_registradores
from compilador.cfg import construir_cfg
from compilador.ir import construir_ir, programa_para_backend
from compilador.parser import analisar_programa
from backend.x86_64 import montar_codigo
from backend.windows_pe import montar_pe
from backend.linux_elf import montar_elf


PROGRAMAS = [
    ('''inicio {
      seja x = 1
      seja y = 9
      se x {
        x = 3
        y = 11
      } senao {
        x = 5
        y = 12
      }
      escreva(x)
      escreva(y)
    }''', ''),
    ('''inicio {
      seja x = 1
      seja y = 0
      enquanto x < 8 {
        se x % 2 == 0 {
          y = y + x
        } senao {
          y = y - 1
        }
        x = x + 1
      }
      escreva(x)
      escreva(y)
    }''', ''),
    ('''inicio {
      seja soma = 0
      seja j = 0
      para i de 1 ate 4 {
        para j de 1 ate 5 {
          se j == 2 {
            continue
          }
          se i == 4 {
            pare
          }
          soma = soma + i * j
        }
      }
      escreva(soma)
      escreva(i)
      escreva(j)
    }''', ''),
    ('''inicio {
      para i de 9223372036854775806 ate 9223372036854775807 {
        escreva(i)
      }
      escreva(i)
      para j de -9223372036854775807 ate -9223372036854775808 passo -1 {
        escreva(j)
      }
      escreva(j)
    }''', ''),
    ('''inicio {
      seja a = 0
      seja b = 4
      leia(a)
      se a > 0 {
        b = a + 3
      } senao {
        b = a - 3
      }
      escreva(a)
      escreva(b)
    }''', '12\n'),
    ('''inicio {
      seja a = 9223372036854775807
      seja b = 0
      se b == 0 {
        a = a + 1
      }
      escreva(a)
    }''', ''),
    ('''inicio {
      seja a = 0
      leia(a)
      escreva(10 / a)
    }''', '0\n'),
    ('''inicio {
      seja a = 0
      seja b = 3
      se b {
        b = 4
      }
      escreva(a + b)
    }''', ''),
]


class TestesBackendSSA(unittest.TestCase):
    def executar(self, fonte, entrada, nivel):
        alvo = 'windows' if sys.platform == 'win32' else 'linux'
        if sys.platform not in ('win32', 'linux'):
            self.skipTest('Windows/Linux')
        if alvo == 'linux' and os.uname().machine != 'x86_64':
            self.skipTest('Exige Linux x86-64')
        programa = analisar_programa(fonte)
        binario = compilar(programa, alvo, nivel=nivel)
        with tempfile.TemporaryDirectory() as pasta:
            arq = Path(pasta) / ('teste.exe' if alvo == 'windows' else 'teste')
            arq.write_bytes(binario)
            if alvo == 'linux':
                arq.chmod(0o755)
            resultado = subprocess.run([str(arq)], input=entrada,
                                      capture_output=True, encoding='utf-8', timeout=7)
        return resultado.returncode, resultado.stdout, resultado.stderr

    def test_equivalencia_com_o3(self):
        for i, (fonte, entrada) in enumerate(PROGRAMAS):
            with self.subTest(programa=i):
                self.assertEqual(self.executar(fonte, entrada, 3),
                                 self.executar(fonte, entrada, 4))

    def test_niveis_antigos_sem_regressao(self):
        fonte, entrada = PROGRAMAS[1]
        antigo = self.executar(fonte, entrada, 3)
        for nivel in (0, 1, 2, 4):
            with self.subTest(nivel=nivel):
                self.assertEqual(antigo, self.executar(fonte, entrada, nivel))

    def test_ssa_phi_e_alocacao_de_registradores(self):
        programa = analisar_programa(PROGRAMAS[0][0])
        ssa, aloc = construir_backend_ssa(construir_ir(programa, nivel=3))
        self.assertTrue(ssa.validar())
        self.assertTrue(any(b.phis for b in ssa.blocos.values()))
        self.assertTrue(any(l.classe == 'reg' for l in aloc.locais.values()))
        self.assertTrue(all(l.indice in ('r13','r14','r15')
                            for l in aloc.locais.values() if l.classe == 'reg'))
        for v, conflitos in aloc.interferencias.items():
            for outro in conflitos:
                self.assertNotEqual(aloc.locais[v], aloc.locais[outro])

    def test_ciclo_de_copias_paralelas_em_maquina_real(self):
        # Dois registradores trocados numa mesma aresta: mov sequencial
        # destruiria o valor original; o slot temporario preserva ambos.
        # Corrigido no propio backend: chamar somente emissao de copias.
        class Legado:
            variaveis = {'tmp': 0}
            instrucoes = [('imprima_num', ('numero', 1))]
        from backend.ssa_x86_64 import _emite_mov
        def callback(g, mensagens, windows):
            g.bytes(b'\x41\xBD\x0A\x00\x00\x00')  # r13d = 10
            g.bytes(b'\x41\xBE\x14\x00\x00\x00')  # r14d = 20
            copias_paralelas(g, [('a','b'),('b','a')],
                            {'a': Local('reg','r13'), 'b': Local('reg','r14')},
                            Local('pilha',0), windows)
            _emite_mov(g, 'rax', 'r13')
            g.chamada('imprimir_inteiro')
            _emite_mov(g, 'rax', 'r14')
            g.chamada('imprimir_inteiro')
        windows = sys.platform == 'win32'
        g, mensagens = montar_codigo(Legado(), windows, callback)
        binario = montar_pe(g,mensagens) if windows else montar_elf(g,mensagens)
        if sys.platform not in ('win32','linux'):
            self.skipTest('Windows/Linux')
        with tempfile.TemporaryDirectory() as pasta:
            arq=Path(pasta)/('swap.exe' if windows else 'swap')
            arq.write_bytes(binario)
            if not windows:arq.chmod(0o755)
            resultado=subprocess.run([str(arq)],capture_output=True,encoding='utf-8',timeout=5)
        self.assertEqual((resultado.returncode,resultado.stdout),(0,'20\n10\n'))

    def test_muita_pressao_em_registradores(self):
        fonte = '''inicio {
            seja a = 1
            seja b = 2
            seja c = 3
            seja d = 4
            seja resultado_e = 5
            seja f = 6
            seja g = 7
            seja h = 8
            leia(a)
            leia(b)
            leia(c)
            leia(d)
            leia(resultado_e)
            leia(f)
            leia(g)
            leia(h)
            escreva(a+b+c+d+resultado_e+f+g+h)
        }'''
        self.assertEqual(self.executar(fonte,'10\n2\n3\n4\n5\n6\n7\n8\n',3), self.executar(fonte,'10\n2\n3\n4\n5\n6\n7\n8\n',4))
        ssa, aloc = construir_backend_ssa(construir_ir(analisar_programa(fonte), nivel=3))
        self.assertTrue(any(l.classe == 'pilha' for l in aloc.locais.values()))

    def test_sem_alteracao_dos_bytes_o3(self):
        fonte = PROGRAMAS[0][0]
        prog=analisar_programa(fonte)
        original = compilar(prog, 'linux', nivel=3)
        repetido = compilar(prog, 'linux', nivel=3)
        self.assertEqual(original, repetido)


if __name__ == '__main__':
    unittest.main()
