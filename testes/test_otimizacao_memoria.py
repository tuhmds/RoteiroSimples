"""RS 0.21 — Memory SSA usada pelo backend conservador de listas."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))
from compilador.ir import construir_ir
from compilador.memory_ssa import construir_memory_ssa
from compilador.parser import analisar_programa
from backend import compilar


def comandos(ir):
    for i in getattr(ir, "instrucoes", ir):
        yield i
        if i.operacao == 'se':
            yield from comandos(i.argumentos[1]); yield from comandos(i.argumentos[2])
        elif i.operacao == 'enquanto':
            yield from comandos(i.argumentos[1])
        elif i.operacao == 'para':
            yield from comandos(i.argumentos[4])


def rodar(fonte, nivel, entrada=''):
    alvo = 'windows' if sys.platform == 'win32' else 'linux'
    if alvo == 'linux' and (sys.platform != 'linux' or os.uname().machine != 'x86_64'):
        raise unittest.SkipTest('Requer Windows ou Linux x86-64')
    with tempfile.TemporaryDirectory() as pasta:
        caminho = Path(pasta) / ('prog.exe' if alvo == 'windows' else 'prog')
        caminho.write_bytes(compilar(analisar_programa(fonte), alvo, nivel=nivel))
        if alvo == 'linux':
            caminho.chmod(0o755)
        return subprocess.run([str(caminho)], input=entrada, capture_output=True,
                              text=True, encoding='utf-8', timeout=5)


class TestesOtimizacaoMemoria(unittest.TestCase):
    def ir(self, fonte, nivel=7):
        return construir_ir(analisar_programa(fonte), nivel=nivel)

    def comparar(self, fonte, esperado=None, entrada=''):
        antigo = rodar(fonte, 6, entrada)
        novo = rodar(fonte, 7, entrada)
        self.assertEqual((novo.returncode, novo.stdout, novo.stderr),
                         (antigo.returncode, antigo.stdout, antigo.stderr))
        if esperado is not None:
            self.assertEqual(novo.stdout, esperado)
        return novo

    def test_substituir_leituras_de_posicoes_comprovadas(self):
        fonte = '''inicio {
            seja a: lista[4]
            a[1] = 5
            escreva(a[1])
            escreva(a[2])
        }'''
        ir = self.ir(fonte)
        impressos = [x.argumentos[0] for x in comandos(ir) if x.operacao == 'imprima_num']
        self.assertEqual([(e.operacao, e.valor) for e in impressos],
                         [('numero', 5), ('numero', 0)])
        self.assertTrue(construir_memory_ssa(ir).validar())
        self.comparar(fonte, '5\n0\n')

    def test_eliminar_escrita_idempotente_mas_nao_a_primeira(self):
        fonte = '''inicio {
            seja notas: lista[3]
            notas[0] = 10
            notas[0] = 10
            notas[1] = 11
            escreva(notas[0] + notas[1])
        }'''
        ir0, ir7 = self.ir(fonte, 6), self.ir(fonte, 7)
        stores = lambda ir: len([x for x in comandos(ir) if x.operacao == 'atribua_indice'])
        self.assertEqual(stores(ir0), 3)
        self.assertEqual(stores(ir7), 2)
        self.comparar(fonte, '21\n')

    def test_duas_listas_nao_sao_alias(self):
        fonte = '''inicio {
            seja a: lista[2]
            seja b: lista[2]
            a[0] = 3
            b[0] = 9
            escreva(a[0])
            escreva(b[0])
        }'''
        self.comparar(fonte, '3\n9\n')

    def test_escrita_desconhecida_invalida_cache(self):
        fonte = '''inicio {
            seja a: lista[2]
            seja i = 0
            a[0] = 3
            a[i] = 9
            escreva(a[0])
        }'''
        ir = self.ir(fonte)
        impressao = [x.argumentos[0] for x in comandos(ir) if x.operacao == 'imprima_num'][0]
        self.assertEqual(impressao.operacao, 'indice')
        self.comparar(fonte, '9\n')

    def test_condicao_nao_propaga_valor_entre_caminhos(self):
        fonte = '''inicio {
            seja a: lista[2]
            seja cond = 1
            a[0] = 3
            se cond {
                a[0] = 4
            }
            escreva(a[0])
        }'''
        ir = self.ir(fonte)
        self.assertEqual([x.argumentos[0].operacao for x in comandos(ir)
                          if x.operacao == 'imprima_num'], ['indice'])
        self.comparar(fonte, '4\n')

    def test_laco_continue_pare_e_efeitos(self):
        fonte = '''inicio {
            seja a: lista[3]
            para i de 0 ate 2 {
                se i == 1 {
                    continue
                }
                a[i] = i + 4
            }
            escreva(a[0])
            escreva(a[1])
            escreva(a[2])
        }'''
        self.comparar(fonte, '4\n0\n6\n')

    def test_leia_indice_invalida_conhecido(self):
        fonte = '''inicio {
            seja a: lista[2]
            a[0] = 7
            leia(a[0])
            escreva(a[0])
        }'''
        ir = self.ir(fonte)
        self.assertEqual([x.argumentos[0].operacao for x in comandos(ir)
                          if x.operacao == 'imprima_num'], ['indice'])
        self.comparar(fonte, '22\n', '22\n')

    def test_indices_fora_dos_limites_continuam_falhando(self):
        for idx in ('-1', '2'):
            with self.subTest(idx=idx):
                fonte = 'inicio {\n seja a: lista[2]\n a[' + idx + '] = 0\n escreva(12)\n}'
                saida = self.comparar(fonte)
                self.assertEqual(saida.returncode, 1)
                self.assertNotIn('12\n', saida.stdout)

    def test_divisao_por_zero_nao_e_eliminada(self):
        fonte = '''inicio {
            seja a: lista[2]
            a[0] = 1
            a[0] = 1 / 0
            escreva(a[0])
        }'''
        result = self.comparar(fonte)
        self.assertEqual(result.returncode, 1)

    def test_textos_e_listas_juntos(self):
        fonte = '''inicio {
            seja a: lista[2]
            seja s: texto[16]
            a[0] = 17
            copie(s, "Olá")
            escreva(s)
            escreva(a[0])
        }'''
        self.comparar(fonte, 'Olá\n17\n')

    def test_sem_objetos_nao_altera_codigo(self):
        fonte = 'inicio {\n seja a = 20\n escreva(a + 1)\n}'
        p = analisar_programa(fonte)
        for alvo in ('linux', 'windows'):
            self.assertEqual(compilar(p, alvo, nivel=6), compilar(p, alvo, nivel=7))


if __name__ == '__main__':
    unittest.main()
