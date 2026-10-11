"""Compatibilidade do padrão ASCII na sintaxe da RS 0.4.1."""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))
from sintaxe import ErroCompilacao, analisar_programa
from codigo_nativo import compilar


class TestesSemAcentos(unittest.TestCase):
    def test_comandos_ascii(self):
        programa = analisar_programa('''inicio {
            seja preco = 10
            se preco > 5 {
                escreva("Está tudo ótimo, coração!")
            } senao {
                escreva("NÃO!")
            }
        }''')
        self.assertEqual(programa.instrucoes[1][0], 'se')
        self.assertEqual(programa.instrucoes[1][2][0], ('texto', 'Está tudo ótimo, coração!\n'))

    def test_rejeitar_acentos_no_codigo(self):
        exemplos = (
            'início {\n escreva(1)\n}',
            'inicio {\n se 0 {\n escreva(1)\n } senão {\n escreva(2)\n }\n}',
            'inicio {\n seja preço = 5\n escreva(1)\n}',
            'inclua matemática\ninicio {\n escreva(1)\n}',
            'ini\u0301cio {\n escreva(1)\n}',
        )
        for fonte in exemplos:
            with self.subTest(fonte=fonte):
                with self.assertRaisesRegex(ErroCompilacao, 'sem acentos'):
                    analisar_programa(fonte)

    def test_utf8_em_textos_e_comentarios(self):
        programa = analisar_programa('inicio {\n escreva("ação, coração, início, senão") // comentário com acento\n}')
        self.assertEqual(programa.instrucoes, [('texto', 'ação, coração, início, senão\n')])

    def test_linux_execucao_ascii_e_saida_utf8(self):
        if sys.platform != 'linux' or os.uname().machine != 'x86_64':
            self.skipTest('Requer Linux x86-64')
        fonte = '''inicio {
            seja preco = 12
            se preco >= 10 {
                escreva("Preço válido!")
            } senao {
                escreva("Preço inválido!")
            }
        }'''
        with tempfile.TemporaryDirectory() as d:
            exe = Path(d) / 'teste'
            exe.write_bytes(compilar(analisar_programa(fonte), 'linux'))
            exe.chmod(0o755)
            resultado = subprocess.run([str(exe)], capture_output=True, encoding='utf-8', timeout=5)
        self.assertEqual((resultado.returncode, resultado.stdout), (0, 'Preço válido!\n'))

    def test_windows_execucao_ascii_e_saida_utf8(self):
        if sys.platform != 'win32':
            self.skipTest('Requer Windows real')
        fonte = 'inicio {\n se 1 {\n escreva("Preço válido!")\n } senao {\n escreva("Erro")\n }\n}'
        with tempfile.TemporaryDirectory() as d:
            exe = Path(d) / 'teste.exe'
            exe.write_bytes(compilar(analisar_programa(fonte), 'windows'))
            resultado = subprocess.run([str(exe)], capture_output=True, encoding='utf-8', timeout=5)
        self.assertEqual((resultado.returncode, resultado.stdout), (0, 'Preço válido!\n'))


if __name__ == '__main__':
    unittest.main()
