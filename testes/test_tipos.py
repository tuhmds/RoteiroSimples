"""Testes de tipos nativos RS 0.7: avaliação real, erros e pilha limitada."""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from sintaxe import analisar_programa, ErroCompilacao, MAX_VARIAVEIS
from codigo_nativo import compilar


class TestesTipos(unittest.TestCase):
    def test_tipos_explicitados_e_inferidos(self):
        p = analisar_programa('''inicio {
            seja x: inteiro = 4
            seja ativo: logico = verdadeiro
            seja resultado = x == 4
            seja numero = x + 1
            seja desligado: logico = falso
            escreva(ativo)
        }''')
        self.assertEqual(p.tipos, dict(x='inteiro', ativo='logico', resultado='logico',
                                       numero='inteiro', desligado='logico'))
        self.assertEqual(p.variaveis['x'], 0)
        self.assertEqual(p.variaveis['desligado'], 4)

    def test_comparar_logicos_e_rejeitar_operacao_aritmetica(self):
        programa = analisar_programa('inicio {\n seja b: logico = verdadeiro == falso\n escreva(b)\n}')
        self.assertEqual(programa.tipos['b'], 'logico')
        for expressao in ('verdadeiro + 1', 'verdadeiro * falso', '-falso', 'verdadeiro < falso'):
            with self.subTest(expressao=expressao):
                with self.assertRaisesRegex(ErroCompilacao, '(exige|inteiro)'):
                    analisar_programa('inicio {\n seja x = ' + expressao + '\n}')

    def test_tipos_incompativeis_declaracao_atribuicao_e_comparacao(self):
        for linha in ('seja x: inteiro = verdadeiro',
                      'seja x: logico = 1',
                      'seja x: real = 1',
                      'seja x: texto = 1',
                      'seja x = verdadeiro\n x = 1',
                      'seja x = 1\n x = falso',
                      'escreva(verdadeiro == 1)',
                      'escreva(1 < falso)'):
            with self.subTest(linha=linha):
                with self.assertRaises(ErroCompilacao):
                    analisar_programa('inicio {\n ' + linha + '\n}')

    def test_leia_e_para_exigem_inteiro(self):
        fontes = [
            'inicio {\n seja ativo = verdadeiro\n leia(ativo)\n}',
            'inicio {\n seja ativo = falso\n para ativo de 1 ate 3 {\n escreva(ativo)\n }\n}',
            'inicio {\n para x de verdadeiro ate 3 {\n escreva(x)\n }\n}',
            'inicio {\n para x de 1 ate falso {\n escreva(x)\n }\n}',
        ]
        for fonte in fontes:
            with self.subTest(fonte=fonte):
                with self.assertRaises(ErroCompilacao):
                    analisar_programa(fonte)

    def test_mais_de_256_variaveis_na_pilha(self):
        fonte = 'inicio {\n' + '\n'.join(f' seja n{i} = {i}' for i in range(MAX_VARIAVEIS + 1)) + '\n}'
        programa = analisar_programa(fonte)
        self.assertEqual(len(programa.variaveis), MAX_VARIAVEIS + 1)

    def test_limites_inteiros_e_acentos_somente_em_texto(self):
        p = analisar_programa('inicio {\n seja menor: inteiro = -9223372036854775808\n escreva("São informações")\n}')
        self.assertEqual(p.tipos['menor'], 'inteiro')
        with self.assertRaisesRegex(ErroCompilacao, 'ultrapassa'):
            analisar_programa('inicio {\n escreva(9223372036854775808)\n}')
        with self.assertRaisesRegex(ErroCompilacao, 'sem acentos'):
            analisar_programa('início {\n escreva(1)\n}')

    def test_emitir_e_executar_em_arquitetura_local(self):
        fonte = '''inicio {
            seja idade: inteiro = 17
            seja habilitado: logico = verdadeiro
            seja ok = idade >= 18
            escreva(ok)
            escreva(habilitado)
            habilitado = falso
            escreva(habilitado)
            se ok {
                escreva(99)
            } senao {
                escreva(-9223372036854775808)
            }
            enquanto idade < 20 {
                idade = idade + 1
            }
            escreva(idade)
        }'''
        target = ('windows' if sys.platform == 'win32' else 'linux')
        if target == 'linux' and (sys.platform != 'linux' or os.uname().machine != 'x86_64'):
            self.skipTest('Requer Linux x86-64 ou Windows x86-64')
        programa = analisar_programa(fonte)
        with tempfile.TemporaryDirectory() as pasta:
            arquivo = Path(pasta) / ('teste.exe' if target == 'windows' else 'teste')
            arquivo.write_bytes(compilar(programa, target))
            if target == 'linux':
                arquivo.chmod(0o755)
            res = subprocess.run([str(arquivo)], capture_output=True, encoding='utf-8', timeout=10)
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertEqual(res.stdout, '0\n1\n0\n-9223372036854775808\n20\n')


if __name__ == '__main__':
    unittest.main()
