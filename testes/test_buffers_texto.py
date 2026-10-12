"""RS 0.18: buffers UTF-8 de capacidade fixa, runtime e diagnósticos."""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))
from compilador.erros import ErroCompilacao
from compilador.parser import analisar_programa
from backend import compilar


class TestesBuffers(unittest.TestCase):
    def executar(self, codigo, *, entrada=b'', nivel=6):
        if sys.platform not in ('win32', 'linux'):
            self.skipTest('Executável requer Windows ou Linux x86-64')
        if sys.platform == 'linux' and os.uname().machine != 'x86_64':
            self.skipTest('Executável requer x86-64')
        alvo = 'windows' if sys.platform == 'win32' else 'linux'
        with tempfile.TemporaryDirectory() as pasta:
            arq = Path(pasta) / ('exemplo.exe' if alvo == 'windows' else 'exemplo')
            arq.write_bytes(compilar(analisar_programa(codigo), alvo, nivel=nivel))
            if alvo == 'linux':
                arq.chmod(0o755)
            return subprocess.run([str(arq)], input=entrada, capture_output=True, timeout=8)

    def test_copie_junte_limpe_tamanho_e_capacidade(self):
        codigo = '''inicio {
            seja nome: texto[48]
            seja outro: texto[32]
            copie(nome, "Olá, ")
            copie(outro, "mundo 🌎")
            junte(nome, outro)
            escreva(nome)
            escreva(tamanho(nome))
            escreva(capacidade(nome))
            limpe(outro)
            escreva(tamanho(outro))
            copie(outro, nome)
            escreva(outro)
        }'''
        esperado = 'Olá, mundo 🌎\n16\n48\n0\nOlá, mundo 🌎\n'.encode('utf-8')
        for nivel in range(7):
            with self.subTest(nivel=nivel):
                r = self.executar(codigo, nivel=nivel)
                self.assertEqual((r.returncode, r.stdout), (0, esperado), r.stderr)

    def test_copia_si_mesma_e_concatena_mesma_fonte(self):
        r = self.executar('inicio {\n seja a: texto[9]\n copie(a,"abc")\n copie(a,a)\n junte(a,a)\n escreva(a)\n}')
        self.assertEqual((r.returncode, r.stdout), (0, b'abcabc\n'), r.stderr)

    def test_memoria_de_vizinhos_e_lista_preservada(self):
        r = self.executar('''inicio {
            seja primeiro = 99
            seja a: texto[9]
            seja numeros: lista[2]
            seja outro: texto[10]
            seja ultimo = 77
            numeros[0] = 11
            numeros[1] = 22
            copie(a, "abc")
            copie(outro, "X")
            junte(outro, a)
            escreva(outro)
            escreva(primeiro)
            escreva(ultimo)
            escreva(numeros[0] + numeros[1])
        }''')
        self.assertEqual((r.returncode, r.stdout), (0, b'Xabc\n99\n77\n33\n'), r.stderr)

    def test_limite_em_tempo_de_compilacao_e_execucao(self):
        with self.assertRaisesRegex(ErroCompilacao, 'capacidade'):
            analisar_programa('inicio {\n seja a: texto[3]\n copie(a,"ação")\n}')
        r = self.executar('inicio {\n seja a: texto[4]\n copie(a,"á")\n junte(a,"éé")\n escreva(a)\n}')
        self.assertEqual(r.returncode, 1)
        self.assertIn(b'capacidade', r.stdout + r.stderr)
        r = self.executar('inicio {\n seja a: texto[2]\n seja b: texto[6]\n copie(b,"mundo")\n copie(a,b)\n}')
        self.assertEqual(r.returncode, 1)
        self.assertIn(b'capacidade', r.stdout + r.stderr)

    def test_leitura_utf8_e_crlf(self):
        codigo = 'inicio {\n seja buf: texto[16]\n leia(buf)\n escreva(buf)\n escreva(tamanho(buf))\n}'
        for entrada, esperado in (("Café\r\n".encode(), 'Café\n5\n'.encode()),
                                  ("🌎\n".encode(), "🌎\n4\n".encode()),
                                  (b'Bom\n', b'Bom\n3\n'),
                                  (b'', b'\n0\n')):
            with self.subTest(entrada=entrada):
                r = self.executar(codigo, entrada=entrada)
                self.assertEqual((r.returncode, r.stdout), (0, esperado), r.stderr)

    def test_rejeita_utf8_invalido(self):
        codigo = 'inicio {\n seja buf: texto[16]\n leia(buf)\n escreva(buf)\n}'
        para_rejeitar = [b'\xc0\xaf\n', b'\xe2\x82\n', b'\xed\xa0\x80\n',
                         b'\xf4\x90\x80\x80\n', b'\xe0\x80\x80\n',
                         b'\xf0\x80\x80\x80\n', b'\x80\n']
        for entrada in para_rejeitar:
            with self.subTest(entrada=entrada):
                r = self.executar(codigo, entrada=entrada)
                self.assertEqual(r.returncode, 1)
                self.assertIn(b'UTF-8', r.stdout + r.stderr)

    def test_nao_trunca_entrada_acima_da_capacidade(self):
        codigo = 'inicio {\n seja buf: texto[4]\n leia(buf)\n escreva(buf)\n}'
        for entrada in (b'ABCDE\n', 'ééé\n'.encode('utf-8')):
            with self.subTest(entrada=entrada):
                r = self.executar(codigo, entrada=entrada)
                self.assertEqual(r.returncode, 1)
                self.assertIn(b'capacidade', r.stdout + r.stderr)
        r = self.executar(codigo, entrada=b'ABCD\n')
        self.assertEqual((r.returncode, r.stdout), (0, b'ABCD\n'))

    def test_leitura_consecutiva(self):
        codigo = '''inicio {
            seja primeiro: texto[16]
            seja segundo: texto[16]
            leia(primeiro)
            leia(segundo)
            junte(primeiro, segundo)
            escreva(primeiro)
        }'''
        r = self.executar(codigo, entrada='Olá\nmundo\n'.encode('utf-8'))
        self.assertEqual((r.returncode, r.stdout), (0, 'Olámundo\n'.encode('utf-8')), r.stderr)

    def test_tipos_tamanhos_e_comandos_invalidos(self):
        fontes = [
            'seja a: texto[0]', 'seja a: texto[x]',
            'seja a: texto[2]\n a = 3', 'seja a: texto[2]\n escreva(a + 1)',
            'seja a: texto[2]\n leia(a[0])',
            'seja a: texto[2]\n copie(a, 4)',
            'seja a: texto[2]\n junte(a, verdadeiro)',
            'seja a: texto[2]\n escreva(a[0])',
            'seja a = 1\n limpe(a)',
            'seja a = 1\n escreva(capacidade(a))',
        ]
        for trecho in fontes:
            with self.subTest(trecho=trecho):
                with self.assertRaises(ErroCompilacao):
                    analisar_programa('inicio {\n ' + trecho + '\n}')

    def test_fonte_aceita_unicode_apenas_no_literal(self):
        for texto in ('início {\n escreva(1)\n}',
                      'inicio {\n seja coração: texto[8]\n}'):
            with self.assertRaisesRegex(ErroCompilacao, 'sem acentos'):
                analisar_programa(texto)

    def test_compilacao_windows_sem_executar(self):
        codigo = '''inicio {
            seja a: texto[8]
            copie(a, "Olá")
            leia(a)
            escreva(a)
        }'''
        binario = compilar(analisar_programa(codigo), 'windows', nivel=6)
        self.assertEqual(binario[:2], b'MZ')
        self.assertIn(b'SetConsoleCP', binario)
        self.assertIn(b'ReadFile', binario)


if __name__ == '__main__':
    unittest.main()
