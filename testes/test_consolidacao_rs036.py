"""RS 0.36: aplicações reais e paridade observável entre todos os -O.

Os binários gerados rodam em um processo distinto, sem Python no executável.
Resultados e efeitos no sistema de arquivos devem coincidir em O0..O8.
"""
import os
from pathlib import Path
import random
import subprocess
import sys
import tempfile
import unittest

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

from backend import compilar
from compilador.parser import analisar_programa
from compilador.estrategia import decidir_estrategia, descrever_estrategia


def plataforma():
    if sys.platform == 'win32':
        return 'windows'
    if sys.platform == 'linux' and os.uname().machine == 'x86_64':
        return 'linux'
    raise unittest.SkipTest('Requer execução nativa Windows ou Linux x86-64.')


def compilar_binario(programa, nivel, pasta, nome):
    alvo = plataforma()
    caminho = Path(pasta) / (nome + ('.exe' if alvo == 'windows' else ''))
    imagem = compilar(programa, alvo, otimizar=nivel > 0, nivel=nivel)
    caminho.write_bytes(imagem)
    if alvo == 'linux':
        caminho.chmod(0o700)
    return caminho


def executar(caminho, pasta):
    return subprocess.run([str(caminho)], cwd=pasta, capture_output=True,
                          text=True, encoding='utf-8', errors='replace', timeout=18)


class TestesConsolidacaoRS036(unittest.TestCase):
    def test_planejamento_reporta_otimizacao_efetiva(self):
        simples = analisar_programa("""inicio {
            escreva(3 + 5)
        }""")
        antigo = analisar_programa("""inicio {
            seja notas: lista[4]
            notas[0] = 99
            escreva(notas[0])
        }""")
        novo = analisar_programa("""inicio {
            seja buffer: texto[32]
            seja estado = 0
            carregue_trecho("entrada.bin", buffer, 0, 32, estado)
            escreva(estado)
        }""")
        self.assertEqual(decidir_estrategia(simples, 0).gerador, 'intermediario')
        self.assertEqual(decidir_estrategia(simples, 4).gerador, 'ssa')
        self.assertEqual(decidir_estrategia(simples, 8).gerador, 'ssa')
        self.assertEqual(decidir_estrategia(antigo, 8).gerador, 'intermediario')
        self.assertEqual(decidir_estrategia(novo, 8).gerador, 'conservador')
        self.assertIn('arquivos nativos', decidir_estrategia(novo, 8).motivos)
        self.assertIn('não aplicadas', descrever_estrategia(
            decidir_estrategia(novo, 8)))
        self.assertFalse(decidir_estrategia(novo, 8).otimiza)

    def test_linha_de_comando_explica_caminho_sem_promessas(self):
        plataforma()
        with tempfile.TemporaryDirectory() as pasta:
            entrada = Path(pasta) / 'simples.rts'
            entrada.write_text("""inicio {
                escreva(40 + 2)
            }""", encoding='utf-8')
            alvo = 'windows' if sys.platform == 'win32' else 'linux'
            for nivel, fragmento in [(0, 'sem transformações'), (8, 'SSA')]:
                saida = Path(pasta) / f'programa_{nivel}'
                processo = subprocess.run([sys.executable, str(RAIZ/'compilar.py'),
                                           str(entrada), '--alvo', alvo,
                                           '--mostrar-estrategia', '-O', str(nivel),
                                           '-o', str(saida)],
                                          capture_output=True, text=True,
                                          encoding='utf-8', errors='replace',
                                          timeout=30)
                self.assertEqual(processo.returncode, 0, processo.stderr)
                self.assertIn(fragmento, processo.stdout)

    def test_nove_niveis_aritmetica_e_condicoes(self):
        codigo = """inicio {
            seja saldo = 0
            para numero de 1 ate 40 {
                se numero % 3 == 0 {
                    saldo = saldo + numero * 4
                } senao {
                    saldo = saldo - numero
                }
            }
            escreva(saldo)
        }"""
        esperado = sum(i * 4 if i % 3 == 0 else -i for i in range(1, 41))
        programa = analisar_programa(codigo)
        with tempfile.TemporaryDirectory() as pasta:
            for nivel in range(9):
                with self.subTest(nivel=nivel):
                    binario = compilar_binario(programa, nivel, pasta, f'saldo_{nivel}')
                    retorno = executar(binario, pasta)
                    self.assertEqual((retorno.returncode, retorno.stdout),
                                     (0, f'{esperado}\n'), retorno.stderr)

    def test_nove_niveis_lista_fixa_e_memoria(self):
        codigo = """inicio {
            seja notas: lista[8]
            para indice de 0 ate 7 {
                notas[indice] = indice * 3 + 20
            }
            seja total = 0
            para indice de 0 ate 7 {
                total = total + notas[indice]
            }
            escreva(total)
            escreva(notas[5])
        }"""
        esperado = sum(i * 3 + 20 for i in range(8))
        programa = analisar_programa(codigo)
        with tempfile.TemporaryDirectory() as pasta:
            for nivel in range(9):
                with self.subTest(nivel=nivel):
                    binario = compilar_binario(programa, nivel, pasta, f'lista_{nivel}')
                    retorno = executar(binario, pasta)
                    self.assertEqual((retorno.returncode, retorno.stdout),
                                     (0, f'{esperado}\n35\n'), retorno.stderr)

    def test_nove_niveis_registros_emprestimos_e_funcoes(self):
        fonte = (RAIZ / 'exemplos' / 'aplicacoes' / 'analisar_entregas.rts').read_text(
            encoding='utf-8')
        programa = analisar_programa(fonte)
        self.assertEqual(decidir_estrategia(programa, 8).gerador, 'conservador')
        esperado = ('Total de entregas:\n150\n'
                    'Entregas concluidas:\n100\n'
                    'Receita concluida em centavos:\n178400\n')
        with tempfile.TemporaryDirectory() as pasta:
            for nivel in range(9):
                with self.subTest(nivel=nivel):
                    binario = compilar_binario(programa, nivel, pasta, f'entregas_{nivel}')
                    retorno = executar(binario, pasta)
                    self.assertEqual((retorno.returncode, retorno.stdout),
                                     (0, esperado), retorno.stderr)

    def test_nove_niveis_copiador_binario_em_blocos(self):
        fonte = (RAIZ / 'exemplos' / 'aplicacoes' /
                 'copiar_arquivo_em_blocos.rts').read_text(encoding='utf-8')
        programa = analisar_programa(fonte)
        self.assertEqual(decidir_estrategia(programa, 8).gerador, 'conservador')
        gerador = random.Random(36012)
        casos = [b'', b'\x00\xff\xfeABC\x00',
                 bytes(range(256)) * 16,
                 gerador.randbytes(4097),
                 gerador.randbytes(16385)]
        with tempfile.TemporaryDirectory() as pasta:
            for nivel in range(9):
                binario = compilar_binario(programa, nivel, pasta, f'copiador_{nivel}')
                for indice, original in enumerate(casos):
                    with self.subTest(nivel=nivel, caso=indice):
                        (Path(pasta)/'origem.bin').write_bytes(original)
                        destino = Path(pasta)/'copia.bin'
                        if destino.exists():
                            destino.unlink()
                        resultado = executar(binario, pasta)
                        self.assertEqual((resultado.returncode, resultado.stdout),
                                         (0, f'Copia concluida; total de bytes:\n{len(original)}\n'),
                                         resultado.stderr)
                        self.assertEqual(destino.read_bytes(), original)

    def test_copiador_rejeita_destino_existente_sem_corromper(self):
        fonte = (RAIZ / 'exemplos' / 'aplicacoes' /
                 'copiar_arquivo_em_blocos.rts').read_text(encoding='utf-8')
        with tempfile.TemporaryDirectory() as pasta:
            programa = analisar_programa(fonte)
            binario = compilar_binario(programa, 8, pasta, 'seguro')
            (Path(pasta)/'origem.bin').write_bytes(b'DADOS')
            destino = Path(pasta)/'copia.bin'
            destino.write_bytes(b'ORIGINAL-IMPORTANTE')
            retorno = executar(binario, pasta)
            self.assertEqual(retorno.returncode, 0, retorno.stderr)
            self.assertIn('Destino existente', retorno.stdout)
            self.assertEqual(destino.read_bytes(), b'ORIGINAL-IMPORTANTE')

    def test_copiador_reporta_origem_ausente(self):
        fonte = (RAIZ / 'exemplos' / 'aplicacoes' /
                 'copiar_arquivo_em_blocos.rts').read_text(encoding='utf-8')
        with tempfile.TemporaryDirectory() as pasta:
            programa = analisar_programa(fonte)
            for nivel in range(9):
                with self.subTest(nivel=nivel):
                    binario = compilar_binario(programa, nivel, pasta, f'ausente_{nivel}')
                    retorno = executar(binario, pasta)
                    self.assertEqual((retorno.returncode, retorno.stdout),
                                     (0, 'Falha ao ler arquivo de origem\n-1\n'), retorno.stderr)
                    self.assertFalse((Path(pasta)/'copia.bin').exists())


if __name__ == '__main__':
    unittest.main()
