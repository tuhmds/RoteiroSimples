"""Contrato dos operadores lógicos na IR, SSA e análise de efeitos."""
from dataclasses import replace
import json
from pathlib import Path
import sys
import unittest

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

from compilador.ast import NoExpressao, PosicaoFonte, Programa
from compilador.cfg import construir_cfg
from compilador.cobertura_intermediaria import analisar_cobertura, formatar_cobertura
from compilador.contrato_efeitos import Efeitos, podem_trocar_de_ordem
from compilador.efeitos import efeito_expressao, resumir_funcoes
from compilador.efeitos_programa import efeito_expressao_arvore
from compilador.fluxo_dados import analisar_fluxo
from compilador.ir import (construir_ir, converter_expressao, expressao_para_ast,
                           formatar_ir, programa_para_backend)
from compilador.memory_ssa import construir_memory_ssa
from compilador.nos_ir import ExpressaoIR, FuncaoIR, InstrucaoIR, ProgramaIR
from compilador.otimizacao_funcoes_ssa import otimizar_funcoes_com_ssa
from compilador.otimizador import dobrar_constantes
from compilador.propagacao import otimizar_expressao, propagar_constantes_locais
from compilador.ssa import construir_ssa
from compilador.ssa_funcoes import construir_ssa_programa
from compilador.ssa_otimizador import analisar_constantes_ssa


def logico(valor):
    return ExpressaoIR('logico', 'logico', int(valor))


def chamada():
    return ExpressaoIR('logico', 'chamada', 'marcar')


def combinacao(operador, esquerdo, direito):
    return ExpressaoIR('logico', 'logica', operador, (esquerdo, direito))


def corpo(instrucoes, tipos=None):
    tipos = tipos or {}
    return ProgramaIR(tuple(instrucoes), tipos, {n: 0 for n in tipos}, False)


def funcao_com_saida():
    return FuncaoIR('marcar', (), 'logico', corpo((
        InstrucaoIR('texto', ('marcou',)),
        InstrucaoIR('retorne', (logico(True),)),
    )))


class TestesLogicosIRRS042O(unittest.TestCase):
    def test_ir_tipado_preserva_arvore_e_posicoes_sem_otimizacao(self):
        ponto = PosicaoFonte(9, 13)
        filho = NoExpressao(('nao', ('var', 'direito')), PosicaoFonte(9, 21))
        arvore = NoExpressao(('logica', 'e', ('var', 'esquerdo'), filho), ponto)
        expr = converter_expressao(arvore,
            {'esquerdo': 'logico', 'direito': 'logico'}, otimizar=False)
        self.assertEqual((expr.tipo, expr.operacao, expr.valor), ('logico', 'logica', 'e'))
        self.assertEqual(expr.origem, ponto)
        reconstruida = expressao_para_ast(expr)
        self.assertEqual(reconstruida, arvore)
        self.assertEqual(reconstruida[3].origem, filho.origem)
        ir = corpo((InstrucaoIR('imprima_num', (expr,)),))
        self.assertEqual(programa_para_backend(ir).instrucoes[0][1], arvore)
        self.assertIn('logica:logico(e,', formatar_ir(ir))
        self.assertIn('nao:logico(', formatar_ir(ir))

    def test_dobramento_das_tabelas_verdade_normaliza_resultado(self):
        for operador in ('e', 'ou'):
            for esquerdo in (False, True):
                for direito in (False, True):
                    with self.subTest(operador=operador, esquerdo=esquerdo, direito=direito):
                        esperado = (esquerdo and direito if operador == 'e' else esquerdo or direito)
                        novo = dobrar_constantes(combinacao(operador, logico(esquerdo), logico(direito)))
                        self.assertEqual((novo.tipo, novo.operacao, novo.valor),
                                         ('logico', 'logico', int(esperado)))
        for valor in (0, 1, 9):
            expr = ExpressaoIR('logico', 'nao', filhos=(logico(valor),))
            self.assertEqual(dobrar_constantes(expr).valor, int(not valor))

    def test_esquerdo_literal_dispensa_chamada_ou_falha_direita(self):
        divisao = converter_expressao(('comparacao', '==',
            ('bin', '/', ('numero', 1), ('numero', 0)), ('numero', 0)), {}, otimizar=True)
        for direito in (chamada(), divisao):
            for operador, esquerdo in (('e', False), ('ou', True)):
                with self.subTest(operador=operador, direito=direito.operacao):
                    novo = dobrar_constantes(combinacao(operador, logico(esquerdo), direito))
                    self.assertEqual(novo, logico(esquerdo))

    def test_direito_literal_nunca_apaga_chamada_ou_falha_esquerda(self):
        divisao = converter_expressao(('comparacao', '==',
            ('bin', '/', ('numero', 1), ('numero', 0)), ('numero', 0)), {}, otimizar=True)
        for esquerdo in (chamada(), divisao):
            for operador, direito in (('e', False), ('ou', True)):
                original = combinacao(operador, esquerdo, logico(direito))
                self.assertEqual(dobrar_constantes(original), original)
        negada = ExpressaoIR('logico', 'nao', filhos=(chamada(),))
        self.assertEqual(dobrar_constantes(negada), negada)

    def test_propagacao_invalida_constantes_apos_chamada_sem_argumentos(self):
        for operador in ('e', 'ou'):
            ambiente = {'flag': 1}
            expr = combinacao(operador, chamada(), ExpressaoIR('logico', 'var', 'flag'))
            novo = otimizar_expressao(expr, ambiente)
            self.assertEqual(novo.filhos[1].operacao, 'var')
            self.assertEqual(ambiente, {})
        ir = corpo((InstrucaoIR('atribua', ('flag', logico(True))),
                    InstrucaoIR('imprima_num', (chamada(),)),
                    InstrucaoIR('imprima_num', (ExpressaoIR('logico', 'var', 'flag'),))),
                   {'flag': 'logico'})
        novo = propagar_constantes_locais(ir)
        self.assertEqual(novo.instrucoes[-1].argumentos[0].operacao, 'var')

    def test_propagacao_preserva_ordem_dos_argumentos_e_ramos_dispenseis(self):
        ambiente = {'flag': 1}
        expr = ExpressaoIR('logico', 'chamada', 'receber',
                          (ExpressaoIR('logico', 'var', 'flag'), chamada(),
                           ExpressaoIR('logico', 'var', 'flag')))
        novo = otimizar_expressao(expr, ambiente)
        self.assertEqual([f.operacao for f in novo.filhos], ['logico', 'chamada', 'var'])
        self.assertFalse(ambiente)
        for operador, valor in (('e', False), ('ou', True)):
            ambiente = {'flag': 1}
            novo = otimizar_expressao(combinacao(operador, logico(valor), chamada()), ambiente)
            self.assertEqual(novo, logico(valor))
            self.assertEqual(ambiente, {'flag': 1})

    def test_efeitos_arvore_e_ir_incluem_leituras_e_falhas_potenciais(self):
        arvore = ('logica', 'e', ('var', 'habilitado'), ('nao', ('comparacao', '==',
                   ('indice', 'dados', ('var', 'indice'), 2), ('numero', 0))))
        expr = converter_expressao(arvore, {'habilitado': 'logico', 'indice': 'inteiro'}, False)
        for efeito in (efeito_expressao_arvore(arvore), efeito_expressao(expr)):
            self.assertEqual(efeito.leituras, frozenset(('habilitado', 'dados', 'indice')))
            self.assertTrue(efeito.pode_falhar)
            self.assertTrue(efeito.controle)
            self.assertFalse(efeito.desconhecido)
            self.assertFalse(podem_trocar_de_ordem(efeito, Efeitos()))
        puro = converter_expressao(('nao', ('var', 'flag')), {'flag': 'logico'}, False)
        self.assertFalse(efeito_expressao(puro).pode_falhar)
        self.assertFalse(efeito_expressao_arvore(('nao', ('var', 'flag'))).desconhecido)

    def test_resumo_de_chamada_direita_permanece_barreira(self):
        ir = replace(corpo(()), funcoes={'marcar': funcao_com_saida()})
        expr = combinacao('e', logico(False), chamada())
        efeito = efeito_expressao(expr, resumir_funcoes(ir))
        self.assertTrue(efeito.saida)
        self.assertTrue(efeito.pode_falhar)
        self.assertTrue(efeito.controle)
        self.assertFalse(efeito.desconhecido)

    def test_ssa_preserva_chamadas_obrigatorias_mesmo_com_resultado_nao_usado(self):
        for operador, direito in (('e', False), ('ou', True)):
            expr = combinacao(operador, chamada(), logico(direito))
            ir = replace(corpo((InstrucaoIR('atribua', ('ignorado', expr)),),
                               {'ignorado': 'logico'}), funcoes={'marcar': funcao_com_saida()})
            novo = otimizar_funcoes_com_ssa(ir)
            self.assertEqual(novo.instrucoes[0].argumentos[1], expr)
            self.assertTrue(construir_ssa_programa(novo).validar())

    def test_ssa_prova_operando_esquerdo_constante_sem_avaliar_chamada_dispensa(self):
        for operador, flag in (('e', False), ('ou', True)):
            ir = replace(corpo((InstrucaoIR('atribua', ('flag', logico(flag))),
                InstrucaoIR('atribua', ('resposta', combinacao(operador,
                    ExpressaoIR('logico', 'var', 'flag'), chamada())))),
                {'flag': 'logico', 'resposta': 'logico'}), funcoes={'marcar': funcao_com_saida()})
            ssa = construir_ssa_programa(ir).principal
            constantes = analisar_constantes_ssa(ssa)
            self.assertEqual(constantes['resposta@0'], int(flag))
            novo = otimizar_funcoes_com_ssa(ir)
            self.assertEqual(novo.instrucoes[-1].argumentos[1], logico(flag))

    def test_ssa_fluxo_serializacao_e_diagnostico_de_desvios_internos(self):
        expr = combinacao('ou', ExpressaoIR('logico', 'var', 'esquerdo'),
                          ExpressaoIR('logico', 'nao', filhos=(ExpressaoIR('logico', 'var', 'direito'),)))
        ir = corpo((InstrucaoIR('atribua', ('esquerdo', logico(False))),
                    InstrucaoIR('atribua', ('direito', logico(True))),
                    InstrucaoIR('imprima_num', (expr,))),
                   {'esquerdo': 'logico', 'direito': 'logico'})
        cfg = construir_cfg(ir)
        fluxo = analisar_fluxo(cfg)
        bid = next(b for b, no in cfg.blocos.items() if no.papel == 'imprima_num')
        self.assertEqual(fluxo.usos[bid], {'esquerdo', 'direito'})
        ssa = construir_ssa(cfg)
        self.assertEqual(ssa.blocos[bid].instrucoes[0].usos, ('esquerdo@0', 'direito@0'))
        self.assertTrue(ssa.validar())
        self.assertIn('curto-circuito', cfg.formatar())
        self.assertIn('nao(direito@0)', ssa.formatar())
        self.assertIn('dependências potenciais', ssa.formatar())
        dados = json.loads(ssa.para_json())
        bjson = next(b for b in dados['blocos'] if b['id'] == bid)
        ej = bjson['instrucoes'][0]['argumentos'][0]
        self.assertEqual((ej['operacao'], ej['filhos'][1]['operacao']), ('logica', 'nao'))
        self.assertFalse(construir_cfg(corpo(())).tem_curto_circuito())
        self.assertNotIn('curto-circuito', construir_cfg(corpo(())).formatar())

    def test_memoria_versionada_conserva_dependencia_de_lista_direita(self):
        expr = converter_expressao(('logica', 'e', ('logico', 0),
            ('comparacao', '==', ('indice', 'dados', ('numero', 7), 2), ('numero', 0))), {}, False)
        ir = corpo((InstrucaoIR('crie_lista', ('dados', 2)),
                    InstrucaoIR('imprima_num', (expr,))), {'dados': ('lista', 'inteiro', 2)})
        memoria = construir_memory_ssa(ir)
        self.assertTrue(memoria.validar())
        infos = [i for b in memoria.blocos.values() for i in b.instrucoes
                 if i.operacao == 'imprima_num']
        self.assertEqual(len(infos), 1)
        self.assertIn('mem:dados', infos[0].usos)
        self.assertIn('efeito:falha', infos[0].definicoes)
        self.assertIn('efeito:ordem', infos[0].definicoes)

    def test_cobertura_visita_filhos_dispensaveis_e_explica_limite_cfg(self):
        p = Programa([('imprima_num', ('logica', 'ou', ('logico', 1),
                      ('nao', ('comparacao', '==', ('byte_texto', 'dados', ('numero', 0)),
                               ('numero', 0)))))], {}, False, {})
        cobertura = analisar_cobertura(p)
        self.assertFalse(cobertura.completa)
        self.assertEqual(cobertura.expressoes_ausentes, ('byte_texto',))
        self.assertEqual(dict(cobertura.expressoes)['nao'], 1)
        self.assertIn('sem expandir seus desvios internos', formatar_cobertura(cobertura))
        p = Programa([('imprima_num', ('nao', ('logico', 1)))], {}, False, {})
        self.assertTrue(analisar_cobertura(p).completa)
        self.assertEqual(construir_ir(p).instrucoes[0].argumentos[0], logico(False))


if __name__ == '__main__':
    unittest.main()
