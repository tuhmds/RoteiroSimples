"""RS 0.35 — gravação e leitura binária posicional com retorno recuperável."""
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


def compilar_fonte(pasta, nome, codigo):
    if sys.platform not in ('win32', 'linux') or (
            sys.platform == 'linux' and os.uname().machine != 'x86_64'):
        raise unittest.SkipTest('A execução requer Windows/Linux x86-64.')
    fonte = Path(pasta) / (nome + '.rts')
    fonte.write_text(codigo, encoding='utf-8')
    executavel = Path(pasta) / (nome + ('.exe' if sys.platform == 'win32' else ''))
    resultado = subprocess.run(
        [sys.executable, str(RAIZ / 'compilar.py'), str(fonte), '--alvo',
         'windows' if sys.platform == 'win32' else 'linux',
         '-O', '8', '-o', str(executavel)],
        capture_output=True, text=True, encoding='utf-8', errors='replace',
        timeout=30, cwd=pasta)
    if resultado.returncode:
        raise AssertionError(resultado.stdout + resultado.stderr)
    return executavel


def executar(executavel, pasta):
    return subprocess.run([str(executavel)], cwd=pasta, capture_output=True,
                          text=True, encoding='utf-8', errors='replace', timeout=15)


class TestesArquivosPosicionais(unittest.TestCase):
    def test_escrita_em_posicao_nao_trunca_dados_e_leitura(self):
        with tempfile.TemporaryDirectory() as pasta:
            exe = compilar_fonte(pasta, 'alterar', """inicio {
                seja dados: texto[20]
                seja estado = -99
                copie(dados, "ABCDEF")
                grave_trecho("dados.rsd", dados, 0, estado)
                escreva(estado)
                copie(dados, "xy")
                grave_trecho("dados.rsd", dados, 2, estado)
                escreva(estado)
                carregue_trecho("dados.rsd", dados, 0, 6, estado)
                escreva(estado)
                escreva(dados)
                escreva(tamanho(dados))
            }""")
            r = executar(exe, pasta)
            self.assertEqual((r.returncode, r.stdout), (0, '6\n2\n6\nABxyEF\n6\n'), r.stderr)
            self.assertEqual((Path(pasta)/'dados.rsd').read_bytes(), b'ABxyEF')

    def test_bytes_nulos_e_nao_utf8(self):
        with tempfile.TemporaryDirectory() as pasta:
            bruto = b'\x00\xff\x80END\x00'
            (Path(pasta)/'entrada.bin').write_bytes(bruto)
            exe = compilar_fonte(pasta, 'binario', """inicio {
                seja dados: texto[16]
                seja estado = 0
                carregue_trecho("entrada.bin", dados, 0, 7, estado)
                escreva(estado)
                grave_trecho("copia.bin", dados, 0, estado)
                escreva(estado)
            }""")
            r = executar(exe, pasta)
            self.assertEqual((r.returncode, r.stdout), (0, '7\n7\n'), r.stderr)
            self.assertEqual((Path(pasta)/'copia.bin').read_bytes(), bruto)

    def test_leitura_parcial_e_fim_de_arquivo(self):
        with tempfile.TemporaryDirectory() as pasta:
            (Path(pasta)/'origem.bin').write_bytes(b'ABCDEFGHIJ')
            exe = compilar_fonte(pasta, 'paginacao', """inicio {
                seja dados: texto[20]
                seja estado = -1
                carregue_trecho("origem.bin", dados, 3, 4, estado)
                escreva(estado)
                escreva(dados)
                carregue_trecho("origem.bin", dados, 8, 12, estado)
                escreva(estado)
                escreva(dados)
                carregue_trecho("origem.bin", dados, 20, 5, estado)
                escreva(estado)
                escreva(tamanho(dados))
            }""")
            r = executar(exe, pasta)
            self.assertEqual((r.returncode, r.stdout),
                             (0, '4\nDEFG\n2\nIJ\n0\n0\n'), r.stderr)

    def test_arquivo_ausente_retorna_erro_sem_encerrar(self):
        with tempfile.TemporaryDirectory() as pasta:
            exe = compilar_fonte(pasta, 'ausente', """inicio {
                seja dados: texto[10]
                seja estado = 0
                copie(dados, "antigo")
                carregue_trecho("nao_existe.bin", dados, 0, 6, estado)
                escreva(estado)
                escreva(tamanho(dados))
                escreva(777)
            }""")
            r = executar(exe, pasta)
            self.assertEqual((r.returncode,r.stdout),(0,'-1\n0\n777\n'), r.stderr)
            self.assertFalse((Path(pasta)/'nao_existe.bin').exists())

    def test_argumentos_invalidos_retorna_erro_e_nao_cria_arquivo(self):
        with tempfile.TemporaryDirectory() as pasta:
            exe = compilar_fonte(pasta, 'invalidos', """inicio {
                seja dados: texto[5]
                seja estado = 0
                copie(dados, "cinco")
                grave_trecho("negativo.bin", dados, -1, estado)
                escreva(estado)
                grave_trecho("estouro.bin", dados, 9223372036854775807, estado)
                escreva(estado)
                carregue_trecho("negativo.bin", dados, 0, 6, estado)
                escreva(estado)
                escreva(tamanho(dados))
            }""")
            r=executar(exe, pasta)
            self.assertEqual((r.returncode,r.stdout),(0,'-3\n-3\n-3\n0\n'), r.stderr)
            self.assertFalse((Path(pasta)/'negativo.bin').exists())
            self.assertFalse((Path(pasta)/'estouro.bin').exists())

    def test_posicao_alta_escrita_dispersa(self):
        with tempfile.TemporaryDirectory() as pasta:
            exe=compilar_fonte(pasta,'disperso',"""inicio {
                seja dados: texto[10]
                seja estado = 0
                copie(dados, "OK")
                grave_trecho("disperso.bin", dados, 4096, estado)
                escreva(estado)
                carregue_trecho("disperso.bin", dados, 4096, 2, estado)
                escreva(estado)
                escreva(dados)
            }""")
            r=executar(exe,pasta)
            self.assertEqual((r.returncode,r.stdout),(0,'2\n2\nOK\n'),r.stderr)
            bruto=(Path(pasta)/'disperso.bin').read_bytes()
            self.assertEqual(len(bruto),4098)
            self.assertEqual(bruto[:4096],bytes(4096))
            self.assertEqual(bruto[4096:],b'OK')

    def test_leitura_e_gravacao_em_programas_separados(self):
        with tempfile.TemporaryDirectory() as pasta:
            escritor=compilar_fonte(pasta,'escritor',"""inicio {
                seja dados: texto[20]
                seja estado = 0
                copie(dados, "PAGINA")
                grave_trecho("banco.rsd", dados, 8192, estado)
                escreva(estado)
            }""")
            leitor=compilar_fonte(pasta,'leitor',"""inicio {
                seja dados: texto[20]
                seja estado = 0
                carregue_trecho("banco.rsd", dados, 8192, 6, estado)
                escreva(estado)
                escreva(dados)
            }""")
            r1=executar(escritor,pasta)
            r2=executar(leitor,pasta)
            self.assertEqual((r1.returncode,r1.stdout),(0,'6\n'),r1.stderr)
            self.assertEqual((r2.returncode,r2.stdout),(0,'6\nPAGINA\n'),r2.stderr)

    def test_zero_bytes_e_comprimento_preenchido(self):
        with tempfile.TemporaryDirectory() as pasta:
            exe=compilar_fonte(pasta,'zero',"""inicio {
                seja dados: texto[8]
                seja estado = -7
                grave_trecho("vazio.bin", dados, 0, estado)
                escreva(estado)
                carregue_trecho("vazio.bin", dados, 0, 8, estado)
                escreva(estado)
                escreva(tamanho(dados))
            }""")
            r=executar(exe,pasta)
            self.assertEqual((r.returncode,r.stdout),(0,'0\n0\n0\n'),r.stderr)
            self.assertEqual((Path(pasta)/'vazio.bin').read_bytes(),b'')

    def test_argumentos_com_funcoes_e_buffer_local(self):
        with tempfile.TemporaryDirectory() as pasta:
            exe=compilar_fonte(pasta,'funcoes',"""funcao acrescente(a: inteiro, b: inteiro) -> inteiro {
                retorne a + b
            }
            funcao ler_um() -> inteiro {
                seja dados: texto[12]
                seja estado = 0
                carregue_trecho("funcoes.bin", dados, acrescente(2, 3), acrescente(1, 2), estado)
                retorne estado
            }
            inicio {
                seja dados: texto[12]
                seja estado = 0
                copie(dados, "ABCDEFGH")
                grave_trecho("funcoes.bin", dados, 0, estado)
                escreva(ler_um())
            }""")
            r=executar(exe,pasta)
            self.assertEqual((r.returncode,r.stdout),(0,'3\n'),r.stderr)

    def test_tipos_e_caminhos_invalidos(self):
        casos=[
            """inicio {
                seja dados: texto[10]
                seja estado = 0
                grave_trecho("../invasao.bin", dados, 0, estado)
            }""",
            """inicio {
                seja dados: texto[10]
                seja estado = 0
                grave_trecho("dados.rsd", dados, verdadeiro, estado)
            }""",
            """inicio {
                seja dados: texto[10]
                seja estado: logico = falso
                grave_trecho("dados.rsd", dados, 0, estado)
            }""",
            """inicio {
                seja dados: texto[10]
                seja estado = 0
                carregue_trecho("dados.rsd", dados, 0, falso, estado)
            }""",
            """inicio {
                seja dados: texto[10]
                carregue_trecho("dados.rsd", dados, 0, 4, inexistente)
            }""",
            """inicio {
                seja dados = 123
                seja estado = 0
                grave_trecho("dados.rsd", dados, 0, estado)
            }""",
        ]
        for fonte in casos:
            with self.subTest(fonte=fonte):
                with self.assertRaises(ErroCompilacao):
                    analisar_programa(fonte)


if __name__=='__main__':
    unittest.main()
