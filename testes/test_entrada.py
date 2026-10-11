import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))
from sintaxe import ErroCompilacao, analisar_programa
from codigo_nativo import Gerador, carregar_numero, compilar, deslocamento_variavel

FONTE = 'inicio {\n seja numero = 0\n leia(numero)\n escreva(numero)\n}'


class TestesEntradaNativa(unittest.TestCase):
    def executar(self, fonte, entrada):
        if sys.platform == 'win32':
            alvo = 'windows'
        elif sys.platform == 'linux' and os.uname().machine == 'x86_64':
            alvo = 'linux'
        else:
            self.skipTest('Requer Windows x64 ou Linux x86-64')
        with tempfile.TemporaryDirectory() as pasta:
            arquivo = Path(pasta) / ('teste.exe' if alvo == 'windows' else 'teste')
            arquivo.write_bytes(compilar(analisar_programa(fonte), alvo))
            if alvo == 'linux':
                arquivo.chmod(0o755)
            return subprocess.run([str(arquivo)], input=entrada, text=True,
                                  capture_output=True, encoding='utf-8', timeout=8)

    def test_analise_do_comando(self):
        programa = analisar_programa(FONTE)
        self.assertIn(('leia_int', 'numero'), programa.instrucoes)
        for fonte in ('inicio {\n leia(n)\n}', 'inicio {\n seja n = 0\n leia(2)\n}',
                      'inicio {\n seja n = 0\n leia(n + 1)\n}'):
            with self.subTest(fonte=fonte):
                with self.assertRaisesRegex(ErroCompilacao, 'leia|declare'):
                    analisar_programa(fonte)

    def test_entradas_validas_nativas(self):
        for entrada, numero in [('0\n', 0), ('+42\r\n', 42), ('-42\n', -42),
                                ('  19 \n', 19), ('73', 73),
                                ('9223372036854775807\n', 9223372036854775807),
                                ('-9223372036854775808\n', -9223372036854775808)]:
            with self.subTest(entrada=entrada):
                r = self.executar(FONTE, entrada)
                self.assertEqual(r.returncode, 0, r.stderr)
                self.assertEqual(r.stdout, str(numero) + '\n')

    def test_entradas_invalidas_nativas(self):
        for entrada in ('', '\n', 'abc\n', '1.5\n', '12x\n', '-\n', '1 2\n'):
            with self.subTest(entrada=entrada):
                r = self.executar(FONTE, entrada)
                self.assertEqual(r.returncode, 1)
                self.assertIn('entrada invalida', r.stderr + r.stdout)

    def test_limites_de_64_bits(self):
        for entrada in ('9223372036854775808\n', '-9223372036854775809\n'):
            r = self.executar(FONTE, entrada)
            self.assertEqual(r.returncode, 1)
            self.assertIn('64 bits', r.stderr + r.stdout)

    def test_duas_leituras_com_laco(self):
        fonte = '''inicio {
            seja x = 0
            seja total = 0
            para i de 1 ate 3 {
                leia(x)
                total = total + x
            }
            escreva(total)
        }'''
        r = self.executar(fonte, '10\n20\n12\n')
        self.assertEqual((r.returncode, r.stdout), (0, '42\n'))

    def test_instrucoes_curta_e_layout_da_pilha(self):
        for n, tamanho in [(0, 5), (42, 5), (4294967295, 5), (-1, 7),
                            (-2147483648, 7), (4294967296, 10), (-2147483649, 10)]:
            with self.subTest(numero=n):
                g = Gerador()
                carregar_numero(g, n)
                self.assertEqual(len(g.codigo), tamanho)
        self.assertEqual(deslocamento_variavel({'n': 0}, 'n', False), -8)
        self.assertEqual(deslocamento_variavel({'n': 0}, 'n', True), -16)

    def test_importacao_readfile_condicional(self):
        com = compilar(analisar_programa(FONTE), 'windows')
        sem = compilar(analisar_programa('inicio {\n escreva(1)\n}'), 'windows')
        self.assertIn(b'ReadFile', com)
        self.assertNotIn(b'ReadFile', sem)


if __name__ == '__main__':
    unittest.main()
