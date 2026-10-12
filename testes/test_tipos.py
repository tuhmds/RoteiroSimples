"""RS 0.7: verificacao de tipos e execucao nativa em Windows e Linux."""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))
from sintaxe import analisar_programa, ErroCompilacao, MAX_VARIAVEIS
from codigo_nativo import compilar


class TestesTipos(unittest.TestCase):
    def test_tipos_explicitos_inferencia_e_logicos(self):
        programa = analisar_programa("""inicio {
            seja idade: inteiro = 17
            seja ligado: logico = verdadeiro
            seja maior = idade >= 18
            seja desligado: logico = falso
            escreva(ligado == desligado)
        }""")
        self.assertEqual(programa.tipos, dict(idade='inteiro', ligado='logico',
                                             maior='logico', desligado='logico'))

    def test_rejeita_erros_de_tipos(self):
        erros = (
            'seja a: inteiro = verdadeiro',
            'seja a: logico = 1',
            'seja a: real = 2',
            'seja a = verdadeiro + 1',
            'seja a = falso < verdadeiro',
            'seja a = 1 == falso',
            'seja a: logico = falso\n a = 12',
            'seja a = 12\n a = verdadeiro',
        )
        for codigo in erros:
            with self.subTest(codigo=codigo):
                with self.assertRaises(ErroCompilacao):
                    analisar_programa('inicio {\n' + codigo + '\n}')

    def test_leia_e_para_exigem_inteiro(self):
        fontes = (
            'inicio {\n seja a: logico = verdadeiro\n leia(a)\n}',
            'inicio {\n para a de verdadeiro ate 2 {\n escreva(a)\n }\n}',
            'inicio {\n para a de 1 ate falso {\n escreva(a)\n }\n}',
            'inicio {\n seja a = falso\n para a de 1 ate 2 {\n escreva(a)\n }\n}',
        )
        for fonte in fontes:
            with self.subTest(fonte=fonte):
                with self.assertRaises(ErroCompilacao):
                    analisar_programa(fonte)

    def test_inteiro_minimo_literais_invalidos_e_utf8(self):
        analisar_programa('inicio {\n seja valor: inteiro = -9223372036854775808\n escreva("Coração!")\n}')
        with self.assertRaisesRegex(ErroCompilacao, 'ultrapassa'):
            analisar_programa('inicio {\n escreva(9223372036854775808)\n}')
        with self.assertRaisesRegex(ErroCompilacao, 'sem acentos'):
            analisar_programa('início {\n escreva(1)\n}')

    def test_limite_temporario_de_variaveis(self):
        fonte = 'inicio {\n' + '\n'.join('seja n%d = 0' % i for i in range(MAX_VARIAVEIS+1)) + '\n}'
        with self.assertRaisesRegex(ErroCompilacao, 'limite temporário'):
            analisar_programa(fonte)

    def test_codigo_nativo_em_duas_plataformas(self):
        if sys.platform not in ('win32', 'linux'):
            self.skipTest('Executa em Windows ou Linux')
        if sys.platform == 'linux' and os.uname().machine != 'x86_64':
            self.skipTest('Linux precisa ser x86-64')
        programa = analisar_programa("""inicio {
            seja idade: inteiro = 17
            seja ativo: logico = verdadeiro
            seja maior = idade >= 18
            escreva(maior)
            escreva(ativo)
            ativo = falso
            escreva(ativo)
            se maior {
                escreva(99)
            } senao {
                escreva(-9223372036854775808)
            }
            enquanto idade < 20 {
                idade = idade + 1
            }
            escreva(idade)
        }""")
        alvo = 'windows' if sys.platform == 'win32' else 'linux'
        with tempfile.TemporaryDirectory() as pasta:
            arq = Path(pasta) / ('programa.exe' if alvo == 'windows' else 'programa')
            arq.write_bytes(compilar(programa, alvo))
            if alvo == 'linux':
                arq.chmod(0o755)
            resultado = subprocess.run([str(arq)], capture_output=True, encoding='utf-8', timeout=10)
        self.assertEqual(resultado.returncode, 0, resultado.stderr)
        self.assertEqual(resultado.stdout, '0\n1\n0\n-9223372036854775808\n20\n')


if __name__ == '__main__':
    unittest.main()
