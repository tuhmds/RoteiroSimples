"""Compressão RS RLE adaptativa, sem perdas e com limite de expansão."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))
from compilador.modulos import carregar_fontes
from compilador.parser import analisar_programa
from backend import compilar

class TestesCompressaoRsMem(unittest.TestCase):
    def _comparar(self, fonte, esperado):
        if sys.platform not in ('linux', 'win32') or (
                sys.platform == 'linux' and os.uname().machine != 'x86_64'):
            self.skipTest('Execução nativa exige Linux x86-64 ou Windows AMD64.')
        alvo = 'windows' if sys.platform == 'win32' else 'linux'
        with tempfile.TemporaryDirectory() as pasta:
            entrada = Path(pasta) / 'fonte.rts'
            entrada.write_text(fonte, encoding='utf-8')
            programa = analisar_programa(carregar_fontes(entrada).texto)
            for nivel in (0, 4, 8):
                with self.subTest(alvo=alvo, nivel=nivel):
                    binario = compilar(programa, alvo, nivel=nivel, otimizar=nivel > 0)
                    destino = Path(pasta) / ('programa.exe' if alvo == 'windows' else 'programa')
                    destino.write_bytes(binario)
                    if alvo == 'linux':
                        destino.chmod(0o755)
                    processo = subprocess.run([str(destino)], cwd=pasta,
                                             capture_output=True, timeout=30)
                    self.assertEqual(processo.returncode, 0, processo.stderr)
                    self.assertEqual(processo.stdout, esperado)

    def test_mil_zeros_comprimem_e_voltam_exatamente(self):
        texto = (RAIZ / 'exemplos/aplicacoes/compressao_rs_mem.rts').read_text(
            encoding='utf-8')
        self._comparar(texto, b'1000\n9\n1000\n0\n0\n')

    def test_dados_incompressiveis_preservam_formato_bruto(self):
        self._comparar('''importe "padrao/memoria_compacta.rts" como memoria
inicio {
    seja dados: bytes
    para n de 0 ate 15 {
        adicione_byte(dados, n * 7)
    }
    seja pacote = memoria.compactar(empreste(dados))
    escreva(pacote.valido)
    escreva(tamanho(pacote.valor))
    escreva(pacote.valor[0])
    seja retorno = memoria.expandir(empreste(pacote.valor), 16)
    escreva(retorno.valido)
    escreva(retorno.valor[0])
    escreva(retorno.valor[15])
}''', b'1\n17\n0\n1\n0\n105\n')

    def test_rejeicao_de_envelopes_invalidos_e_expansao_excessiva(self):
        self._comparar('''importe "padrao/memoria_compacta.rts" como memoria
inicio {
    seja vazio: bytes
    seja a = memoria.expandir(empreste(vazio), 50)
    escreva(a.codigo_erro)
    adicione_byte(vazio, 1)
    seja b = memoria.expandir(empreste(vazio), 50)
    escreva(b.valido)
    adicione_byte(vazio, 5)
    seja c = memoria.expandir(empreste(vazio), 50)
    escreva(c.codigo_erro)
    adicione_byte(vazio, 255)
    seja d = memoria.expandir(empreste(vazio), 4)
    escreva(d.codigo_erro)
    seja e_resultado = memoria.expandir(empreste(vazio), 5)
    escreva(e_resultado.valido)
    escreva(tamanho(e_resultado.valor))
    escreva(e_resultado.valor[4])
}''', b'1\n1\n1\n2\n1\n5\n255\n')

    def test_zero_e_valor_255_e_pacote_vazio(self):
        self._comparar('''importe "padrao/memoria_compacta.rts" como memoria
inicio {
    seja dados: bytes
    seja pacote = memoria.compactar(empreste(dados))
    escreva(tamanho(pacote.valor))
    escreva(pacote.valor[0])
    seja retorno = memoria.expandir(empreste(pacote.valor), 0)
    escreva(retorno.valido)
    escreva(tamanho(retorno.valor))
    adicione_byte(dados, 0)
    adicione_byte(dados, 255)
    adicione_byte(dados, 0)
    seja pacote2 = memoria.compactar(empreste(dados))
    seja retorno2 = memoria.expandir(empreste(pacote2.valor), 3)
    escreva(tamanho(retorno2.valor))
    escreva(retorno2.valor[1])
}''', b'1\n0\n1\n0\n3\n255\n')


if __name__ == '__main__':
    unittest.main()
