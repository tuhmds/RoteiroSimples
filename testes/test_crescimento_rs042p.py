"""Instrumentacao nao altera bytes; geradores tem oraculos e falhas visiveis."""
import copy
from pathlib import Path
import random
import tempfile
import unittest
from unittest.mock import patch

from backend import compilar
from backend.x86_64 import Gerador
from benchmarks.crescimento import gerar_caso, compilar_caso, medir_crescimento
from benchmarks.crescimento import executar_trabalhador
from benchmarks.saltos import medir_saltos
from compilador.medicao_compilacao import MedicaoCompilacao
from compilador.modulos import carregar_fontes
from compilador.parser import analisar_programa
from testes.fixtures.compactacao_rs042o import compactar_antes
from testes.test_valores_dinamicos_rs042a import alvo_nativo


class TestesCompactacaoRS042P(unittest.TestCase):
    def test_microbenchmark_tem_bytes_iguais_e_amostras_intercaladas(self):
        resultado = medir_saltos((16, 48), repeticoes=2, comparar_legado=True)
        self.assertEqual(len(resultado['ordens']), 3)
        for quantidade in (16, 48):
            dupla = [r for r in resultado['resultados'] if r['saltos'] == quantidade]
            self.assertEqual(dupla[0]['sha256'], dupla[1]['sha256'])
            self.assertTrue(all(len(r['amostras_ms']) == 2 for r in dupla))

    def comparar(self, gerador):
        anterior = copy.deepcopy(gerador)
        self.assertEqual(gerador.compactar_saltos_ssa(), compactar_antes(anterior))
        self.assertEqual((gerador.codigo, gerador.rotulos, gerador.pendencias, gerador.saltos_compactados),
                         (anterior.codigo, anterior.rotulos, anterior.pendencias, anterior.saltos_compactados))
        gerador.finalizar(0x1000, {'externa': 0x8000, 'dado': 0x9000})
        anterior.finalizar(0x1000, {'externa': 0x8000, 'dado': 0x9000})
        self.assertEqual(gerador.codigo, anterior.codigo)

    def test_referencia_congelada_com_destinos_relocacoes_e_fronteiras(self):
        aleatorio = random.Random(424201)
        for caso in range(100):
            with self.subTest(caso=caso):
                quantidade = aleatorio.randrange(2, 40)
                g = Gerador()
                g.ativar_saltos_curtos_ssa()
                for indice in range(quantidade + 1):
                    g.marcar(f'ssa_{indice}')
                    g.bytes(b'\x90' * aleatorio.choice((0, 1, 9, 120, 126, 127, 128, 140)))
                    if indice < quantidade:
                        g.salto(f'ssa_{aleatorio.randrange(quantidade + 1)}',
                                aleatorio.choice(('jmp', 'jz', 'jnz', 'jg', 'jl', 'jo')))
                    if indice % 7 == 0:
                        g.chamada('externa')
                        g.relativo(b'\x48\x8D\x05', 'dado')
                self.comparar(g)

    def test_trabalho_do_indice_cresce_sem_varredura_por_candidato(self):
        for quantidade in (64, 256, 1024, 2048):
            g = Gerador()
            g.ativar_saltos_curtos_ssa()
            for indice in range(quantidade):
                g.salto(f'ssa_{indice}')
                g.bytes(b'\x90')
                g.marcar(f'ssa_{indice}')
            self.assertEqual(g.compactar_saltos_ssa(), quantidade)
            self.assertEqual(bytes(g.codigo), b'\xeb\x01\x90' * quantidade)
            estatisticas = g.estatisticas_compactacao
            self.assertEqual((estatisticas['passagens'], estatisticas['avaliacoes']), (2, quantidade))
            self.assertEqual(estatisticas['consultas_prefixo'], 2 * quantidade)
            self.assertLessEqual(estatisticas['passos_indice'], 3 * quantidade * quantidade.bit_length())

    def test_sem_candidatos_ou_sem_encurtamento_preserva_referencias(self):
        for coletar in (False, True):
            g = Gerador()
            if coletar:
                g.ativar_saltos_curtos_ssa()
            g.salto('ssa_fim')
            g.bytes(b'\x90' * 200)
            g.marcar('ssa_fim')
            self.comparar(g)


class TestesMedicaoCompilacaoRS042P(unittest.TestCase):
    def test_campanha_real_isolada_valida_programas_mistos_e_memoria(self):
        with tempfile.TemporaryDirectory() as pasta:
            caminho = Path(pasta) / 'resultado.json'
            resultado = medir_crescimento((2, 4), ('funcoes', 'misto'), (0, 8),
                                          repeticoes=2, arquivo=caminho)
            self.assertEqual(resultado['conclusao'], 'aprovado')
            self.assertEqual(len(resultado['resultados']), 8)
            self.assertTrue(caminho.exists())
            for registro in resultado['resultados']:
                self.assertEqual(len(registro['amostras']), 2)
                self.assertGreater(registro['memoria']['python_pico_bytes'], 0)
                gerador = registro['aquecimento']['gerador']
                self.assertEqual(gerador, 'conservador' if registro['familia'] == 'misto'
                                 else ('ssa' if registro['nivel'] == 8 else 'intermediario'))
            for tamanho in (2, 4):
                mistos = [r for r in resultado['resultados'] if r['familia'] == 'misto' and r['tamanho'] == tamanho]
                self.assertEqual(mistos[0]['identidade'][0], mistos[1]['identidade'][0])

    def test_trabalhador_registra_timeout_processo_e_protocolo_invalidos(self):
        import subprocess
        from types import SimpleNamespace
        with tempfile.TemporaryDirectory() as pasta:
            arquivo = Path(pasta) / 'configuracao.json'
            with patch('benchmarks.crescimento.subprocess.run', side_effect=subprocess.TimeoutExpired('ensaio', 2)):
                self.assertEqual(executar_trabalhador({}, arquivo, 2)['estado'], 'tempo_esgotado')
            with patch('benchmarks.crescimento.subprocess.run', return_value=SimpleNamespace(returncode=3, stderr='falha')):
                self.assertEqual(executar_trabalhador({}, arquivo, 2)['estado'], 'erro_processo')
            with patch('benchmarks.crescimento.subprocess.run', return_value=SimpleNamespace(returncode=0, stdout='invalido')):
                self.assertEqual(executar_trabalhador({}, arquivo, 2)['estado'], 'erro_protocolo')

    def test_tempos_aninhados_nao_sao_somados_duas_vezes(self):
        medidor = MedicaoCompilacao()
        with patch('compilador.medicao_compilacao.time.perf_counter_ns', side_effect=(100, 200, 300, 500)):
            with medidor.etapa('pai'):
                with medidor.etapa('filho'):
                    medidor.contar('unidades', 7)
        resumo = medidor.resumo()
        self.assertEqual(resumo['etapas']['pai'], {'chamadas': 1, 'total_ns': 400, 'proprio_ns': 300})
        self.assertEqual(resumo['etapas']['filho'], {'chamadas': 1, 'total_ns': 100, 'proprio_ns': 100})
        self.assertEqual(resumo['contadores'], {'unidades': 7})

    def test_excecao_fecha_as_etapas_e_preserva_diagnostico(self):
        medidor = MedicaoCompilacao()
        with self.assertRaises(RuntimeError):
            with medidor.etapa('falhou'):
                with self.assertRaises(ValueError):
                    medidor.resumo()
                raise RuntimeError('ensaio')
        self.assertEqual(medidor.resumo()['etapas']['falhou']['chamadas'], 1)

    def test_medidor_preserva_imagens_em_todos_os_caminhos(self):
        fontes = (
            'inicio {\n seja numero = 0\n leia(numero)\n escreva(numero + 2)\n}',
            'funcao calcular(numero: inteiro) -> inteiro {\n se numero > 0 {\n retorne numero + 3\n}\n retorne 0\n}\ninicio {\n escreva(calcular(4))\n}',
            'inicio {\n seja dados: bytes\n adicione_byte(dados, 7)\n escreva(dados[0])\n}',
        )
        for fonte in fontes:
            programa = analisar_programa(fonte)
            for alvo in ('windows', 'linux'):
                for nivel in (0, 3, 4, 6, 8):
                    with self.subTest(alvo=alvo, nivel=nivel):
                        medidor = MedicaoCompilacao()
                        self.assertEqual(compilar(programa, alvo, nivel=nivel, otimizar=nivel > 0),
                                         compilar(programa, alvo, nivel=nivel, otimizar=nivel > 0, medidor=medidor))
                        self.assertIn('montagem_executavel', medidor.resumo()['etapas'])
                        self.assertIn('emissao_nativa', medidor.resumo()['etapas'])
                        self.assertTrue(all(e['proprio_ns'] >= 0 for e in medidor.resumo()['etapas'].values()))

    def test_geradores_validos_tem_escala_e_oraculo_sem_dependencia_do_compilador(self):
        with tempfile.TemporaryDirectory() as pasta:
            for familia in ('instrucoes', 'desvios', 'funcoes', 'misto', 'modulos'):
                caso = gerar_caso(Path(pasta) / familia, familia, 4)
                analisar_programa(carregar_fontes(Path(caso['fonte'])).texto)
                self.assertEqual(caso['entrada'], '3\n')
                self.assertEqual(caso['esperado'], '4\n' if familia == 'desvios' else ('7\n' if familia == 'instrucoes' else '9\n'))
                self.assertGreater(caso['linhas'], 4)

    def test_memoria_em_amostra_separada_nao_muda_o_executavel(self):
        with tempfile.TemporaryDirectory() as pasta:
            base = Path(pasta)
            caso = gerar_caso(base / 'fonte', 'funcoes', 3)
            configuracao = {**caso, 'alvo': alvo_nativo(), 'nivel': 8,
                             'executavel': str(base / 'programa')}
            normal = compilar_caso(configuracao)
            memoria = compilar_caso(configuracao, memoria=True)
            self.assertEqual((normal['estado'], memoria['estado']), ('aprovado', 'aprovado'))
            self.assertEqual(normal['sha256_executavel'], memoria['sha256_executavel'])
            self.assertNotIn('compilacao_ms', memoria)
            self.assertGreater(memoria['memoria']['python_pico_bytes'], 0)
            self.assertGreater(memoria['memoria']['residente_pico_bytes'], 0)

    def test_erro_real_nao_e_classificado_como_medicao_aprovada(self):
        with tempfile.TemporaryDirectory() as pasta:
            fonte = Path(pasta) / 'falha.rts'
            fonte.write_text('inicio {\n escreva(desconhecido)\n}', encoding='utf-8')
            resultado = compilar_caso({'fonte': str(fonte), 'alvo': alvo_nativo(),
                                       'nivel': 8, 'executavel': str(Path(pasta) / 'programa')})
            self.assertEqual((resultado['estado'], resultado['tipo_erro']), ('recusado', 'ErroCompilacao'))
            self.assertIn('carregar_modulos', resultado['etapas'])

    def test_parametros_nao_criam_uma_campanha_impossivel(self):
        for opcoes in ({'tamanhos': ()}, {'tamanhos': (1, 1)}, {'familias': ('desconhecido',)},
                       {'niveis': (9,)}, {'repeticoes': 1}, {'timeout': 0}):
            with self.subTest(opcoes=opcoes), self.assertRaises(ValueError):
                medir_crescimento(**opcoes)
