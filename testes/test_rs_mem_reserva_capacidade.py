"""RS-MEM: reserva antecipada de capacidade sem mudança de comprimento."""
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


class TestesReservaCapacidade(unittest.TestCase):
    def executar(self, fonte, esperado=None, falha=False):
        if sys.platform not in ('linux', 'win32') or (
                sys.platform == 'linux' and os.uname().machine != 'x86_64'):
            self.skipTest('Exige Linux x86-64 ou Windows AMD64.')
        alvo = 'windows' if sys.platform == 'win32' else 'linux'
        programa = analisar_programa(fonte)
        for nivel in (0, 4, 8):
            with self.subTest(alvo=alvo, nivel=nivel):
                codigo = compilar(programa, alvo, nivel=nivel, otimizar=nivel > 0)
                with tempfile.TemporaryDirectory() as pasta:
                    caminho = Path(pasta) / ('teste.exe' if alvo == 'windows' else 'teste')
                    caminho.write_bytes(codigo)
                    if alvo == 'linux':
                        caminho.chmod(0o755)
                    resultado = subprocess.run([str(caminho)], capture_output=True, timeout=30)
                if falha:
                    self.assertNotEqual(resultado.returncode, 0)
                else:
                    self.assertEqual(resultado.returncode, 0, resultado.stderr)
                    self.assertEqual(resultado.stdout, esperado)

    def test_lista_reservada_nao_realoca_no_crescimento_previsto(self):
        fonte = """inicio {
            seja valores: lista[]
            reserve_capacidade(valores, 1000)
            escreva(tamanho(valores))
            escreva(capacidade(valores))
            para i de 0 ate 999 {
                adicione(valores, i + 1)
            }
            escreva(tamanho(valores))
            escreva(valores[999])
            escreva(capacidade(valores))
        }"""
        self.executar(fonte, b'0\n1024\n1000\n1000\n1024\n')

    def test_bytes_textos_e_reserva_que_nao_encolhe(self):
        fonte = """inicio {
            seja dados: bytes
            reserve_capacidade(dados, 40)
            adicione_byte(dados, 255)
            reserve_capacidade(dados, 2)
            escreva(dados[0])
            escreva(tamanho(dados))
            escreva(capacidade(dados))
            seja mensagem: texto = "a"
            reserve_capacidade(mensagem, 200)
            junte(mensagem, "ção")
            escreva(mensagem)
            escreva(tamanho(mensagem))
            escreva(capacidade(mensagem))
        }"""
        self.executar(fonte, '255\n1\n64\nação\n6\n256\n'.encode('utf-8'))

    def test_reserva_nao_destroi_conteudo_antigo(self):
        fonte = """inicio {
            seja valores: lista[]
            adicione(valores, 123)
            reserve_capacidade(valores, 5000)
            escreva(valores[0])
            escreva(tamanho(valores))
            escreva(capacidade(valores))
        }"""
        self.executar(fonte, b'123\n1\n8192\n')

    def test_negativo_e_uso_apos_liberacao_rejeitados(self):
        self.executar("""inicio {
            seja dados: bytes
            reserve_capacidade(dados, -1)
        }""", falha=True)
        self.executar("""inicio {
            seja dados: lista[]
            libere(dados)
            reserve_capacidade(dados, 10)
        }""", falha=True)

    def test_reserva_em_tipo_fixo_e_emprestado_e_recusada(self):
        fontes = [
            """inicio {
                seja dados: lista[4]
                reserve_capacidade(dados, 100)
            }""",
            """inicio {
                seja texto_fixo: texto[16]
                reserve_capacidade(texto_fixo, 32)
            }""",
            """funcao consultar(dados: emprestimo[lista]) -> inteiro {
                reserve_capacidade(dados, 10)
                retorne 0
            }
            inicio {
                seja dados: lista[]
                escreva(consultar(empreste(dados)))
            }""",
        ]
        for fonte in fontes:
            with self.subTest(fonte=fonte[:45]):
                with self.assertRaises(ErroCompilacao):
                    analisar_programa(fonte)


if __name__ == '__main__':
    unittest.main()
