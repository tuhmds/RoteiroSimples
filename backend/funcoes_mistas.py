"""Emissão por função, preservando o início e os corpos não elegíveis."""
from dataclasses import replace

from compilador.alocacao import alocar_registradores
from compilador.funcoes_mistas import construir_ir_funcoes
from compilador.ir import programa_para_backend
from compilador.medicao_compilacao import etapa
from compilador.ssa_funcoes import construir_ssa_funcoes
from .funcoes_ssa import BackendFuncoesSSA, preparar_emissor_funcao
from .x86_64 import montar_codigo


def preparar_funcoes_mistas(programa, decisao, windows, medidor=None):
    nomes = tuple(f.nome for f in decisao.funcoes if f.elegivel)
    grupo = construir_ir_funcoes(programa, nomes, nivel=min(decisao.nivel_solicitado, 3),
                                otimizar=decisao.otimiza, medidor=medidor)
    # As cópias evitam modificar a AST usada por O0 ou por uma segunda compilação.
    funcoes = dict(programa.funcoes)
    emissores = {}
    plano = None
    if decisao.nivel_solicitado >= 4 and decisao.otimiza:
        ssa = construir_ssa_funcoes(grupo, medidor)
        with etapa(medidor, 'alocacao_registradores'):
            alocacoes = {nome: alocar_registradores(corpo, coalescer=decisao.nivel_solicitado >= 6,
                                                  limite_vagas=None)
                         for nome, corpo in ssa.funcoes.items()}
        plano = BackendFuncoesSSA(ssa, alocacoes)
        if medidor is not None:
            medidor.contar('blocos_cfg', sum(len(s.cfg.blocos) for s in ssa.funcoes.values()))
            medidor.contar('vagas_pilha', sum(a.vagas_pilha for a in alocacoes.values()))
    with etapa(medidor, 'preparacao_emissor_funcoes_mistas'):
        for nome, funcao_ir in grupo.funcoes.items():
            funcoes[nome] = replace(programa.funcoes[nome], programa=programa_para_backend(funcao_ir.programa))
            if plano is not None:
                emissores[nome] = preparar_emissor_funcao(funcoes[nome], funcao_ir,
                    plano.programa.funcoes[nome], plano.alocacoes[nome], windows, decisao.nivel_solicitado)
    return replace(programa, funcoes=funcoes), emissores, plano


def montar_funcoes_mistas(programa, decisao, windows, medidor=None):
    legado, emissores, _ = preparar_funcoes_mistas(programa, decisao, windows, medidor)
    with etapa(medidor, 'emissao_nativa'):
        return montar_codigo(legado, windows, emissores_funcoes=emissores)
