"""RS 0.17: listas contiguas na pilha e verificacao obrigatoria de indices."""
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


class TestesListas(unittest.TestCase):
    def executar(self, codigo, nivel=6, entrada=''):
        if sys.platform != 'win32' and (sys.platform != 'linux' or os.uname().machine != 'x86_64'):
            self.skipTest('Execucao nativa exige Linux x86-64 ou Windows x86-64')
        alvo = 'windows' if sys.platform == 'win32' else 'linux'
        with tempfile.TemporaryDirectory() as d:
            exe = Path(d) / ('teste.exe' if alvo == 'windows' else 'teste')
            exe.write_bytes(compilar(analisar_programa(codigo), alvo, nivel=nivel))
            if alvo == 'linux':
                exe.chmod(0o755)
            return subprocess.run([str(exe)], input=entrada, text=True,
                                  capture_output=True, timeout=5)

    def test_memoria_contigua_zerada_e_limites_inclusivos(self):
        codigo = '''inicio {
            seja antes = 9
            seja v: lista[5]
            seja depois = 11
            v[0] = 10
            v[4] = 50
            escreva(v[0] + v[4])
            escreva(v[2])
            escreva(antes)
            escreva(depois)
            escreva(tamanho(v))
        }'''
        for o in (0, 1, 2, 3, 4, 5, 6):
            with self.subTest(nivel=o):
                r = self.executar(codigo, o)
                self.assertEqual((r.returncode, r.stdout), (0, '60\n0\n9\n11\n5\n'), r.stderr)

    def test_para_soma_e_outros_valores(self):
        codigo = '''inicio {
            seja n: lista[5]
            seja total = 0
            para i de 0 ate tamanho(n) - 1 {
                n[i] = (i + 1) * 10
                total = total + n[i]
            }
            escreva(total)
        }'''
        self.assertEqual((self.executar(codigo).returncode, self.executar(codigo).stdout), (0, '150\n'))

    def test_limites_negativo_igual_tamanho_e_muito_alto(self):
        for indice in ('-1', '2', '9223372036854775807'):
            with self.subTest(indice=indice):
                codigo = f'inicio {{\n seja a: lista[2]\n escreva(a[{indice}])\n}}'
                r = self.executar(codigo)
                self.assertEqual(r.returncode, 1)
                self.assertIn('fora dos limites', r.stdout + r.stderr)
                codigo = f'inicio {{\n seja a: lista[2]\n a[{indice}] = 99\n}}'
                r = self.executar(codigo)
                self.assertEqual(r.returncode, 1)
                self.assertIn('fora dos limites', r.stdout + r.stderr)

    def test_leia_indice_e_variavel(self):
        codigo = '''inicio {
            seja n: lista[3]
            seja indice = 1
            leia(n[indice])
            escreva(n[indice])
        }'''
        r = self.executar(codigo, entrada='42\n')
        self.assertEqual((r.returncode, r.stdout), (0, '42\n'))

    def test_declaracoes_e_tipos_invalidos(self):
        fontes = [
            'seja n: lista[0]', 'seja n: lista[x]',
            'seja n: lista[2]\n escreva(n)',
            'seja n: lista[2]\n n = 3',
            'seja n: lista[2]\n n[verdadeiro] = 1',
            'seja n = 2\n escreva(n[0])',
            'seja n: lista[2]\n escreva(n[0] + verdadeiro)',
            'seja n: lista[2]\n escreva(tamanho(1))',
        ]
        for texto in fontes:
            with self.subTest(codigo=texto):
                with self.assertRaises(ErroCompilacao):
                    analisar_programa('inicio {\n ' + texto + '\n}')

    def test_256_posicoes_e_limites_maiores(self):
        codigo = 'inicio {\n seja n: lista[256]\n escreva(n[255])\n}'
        r = self.executar(codigo)
        self.assertEqual((r.returncode, r.stdout), (0, '0\n'), r.stderr)

    def test_versoes_anteriores_nao_mudaram(self):
        codigo = 'inicio {\n seja a = 2\n escreva(a + 3)\n}'
        for o in range(7):
            self.assertEqual(self.executar(codigo, o).stdout, '5\n')


if __name__ == '__main__':
    unittest.main()
