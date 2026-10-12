"""RS 0.22: provas de segurança e equivalência de memória entre blocos."""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))
from compilador.ir import construir_ir
from compilador.parser import analisar_programa
from compilador.memory_ssa import construir_memory_ssa
from backend import compilar


def instrucoes(ir):
    for instrucao in ir.instrucoes if hasattr(ir, 'instrucoes') else ir:
        yield instrucao
        if instrucao.operacao == 'se':
            yield from instrucoes(instrucao.argumentos[1]); yield from instrucoes(instrucao.argumentos[2])
        elif instrucao.operacao == 'enquanto':
            yield from instrucoes(instrucao.argumentos[1])
        elif instrucao.operacao == 'para':
            yield from instrucoes(instrucao.argumentos[4])


def executar(fonte, nivel, entrada=''):
    if sys.platform not in ('linux', 'win32'):
        raise unittest.SkipTest('Exige Linux ou Windows.')
    if sys.platform == 'linux' and os.uname().machine != 'x86_64':
        raise unittest.SkipTest('Exige processador x86-64.')
    alvo = 'windows' if sys.platform == 'win32' else 'linux'
    with tempfile.TemporaryDirectory() as pasta:
        caminho = Path(pasta) / ('teste.exe' if alvo == 'windows' else 'teste')
        caminho.write_bytes(compilar(analisar_programa(fonte), alvo, nivel=nivel))
        if alvo == 'linux':
            caminho.chmod(0o755)
        return subprocess.run([str(caminho)], input=entrada, capture_output=True,
                              text=True, encoding='utf-8', timeout=8)


class TestesOtimizacaoEntreBlocos(unittest.TestCase):
    def comparar(self, fonte, saida=None, entrada=''):
        anterior = executar(fonte, 7, entrada)
        novo = executar(fonte, 8, entrada)
        self.assertEqual((anterior.returncode, anterior.stdout, anterior.stderr),
                         (novo.returncode, novo.stdout, novo.stderr))
        if saida is not None:
            self.assertEqual(novo.stdout, saida)
        return novo

    def ir(self, fonte, nivel=8):
        return construir_ir(analisar_programa(fonte), nivel=nivel)

    def test_juncao_com_duas_atribuicoes_iguais(self):
        fonte = '''inicio {
            seja notas: lista[3]
            seja escolha = 0
            leia(escolha)
            se escolha {
                notas[1] = 42
            } senao {
                notas[1] = 42
            }
            escreva(notas[1])
        }'''
        ir = self.ir(fonte)
        self.assertEqual([i.argumentos[0].operacao for i in instrucoes(ir)
                          if i.operacao == 'imprima_num'], ['numero'])
        self.assertTrue(construir_memory_ssa(ir).validar())
        for escolha in ('0\n', '1\n'):
            self.comparar(fonte, '42\n', escolha)

    def test_juncao_com_valores_distintos_nao_substitui(self):
        fonte = '''inicio {
            seja notas: lista[2]
            seja escolha = 0
            leia(escolha)
            se escolha {
                notas[0] = 10
            } senao {
                notas[0] = 11
            }
            escreva(notas[0])
        }'''
        ir = self.ir(fonte)
        self.assertEqual([i.argumentos[0].operacao for i in instrucoes(ir)
                          if i.operacao == 'imprima_num'], ['indice'])
        self.comparar(fonte, '10\n', '1\n')
        self.comparar(fonte, '11\n', '0\n')

    def test_valor_inicial_em_um_dos_caminhos(self):
        fonte = '''inicio {
            seja a: lista[2]
            seja escolha = 0
            leia(escolha)
            a[0] = 7
            se escolha {
                a[0] = 7
            }
            escreva(a[0])
        }'''
        ir = self.ir(fonte)
        self.assertEqual([i.argumentos[0].operacao for i in instrucoes(ir)
                          if i.operacao == 'imprima_num'], ['numero'])
        self.comparar(fonte, '7\n', '0\n')
        self.comparar(fonte, '7\n', '1\n')

    def test_escrita_redundante_dentro_do_ramo(self):
        fonte = '''inicio {
            seja dados: lista[2]
            seja escolha = 0
            leia(escolha)
            dados[0] = 5
            se escolha {
                dados[0] = 5
            } senao {
                dados[0] = 5
            }
            escreva(dados[0])
        }'''
        ir7, ir8 = self.ir(fonte, 7), self.ir(fonte)
        n = lambda ir: sum(i.operacao == 'atribua_indice' for i in instrucoes(ir))
        self.assertGreater(n(ir7), n(ir8))
        self.comparar(fonte, '5\n', '0\n')
        self.comparar(fonte, '5\n', '1\n')

    def test_valor_estavel_em_laco_sem_escritas(self):
        fonte = '''inicio {
            seja a: lista[2]
            seja contador = 0
            a[0] = 9
            enquanto contador < 4 {
                escreva(a[0])
                contador = contador + 1
            }
        }'''
        ir = self.ir(fonte)
        self.assertEqual([i.argumentos[0].operacao for i in instrucoes(ir)
                          if i.operacao == 'imprima_num'], ['numero'])
        self.comparar(fonte, '9\n' * 4)

    def test_laco_com_escrita_muda_valor(self):
        fonte = '''inicio {
            seja a: lista[2]
            seja contador = 0
            a[0] = 9
            enquanto contador < 3 {
                escreva(a[0])
                a[0] = contador
                contador = contador + 1
            }
            escreva(a[0])
        }'''
        ir = self.ir(fonte)
        self.assertEqual([i.argumentos[0].operacao for i in instrucoes(ir)
                          if i.operacao == 'imprima_num'][0], 'indice')
        self.comparar(fonte, '9\n0\n1\n2\n')

    def test_leitura_entrada_invalida_uma_lista_nao_outra(self):
        fonte = '''inicio {
            seja a: lista[2]
            seja b: lista[2]
            a[0] = 4
            b[0] = 8
            leia(a[0])
            escreva(a[0])
            escreva(b[0])
        }'''
        ir = self.ir(fonte)
        self.assertEqual([i.argumentos[0].operacao for i in instrucoes(ir)
                          if i.operacao == 'imprima_num'], ['indice', 'numero'])
        self.comparar(fonte, '15\n8\n', '15\n')

    def test_indice_dinamico_invalida_so_objeto_alterado(self):
        fonte = '''inicio {
            seja a: lista[2]
            seja b: lista[2]
            seja pos = 0
            a[0] = 4
            b[0] = 8
            leia(pos)
            a[pos] = 99
            escreva(a[0])
            escreva(b[0])
        }'''
        ir = self.ir(fonte)
        self.assertEqual([i.argumentos[0].operacao for i in instrucoes(ir)
                          if i.operacao == 'imprima_num'], ['indice', 'numero'])
        self.comparar(fonte, '99\n8\n', '0\n')
        resultado = self.comparar(fonte, entrada='-1\n')
        self.assertEqual(resultado.returncode, 1)

    def test_divisao_por_zero_nao_e_suprimida(self):
        fonte = '''inicio {
            seja a: lista[2]
            seja escolha = 0
            a[0] = 10
            se escolha {
                a[0] = 10
            } senao {
                a[0] = 10
            }
            escreva(2 / 0)
            escreva(a[0])
        }'''
        resultado = self.comparar(fonte)
        self.assertEqual(resultado.returncode, 1)
        self.assertNotIn('10\n', resultado.stdout)

    def test_estouro_e_indices_invalidos_continuam_falhando(self):
        fontes = [
            'inicio {\n seja a: lista[2]\n a[0] = 9223372036854775807\n escreva(a[0] + 1)\n}',
            'inicio {\n seja a: lista[2]\n a[2] = 0\n escreva(a[0])\n}',
            'inicio {\n seja a: lista[2]\n escreva(a[-1])\n}',
        ]
        for fonte in fontes:
            with self.subTest(fonte=fonte):
                resultado = self.comparar(fonte)
                self.assertEqual(resultado.returncode, 1)

    def test_texto_utf8_mantido_e_referencia_nao_inventada(self):
        fonte = '''inicio {
            seja a: lista[2]
            seja mensagem: texto[24]
            a[0] = 7
            copie(mensagem, "Ação e razão")
            escreva(mensagem)
            escreva(a[0])
        }'''
        self.comparar(fonte, 'Ação e razão\n7\n')

    def test_opcoes_tecnicas_em_portugues(self):
        with tempfile.TemporaryDirectory() as pasta:
            destino = Path(pasta) / ('exemplo.exe' if sys.platform == 'win32' else 'exemplo')
            relatorio = Path(pasta) / 'memoria.json'
            comando = [sys.executable, str(RAIZ / 'compilar.py'),
                       str(RAIZ / 'exemplos' / 'memoria_entre_blocos.rts'),
                       '--alvo', 'windows' if sys.platform == 'win32' else 'linux',
                       '-O', '8', '--mostrar-memoria-versionada',
                       '--salvar-memoria-versionada', str(relatorio),
                       '--mostrar-representacao-intermediaria',
                       '-o', str(destino)]
            resultado = subprocess.run(comando, capture_output=True, text=True,
                                      encoding='utf-8', timeout=12)
            self.assertEqual(resultado.returncode, 0, resultado.stderr)
            self.assertIn('Memoria versionada em atribuicao unica', resultado.stdout)
            self.assertIn('juncao(', resultado.stdout)
            self.assertTrue(destino.exists())
            self.assertTrue(relatorio.exists())

    def test_oitavo_nivel_nao_altera_binarios_sem_listas(self):
        programa = analisar_programa('inicio {\n seja x = 2\n escreva(x * 5)\n}')
        for alvo in ('windows', 'linux'):
            self.assertEqual(compilar(programa, alvo, nivel=7),
                             compilar(programa, alvo, nivel=8))


if __name__ == '__main__':
    unittest.main()
