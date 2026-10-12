"""RS 0.23: escopos, chamadas nativas e dimensionamento seguro da memória."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))
from compilador.parser import analisar_programa
from compilador.erros import ErroCompilacao
from backend import compilar


class TestesFundacao(unittest.TestCase):
    def executar(self, fonte, esperado, entrada=b'', nivel=8):
        if sys.platform not in ('linux', 'win32'):
            self.skipTest('Necessário Windows ou Linux')
        if sys.platform == 'linux' and os.uname().machine != 'x86_64':
            self.skipTest('Necessário processador x86-64')
        p = analisar_programa(fonte)
        alvo = 'windows' if sys.platform == 'win32' else 'linux'
        with tempfile.TemporaryDirectory() as pasta:
            caminho = Path(pasta) / ('prog.exe' if alvo == 'windows' else 'prog')
            caminho.write_bytes(compilar(p, alvo, nivel=nivel))
            if alvo == 'linux':
                caminho.chmod(0o755)
            proc = subprocess.run([str(caminho)], input=entrada, capture_output=True, timeout=8)
        self.assertEqual(proc.returncode, 0, proc.stderr.decode('utf-8', errors='replace'))
        self.assertEqual(proc.stdout.decode('utf-8'), esperado)

    def test_escopos_sombreamento_e_visibilidade(self):
        fonte = '''inicio {
            seja numero = 1
            se verdadeiro {
                seja numero = 10
                escreva(numero)
                se numero > 5 {
                    seja numero = 20
                    escreva(numero)
                }
                escreva(numero)
            }
            escreva(numero)
        }'''
        p = analisar_programa(fonte)
        self.assertEqual(len(p.variaveis), 3)
        self.executar(fonte, '10\n20\n10\n1\n')

    def test_variavel_nao_vaza_para_fora_do_escopo(self):
        with self.assertRaisesRegex(ErroCompilacao, 'não foi declarada'):
            analisar_programa('inicio {\n se 1 {\n seja segredo = 10\n }\n escreva(segredo)\n}')
        with self.assertRaisesRegex(ErroCompilacao, 'duplicada'):
            analisar_programa('inicio {\n seja x=1\n seja x=2\n}')

    def test_escopo_com_lista_e_texto(self):
        fonte = '''inicio {
            seja numero = 7
            se 1 {
                seja notas: lista[3]
                notas[0] = numero
                escreva(notas[0])
                seja saudacao: texto[48]
                copie(saudacao, "Olá")
                escreva(saudacao)
            }
        }'''
        self.executar(fonte, '7\nOlá\n')

    def test_funcoes_com_parametros_tipos_e_retorno(self):
        fonte = '''funcao calcular_total(preco: inteiro, quantidade: inteiro) -> inteiro {
            seja total: inteiro = preco * quantidade
            retorne total
        }
        inicio {
            escreva(calcular_total(25, 4))
            escreva(calcular_total(3, 7))
        }'''
        self.executar(fonte, '100\n21\n')

    def test_funcoes_encadeadas_e_aninhadas_em_expressoes(self):
        fonte = '''funcao dobro(valor: inteiro) -> inteiro {
            retorne valor * 2
        }
        funcao quadruplicar(valor: inteiro) -> inteiro {
            retorne dobro(dobro(valor))
        }
        inicio {
            escreva(4 + quadruplicar(3) * 2)
            escreva(dobro(quadruplicar(4) + 1))
        }'''
        self.executar(fonte, '28\n34\n')

    def test_retornos_condicionais_e_logicos(self):
        fonte = '''funcao maximo(a: inteiro, b: inteiro) -> inteiro {
            se a > b {
                retorne a
            } senao {
                retorne b
            }
        }
        funcao pode_votar(idade: inteiro) -> logico {
            retorne idade >= 16
        }
        inicio {
            escreva(maximo(2, 7))
            escreva(maximo(10, 3))
            se pode_votar(18) {
                escreva("Sim")
            }
        }'''
        self.executar(fonte, '7\n10\nSim\n')

    def test_funcoes_com_lacos_e_locais(self):
        fonte = '''funcao triangular(n: inteiro) -> inteiro {
            seja soma = 0
            para i de 1 ate n {
                soma = soma + i
            }
            retorne soma
        }
        inicio {
            escreva(triangular(10))
            escreva(triangular(4))
        }'''
        self.executar(fonte, '55\n10\n')

    def test_funcao_sem_parametros(self):
        fonte = '''funcao resposta() -> inteiro {
            retorne 42
        }
        inicio {
            escreva(8 + resposta())
        }'''
        self.executar(fonte, '50\n')

    def test_erro_tipo_arity_e_retorno(self):
        corpo = 'funcao f(a: inteiro) -> inteiro {\n retorne a\n}\ninicio {\n escreva(f(%s))\n}'
        for argumento in ('verdadeiro', '1, 2', ''):
            with self.subTest(argumento=argumento):
                with self.assertRaisesRegex(ErroCompilacao, 'argumento|espera|recebeu'):
                    analisar_programa(corpo % argumento)
        with self.assertRaisesRegex(ErroCompilacao, 'tipo incompatível'):
            analisar_programa('funcao f() -> inteiro {\n retorne verdadeiro\n}\ninicio {\n escreva(1)\n}')
        with self.assertRaisesRegex(ErroCompilacao, 'todos os caminhos'):
            analisar_programa('funcao f(a: inteiro) -> inteiro {\n se a {\n retorne a\n }\n}\ninicio {\n escreva(1)\n}')
        with self.assertRaisesRegex(ErroCompilacao, 'dentro de função'):
            analisar_programa('inicio {\n retorne 1\n}')

    def test_chamadas_dentro_de_indices_e_atribuicoes(self):
        fonte = '''funcao mais_um(valor: inteiro) -> inteiro {
            retorne valor + 1
        }
        inicio {
            seja numeros: lista[8]
            numeros[mais_um(2)] = mais_um(40)
            escreva(numeros[mais_um(2)])
            escreva(numeros[3] + mais_um(1))
        }'''
        self.executar(fonte, '41\n43\n')

    def test_multiplos_argumentos_e_chamada_sem_argumentos(self):
        fonte = '''funcao nove() -> inteiro {
            retorne 9
        }
        funcao somar_quatro(a: inteiro, b: inteiro, c: inteiro, d: inteiro) -> inteiro {
            retorne a + b + c + d
        }
        inicio {
            escreva(somar_quatro(1, nove(), nove() + 1, 2))
        }'''
        self.executar(fonte, '22\n')

    def test_recursao_reconhecida_e_limitada(self):
        fonte = 'funcao f(n: inteiro) -> inteiro {\n retorne f(n)\n}\ninicio {\n escreva(f(1))\n}'
        programa = analisar_programa(fonte)
        self.assertTrue(programa.funcoes['f'].recursiva)
        fonte2 = ('funcao f(n: inteiro) -> inteiro {\n retorne g(n)\n}\n'
                  'funcao g(n: inteiro) -> inteiro {\n retorne f(n)\n}\n'
                  'inicio {\n escreva(1)\n}')
        programa2 = analisar_programa(fonte2)
        self.assertTrue(programa2.funcoes['f'].recursiva)
        self.assertTrue(programa2.funcoes['g'].recursiva)

    def test_mais_de_256_locais_e_pilha_sondada(self):
        fonte = ('inicio {\n' + '\n'.join(f'seja v{i} = {i}' for i in range(900))
                 + '\n escreva(v899)\n}')
        self.executar(fonte, '899\n')

    def test_lista_e_texto_acima_do_limite_antigo(self):
        self.executar('inicio {\n seja dados: lista[500]\n dados[499]=9\n escreva(dados[499])\n}', '9\n')
        self.executar('inicio {\n seja msg: texto[5000]\n copie(msg,"Olá, mundo!")\n escreva(msg)\n escreva(capacidade(msg))\n}', 'Olá, mundo!\n5000\n')

    def test_secao_pe_dinamica(self):
        fonte = 'inicio {\n' + '\n'.join(f'escreva({i})' for i in range(1000)) + '\n}'
        import struct
        binario = compilar(analisar_programa(fonte), 'windows', nivel=0)
        self.assertEqual(binario[:2], b'MZ')
        deslocamento = struct.unpack_from('<I', binario, 0x3c)[0]
        self.assertEqual(binario[deslocamento:deslocamento+4], b'PE\0\0')
        self.assertGreater(len(binario), 4096)
        # Primeira seção > 4 KiB: dados importados não podem sobrepor código.
        text_size = struct.unpack_from('<I', binario, 0x98+0xF0+8)[0]
        self.assertGreater(text_size, 4096)


if __name__ == '__main__':
    unittest.main()
