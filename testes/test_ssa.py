"""RS 0.12: construção, renomeação e verificação de SSA com nós phi reais."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))
from compilador.parser import analisar_programa
from compilador.ir import construir_ir
from compilador.cfg import construir_cfg
from compilador.ssa import construir_ssa
from backend import compilar


def analisar(fonte):
    return construir_ssa(construir_cfg(construir_ir(analisar_programa(fonte), otimizar=False, nivel=0)))


class TestesSSA(unittest.TestCase):
    def test_se_senao_phi_exato(self):
        p = analisar('''inicio {
            seja x = 1
            seja cond = 1
            se cond {
                x = 2
            } senao {
                x = 3
            }
            escreva(x)
        }''')
        f = [b for b in p.blocos.values() if 'x' in b.phis]
        self.assertEqual(len(f), 1)
        phi = f[0].phis['x']
        self.assertEqual(set(phi.entradas), p.predecessores[f[0].id])
        self.assertEqual(len(set(phi.entradas.values())), 2)
        self.assertEqual(set(phi.entradas.values()), {'x@1', 'x@2'})
        self.assertEqual(f[0].instrucoes[0].usos, (phi.destino,))
        self.assertTrue(p.validar())

    def test_se_sem_senao_usa_valor_anterior(self):
        p = analisar('''inicio {
            seja x: inteiro = 1
            seja t = 0
            se t {
                x = 4
            }
            escreva(x)
        }''')
        phi = next(b.phis['x'] for b in p.blocos.values() if 'x' in b.phis)
        self.assertEqual(set(phi.entradas.values()), {'x@0', 'x@1'})

    def test_enquanto_tem_phi_ciclico(self):
        p = analisar('''inicio {
            seja n = 0
            enquanto n < 3 {
                n = n + 1
            }
            escreva(n)
        }''')
        head = next(b for b in p.blocos.values() if b.papel == 'enquanto:condicao')
        self.assertIn('n', head.phis)
        phi = head.phis['n']
        self.assertEqual(len(phi.entradas), 2)
        self.assertIn(phi.destino, head.instrucoes[0].usos)
        self.assertTrue(p.validar())

    def test_para_continue_une_incremento(self):
        p = analisar('''inicio {
            seja soma = 0
            para i de 1 ate 3 {
                se i == 2 {
                    continue
                }
                soma = soma + i
            }
            escreva(soma)
        }''')
        cond = next(b for b in p.blocos.values() if b.papel == 'para:condicao')
        inc = next(b for b in p.blocos.values() if b.papel == 'para:incremento')
        self.assertIn('i', cond.phis)
        self.assertIn('soma', cond.phis)
        self.assertIn('soma', inc.phis)
        self.assertEqual(len(inc.phis['soma'].entradas), 2)
        self.assertTrue(p.validar())

    def test_para_reavalia_limite_com_renomeacao(self):
        p = analisar('''inicio {
            seja n = 3
            para i de 1 ate n {
                n = n - 1
            }
            escreva(n)
        }''')
        cabecalho = next(b for b in p.blocos.values() if b.papel == 'para:condicao')
        self.assertIn('n', cabecalho.phis)
        self.assertIn(cabecalho.phis['n'].destino, cabecalho.instrucoes[0].usos)
        self.assertTrue(p.validar())

    def test_lacos_aninhados_e_pare(self):
        p = analisar('''inicio {
            seja n = 0
            para i de 1 ate 3 {
                para j de 1 ate 4 {
                    se j == 2 {
                        pare
                    }
                    n = n + 1
                }
                n = n + i
            }
            escreva(n)
        }''')
        self.assertTrue(p.validar())
        self.assertTrue(any(b.phis for b in p.blocos.values()))

    def test_bloco_inalcancavel_nao_produz_versoes(self):
        p = analisar('''inicio {
            seja n = 0
            enquanto n < 10 {
                pare
                n = n + 1
            }
            escreva(n)
        }''')
        inalcan = [b for b in p.blocos.values() if not b.alcancavel]
        self.assertTrue(inalcan)
        self.assertTrue(all(not b.instrucoes and not b.phis for b in inalcan))

    def test_tipo_logico_em_phi(self):
        p = analisar('''inicio {
            seja flag: logico = falso
            seja cond = 1
            se cond {
                flag = verdadeiro
            }
            escreva(flag)
        }''')
        phi = next(b.phis['flag'] for b in p.blocos.values() if 'flag' in b.phis)
        self.assertEqual(phi.tipo, 'logico')
        self.assertEqual(p.tipos['flag'], 'logico')

    def test_erro_na_entrada_de_phi_e_dominancia(self):
        p = analisar('''inicio {
            seja x = 0
            seja t = 1
            se t {
                x = 1
            }
            escreva(x)
        }''')
        phi = next(b.phis['x'] for b in p.blocos.values() if 'x' in b.phis)
        predecessor = next(iter(phi.entradas))
        anterior = phi.entradas.pop(predecessor)
        with self.assertRaisesRegex(ValueError, 'Phi incompleto'):
            p.validar()
        phi.entradas[predecessor] = 'x@9999'
        with self.assertRaisesRegex(ValueError, 'inválido'):
            p.validar()
        phi.entradas[predecessor] = anterior
        self.assertTrue(p.validar())

    def test_ssa_json_deterministico_sem_efeitos_colaterais(self):
        p = analisar('inicio {\n seja a = 2\n escreva(a)\n}')
        s = p.para_json()
        self.assertEqual(s, p.para_json())
        obj = json.loads(s)
        self.assertEqual(obj['versao'], 'RS 0.12')
        self.assertEqual(obj['tipos']['a'], 'inteiro')
        self.assertIn('SSA tipada', p.formatar())

    def test_cli_exporta_ssa_em_json(self):
        with tempfile.TemporaryDirectory() as d:
            pasta = Path(d)
            arq = pasta/'fonte.rts'
            arq.write_text('inicio {\n seja x = 1\n enquanto x < 3 {\n x = x + 1\n }\n escreva(x)\n}', encoding='utf-8')
            out = pasta/'ssa.json'
            exe = pasta/'programa.exe'
            r = subprocess.run([sys.executable, str(RAIZ/'compilar.py'), str(arq),
                                '--alvo', 'windows', '-O', '2', '--mostrar-ssa',
                                '--salvar-ssa', str(out), '-o', str(exe)],
                               capture_output=True, text=True, timeout=15)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertIn('phi(', r.stdout)
            self.assertTrue(exe.read_bytes().startswith(b'MZ'))
            data = json.loads(out.read_text(encoding='utf-8'))
            self.assertTrue(any(b['phis'] for b in data['blocos']))

    def test_regressao_72_binarios_rs11(self):
        referencia = json.loads((RAIZ/'testes/fixtures/rs11_binarios.json').read_text(encoding='utf-8'))
        self.assertEqual(len(referencia), 72)
        for chave, digest in referencia.items():
            nome, alvo, nivel = chave.split('|')
            with self.subTest(programa=nome, alvo=alvo, nivel=nivel):
                programa = analisar_programa((RAIZ/nome).read_text(encoding='utf-8'))
                binario = compilar(programa, alvo, otimizar=nivel != 'O0', nivel=int(nivel[-1]))
                self.assertEqual(hashlib.sha256(binario).hexdigest(), digest)


if __name__ == '__main__':
    unittest.main()
