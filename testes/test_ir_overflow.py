"""Testes do contrato de overflow e da IR tipada em Windows e Linux x86-64."""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

from sintaxe import analisar_programa, ErroCompilacao
from codigo_nativo import compilar
from ir import construir_ir, formatar_ir, ExpressaoIR, programa_para_backend


def executar(fonte, otimizar=True, entrada=None):
    alvo = 'windows' if sys.platform == 'win32' else 'linux'
    with tempfile.TemporaryDirectory() as pasta:
        executavel = Path(pasta) / ('codigo.exe' if alvo == 'windows' else 'codigo')
        executavel.write_bytes(compilar(analisar_programa(fonte), alvo, otimizar=otimizar))
        if alvo == 'linux':
            executavel.chmod(0o755)
        return subprocess.run([str(executavel)], input=entrada, capture_output=True,
                              text=True, encoding='utf-8', timeout=5)


class TestesIR(unittest.TestCase):
    def test_tipos_ir_e_retorno_ao_backend(self):
        programa = analisar_programa('inicio {\n seja valor: inteiro = 2 + 3 * 4\n seja ok = valor >= 10\n escreva(ok)\n}')
        ir = construir_ir(programa)
        self.assertEqual(ir.tipos, {'valor': 'inteiro', 'ok': 'logico'})
        atrib = ir.instrucoes[0]
        self.assertEqual((atrib.operacao, atrib.argumentos[1].tipo), ('atribua', 'inteiro'))
        self.assertEqual((atrib.argumentos[1].operacao, atrib.argumentos[1].valor), ('numero', 14))
        self.assertIn('comparacao:logico', formatar_ir(ir))
        self.assertEqual(programa_para_backend(ir).variaveis, programa.variaveis)

    def test_otimizacao_nao_dobra_erro_em_constantes(self):
        casos = ['9223372036854775807 + 1', '-9223372036854775808 - 1',
                 '3037000500 * 3037000500', '-(-9223372036854775808)',
                 '10 / 0', '-9223372036854775808 / -1']
        for conta in casos:
            with self.subTest(conta=conta):
                ir = construir_ir(analisar_programa(f'inicio {{\n escreva({conta})\n}}'))
                e = ir.instrucoes[0].argumentos[0]
                self.assertNotIn(e.operacao, ('numero', 'logico'))

    def test_divisao_truncada_e_resto_com_sinal(self):
        ir = construir_ir(analisar_programa('inicio {\n escreva(-17 / 5)\n escreva(-17 % 5)\n}'))
        self.assertEqual([x.argumentos[0].valor for x in ir.instrucoes], [-3, -2])

    def test_ir_reduz_codigo(self):
        programa = analisar_programa('inicio {\n escreva((2 + 3) * (4 + 5) - 6)\n}')
        compilado_o0 = compilar(programa, 'linux', otimizar=False)
        compilado_o1 = compilar(programa, 'linux', otimizar=True)
        self.assertLess(len(compilado_o1), len(compilado_o0))
        self.assertEqual(construir_ir(programa).instrucoes[0].argumentos[0].valor, 39)

    def test_ir_aninhada_e_variaveis(self):
        programa = analisar_programa('''inicio {
            seja i: inteiro = 0
            enquanto i < 3 {
                i = i + 1
                se i == 2 {
                    escreva("dois")
                }
            }
        }''')
        ir = construir_ir(programa)
        self.assertEqual(ir.instrucoes[1].operacao, 'enquanto')
        self.assertEqual(ir.instrucoes[1].argumentos[1][1].operacao, 'se')


class TestesOverflowNativo(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if sys.platform not in ('linux', 'win32'):
            raise unittest.SkipTest('Exige Windows ou Linux')
        if sys.platform == 'linux' and os.uname().machine != 'x86_64':
            raise unittest.SkipTest('Exige Linux x86-64')

    def test_adicao_subtracao_multiplicacao_negacao(self):
        casos = [
            ('9223372036854775807 + 1', 'estouro aritm'),
            ('-9223372036854775808 - 1', 'estouro aritm'),
            ('3037000500 * 3037000500', 'estouro aritm'),
            ('-(-9223372036854775808)', 'estouro aritm'),
            ('-9223372036854775808 / -1', 'fora do limite'),
            ('17 / 0', 'divisão por zero'),
        ]
        for conta, mensagem in casos:
            for otimizar in (False, True):
                with self.subTest(conta=conta, otimizar=otimizar):
                    r = executar(f'inicio {{\n escreva({conta})\n}}', otimizar)
                    self.assertEqual(r.returncode, 1)
                    self.assertIn(mensagem, r.stdout + r.stderr)

    def test_operacoes_com_valor_lido(self):
        casos = [('x + 1', '9223372036854775807\n'),
                 ('x - 1', '-9223372036854775808\n'),
                 ('x * 2', '9223372036854775807\n'),
                 ('-x', '-9223372036854775808\n')]
        for expr, entrada in casos:
            fonte = f'inicio {{\n seja x: inteiro = 0\n leia(x)\n escreva({expr})\n}}'
            for otimizar in (False, True):
                with self.subTest(expr=expr, entrada=entrada, otimizar=otimizar):
                    r = executar(fonte, otimizar, entrada)
                    self.assertEqual(r.returncode, 1)
                    self.assertIn('estouro aritm', r.stdout + r.stderr)

    def test_limites_validos_e_equivalencia(self):
        fonte = '''inicio {
            escreva(9223372036854775807)
            escreva(-9223372036854775808)
            escreva(-17 / 5)
            escreva(-17 % 5)
            escreva(2 + 3 * 4)
        }'''
        esperado = '9223372036854775807\n-9223372036854775808\n-3\n-2\n14\n'
        for otimizar in (False, True):
            r = executar(fonte, otimizar)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertEqual(r.stdout, esperado)

    def test_overflow_no_laco_para_nao_trava(self):
        # A atualização interna do contador é especial: encerra o laço no limite.
        fonte = '''inicio {
            para i de 9223372036854775806 ate 9223372036854775807 {
                escreva(i)
            }
        }'''
        for otimizar in (False, True):
            r = executar(fonte, otimizar)
            self.assertEqual((r.returncode, r.stdout),
                             (0, '9223372036854775806\n9223372036854775807\n'))

    def test_programa_com_entrada_e_ramos(self):
        fonte = '''inicio {
            seja n: inteiro = 0
            leia(n)
            se n < 0 {
                escreva(-n)
            } senao {
                escreva(n + 2 * 5)
            }
        }'''
        for otimizar in (False, True):
            r = executar(fonte, otimizar, '4\n')
            self.assertEqual((r.returncode, r.stdout), (0, '14\n'))
            erro = executar(fonte, otimizar, '-9223372036854775808\n')
            self.assertEqual(erro.returncode, 1)
            self.assertIn('estouro aritm', erro.stdout + erro.stderr)


if __name__ == '__main__':
    unittest.main()
