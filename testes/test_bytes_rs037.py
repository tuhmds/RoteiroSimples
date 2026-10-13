"""RS 0.37 — contratos binários seguros e códigos de saída reais."""
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
from compilador.erros import ErroCompilacao


def _alvo():
    if sys.platform == 'win32':
        return 'windows'
    if sys.platform == 'linux' and os.uname().machine == 'x86_64':
        return 'linux'
    raise unittest.SkipTest('Requer Windows ou Linux x86-64.')


def _compilar(pasta, nome, fonte, nivel=8):
    programa = analisar_programa(fonte)
    destino = Path(pasta) / (nome + ('.exe' if _alvo() == 'windows' else ''))
    destino.write_bytes(compilar(programa, _alvo(), otimizar=nivel > 0, nivel=nivel))
    if sys.platform != 'win32':
        destino.chmod(0o700)
    return destino


def _executar(caminho, pasta):
    return subprocess.run([str(caminho)], cwd=pasta, capture_output=True,
                          text=True, encoding='utf-8', errors='replace', timeout=15)


class TestesBytesRS037(unittest.TestCase):
    def test_acrescentar_ler_substituir_e_limpar(self):
        fonte = """inicio {
            seja dados: bytes[3]
            escreva(tamanho(dados))
            escreva(capacidade(dados))
            adicione_byte(dados, 0)
            adicione_byte(dados, 255)
            adicione_byte(dados, 31)
            escreva(tamanho(dados))
            escreva(dados[0])
            escreva(dados[1])
            escreva(dados[2])
            dados[1] = 128
            escreva(dados[1])
            limpe(dados)
            escreva(tamanho(dados))
            adicione_byte(dados, 17)
            escreva(dados[0])
        }"""
        with tempfile.TemporaryDirectory() as pasta:
            for nivel in range(9):
                with self.subTest(nivel=nivel):
                    r = _executar(_compilar(pasta, f'basico_{nivel}', fonte, nivel), pasta)
                    self.assertEqual((r.returncode, r.stdout),
                                     (0, '0\n3\n3\n0\n255\n31\n128\n0\n17\n'), r.stderr)

    def test_variacao_binaria_deterministica_em_arquivo(self):
        gerador = random.Random(3701)
        dados = bytes(gerador.randrange(256) for _ in range(130))
        operacoes = '\n'.join(f'    adicione_byte(bloco, {valor})' for valor in dados)
        fonte = f"""inicio {{
            seja bloco: bytes[130]
            seja estado = -99
{operacoes}
            grave_trecho("aleatorio.bin", bloco, 777, estado)
            escreva(estado)
            limpe(bloco)
            carregue_trecho("aleatorio.bin", bloco, 777, 130, estado)
            escreva(estado)
            escreva(tamanho(bloco))
            escreva(bloco[0])
            escreva(bloco[129])
        }}"""
        with tempfile.TemporaryDirectory() as pasta:
            for nivel in range(9):
                with self.subTest(nivel=nivel):
                    arquivo = Path(pasta)/'aleatorio.bin'
                    if arquivo.exists():
                        arquivo.unlink()
                    r = _executar(_compilar(pasta, f'aleatorio_{nivel}', fonte, nivel), pasta)
                    self.assertEqual((r.returncode, r.stdout),
                                     (0, f'130\n130\n130\n{dados[0]}\n{dados[-1]}\n'),
                                     r.stderr)
                    self.assertEqual(arquivo.read_bytes(), bytes(777) + dados)

    def test_bytes_zero_e_utf8_invalido_nao_sao_texto(self):
        with tempfile.TemporaryDirectory() as pasta:
            (Path(pasta)/'entrada.bin').write_bytes(b'\x00\xff\x80\x01\xfe')
            fonte = """inicio {
                seja bloco: bytes[5]
                seja estado = 0
                carregue_trecho("entrada.bin", bloco, 0, 5, estado)
                escreva(estado)
                escreva(bloco[0])
                escreva(bloco[1])
                escreva(bloco[2])
                grave_trecho("saida.bin", bloco, 0, estado)
                escreva(estado)
            }"""
            r = _executar(_compilar(pasta, 'roundtrip', fonte), pasta)
            self.assertEqual((r.returncode, r.stdout), (0, '5\n0\n255\n128\n5\n'),r.stderr)
            self.assertEqual((Path(pasta)/'saida.bin').read_bytes(), b'\x00\xff\x80\x01\xfe')

    def test_byte_valor_negativo_e_superior_a_255_rejeitados(self):
        for valor in ('-1', '256', '300', '9223372036854775807'):
            with self.subTest(valor=valor), tempfile.TemporaryDirectory() as pasta:
                codigo = f"""inicio {{
                    seja bloco: bytes[3]
                    adicione_byte(bloco, {valor})
                    escreva(999)
                }}"""
                r = _executar(_compilar(pasta, 'valor', codigo), pasta)
                self.assertNotEqual(r.returncode, 0)
                self.assertIn('byte', (r.stdout+r.stderr).lower())
                self.assertNotIn('999', r.stdout)

    def test_indice_negativo_e_nao_inicializado(self):
        for indice in ('-1', '0', '1', '9223372036854775807'):
            with self.subTest(indice=indice), tempfile.TemporaryDirectory() as pasta:
                codigo = f"""inicio {{
                    seja bloco: bytes[4]
                    escreva(bloco[{indice}])
                }}"""
                r = _executar(_compilar(pasta, 'indice', codigo), pasta)
                self.assertNotEqual(r.returncode, 0)
                self.assertIn('indice', (r.stdout+r.stderr).lower())

    def test_substituicao_nao_estende_comprimento(self):
        with tempfile.TemporaryDirectory() as pasta:
            fonte = """inicio {
                seja bloco: bytes[5]
                adicione_byte(bloco, 12)
                bloco[3] = 45
                escreva(999)
            }"""
            r = _executar(_compilar(pasta, 'limite', fonte), pasta)
            self.assertNotEqual(r.returncode, 0)
            self.assertIn('indice', (r.stdout+r.stderr).lower())
            self.assertNotIn('999', r.stdout)

    def test_append_ate_capacidade_e_erro_ao_ultrapassar(self):
        with tempfile.TemporaryDirectory() as pasta:
            fonte = """inicio {
                seja bloco: bytes[2]
                adicione_byte(bloco, 3)
                adicione_byte(bloco, 4)
                escreva(tamanho(bloco))
                adicione_byte(bloco, 5)
                escreva(999)
            }"""
            r = _executar(_compilar(pasta, 'capacidade', fonte), pasta)
            self.assertNotEqual(r.returncode, 0)
            self.assertIn('capacidade', (r.stdout+r.stderr).lower())
            self.assertEqual(r.stdout.splitlines()[0], '2')

    def test_saida_processos_valida_0_a_255(self):
        with tempfile.TemporaryDirectory() as pasta:
            for valor in (0,1,7,127,255):
                with self.subTest(valor=valor):
                    fonte = f"""inicio {{
                        escreva(42)
                        encerre({valor})
                        escreva(999)
                    }}"""
                    r = _executar(_compilar(pasta, f'saida_{valor}', fonte), pasta)
                    self.assertEqual((r.returncode, r.stdout), (valor, '42\n'),r.stderr)

    def test_saida_invalida_rejeitada(self):
        with tempfile.TemporaryDirectory() as pasta:
            for valor in ('-1','256','999'):
                with self.subTest(valor=valor):
                    fonte = f"""inicio {{
                        encerre({valor})
                        escreva(999)
                    }}"""
                    r = _executar(_compilar(pasta, f'invalido_{valor.replace("-","n")}', fonte), pasta)
                    self.assertNotEqual(r.returncode, 0)
                    self.assertIn('codigo de saida', (r.stdout+r.stderr).lower())
                    self.assertNotIn('999', r.stdout)

    def test_erro_arquivo_pode_sair_com_status_diferente_de_zero(self):
        fonte = """inicio {
            seja bloco: bytes[32]
            seja resultado = 0
            carregue_trecho("inexistente.rsd", bloco, 0, 32, resultado)
            se resultado < 0 {
                encerre(9)
            }
            escreva(999)
        }"""
        with tempfile.TemporaryDirectory() as pasta:
            r = _executar(_compilar(pasta, 'falha_arquivo', fonte), pasta)
            self.assertEqual((r.returncode,r.stdout),(9,''),r.stderr)

    def test_bytes_campo_registro_e_argumento_por_valor(self):
        fonte = """tipo Pacote {
            dados: bytes[4]
            codigo: inteiro
        }
        funcao primeiro(pacote: Pacote) -> inteiro {
            retorne pacote.dados[0]
        }
        inicio {
            seja pacote: Pacote
            adicione_byte(pacote.dados, 77)
            pacote.codigo = 21
            escreva(primeiro(pacote))
            escreva(pacote.codigo)
        }"""
        with tempfile.TemporaryDirectory() as pasta:
            r = _executar(_compilar(pasta, 'registro', fonte), pasta)
            self.assertEqual((r.returncode,r.stdout),(0,'77\n21\n'),r.stderr)

    def test_copia_composta_binaria_conserva_comprimento(self):
        fonte = """inicio {
            seja fonte: bytes[5]
            adicione_byte(fonte, 99)
            adicione_byte(fonte, 0)
            seja copia: bytes[5] = fonte
            fonte[0] = 7
            escreva(copia[0])
            escreva(copia[1])
            escreva(tamanho(copia))
            escreva(fonte[0])
        }"""
        with tempfile.TemporaryDirectory() as pasta:
            r = _executar(_compilar(pasta, 'copia', fonte), pasta)
            self.assertEqual((r.returncode,r.stdout),(0,'99\n0\n2\n7\n'),r.stderr)

    def test_exemplo_cabecalho_binario_e_saida_sistema(self):
        fonte = (RAIZ/'exemplos'/'aplicacoes'/'criar_cabecalho_binario.rts').read_text(
            encoding='utf-8')
        with tempfile.TemporaryDirectory() as pasta:
            for nivel in range(9):
                with self.subTest(nivel=nivel):
                    r = _executar(_compilar(pasta, f'cabecalho_{nivel}', fonte, nivel), pasta)
                    self.assertEqual((r.returncode, r.stdout),
                                     (0, 'Quantidade recuperada:\n100\n'), r.stderr)
                    self.assertEqual((Path(pasta)/'cabecalho_teste.rsd').read_bytes(),
                                     b'RSDB\x01\x64\x00\x00\x00')

    def test_rejeicoes_de_tipo_separacao_de_texto_e_bytes(self):
        invalidos=[
            '''inicio { 
                seja bloco: bytes[6]
                escreva(bloco)
            }''',
            '''inicio {
                seja bloco: bytes[6]
                copie(bloco, "ola")
            }''',
            '''inicio {
                seja bloco: texto[6]
                adicione_byte(bloco, 77)
            }''',
            '''inicio {
                seja bloco: bytes[6]
                adicione_byte(bloco, verdadeiro)
            }''',
            '''inicio {
                seja bloco: bytes[6]
                bloco[0] = falso
            }''',
            '''inicio {
                seja bloco: bytes[6]
                encerre(bloco)
            }''',
            '''inicio {
                seja bloco: bytes[0]
            }''',
            '''inicio {
                seja bloco: bytes[-1]
            }''',
            '''inicio {
                seja bloco: bytes[6]
                seja texto_buffer: texto[6]
                copie(texto_buffer, bloco)
            }''',
        ]
        for codigo in invalidos:
            with self.subTest(codigo=codigo):
                with self.assertRaises(ErroCompilacao):
                    analisar_programa(codigo)


if __name__ == '__main__':
    unittest.main()
