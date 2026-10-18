"""RS-MEM: crescimento nativo no Linux e equivalência em Windows/Linux.

Exercita várias fronteiras de página e os três tipos que compartilham
rs_valor_reservar. A ABI de Windows permanece no caminho anterior.
"""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

from backend import compilar
from backend.x86_64 import montar_codigo
from compilador.parser import analisar_programa


class TestesRsMemCrescimento(unittest.TestCase):
    def _executar_comparar(self, fonte, esperado):
        sistema = sys.platform
        if sistema not in ('linux', 'win32') or (sistema == 'linux' and
                                                os.uname().machine != 'x86_64'):
            self.skipTest('Exige Windows AMD64 ou Linux x86-64.')
        alvo = 'windows' if sistema == 'win32' else 'linux'
        programa = analisar_programa(fonte)
        for nivel in (0, 4, 8):
            with self.subTest(alvo=alvo, nivel=nivel):
                binario = compilar(programa, alvo, nivel=nivel, otimizar=nivel > 0)
                with tempfile.TemporaryDirectory() as pasta:
                    saida = Path(pasta) / ('teste.exe' if alvo == 'windows' else 'teste')
                    saida.write_bytes(binario)
                    if alvo == 'linux':
                        saida.chmod(0o755)
                    resultado = subprocess.run([str(saida)], capture_output=True,
                                              timeout=30)
                self.assertEqual(resultado.returncode, 0, resultado.stderr)
                self.assertEqual(resultado.stdout, esperado)

    def test_listas_cruzam_varias_paginas(self):
        fonte = """inicio {
            seja dados: lista[]
            para i de 0 ate 16383 {
                adicione(dados, i)
            }
            escreva(tamanho(dados))
            escreva(dados[0])
            escreva(dados[4095])
            escreva(dados[16383])
            escreva(capacidade(dados))
        }"""
        self._executar_comparar(fonte, b'16384\n0\n4095\n16383\n16384\n')

    def test_bytes_crescem_entre_paginas_sem_perder_conteudo(self):
        fonte = """funcao gerar() -> bytes {
            seja dados: bytes
            para i de 0 ate 32768 {
                adicione_byte(dados, i % 256)
            }
            retorne mova(dados)
        }
        inicio {
            seja dados = gerar()
            escreva(tamanho(dados))
            escreva(dados[0])
            escreva(dados[4095])
            escreva(dados[4096])
            escreva(dados[32768])
            escreva(capacidade(dados))
        }"""
        self._executar_comparar(fonte, b'32769\n0\n255\n0\n0\n65536\n')

    def test_textos_continuam_funcionando(self):
        fonte = """inicio {
            seja texto_original: texto = "ação"
            junte(texto_original, " - RS")
            escreva(texto_original)
            escreva(tamanho(texto_original))
        }"""
        self._executar_comparar(fonte, 'ação - RS\n11\n'.encode('utf-8'))

    def test_emissor_usa_mremap_somente_no_linux(self):
        fonte = analisar_programa("""inicio {
            seja dados: bytes
            adicione_byte(dados, 1)
        }""")
        for windows in (False, True):
            with self.subTest(windows=windows):
                gerador, _ = montar_codigo(fonte, windows)
                inicio = gerador.rotulos['rs_valor_reservar']
                fim = gerador.rotulos['rs_valor_reservar_fim']
                trecho = bytes(gerador.codigo[inicio:fim])
                syscall_mremap = bytes.fromhex('B8 19 00 00 00 0F 05')
                self.assertEqual(syscall_mremap in trecho, not windows)
                if not windows:
                    self.assertIn('rs_valor_reservar_copia', gerador.rotulos)


if __name__ == '__main__':
    unittest.main()
