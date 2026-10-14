"""Projeções completas nos dados necessários; demais cálculos não executados."""
from contextlib import ExitStack
import json
import unittest
from unittest.mock import patch

from backend import compilar
from benchmarks.analise_ssa import medir_analise
from compilador.cfg import construir_cfg, construir_cfg_programa
from compilador.fluxo_dados import (analisar_fluxo, analisar_fluxo_ssa,
                                   analisar_vivacidade, analisar_dominadores)
from compilador.ir import construir_ir
from compilador.medicao_compilacao import MedicaoCompilacao
from compilador.parser import analisar_programa
from compilador.ssa import construir_ssa
from compilador.ssa_otimizador import otimizar_com_ssa
from testes.fixtures.fluxo_rs042q import (analisar_fluxo_antes, construir_ssa_antes,
                                        otimizar_com_ssa_antes)
from testes.test_analise_ssa_rs042q import fonte_gerada


class TestesFluxoSeletivoRS042R(unittest.TestCase):
    def conferir(self, cfg):
        completo = analisar_fluxo_antes(cfg)
        atual = analisar_fluxo(cfg)
        self.assertEqual(atual, completo)
        self.assertEqual(atual.para_json(), completo.para_json())
        self.assertEqual(atual.formatar(), completo.formatar())
        vivacidade = analisar_vivacidade(cfg)
        ssa = analisar_fluxo_ssa(cfg)
        for nome in ('cfg', 'usos', 'definicoes', 'vivos_entrada', 'vivos_saida'):
            self.assertEqual(getattr(vivacidade, nome), getattr(completo, nome))
            self.assertEqual(getattr(ssa, nome), getattr(completo, nome))
        self.assertEqual(ssa.dominadores, completo.dominadores)
        self.assertEqual(analisar_dominadores(cfg), completo.dominadores)
        self.assertFalse(hasattr(vivacidade, 'dominadores'))
        self.assertFalse(hasattr(ssa, 'entradas_def'))
        atual_ssa, antes_ssa = construir_ssa(cfg), construir_ssa_antes(cfg)
        self.assertEqual(atual_ssa.para_json(), antes_ssa.para_json())
        self.assertEqual(atual_ssa.dominadores, antes_ssa.dominadores)

    def test_64_programas_com_lacos_e_juncoes_preservam_dados(self):
        for semente in range(64):
            with self.subTest(semente=semente):
                ir = construir_ir(analisar_programa(fonte_gerada(semente)), nivel=2)
                self.conferir(construir_cfg(ir))
                self.assertEqual(otimizar_com_ssa(ir), otimizar_com_ssa_antes(ir))

    def test_parametros_retornos_e_blocos_inacessiveis(self):
        fonte = '''funcao calcular(numero: inteiro) -> inteiro {
            seja total = numero
            enquanto total < 5 {
                total = total + 1
                se total == 3 {
                    retorne total
                }
            }
            retorne total
            escreva(999)
        }
        inicio {
            escreva(calcular(0))
        }'''
        grafos = construir_cfg_programa(construir_ir(analisar_programa(fonte), nivel=2))
        for cfg in (grafos.principal, *grafos.funcoes.values()):
            self.conferir(cfg)

    def test_cada_projecao_impede_calculos_que_nao_utiliza(self):
        cfg = construir_cfg(construir_ir(analisar_programa(fonte_gerada(2)), nivel=2))
        for funcao, proibidos in (
            (analisar_vivacidade, ('calcular_dominadores', 'calcular_definicoes_alcancam', 'calcular_garantidas', 'calcular_diagnosticos')),
            (analisar_fluxo_ssa, ('calcular_definicoes_alcancam', 'calcular_garantidas', 'calcular_diagnosticos')),
            (analisar_dominadores, ('calcular_vivacidade', 'calcular_definicoes_alcancam', 'calcular_garantidas', 'calcular_diagnosticos'))):
            with self.subTest(funcao=funcao.__name__), ExitStack() as pilha:
                for nome in proibidos:
                    pilha.enter_context(patch('compilador.calculos_fluxo.' + nome, side_effect=AssertionError(nome)))
                if funcao is analisar_dominadores:
                    pilha.enter_context(patch('compilador.fluxo_dados.efeitos_bloco', side_effect=AssertionError('efeitos')))
                funcao(cfg)

    def test_compilacao_tem_duas_dominancias_e_somente_vivacidade_no_exame_de_mortos(self):
        medidor = MedicaoCompilacao()
        programa = analisar_programa(fonte_gerada(5))
        compilar(programa, 'windows', nivel=8, medidor=medidor)
        resumo = medidor.resumo()
        self.assertEqual(resumo['contadores']['fluxo_analises_ssa'], 2)
        self.assertEqual(resumo['contadores']['fluxo_analises_vivacidade'], 1)
        self.assertEqual(resumo['etapas']['fluxo_dominadores']['chamadas'], 2)
        self.assertEqual(resumo['etapas']['fluxo_vivacidade']['chamadas'], 3)
        for nome in ('fluxo_definicoes_alcancam', 'fluxo_definicoes_garantidas', 'fluxo_diagnosticos'):
            self.assertNotIn(nome, resumo['etapas'])

    def test_grafo_modificado_e_analise_nova_nao_compartilham_cache(self):
        cfg = construir_cfg(construir_ir(analisar_programa(fonte_gerada(5)), nivel=2))
        self.conferir(cfg)
        cfg.blocos[cfg.entrada].saidas = ()
        self.conferir(cfg)

    def test_excecao_fecha_observacao_de_todas_as_projecoes(self):
        for funcao in (analisar_fluxo, analisar_fluxo_ssa, analisar_vivacidade, analisar_dominadores):
            medidor = MedicaoCompilacao()
            cfg = construir_cfg(construir_ir(analisar_programa(fonte_gerada(1)), nivel=2))
            with patch('compilador.calculos_fluxo.preparar_grafo', side_effect=ValueError('ensaio')):
                with self.assertRaisesRegex(ValueError, 'ensaio'):
                    funcao(cfg, medidor)
            self.assertIn('fluxo_preparacao', medidor.resumo()['etapas'])

    def test_imagens_preservadas_contra_a_042q_inclusive_memoria(self):
        fontes = [fonte_gerada(n) for n in (1, 5, 9)] + [
            'inicio {\n seja numeros: lista[8]\n seja indice = 0\n leia(indice)\n numeros[indice] = 3\n escreva(numeros[indice])\n}',
            'funcao calcular(numero: inteiro) -> inteiro {\n seja total = 0\n para indice de 1 ate numero {\n total = total + indice\n }\n retorne total\n}\ninicio {\n escreva(calcular(5))\n}',
            'inicio {\n seja divisor = 0\n leia(divisor)\n escreva(10 / divisor)\n}',
        ]
        for fonte in fontes:
            programa = analisar_programa(fonte)
            for alvo in ('windows', 'linux'):
                for nivel in range(9):
                    atual = compilar(programa, alvo, nivel=nivel, otimizar=nivel > 0)
                    with ExitStack() as pilha:
                        for modulo in ('compilador.ssa_otimizador', 'compilador.ssa_funcoes', 'backend.ssa_x86_64'):
                            pilha.enter_context(patch(modulo + '.construir_ssa', side_effect=construir_ssa_antes))
                        pilha.enter_context(patch('compilador.ssa_otimizador.otimizar_com_ssa', side_effect=otimizar_com_ssa_antes))
                        pilha.enter_context(patch('compilador.memory_ssa.analisar_dominadores', side_effect=lambda cfg: analisar_fluxo_antes(cfg).dominadores))
                        anterior = compilar(programa, alvo, nivel=nivel, otimizar=nivel > 0)
                    self.assertEqual(atual, anterior, (alvo, nivel, fonte[:50]))

    def test_benchmark_compara_referencia_042q_e_preserva_default_042p(self):
        resultado = medir_analise((4, 12), repeticoes=2, referencia='rs042q')
        self.assertEqual(resultado['referencia_commit'], '47eb322107b41fd9c675fdb3d243df66794f4e2b')
        for tamanho in (4, 12):
            for fase in ('construcao', 'otimizacao'):
                dupla = [r for r in resultado['resultados'] if r['tamanho'] == tamanho and r['metodo'].startswith(fase)]
                self.assertEqual(dupla[0]['sha256'], dupla[1]['sha256'])
        with self.assertRaises(ValueError):
            medir_analise((4,), repeticoes=2, referencia='inexistente')
