"""RS 0.11: fluxo de dados real e otimização O2 conservadora."""
import json
import os
import struct
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))
from compilador.cfg import construir_cfg
from compilador.fluxo_dados import analisar_fluxo
from compilador.ir import construir_ir, formatar_ir
from compilador.parser import analisar_programa
from backend import compilar


def fluxo(fonte):
    return analisar_fluxo(construir_cfg(construir_ir(analisar_programa(fonte))))


def executar(fonte, nivel, entrada=''):
    alvo = 'windows' if sys.platform == 'win32' else 'linux'
    if alvo == 'linux' and os.uname().machine != 'x86_64':
        raise unittest.SkipTest('Requer Linux x86-64')
    if alvo == 'windows' and sys.platform != 'win32':
        raise unittest.SkipTest('Requer Windows')
    with tempfile.TemporaryDirectory() as pasta:
        caminho = Path(pasta)/('programa.exe' if alvo == 'windows' else 'programa')
        caminho.write_bytes(compilar(analisar_programa(fonte), alvo,
                                    otimizar=nivel>0, nivel=nivel))
        if alvo == 'linux':
            caminho.chmod(0o755)
        p = subprocess.run([str(caminho)], input=entrada, capture_output=True,
                           text=True, encoding='utf-8', timeout=5)
        return p.returncode, p.stdout, p.stderr


class TestesFluxoDados(unittest.TestCase):
    def test_reaching_defs_e_phi_no_se(self):
        f = fluxo('''inicio {
            seja x = 1
            seja teste = 0
            se teste {
                x = 2
            } senao {
                x = 3
            }
            escreva(x)
        }''')
        juncoes = [b for b in f.cfg.blocos if 'x' in f.phi_candidatos.get(b, {})]
        self.assertEqual(len(juncoes), 1)
        decisao = juncoes[0]
        self.assertEqual(len(f.phi_candidatos[decisao]['x']), 2)
        self.assertIn('x', f.vivos_entrada[decisao])
        self.assertIn('phi?', f.formatar())
        self.assertIn('x', f.para_json())

    def test_laco_phi_dominadores_e_vivacidade(self):
        f = fluxo('''inicio {
            seja n = 0
            enquanto n < 3 {
                n = n + 1
            }
            escreva(n)
        }''')
        cond = next(b.id for b in f.cfg.blocos.values() if b.papel=='enquanto:condicao')
        self.assertIn('n', f.phi_candidatos[cond])
        self.assertEqual(len(f.phi_candidatos[cond]['n']), 2)
        self.assertIn('n', f.vivos_entrada[cond])
        self.assertIn(f.cfg.entrada, f.dominadores[cond])
        self.assertTrue(all(f.cfg.entrada in f.dominadores[b]
                            for b in f.cfg.alcancaveis()))

    def test_para_incrementa_com_continue(self):
        f = fluxo('''inicio {
            seja soma = 0
            para i de 1 ate 3 {
                se i == 2 {
                    continue
                }
                soma = soma + i
            }
            escreva(soma)
        }''')
        inc = next(b.id for b in f.cfg.blocos.values() if b.papel=='para:incremento')
        cond = next(b.id for b in f.cfg.blocos.values() if b.papel=='para:condicao')
        ini = next(b.id for b in f.cfg.blocos.values() if b.papel=='para:inicio')
        self.assertEqual(f.definicoes[ini], {'i'})
        self.assertEqual(f.definicoes[inc], {'i'})
        self.assertEqual(f.usos[inc], {'i'})
        self.assertIn('i', f.phi_candidatos[cond])
        self.assertTrue(any('soma' in d for d in f.saidas_def[cond]))

    def test_inalcancavel_ignorado(self):
        f = fluxo('''inicio {
            seja n = 1
            enquanto n {
                pare
                n = 20
            }
            escreva(n)
        }''')
        mortos = f.cfg.inalcancaveis()
        self.assertTrue(mortos)
        self.assertTrue(all(not f.entradas_def[b] for b in mortos))
        self.assertTrue(all(not f.dominadores[b] for b in mortos))
        self.assertTrue(all(not f.vivos_entrada[b] for b in mortos))

    def test_nao_inventa_phi_para_ramificacoes_iguais(self):
        f = fluxo('''inicio {
            seja x = 1
            se x {
                escreva(2)
            } senao {
                escreva(3)
            }
            escreva(x)
        }''')
        self.assertFalse(any('x' in p for p in f.phi_candidatos.values()))

    def test_json_valido_e_deterministico(self):
        f = fluxo('inicio {\n seja x = 1\n escreva(x)\n}')
        raw = f.para_json()
        self.assertEqual(raw, f.para_json())
        j = json.loads(raw)
        self.assertEqual(j['versao'], 'RS 0.11')
        self.assertTrue(any('vivas_entrada' in b for b in j['blocos']))
        self.assertIn('nao sao SSA', j['observacao'])

    def test_o0_o1_preservados_o2_gera_menos_codigo(self):
        p = analisar_programa('inicio {\n seja a = 2\n seja b = a * 3 + 4\n escreva(b)\n}')
        o1 = construir_ir(p, otimizar=True, nivel=1)
        o2 = construir_ir(p, otimizar=True, nivel=2)
        self.assertEqual(o1.instrucoes[1].argumentos[1].operacao, 'bin')
        self.assertEqual(o2.instrucoes[1].argumentos[1].valor, 10)
        self.assertEqual(o2.instrucoes[2].argumentos[0].valor, 10)
        tamanho1 = len(compilar(p, 'linux', otimizar=True, nivel=1))
        tamanho2 = len(compilar(p, 'linux', otimizar=True, nivel=2))
        self.assertLess(tamanho2, tamanho1)

    def test_regressao_diferencial_tres_niveis(self):
        programas = [
            ('inicio {\n seja a = 2\n seja b = a * 3 + 4\n escreva(b)\n}', '', (0,'10\n','')),
            ('inicio {\n seja a = 1\n se a {\n a = 3\n }\n escreva(a)\n}', '', (0,'3\n','')),
            ('inicio {\n seja a = 0\n enquanto a < 4 {\n a = a + 1\n }\n escreva(a)\n}', '', (0,'4\n','')),
            ('inicio {\n seja x = 7\n leia(x)\n escreva(x)\n}', '41\n', (0,'41\n','')),
            ('inicio {\n seja x = 9223372036854775807\n seja y = x + 1\n escreva(y)\n}', '', (1,'','estouro aritmético')),
            ('inicio {\n seja x = 0\n escreva(5 / x)\n}', '', (1,'','divisão por zero')),
            ('inicio {\n seja x = 1\n se x {\n x = 0\n }\n escreva(x)\n}', '', (0,'0\n','')),
            ('inicio {\n seja n = 2\n para i de 1 ate n {\n escreva(i)\n n = n + 1\n se i == 3 {\n pare\n }\n }\n}', '', (0,'1\n2\n3\n','')),
            ('inicio {\n seja n = 0\n se n == 0 {\n escreva("Olá!")\n }\n}', '', (0,'Olá!\n','')),
        ]
        for codigo, entrada, esperado in programas:
            with self.subTest(codigo=codigo[:32]):
                resultados = [executar(codigo, nivel, entrada) for nivel in (0, 1, 2)]
                self.assertEqual(resultados[0], resultados[1])
                self.assertEqual(resultados[1], resultados[2])
                self.assertEqual(resultados[0][0], esperado[0])
                if esperado[0] == 0:
                    self.assertEqual(resultados[0][1], esperado[1])
                    self.assertEqual(resultados[0][2], esperado[2])
                else:
                    # No PE/Windows, o backend legado escreve erros em stdout;
                    # no ELF/Linux, escreve em stderr. Aceitamos ambos e
                    # verificamos um trecho ASCII da mensagem nas duas plataformas.
                    diagnostico = resultados[0][1] + resultados[0][2]
                    self.assertIn('Erro:', diagnostico)
                    trecho = 'estouro aritm' if 'estouro' in esperado[2] else 'divis'
                    self.assertIn(trecho, diagnostico)

    def test_cli_exibe_e_salva_fluxo_o2(self):
        with tempfile.TemporaryDirectory() as pasta:
            pasta = Path(pasta)
            programa = pasta/'fluxo.rts'
            programa.write_text('inicio {\n seja a = 2\n seja b = a + 3\n escreva(b)\n}', encoding='utf-8')
            binario = pasta/('demo.exe' if sys.platform=='win32' else 'demo')
            dados = pasta/'analise.json'
            p = subprocess.run([sys.executable, str(RAIZ/'compilar.py'), str(programa),
                                '-O', '2', '--alvo', 'windows' if sys.platform=='win32' else 'linux',
                                '--mostrar-ir', '--mostrar-fluxo', '--salvar-fluxo', str(dados),
                                '-o',str(binario)], capture_output=True, text=True, timeout=10)
            self.assertEqual(p.returncode,0,p.stderr)
            self.assertIn('RS 0.11 - Fluxo',p.stdout)
            self.assertIn('numero:inteiro(5)',p.stdout)
            self.assertTrue(dados.exists())
            self.assertEqual(json.loads(dados.read_text(encoding='utf-8'))['versao'], 'RS 0.11')
            self.assertTrue(binario.exists())
            self.assertEqual(binario.read_bytes()[:2],b'MZ' if sys.platform=='win32' else b'\x7fE')


if __name__ == '__main__':
    unittest.main()
