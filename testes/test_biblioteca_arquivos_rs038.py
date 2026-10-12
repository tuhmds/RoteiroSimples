"""RS 0.38: integração real da biblioteca padrão com resultados tipados."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

RAIZ = Path(__file__).resolve().parents[1]


def alvo():
    if sys.platform == 'win32':
        return 'windows'
    if sys.platform == 'linux' and os.uname().machine == 'x86_64':
        return 'linux'
    raise unittest.SkipTest('Execução somente em Windows/Linux x86-64.')


def compilar_cli(pasta, nome, codigo, nivel):
    destino = Path(pasta)/(nome+'.rts')
    destino.write_text(codigo,encoding='utf-8')
    saida = Path(pasta)/(nome+('.exe' if alvo()=='windows' else ''))
    proc = subprocess.run([sys.executable,str(RAIZ/'compilar.py'),str(destino),
                           '--alvo',alvo(),'-O',str(nivel),
                           '-o',str(saida)],
                          capture_output=True,text=True,encoding='utf-8',
                          errors='replace',timeout=45)
    if proc.returncode:
        raise AssertionError(proc.stderr+proc.stdout)
    return saida


def executar(arquivo,pasta):
    return subprocess.run([str(arquivo)],cwd=pasta,capture_output=True,text=True,
                          encoding='utf-8',errors='replace',timeout=15)


class TestesBibliotecaArquivos(unittest.TestCase):
    def test_conversao_para_resultado_generico(self):
        fonte = """importe "padrao/arquivos.rts" como arquivos
        inicio {
            seja a = arquivos.resultado_arquivo(42)
            seja b = arquivos.resultado_arquivo(0)
            seja c = arquivos.resultado_arquivo(-6)
            seja d = arquivos.resultado_arquivo(-9223372036854775808)
            escreva(a.valido)
            escreva(a.valor)
            escreva(a.codigo_erro)
            escreva(b.valido)
            escreva(b.valor)
            escreva(c.valido)
            escreva(c.codigo_erro)
            escreva(d.codigo_erro)
        }"""
        esperado='1\n42\n0\n1\n0\n0\n6\n10\n'
        with tempfile.TemporaryDirectory() as pasta:
            for nivel in (0,4,8):
                with self.subTest(nivel=nivel):
                    caminho=compilar_cli(pasta,f'resultado_{nivel}',fonte,nivel)
                    r=executar(caminho,pasta)
                    self.assertEqual((r.returncode,r.stdout),(0,esperado),r.stderr)

    def test_aplicacao_completa_com_abertura_exclusiva(self):
        fonte=(RAIZ/'exemplos'/'aplicacoes'/'persistencia_segura_rs038.rts').read_text(encoding='utf-8')
        with tempfile.TemporaryDirectory() as pasta:
            for nivel in (0,4,8):
                with self.subTest(nivel=nivel):
                    arquivo=Path(pasta)/'exemplo_seguro.rsd'
                    if arquivo.exists():
                        arquivo.unlink()
                    executavel=compilar_cli(pasta,f'persistencia_{nivel}',fonte,nivel)
                    r=executar(executavel,pasta)
                    self.assertEqual((r.returncode,r.stdout),
                                     (0,'Dados recuperados e conferidos\n'),r.stderr)
                    self.assertEqual(arquivo.read_bytes(),bytes(4096)+b'RSDB\x01\x64')
                    # Uma segunda execução recusa sobrescrever o original.
                    r2=executar(executavel,pasta)
                    self.assertEqual((r2.returncode,r2.stdout),
                                     (1,'Falha na abertura:\n1\n'),r2.stderr)
                    self.assertEqual(arquivo.read_bytes(),bytes(4096)+b'RSDB\x01\x64')


if __name__=='__main__':
    unittest.main()
