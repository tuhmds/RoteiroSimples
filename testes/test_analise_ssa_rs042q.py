"""Equivalência com a RS 0.42P e limites estruturais das buscas eliminadas."""
from contextlib import ExitStack
import json
from pathlib import Path
import random
import tempfile
import unittest
from unittest.mock import patch

from backend import compilar
from benchmarks.analise_ssa import medir_analise
from benchmarks.crescimento import gerar_caso
from compilador.cfg import GrafoCFG, construir_cfg, construir_cfg_programa
from compilador.ir import construir_ir
from compilador.fluxo_dados import analisar_fluxo
from compilador.medicao_compilacao import MedicaoCompilacao
from compilador.modulos import carregar_fontes
from compilador.parser import analisar_programa
from compilador.ssa import BlocoSSA, _ordenar_bloco, _posicionar_phis, construir_ssa
from compilador.ssa_otimizador import otimizar_com_ssa
from testes.fixtures.ssa_rs042p import analisar_fluxo_antes, construir_ssa_antes, otimizar_com_ssa_antes


def fonte_gerada(semente):
    aleatorio = random.Random(semente)
    corpo = ['seja numero = 0', 'leia(numero)', 'seja total = 0', 'seja indice = 0',
             'seja aceita: logico = falso']
    for n in range(aleatorio.randrange(2, 7)):
        limite = aleatorio.randrange(1, 5)
        tipo = aleatorio.randrange(3)
        if tipo == 0:
            corpo += [f'se numero >= {limite} {{', 'total = total + 1',
                      '} senao {', 'total = total + 2', '}']
        elif tipo == 1:
            corpo += ['indice = 0', f'enquanto indice < {limite} {{', 'indice = indice + 1',
                      'se indice == 2 {', 'continue', '}', 'total = total + indice',
                      'se total > 20 {', 'pare', '}', '}']
        else:
            corpo += [f'para contador_{n} de 1 ate {limite} {{',
                      f'se contador_{n} == 2 {{', 'continue', '}',
                      f'total = total + contador_{n}', '}']
        corpo += [f'aceita = numero < {limite} e total >= 0 ou falso']
    return 'inicio {\n' + '\n'.join(corpo + ['escreva(total)', 'escreva(aceita)']) + '\n}'


def referencia_nativa():
    pilha = ExitStack()
    for modulo in ('compilador.ssa_otimizador', 'compilador.ssa_funcoes', 'backend.ssa_x86_64'):
        pilha.enter_context(patch(modulo + '.construir_ssa', side_effect=lambda cfg, medidor=None: construir_ssa_antes(cfg)))
    pilha.enter_context(patch('compilador.ssa_otimizador.otimizar_com_ssa',
                             side_effect=lambda ir, medidor=None: otimizar_com_ssa_antes(ir)))
    return pilha


class TestesAnaliseSSARS042Q(unittest.TestCase):
    def comparar_ssa(self, cfg):
        atual, anterior = construir_ssa(cfg), construir_ssa_antes(cfg)
        self.assertEqual(json.loads(atual.para_json()), json.loads(anterior.para_json()))
        self.assertEqual(atual.dominadores, anterior.dominadores)
        self.assertEqual(atual.predecessores, anterior.predecessores)
        self.assertEqual(atual.idom, anterior.idom)
        self.assertEqual(atual.fronteiras, anterior.fronteiras)
        self.assertTrue(atual.validar())

    def test_programas_gerados_preservam_phi_dominancia_e_ir(self):
        for semente in range(64):
            with self.subTest(semente=semente):
                ir = construir_ir(analisar_programa(fonte_gerada(semente)), nivel=2)
                cfg = construir_cfg(ir)
                self.assertEqual(analisar_fluxo(cfg), analisar_fluxo_antes(cfg))
                self.comparar_ssa(cfg)
                self.assertEqual(otimizar_com_ssa(ir), otimizar_com_ssa_antes(ir))

    def test_funcao_com_retornos_parametros_e_codigo_inalcancavel(self):
        fonte = '''funcao calcular(numero: inteiro, aceita: logico) -> inteiro {
            seja total = numero
            enquanto total < 5 {
                total = total + 1
                se aceita e total >= 3 {
                    retorne total
                }
            }
            retorne total
            escreva(999)
        }
        inicio {
            escreva(calcular(0, verdadeiro))
        }
        '''
        grafos = construir_cfg_programa(construir_ir(analisar_programa(fonte), nivel=2))
        self.comparar_ssa(grafos.principal)
        for cfg in grafos.funcoes.values():
            self.comparar_ssa(cfg)

    def test_dois_grafos_modificados_nao_reutilizam_alcancabilidade(self):
        ir = construir_ir(analisar_programa(fonte_gerada(3)), nivel=2)
        primeiro = construir_cfg(ir)
        self.comparar_ssa(primeiro)
        entrada = primeiro.blocos[primeiro.entrada]
        entrada.saidas = ()
        # Grafo apenas de análise, sem leitura de variáveis na entrada.
        self.comparar_ssa(primeiro)
        self.comparar_ssa(construir_cfg(ir))

    def test_imagens_iguais_ao_algoritmo_anterior_em_todos_os_niveis(self):
        fontes = [fonte_gerada(n) for n in (0, 1, 3, 7)] + [
            'inicio {\n seja numero = 0\n leia(numero)\n seja total = 9223372036854775807\n total = total + numero\n escreva(total)\n}',
            'inicio {\n seja numero = 0\n leia(numero)\n escreva(10 / numero)\n}',
            'funcao calcular(numero: inteiro) -> inteiro {\n se numero < 0 {\n retorne 0\n }\n seja soma = 0\n para indice de 1 ate numero {\n soma = soma + indice\n }\n retorne soma\n}\ninicio {\n escreva(calcular(5))\n}',
        ]
        for fonte in fontes:
            programa = analisar_programa(fonte)
            for alvo in ('windows', 'linux'):
                for nivel in range(9):
                    with self.subTest(alvo=alvo, nivel=nivel, fonte=fonte[:55]):
                        atual = compilar(programa, alvo, nivel=nivel, otimizar=nivel > 0)
                        with referencia_nativa():
                            anterior = compilar(programa, alvo, nivel=nivel, otimizar=nivel > 0)
                        self.assertEqual(atual, anterior)

    def test_fila_minima_nao_busca_o_menor_por_varredura(self):
        for quantidade in (64, 256, 1024):
            ids = {f'b{n}' for n in range(quantidade)}
            blocos = {b: BlocoSSA(b, 'atribua') for b in ids}
            medidor = MedicaoCompilacao()
            with patch('compilador.ssa._ordenar_bloco', wraps=_ordenar_bloco) as chave:
                _posicionar_phis({'numero': ids}, {b: set() for b in ids},
                                {b: {'numero'} for b in ids}, blocos, {'numero': 'inteiro'}, medidor)
            self.assertEqual(chave.call_count, quantidade)
            contadores = medidor.resumo()['contadores']
            self.assertEqual(contadores['ssa_fila_phi_insercoes'], quantidade)
            self.assertEqual(contadores['ssa_fila_phi_remocoes'], quantidade)

    def test_otimizacao_percorre_alcancaveis_um_numero_constante_de_vezes(self):
        with tempfile.TemporaryDirectory() as pasta:
            for tamanho in (8, 64, 256):
                caso = gerar_caso(Path(pasta) / str(tamanho), 'desvios', tamanho)
                ir = construir_ir(analisar_programa(carregar_fontes(Path(caso['fonte'])).texto), nivel=2)
                original = GrafoCFG.alcancaveis
                with patch.object(GrafoCFG, 'alcancaveis', autospec=True, side_effect=original) as buscas:
                    otimizar_com_ssa(ir)
                self.assertLessEqual(buscas.call_count, 6)

    def test_etapas_internas_preservam_imagens_e_tempos_proprios(self):
        fontes = [fonte_gerada(7),
                  'funcao calcular(numero: inteiro) -> inteiro {\n retorne numero + 2\n}\ninicio {\n escreva(calcular(3))\n}',
                  'inicio {\n seja dados: bytes\n adicione_byte(dados, 7)\n escreva(dados[0])\n}']
        for fonte in fontes:
            programa = analisar_programa(fonte)
            for alvo in ('windows', 'linux'):
                medidor = MedicaoCompilacao()
                atual = compilar(programa, alvo, nivel=8, medidor=medidor)
                self.assertEqual(atual, compilar(programa, alvo, nivel=8))
                resumo = medidor.resumo()
                self.assertTrue(all(0 <= e['proprio_ns'] <= e['total_ns'] for e in resumo['etapas'].values()))
                if 'bytes' not in fonte:
                    for nome in ('ir_conversao', 'ssa_dominancia', 'ssa_posicionamento_phi',
                                 'ssa_renomeacao', 'ssa_validacao', 'fluxo_dominadores', 'fluxo_vivacidade'):
                        self.assertIn(nome, resumo['etapas'])
                    self.assertEqual(resumo['contadores']['ssa_fila_phi_insercoes'],
                                     resumo['contadores']['ssa_fila_phi_remocoes'])
                else:
                    self.assertNotIn('ssa_dominancia', resumo['etapas'])

    def test_medidor_fecha_etapas_quando_ssa_recusa_leitura(self):
        ir = construir_ir(analisar_programa('inicio {\n seja numero = 2\n escreva(numero)\n}'), nivel=0)
        cfg = construir_cfg(ir)
        bloco = next(b for b in cfg.blocos.values() if b.papel == 'atribua')
        bloco.instrucoes = ()
        medidor = MedicaoCompilacao()
        with self.assertRaisesRegex(ValueError, 'antes de definição'):
            construir_ssa(cfg, medidor=medidor)
        self.assertIn('ssa_renomeacao', medidor.resumo()['etapas'])

    def test_serializacao_calcula_alcancabilidade_uma_vez_por_documento(self):
        cfg = construir_cfg(construir_ir(analisar_programa(fonte_gerada(5)), nivel=2))
        fluxo = analisar_fluxo(cfg)
        original = GrafoCFG.alcancaveis
        with patch.object(GrafoCFG, 'alcancaveis', autospec=True, side_effect=original) as buscas:
            primeiro = json.loads(fluxo.para_json())
            self.assertEqual(buscas.call_count, 1)
        cfg.blocos[cfg.entrada].saidas = ()
        with patch.object(GrafoCFG, 'alcancaveis', autospec=True, side_effect=original) as buscas:
            segundo = json.loads(fluxo.para_json())
            self.assertEqual(buscas.call_count, 1)
        self.assertGreater(sum(b['alcancavel'] for b in primeiro['blocos']), 1)
        self.assertEqual([b['id'] for b in segundo['blocos'] if b['alcancavel']], [cfg.entrada])

    def test_microbenchmark_confere_resultados_e_intercala_amostras(self):
        resultado = medir_analise((4, 12), repeticoes=2)
        self.assertEqual(len(resultado['ordens']), 3)
        self.assertEqual(len(resultado['resultados']), 8)
        for tamanho in (4, 12):
            for fase in ('construcao', 'otimizacao'):
                dupla = [r for r in resultado['resultados'] if r['tamanho'] == tamanho and r['metodo'].startswith(fase)]
                self.assertEqual(dupla[0]['sha256'], dupla[1]['sha256'])
                self.assertTrue(all(len(r['amostras_ms']) == 2 for r in dupla))

    def test_microbenchmark_recusa_parametros_invalidos(self):
        for tamanhos, repeticoes in (((), 2), ((4, 4), 2), ((0,), 2), ((2049,), 2), ((4,), 1)):
            with self.assertRaises(ValueError):
                medir_analise(tamanhos, repeticoes)
