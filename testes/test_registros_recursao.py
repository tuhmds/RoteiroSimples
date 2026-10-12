"""RS 0.24: registros por valor, chamadas recursivas e erros de pilha."""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))
from compilador.parser import analisar_programa
from compilador.erros import ErroCompilacao
from backend import compilar


class TestesRegistrosRecursao(unittest.TestCase):
    def executar(self, fonte, esperado=None, nivel=8, codigo=0):
        if sys.platform not in ('win32', 'linux'):
            self.skipTest('Requer Windows ou Linux')
        if sys.platform == 'linux' and os.uname().machine != 'x86_64':
            self.skipTest('Requer x86-64')
        alvo = 'windows' if sys.platform == 'win32' else 'linux'
        with tempfile.TemporaryDirectory() as pasta:
            exe = Path(pasta) / ('teste.exe' if alvo == 'windows' else 'teste')
            exe.write_bytes(compilar(analisar_programa(fonte), alvo, nivel=nivel))
            if alvo == 'linux':
                exe.chmod(0o755)
            resultado = subprocess.run([str(exe)], capture_output=True, timeout=8)
        self.assertEqual(resultado.returncode, codigo,
                         resultado.stderr.decode('utf-8', 'replace'))
        if esperado is not None:
            self.assertEqual(resultado.stdout.decode('utf-8'), esperado)
        return resultado

    def test_funcao_registro_por_valor_e_preservacao_original(self):
        fonte = '''tipo Pessoa {
            idade: inteiro
            ativo: logico
        }
        funcao mudar(p: Pessoa) -> inteiro {
            p.idade = 99
            p.ativo = falso
            retorne p.idade
        }
        inicio {
            seja p: Pessoa
            p.idade = 17
            p.ativo = verdadeiro
            escreva(mudar(p))
            escreva(p.idade)
            escreva(p.ativo)
        }'''
        self.executar(fonte, '99\n17\n1\n', nivel=0)
        self.executar(fonte, '99\n17\n1\n', nivel=8)

    def test_registros_em_funcoes_encadeadas_e_locais(self):
        fonte = '''tipo Medida {
            valor: inteiro
            valido: logico
        }
        funcao elevar(m: Medida, vezes: inteiro) -> inteiro {
            se m.valido {
                retorne m.valor * vezes
            } senao {
                retorne 0
            }
        }
        funcao calcular(m: Medida) -> inteiro {
            seja local: Medida
            local.valor = m.valor + 2
            local.valido = m.valido
            retorne elevar(local, 3)
        }
        inicio {
            seja m: Medida
            m.valor = 8
            m.valido = verdadeiro
            escreva(calcular(m))
        }'''
        self.executar(fonte, '30\n')

    def test_fatorial_e_recursao_indireta(self):
        fonte = '''funcao f(n: inteiro) -> inteiro {
            se n == 0 {
                retorne 0
            } senao {
                retorne g(n - 1) + 1
            }
        }
        funcao g(n: inteiro) -> inteiro {
            se n == 0 {
                retorne 0
            } senao {
                retorne f(n - 1) + 1
            }
        }
        inicio {
            escreva(f(8))
            escreva(g(5))
        }'''
        self.executar(fonte, '8\n5\n')

    def test_recursao_sem_terminacao_encerrada_com_erro(self):
        fonte = '''funcao sem_fim(n: inteiro) -> inteiro {
            retorne sem_fim(n)
        }
        inicio {
            escreva(sem_fim(1))
        }'''
        r = self.executar(fonte, codigo=1)
        mensagem = (r.stdout + r.stderr).decode('utf-8', 'replace')
        self.assertIn('limite seguro de pilha', mensagem)

    def test_campos_tipos_e_assinaturas_invalidos(self):
        casos = [
            'tipo P {\n x: inteiro\n}\ninicio {\n seja p: P\n p.y = 2\n}',
            'tipo P {\n x: inteiro\n}\ninicio {\n seja p: P\n p.x = verdadeiro\n}',
            'tipo P {\n x: inteiro\n x: logico\n}\ninicio {\n escreva(1)\n}',
            'tipo P {\n x: inteiro\n}\ninicio {\n seja p: P\n escreva(p)\n}',
            ('tipo A {\n x: inteiro\n}\ntipo B {\n x: inteiro\n}\n'
             'funcao f(v: A) -> inteiro {\n retorne v.x\n}\n'
             'inicio {\n seja b: B\n escreva(f(b))\n}'),
        ]
        for fonte in casos:
            with self.subTest(fonte=fonte):
                with self.assertRaises(ErroCompilacao):
                    analisar_programa(fonte)

    def test_utf8_e_modo_seguro_sem_acentos_nos_comandos(self):
        fonte = 'tipo P {\n x: inteiro\n}\ninicio {\n seja p: P\n escreva("Coração — útil!")\n}'
        self.executar(fonte, 'Coração — útil!\n')
        with self.assertRaisesRegex(ErroCompilacao, 'sem acentos'):
            analisar_programa('início {\n escreva(1)\n}')

if __name__ == '__main__':
    unittest.main()
