"""RS 0.38: descritores proprietários, sincronização e recuperação de erros.

Exercita binários RS em processos separados no Windows e no Linux.
"""
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
from backend import compilar


def alvo():
    if sys.platform == 'win32':
        return 'windows'
    if sys.platform == 'linux' and os.uname().machine == 'x86_64':
        return 'linux'
    raise unittest.SkipTest('Exige executável nativo Windows ou Linux x86-64.')


def construir(pasta, nome, fonte, nivel=8):
    programa = analisar_programa(fonte)
    caminho = Path(pasta) / (nome + ('.exe' if alvo() == 'windows' else ''))
    caminho.write_bytes(compilar(programa, alvo(), otimizar=nivel > 0, nivel=nivel))
    if sys.platform != 'win32':
        caminho.chmod(0o700)
    return caminho


def executar(caminho, pasta):
    return subprocess.run([str(caminho)], cwd=pasta, capture_output=True,
                          text=True, encoding='utf-8', errors='replace', timeout=15)


class TestesArquivosAbertosRS038(unittest.TestCase):
    def test_abrir_gravar_sincronizar_ler_e_fechar(self):
        fonte = """inicio {
            seja arq: arquivo
            seja bloco: bytes[8]
            seja estado = 999
            abra_arquivo("entregas.rsd", arq, "novo", estado)
            escreva(estado)
            adicione_byte(bloco, 82)
            adicione_byte(bloco, 83)
            adicione_byte(bloco, 0)
            adicione_byte(bloco, 255)
            grave_em(arq, bloco, 4096, estado)
            escreva(estado)
            sincronize_arquivo(arq, estado)
            escreva(estado)
            limpe(bloco)
            carregue_de(arq, bloco, 4096, 4, estado)
            escreva(estado)
            escreva(bloco[0])
            escreva(bloco[3])
            feche_arquivo(arq, estado)
            escreva(estado)
            feche_arquivo(arq, estado)
            escreva(estado)
        }"""
        esperado = '0\n4\n0\n4\n82\n255\n0\n-3\n'
        for nivel in range(9):
            with self.subTest(nivel=nivel), tempfile.TemporaryDirectory() as pasta:
                r = executar(construir(pasta, f'ciclo_{nivel}', fonte, nivel), pasta)
                self.assertEqual((r.returncode,r.stdout),(0,esperado),r.stderr)
                bruto = (Path(pasta)/'entregas.rsd').read_bytes()
                self.assertEqual(bruto,bytes(4096)+b'RS\x00\xff')

    def test_modo_novo_exclusivo_nao_sobrescreve(self):
        fonte = """inicio {
            seja arq: arquivo
            seja estado = 0
            abra_arquivo("banco.rsd", arq, "novo", estado)
            escreva(estado)
            abra_arquivo("banco.rsd", arq, "novo", estado)
            escreva(estado)
            feche_arquivo(arq, estado)
            escreva(estado)
            abra_arquivo("banco.rsd", arq, "novo", estado)
            escreva(estado)
            feche_arquivo(arq, estado)
            escreva(estado)
        }"""
        with tempfile.TemporaryDirectory() as pasta:
            r = executar(construir(pasta,'exclusivo',fonte),pasta)
            self.assertEqual((r.returncode,r.stdout),(0,'0\n-5\n0\n-1\n-3\n'),r.stderr)
            self.assertEqual((Path(pasta)/'banco.rsd').read_bytes(),b'')

    def test_reabertura_leitura_persistencia_dois_processos(self):
        escrita = """inicio {
            seja arq: arquivo
            seja bloco: bytes[5]
            seja estado = 0
            abra_arquivo("registro.bin", arq, "novo", estado)
            se estado < 0 { encerre(1) }
            adicione_byte(bloco, 100)
            adicione_byte(bloco, 0)
            adicione_byte(bloco, 250)
            grave_em(arq, bloco, 0, estado)
            se estado != 3 { encerre(2) }
            sincronize_arquivo(arq, estado)
            se estado != 0 { encerre(3) }
            feche_arquivo(arq, estado)
            se estado != 0 { encerre(4) }
        }"""
        leitura = """inicio {
            seja arq: arquivo
            seja bloco: bytes[5]
            seja estado = 0
            abra_arquivo("registro.bin", arq, "leitura", estado)
            se estado < 0 { encerre(11) }
            carregue_de(arq, bloco, 0, 5, estado)
            escreva(estado)
            escreva(bloco[2])
            feche_arquivo(arq, estado)
            escreva(estado)
        }"""
        # O lexer RS trabalha com blocos de controle por linhas próprias.
        escrita = escrita.replace('se estado < 0 { encerre(1) }','se estado < 0 {\n encerre(1)\n }')
        escrita = escrita.replace('se estado != 3 { encerre(2) }','se estado != 3 {\n encerre(2)\n }')
        escrita = escrita.replace('se estado != 0 { encerre(3) }','se estado != 0 {\n encerre(3)\n }')
        escrita = escrita.replace('se estado != 0 { encerre(4) }','se estado != 0 {\n encerre(4)\n }')
        leitura = leitura.replace('se estado < 0 { encerre(11) }','se estado < 0 {\n encerre(11)\n }')
        with tempfile.TemporaryDirectory() as pasta:
            prog1=construir(pasta,'escritor',escrita)
            prog2=construir(pasta,'leitor',leitura)
            r1=executar(prog1,pasta)
            r2=executar(prog2,pasta)
            self.assertEqual((r1.returncode,r1.stdout),(0,''),r1.stderr)
            self.assertEqual((r2.returncode,r2.stdout),(0,'3\n250\n0\n'),r2.stderr)

    def test_ausencia_e_falhas_recuperaveis(self):
        fonte = """inicio {
            seja arq: arquivo
            seja dados: bytes[8]
            seja estado = 0
            carregue_de(arq, dados, 0, 3, estado)
            escreva(estado)
            sincronize_arquivo(arq, estado)
            escreva(estado)
            feche_arquivo(arq, estado)
            escreva(estado)
            abra_arquivo("inexistente.bin", arq, "leitura", estado)
            escreva(estado)
            abra_arquivo("criado.bin", arq, "alteracao", estado)
            escreva(estado)
            carregue_de(arq, dados, 0, 9, estado)
            escreva(estado)
            carregue_de(arq, dados, -1, 4, estado)
            escreva(estado)
            feche_arquivo(arq, estado)
            escreva(estado)
            escreva(777)
        }"""
        with tempfile.TemporaryDirectory() as pasta:
            r=executar(construir(pasta,'erros',fonte),pasta)
            self.assertEqual((r.returncode,r.stdout),
                             (0,'-3\n-3\n-3\n-1\n0\n-3\n-3\n0\n777\n'),r.stderr)
            self.assertEqual((Path(pasta)/'criado.bin').read_bytes(),b'')

    def test_ciclo_repetido_limpa_arquivo_local(self):
        fonte = """inicio {
            seja estado = 0
            para numero de 1 ate 150 {
                seja arq: arquivo
                abra_arquivo("ciclos.bin", arq, "alteracao", estado)
                se estado != 0 {
                    encerre(19)
                }
                // Fecha no fim deste bloco do laço, de forma automática.
            }
            escreva(123)
        }"""
        with tempfile.TemporaryDirectory() as pasta:
            r=executar(construir(pasta,'loop',fonte),pasta)
            self.assertEqual((r.returncode,r.stdout),(0,'123\n'),r.stderr)

    def test_saida_de_laco_pare_e_continue_fecha_recursos(self):
        fonte = """inicio {
            seja estado = 0
            para numero de 1 ate 3 {
                seja arq: arquivo
                abra_arquivo("teste.bin", arq, "novo", estado)
                se numero == 1 {
                    continue
                }
                pare
            }
            seja arq2: arquivo
            abra_arquivo("teste.bin", arq2, "alteracao", estado)
            escreva(estado)
            feche_arquivo(arq2, estado)
            escreva(estado)
        }"""
        with tempfile.TemporaryDirectory() as pasta:
            r=executar(construir(pasta,'controle',fonte),pasta)
            self.assertEqual((r.returncode,r.stdout),(0,'0\n0\n'),r.stderr)

    def test_funcao_recursos_locais_fechados_e_retorno_preservado(self):
        fonte = """funcao analisar() -> inteiro {
            seja arq: arquivo
            seja estado = 0
            abra_arquivo("analise.bin", arq, "alteracao", estado)
            retorne 1234 + estado
        }
        inicio {
            escreva(analisar())
            escreva(analisar())
        }"""
        with tempfile.TemporaryDirectory() as pasta:
            r=executar(construir(pasta,'funcoes',fonte),pasta)
            self.assertEqual((r.returncode,r.stdout),(0,'1234\n1234\n'),r.stderr)

    def test_rejeicao_estatica_propriedade_e_caminhos(self):
        fontes=[
            """inicio {
                seja arq: arquivo
                seja copia = arq
            }""",
            """inicio {
                seja arq: arquivo
                seja outro: arquivo
                outro = arq
            }""",
            """inicio {
                seja arq: arquivo
                escreva(arq)
            }""",
            """inicio {
                seja arq: arquivo
                se arq == arq { escreva(1) }
            }""",
            """inicio {
                seja arq: arquivo
                seja estado = 0
                abra_arquivo("../escapa", arq, "novo", estado)
            }""",
            """inicio {
                seja arq: arquivo
                seja estado = 0
                abra_arquivo("a.bin", arq, "apagar", estado)
            }""",
            """inicio {
                seja arq: arquivo
                seja dados: texto[4]
                seja estado = 0
                grave_em(arq, dados, 0, estado)
            }""",
            """inicio {
                seja arq: arquivo
                seja estado = 0
                sincronize_arquivo(arq, arq)
            }""",
            """funcao usar(arq: arquivo) -> inteiro {
                retorne 1
            }
            inicio { escreva(1) }""",
            """inicio {
                seja arq: arquivo = 0
            }""",
        ]
        for fonte in fontes:
            with self.subTest(fonte=fonte):
                with self.assertRaises(ErroCompilacao):
                    analisar_programa(fonte)


if __name__ == '__main__':
    unittest.main()
