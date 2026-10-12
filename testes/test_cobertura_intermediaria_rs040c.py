"""RS 0.40C — cobertura verificável da IR e paridade entre otimizações.

Executa programas nativos em processos independentes (Windows/Linux).
Os casos são determinísticos e comparam saídas e estados reais.
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
from compilador.ast import Programa
from compilador.cobertura_intermediaria import (
    INSTRUCOES_IR, EXPRESSOES_IR, analisar_cobertura,
    formatar_cobertura, motivos_de_cobertura,
)
from compilador.erros import ErroCompilacao
from compilador.estrategia import decidir_estrategia
from compilador.ir import construir_ir, programa_para_backend
from compilador.parser import analisar_programa


def plataforma():
    if sys.platform == 'win32':
        return 'windows'
    if sys.platform == 'linux' and os.uname().machine == 'x86_64':
        return 'linux'
    raise unittest.SkipTest('Exige executável Windows ou Linux x86-64.')


def executar(programa, nivel, pasta, nome):
    destino = Path(pasta)/(nome + ('.exe' if plataforma() == 'windows' else ''))
    destino.write_bytes(compilar(programa, plataforma(),
                                 otimizar=nivel > 0, nivel=nivel))
    if plataforma() == 'linux':
        destino.chmod(0o700)
    return subprocess.run((str(destino),), cwd=pasta, capture_output=True,
                          text=True, encoding='utf-8',
                          errors='replace', timeout=20)


def executar_cli(codigo, argumentos):
    with tempfile.TemporaryDirectory() as pasta:
        origem = Path(pasta)/'analise.rts'
        origem.write_text(codigo, encoding='utf-8')
        saida = Path(pasta)/('resultado.exe' if plataforma() == 'windows'
                              else 'resultado')
        retorno = subprocess.run(
            (sys.executable, str(RAIZ/'compilar.py'), str(origem),
             '--alvo', plataforma(), '-o', str(saida), *argumentos),
            cwd=pasta, capture_output=True, text=True, encoding='utf-8',
            errors='replace', timeout=35)
        return retorno, saida.exists()


class TestesCoberturaRS040C(unittest.TestCase):
    def test_operacoes_reconhecidas_pela_ir_sao_explicitas(self):
        self.assertIn('atribu a'.replace(' ', ''), INSTRUCOES_IR)
        self.assertIn('para', INSTRUCOES_IR)
        self.assertIn('indice', EXPRESSOES_IR)
        self.assertNotIn('grave_em', INSTRUCOES_IR)
        self.assertNotIn('adicione_byte', INSTRUCOES_IR)
        self.assertNotIn('indice_bytes', EXPRESSOES_IR)

    def test_representacao_das_instrucoes_antigas_e_reversivel(self):
        codigo = """inicio {
            seja numero = 17
            seja texto_atual: texto[10]
            copie(texto_atual, "RS")
            escreva(texto_atual)
            numero = numero + 5
            escreva(numero)
        }"""
        programa = analisar_programa(codigo)
        cobertura = analisar_cobertura(programa)
        self.assertTrue(cobertura.completa, formatar_cobertura(cobertura))
        ir = construir_ir(programa, otimizar=False, nivel=0)
        reconstruido = programa_para_backend(ir)
        self.assertEqual(reconstruido.instrucoes, list(programa.instrucoes))

    def test_instrucao_nova_desconhecida_nunca_usa_a_ir(self):
        programa = Programa([('instru cao_nova'.replace(' ', ''),)],
                            {}, False, {})
        cobertura = analisar_cobertura(programa)
        self.assertEqual(cobertura.instrucoes_ausentes, ('instrucao_nova',))
        self.assertEqual(decidir_estrategia(programa, 8).gerador, 'conservador')
        with self.assertRaisesRegex(ErroCompilacao, 'instrucao_nova'):
            construir_ir(programa, nivel=8)

    def test_expr_nova_em_bloco_aninhado_retorna_motivo_especifico(self):
        programa = Programa([
            ('se', ('logico', 1),
                [('imprima_num', ('indice_bytes', 'dados', ('numero', 0)))], []),
        ], {'dados': 0}, False, {'dados': ('bytes', 8)})
        cobertura = analisar_cobertura(programa)
        self.assertIn('indice_bytes', cobertura.expressoes_ausentes)
        self.assertIn('se', dict(cobertura.instrucoes))
        motivos = motivos_de_cobertura(cobertura)
        self.assertTrue(any('indice_bytes' in motivo for motivo in motivos))
        with self.assertRaisesRegex(ErroCompilacao, 'indice_bytes'):
            construir_ir(programa, otimizar=True, nivel=8)

    def test_aplicacao_com_bytes_usa_caminho_conservador(self):
        codigo = """inicio {
            seja dados: bytes[2]
            adicione_byte(dados, 255)
            escreva(dados[0])
        }"""
        programa = analisar_programa(codigo)
        cobertura = analisar_cobertura(programa)
        self.assertIn('adicione_byte', cobertura.instrucoes_ausentes)
        self.assertIn('indice_bytes', cobertura.expressoes_ausentes)
        for nivel in range(9):
            with self.subTest(nivel=nivel):
                decisao = decidir_estrategia(programa, nivel,
                                            otimizar=nivel > 0)
                self.assertEqual(decisao.gerador, 'conservador')
                self.assertTrue(any('adicione_byte' in m for m in decisao.motivos))

    def test_comando_de_cobertura_mostra_gerador_e_lacunas(self):
        codigo = """inicio {
            seja dados: bytes[3]
            adicione_byte(dados, 7)
            escreva(dados[0])
        }"""
        retorno, gerou = executar_cli(
            codigo, ('-O', '8', '--mostrar-cobertura-intermediaria',
                     '--mostrar-estrategia'))
        self.assertEqual(retorno.returncode, 0, retorno.stderr)
        self.assertTrue(gerou)
        self.assertIn('Representação dos nós: incompleta', retorno.stdout)
        self.assertIn('adicione_byte', retorno.stdout)
        self.assertIn('Gerador selecionado: conservador', retorno.stdout)
        self.assertIn('transformações IR/SSA não aplicadas', retorno.stdout)

    def test_analise_indisponivel_falha_antes_de_gerar_executavel(self):
        codigo = """inicio {
            seja dados: bytes[3]
            adicione_byte(dados, 7)
            escreva(dados[0])
        }"""
        for modo in ('--mostrar-ir','--mostrar-efeitos',
                     '--mostrar-memoria-versionada','--mostrar-fluxo'):
            with self.subTest(modo=modo):
                retorno, gerou = executar_cli(codigo, ('-O','8',modo))
                self.assertEqual(retorno.returncode, 1)
                self.assertFalse(gerou)
                self.assertIn('gerador conservador', retorno.stderr.lower())
                self.assertIn('adicione_byte', retorno.stderr)
                self.assertNotIn('Traceback', retorno.stderr)

    def test_programa_antigo_exibe_cobertura_completa_e_ssa(self):
        codigo = """inicio {
            seja x = 5
            escreva(x * 7)
        }"""
        retorno, gerou = executar_cli(codigo, ('-O','8',
                                              '--mostrar-cobertura-intermediaria',
                                              '--mostrar-ir'))
        self.assertEqual(retorno.returncode, 0, retorno.stderr)
        self.assertTrue(gerou)
        self.assertIn('Representação dos nós: completa', retorno.stdout)
        self.assertIn('Gerador selecionado: ssa', retorno.stdout)
        self.assertIn('RS IR v1', retorno.stdout)

    def test_caminhos_diferentes_mantem_resultado_binario(self):
        codigo = """inicio {
            seja dados: bytes[3]
            adicione_byte(dados, 0)
            adicione_byte(dados, 255)
            escreva(dados[1])
            encerre(7)
        }"""
        programa = analisar_programa(codigo)
        with tempfile.TemporaryDirectory() as pasta:
            for nivel in range(9):
                with self.subTest(nivel=nivel):
                    retorno = executar(programa, nivel, pasta, f'binario_{nivel}')
                    self.assertEqual((retorno.returncode, retorno.stdout),
                                     (7, '255\n'), retorno.stderr)

    def test_paridade_diferencial_nove_niveis_programas_variados(self):
        gerador = random.Random(40031)
        exemplos = []
        for _ in range(6):
            limite = gerador.randint(6, 28)
            multiplicador = gerador.randint(2, 9)
            incremento = gerador.randint(1, 17)
            codigo = f"""inicio {{
                seja total = 0
                para numero de 1 ate {limite} {{
                    se numero % 3 == 0 {{
                        total = total + numero * {multiplicador}
                    }} senao {{
                        total = total - numero + {incremento}
                    }}
                }}
                escreva(total)
            }}"""
            esperado = sum((i * multiplicador if i % 3 == 0
                            else -i + incremento) for i in range(1, limite+1))
            exemplos.append((codigo, f'{esperado}\n'))

        exemplos.append((
            """inicio {
                seja buffer: texto[24]
                copie(buffer, "Roteiro")
                junte(buffer, "Simples")
                escreva(buffer)
                escreva(tamanho(buffer))
            }""", 'RoteiroSimples\n14\n'))
        exemplos.append((
            """inicio {
                seja valores: lista[6]
                para i de 0 ate 5 {
                    valores[i] = i * 3
                }
                escreva(valores[4])
                escreva(valores[5])
            }""", '12\n15\n'))

        with tempfile.TemporaryDirectory() as pasta:
            for indice, (codigo, esperado) in enumerate(exemplos):
                programa = analisar_programa(codigo)
                for nivel in range(9):
                    with self.subTest(exemplo=indice, nivel=nivel):
                        retorno = executar(programa, nivel, pasta,
                                          f'prova_{indice}_{nivel}')
                        self.assertEqual((retorno.returncode, retorno.stdout),
                                         (0, esperado), retorno.stderr)


if __name__ == '__main__':
    unittest.main()
