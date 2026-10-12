"""RS 0.20: SSA de memoria por objeto, efeitos observaveis e phi.

A analise nao altera o backend, que continua compilando os programas antigos.
"""
import json
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


def memoria(fonte):
    return construir_memory_ssa(construir_ir(analisar_programa(fonte), nivel=6))


def instrucoes(programa, op=None):
    for bloco in programa.blocos.values():
        if not bloco.alcancavel:
            continue
        for instr in bloco.instrucoes:
            if op is None or instr.operacao == op:
                yield bloco, instr


class TestesMemorySSA(unittest.TestCase):
    def test_juncao_memoria_em_se_senao(self):
        m = memoria('''inicio {
            seja a: texto[32]
            seja cond = 1
            se cond {
                copie(a, "sim")
            } senao {
                copie(a, "nao")
            }
            escreva(a)
        }''')
        self.assertTrue(m.validar())
        phis = [(b, b.phis['mem:a']) for b in m.blocos.values() if 'mem:a' in b.phis]
        self.assertEqual(len(phis), 1)
        bb, phi = phis[0]
        self.assertEqual(len(phi.entradas), 2)
        saidas = [i for _, i in instrucoes(m, 'imprima_texto')]
        self.assertEqual(len(saidas), 1)
        self.assertEqual(saidas[0].usos['mem:a'], phi.destino)
        self.assertEqual(set(m.predecessores[bb.id]), set(phi.entradas))

    def test_laco_phi_lista_e_controle(self):
        m = memoria('''inicio {
            seja a: lista[4]
            para i de 0 ate 3 {
                a[i] = i
            }
            escreva(a[2])
        }''')
        self.assertTrue(m.validar())
        phis = [phi for b in m.blocos.values() for phi in b.phis.values()]
        self.assertTrue(any(p.regiao == 'mem:a' for p in phis))
        self.assertTrue(any(p.regiao == 'efeito:ordem' for p in phis))
        gravacoes = list(instrucoes(m, 'atribua_indice'))
        self.assertEqual(len(gravacoes), 1)
        _, gravacao = gravacoes[0]
        self.assertIn('mem:a', gravacao.usos)
        self.assertIn('mem:a', gravacao.definicoes)
        self.assertNotEqual(gravacao.usos['mem:a'], gravacao.definicoes['mem:a'])

    def test_buferes_independentes(self):
        m = memoria('''inicio {
            seja a: texto[16]
            seja b: texto[16]
            copie(a, "A")
            copie(b, "B")
            junte(a, "!")
            escreva(b)
        }''')
        mods = list(instrucoes(m, 'modifique_texto'))
        self.assertEqual(len(mods), 3)
        primeiro_a = next(i for _, i in mods if 'mem:a' in i.definicoes)
        b = next(i for _, i in mods if 'mem:b' in i.definicoes)
        ultimo_a = [i for _, i in mods if 'mem:a' in i.definicoes][-1]
        self.assertEqual(ultimo_a.usos['mem:a'], primeiro_a.definicoes['mem:a'])
        self.assertNotIn('mem:b', ultimo_a.definicoes)
        self.assertNotIn('mem:a', b.definicoes)
        impressao = list(instrucoes(m, 'imprima_texto'))[0][1]
        self.assertEqual(impressao.usos['mem:b'], b.definicoes['mem:b'])

    def test_io_e_falhas_ordenados(self):
        m = memoria('''inicio {
            seja a = 0
            seja b = 0
            escreva("Informe:")
            leia(a)
            leia(b)
            escreva(a + b)
        }''')
        xs = [i for _, i in instrucoes(m)]
        io = [i for i in xs if i.efeitos.entrada or i.efeitos.saida]
        self.assertEqual(len(io), 4)
        for anterior, posterior in zip(io, io[1:]):
            self.assertEqual(posterior.usos['efeito:ordem'], anterior.definicoes['efeito:ordem'])
        self.assertIn('io:entrada', io[1].definicoes)
        self.assertIn('io:saida', io[0].definicoes)
        self.assertIn('efeito:falha', io[1].definicoes)

    def test_memoria_e_falha_do_indice(self):
        m = memoria('''inicio {
            seja dados: lista[2]
            dados[0] = 1
            escreva(dados[1])
        }''')
        gravacao = list(instrucoes(m, 'atribua_indice'))[0][1]
        impressao = list(instrucoes(m, 'imprima_num'))[0][1]
        self.assertEqual(impressao.usos['mem:dados'], gravacao.definicoes['mem:dados'])
        self.assertIn('efeito:falha', gravacao.definicoes)
        self.assertIn('efeito:falha', impressao.definicoes)

    def test_variavel_simples_nao_vira_regiao_de_memoria(self):
        m = memoria('''inicio {
            seja a = 2
            seja b = a + 3
            escreva(b)
        }''')
        self.assertFalse(any(r.startswith('mem:') for r in m.regioes))
        self.assertTrue(m.validar())

    def test_laco_com_pare_continue(self):
        m = memoria('''inicio {
            seja a: lista[6]
            para i de 0 ate 5 {
                se i == 1 {
                    continue
                }
                se i == 4 {
                    pare
                }
                a[i] = i * 2
            }
            escreva(a[3])
        }''')
        self.assertTrue(m.validar())
        self.assertTrue(any('mem:a' in b.phis for b in m.blocos.values()))
        self.assertGreater(len(m.cfg.blocos), 10)

    def test_texto_lendo_e_copiando_para_si(self):
        m = memoria('''inicio {
            seja a: texto[64]
            leia(a)
            junte(a, a)
            escreva(tamanho(a))
        }''')
        self.assertTrue(m.validar())
        entrada = list(instrucoes(m, 'leia_texto'))[0][1]
        junte = list(instrucoes(m, 'modifique_texto'))[0][1]
        self.assertEqual(junte.usos['mem:a'], entrada.definicoes['mem:a'])
        self.assertIn('io:entrada', entrada.definicoes)
        self.assertIn('efeito:ordem', junte.definicoes)

    def test_json_deterministico_e_completo(self):
        source = 'inicio {\n seja a: texto[12]\n copie(a, "oi")\n escreva(a)\n}'
        a = memoria(source)
        b = memoria(source)
        self.assertEqual(a.para_json(), b.para_json())
        obj = json.loads(a.para_json())
        self.assertEqual(obj['versao'], 'RS 0.20')
        self.assertIn('mem:a', obj['regioes'])
        self.assertTrue(a.formatar().startswith('RS 0.20'))
        self.assertIn('mem:a@', a.formatar())

    def test_validador_rejeita_phi_incompleto(self):
        m = memoria('''inicio {
            seja a: texto[16]
            se 1 {
                copie(a, "sim")
            } senao {
                copie(a, "nao")
            }
            escreva(a)
        }''')
        phi = next(b.phis['mem:a'] for b in m.blocos.values() if 'mem:a' in b.phis)
        phi.entradas.pop(next(iter(phi.entradas)))
        with self.assertRaisesRegex(ValueError, 'incompleto'):
            m.validar()

    def test_analise_nao_altera_execucao_windows_linux(self):
        if sys.platform not in ('linux', 'win32'):
            self.skipTest('Requer Linux ou Windows')
        if sys.platform == 'linux' and os.uname().machine != 'x86_64':
            self.skipTest('Requer x86-64')
        arquivo = RAIZ / 'exemplos' / 'memory_ssa.rts'
        fonte = arquivo.read_text(encoding='utf-8')
        programa = analisar_programa(fonte)
        self.assertTrue(construir_memory_ssa(construir_ir(programa, nivel=6)).validar())
        alvo = 'windows' if sys.platform == 'win32' else 'linux'
        with tempfile.TemporaryDirectory() as temp:
            exe = Path(temp) / ('programa.exe' if alvo == 'windows' else 'programa')
            exe.write_bytes(compilar(programa, alvo, nivel=6))
            if alvo == 'linux':
                exe.chmod(0o755)
            result = subprocess.run([str(exe)], stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                    encoding='utf-8', timeout=10)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout, 'Olá.!.\n20\n')

    def test_cli_memory_ssa_json_sem_bloquear_listas(self):
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / 'saida.json'
            exe = Path(temp) / 'programa.exe'
            cmd = [sys.executable, str(RAIZ / 'compilar.py'),
                   str(RAIZ / 'exemplos' / 'memory_ssa.rts'),
                   '--alvo', 'windows', '-O', '6', '--mostrar-memory-ssa',
                   '--salvar-memory-ssa', str(output), '-o', str(exe)]
            result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', timeout=20)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn('Memory SSA', result.stdout)
            self.assertTrue(exe.exists())
            self.assertTrue(json.loads(output.read_text(encoding='utf-8'))['blocos'])

    def test_analises_distintas_e_sem_efeitos(self):
        m = memoria('inicio {\n escreva("Oi")\n}')
        self.assertNotIn('mem:a', m.regioes)
        self.assertIn('io:saida', m.regioes)
        self.assertTrue(m.validar())


if __name__ == '__main__':
    unittest.main()
