"""RS 0.34: persistência nativa entre processos, limites e tratamento de falhas."""
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


def testar_plataforma():
    if sys.platform not in ('win32', 'linux') or (
            sys.platform == 'linux' and os.uname().machine != 'x86_64'):
        raise unittest.SkipTest('Execução nativa disponível apenas em Windows/Linux x86-64.')


def compilar_fonte(pasta, nome, codigo):
    testar_plataforma()
    pasta = Path(pasta)
    fonte = pasta / (nome + '.rts')
    fonte.write_text(codigo, encoding='utf-8')
    executavel = pasta / (nome + ('.exe' if sys.platform == 'win32' else ''))
    alvo = 'windows' if sys.platform == 'win32' else 'linux'
    resultado = subprocess.run(
        [sys.executable, str(RAIZ / 'compilar.py'), str(fonte),
         '--alvo', alvo, '-O', '8', '-o', str(executavel)],
        capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=30,
        cwd=pasta)
    if resultado.returncode != 0:
        raise AssertionError(resultado.stderr + resultado.stdout)
    return executavel


def executar(executavel, pasta):
    return subprocess.run([str(executavel)], cwd=pasta, capture_output=True,
                          text=True, encoding='utf-8', errors='replace', timeout=15)


class TestesArquivos(unittest.TestCase):
    def test_persistencia_em_processos_distintos(self):
        with tempfile.TemporaryDirectory() as pasta:
            programa1 = compilar_fonte(pasta, 'gravar', """inicio {
                seja dados: texto[200]
                copie(dados, "Pedido 101: entregue")
                grave_arquivo("pedidos.txt", dados)
                escreva(tamanho(dados))
            }""")
            programa2 = compilar_fonte(pasta, 'ler', """inicio {
                seja dados: texto[200]
                carregue_arquivo("pedidos.txt", dados)
                escreva(dados)
                escreva(tamanho(dados))
            }""")
            gravado = executar(programa1, pasta)
            lido = executar(programa2, pasta)
            self.assertEqual((gravado.returncode, gravado.stdout), (0, '20\n'), gravado.stderr)
            self.assertEqual((lido.returncode, lido.stdout),
                             (0, 'Pedido 101: entregue\n20\n'), lido.stderr)
            self.assertEqual((Path(pasta) / 'pedidos.txt').read_bytes(),
                             b'Pedido 101: entregue')

    def test_gravacao_repetida_substitui_e_nao_adiciona(self):
        with tempfile.TemporaryDirectory() as pasta:
            executavel = compilar_fonte(pasta, 'programa', """inicio {
                seja dados: texto[30]
                copie(dados, "Uma frase longa")
                grave_arquivo("notas.txt", dados)
                copie(dados, "Curto")
                grave_arquivo("notas.txt", dados)
                carregue_arquivo("notas.txt", dados)
                escreva(dados)
            }""")
            r = executar(executavel, pasta)
            self.assertEqual((r.returncode, r.stdout), (0, 'Curto\n'), r.stderr)
            self.assertEqual((Path(pasta) / 'notas.txt').read_bytes(), b'Curto')

    def test_arquivo_vazio_e_limite_exato(self):
        with tempfile.TemporaryDirectory() as pasta:
            programa = compilar_fonte(pasta, 'limites', """inicio {
                seja dados: texto[5]
                grave_arquivo("vazio.txt", dados)
                copie(dados, "12345")
                grave_arquivo("cinco.txt", dados)
                limpe(dados)
                carregue_arquivo("vazio.txt", dados)
                escreva(tamanho(dados))
                carregue_arquivo("cinco.txt", dados)
                escreva(tamanho(dados))
                escreva(dados)
            }""")
            r = executar(programa, pasta)
            self.assertEqual((r.returncode, r.stdout), (0, '0\n5\n12345\n'), r.stderr)
            self.assertEqual((Path(pasta) / 'vazio.txt').stat().st_size, 0)
            self.assertEqual((Path(pasta) / 'cinco.txt').read_bytes(), b'12345')

    def test_arquivo_maior_que_buffer_rejeitado(self):
        with tempfile.TemporaryDirectory() as pasta:
            (Path(pasta) / 'grande.txt').write_bytes(b'0123456789')
            exe = compilar_fonte(pasta, 'pequeno', """inicio {
                seja dados: texto[5]
                carregue_arquivo("grande.txt", dados)
                escreva(999)
            }""")
            r = executar(exe, pasta)
            self.assertNotEqual(r.returncode, 0)
            self.assertIn('capacidade', (r.stdout + r.stderr).lower())
            self.assertNotIn('999', r.stdout)

    def test_arquivo_inexistente_diagnostico(self):
        with tempfile.TemporaryDirectory() as pasta:
            exe = compilar_fonte(pasta, 'ausente', """inicio {
                seja dados: texto[100]
                carregue_arquivo("nao_existe.txt", dados)
            }""")
            r = executar(exe, pasta)
            self.assertNotEqual(r.returncode, 0)
            self.assertIn('abrir o arquivo', (r.stdout + r.stderr).lower())

    def test_gravacao_em_diretorio_inexistente_rejeitada(self):
        with tempfile.TemporaryDirectory() as pasta:
            exe = compilar_fonte(pasta, 'diretorio', """inicio {
                seja dados: texto[100]
                copie(dados, "Dado")
                grave_arquivo("pasta_inexistente/dados.txt", dados)
            }""")
            r = executar(exe, pasta)
            self.assertNotEqual(r.returncode, 0)
            self.assertIn('abrir o arquivo', (r.stdout + r.stderr).lower())

    def test_utf8_preservado_em_bytes(self):
        with tempfile.TemporaryDirectory() as pasta:
            exe = compilar_fonte(pasta, 'acentos', """inicio {
                seja dados: texto[100]
                copie(dados, "Ipatinga: aço, educação e café.")
                grave_arquivo("letras.txt", dados)
                limpe(dados)
                carregue_arquivo("letras.txt", dados)
                escreva(dados)
            }""")
            r = executar(exe, pasta)
            self.assertEqual((r.returncode, r.stdout),
                             (0, 'Ipatinga: aço, educação e café.\n'), r.stderr)
            self.assertEqual((Path(pasta) / 'letras.txt').read_bytes(),
                             'Ipatinga: aço, educação e café.'.encode('utf-8'))

    def test_leitura_em_funcao_com_texto_local(self):
        with tempfile.TemporaryDirectory() as pasta:
            (Path(pasta) / 'valor.txt').write_bytes(b'abcdefg')
            exe = compilar_fonte(pasta, 'funcao', """funcao tamanho_salvo() -> inteiro {
                seja dados: texto[50]
                carregue_arquivo("valor.txt", dados)
                retorne tamanho(dados)
            }
            inicio {
                escreva(tamanho_salvo())
            }""")
            r = executar(exe, pasta)
            self.assertEqual((r.returncode, r.stdout), (0, '7\n'), r.stderr)

    def test_rejeicao_estatica_de_tipos_caminhos_e_sintaxe(self):
        exemplos = [
            """inicio {
                seja valor = 7
                grave_arquivo("arquivo.txt", valor)
            }""",
            """inicio {
                seja dados: texto[10]
                carregue_arquivo("../fora.txt", dados)
            }""",
            """inicio {
                seja dados: texto[10]
                grave_arquivo("/tmp/f.txt", dados)
            }""",
            """inicio {
                seja dados: texto[10]
                grave_arquivo("pastas\\arquivo.txt", dados)
            }""",
            """inicio {
                seja dados: texto[10]
                grave_arquivo("á.txt", dados)
            }""",
            """inicio {
                seja dados: texto[10]
                grave_arquivo("arquivo.txt")
            }""",
        ]
        for fonte in exemplos:
            with self.subTest(fonte=fonte):
                with self.assertRaises(ErroCompilacao):
                    analisar_programa(fonte)


if __name__ == '__main__':
    unittest.main()
