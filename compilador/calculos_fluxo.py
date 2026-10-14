"""Cálculos puros compartilhados pelas análises de fluxo selecionadas."""
from collections import defaultdict
from dataclasses import dataclass


@dataclass
class GrafoAnalise:
    cfg: object
    alcancaveis: set
    ordem: list
    predecessores: dict


def preparar_grafo(cfg):
    cfg.validar()
    vivos = cfg.alcancaveis()
    blocos = cfg.blocos
    ordem = [nome for nome in blocos if nome in vivos]
    predecessores = defaultdict(set)
    for nome in ordem:
        for aresta in blocos[nome].saidas:
            if aresta.destino in vivos:
                predecessores[aresta.destino].add(nome)

    return GrafoAnalise(cfg, vivos, ordem, predecessores)


def calcular_definicoes_alcancam(grafo, defs):
    cfg = grafo.cfg
    blocos = cfg.blocos
    vivos = grafo.alcancaveis
    ordem = grafo.ordem
    predecessores = grafo.predecessores
    definicoes_por_variavel = defaultdict(set)
    for nome in ordem:
        for variavel in defs[nome]:
            definicoes_por_variavel[variavel].add(f'{nome}:{variavel}')
    geradas = {b: {f'{b}:{var}' for var in defs[b]} for b in ordem}
    eliminadas = {b: set().union(*(definicoes_por_variavel[var] for var in defs[b])) - geradas[b]
                  for b in ordem}
    entradas_def = {b: set() for b in blocos}
    saidas_def = {b: set() for b in blocos}
    mudou = True
    while mudou:
        mudou = False
        for nome in ordem:
            entrada = set().union(*(saidas_def[p] for p in predecessores[nome])) if predecessores[nome] else set()
            saida = geradas[nome] | (entrada - eliminadas[nome])
            if entrada != entradas_def[nome] or saida != saidas_def[nome]:
                entradas_def[nome], saidas_def[nome] = entrada, saida
                mudou = True
    return definicoes_por_variavel, entradas_def, saidas_def


def calcular_vivacidade(grafo, usos, defs):
    cfg = grafo.cfg
    blocos = cfg.blocos
    vivos = grafo.alcancaveis
    ordem = grafo.ordem
    predecessores = grafo.predecessores
    vivos_entrada = {b: set() for b in blocos}
    vivos_saida = {b: set() for b in blocos}
    mudou = True
    while mudou:
        mudou = False
        for nome in reversed(ordem):
            saida = set().union(*(vivos_entrada[e.destino] for e in blocos[nome].saidas
                                  if e.destino in vivos)) if blocos[nome].saidas else set()
            entrada = usos[nome] | (saida - defs[nome])
            if entrada != vivos_entrada[nome] or saida != vivos_saida[nome]:
                vivos_entrada[nome], vivos_saida[nome] = entrada, saida
                mudou = True
    return vivos_entrada, vivos_saida


def calcular_dominadores(grafo):
    cfg = grafo.cfg
    blocos = cfg.blocos
    vivos = grafo.alcancaveis
    ordem = grafo.ordem
    predecessores = grafo.predecessores
    dominadores = {b: set(vivos) if b in vivos else set() for b in blocos}
    dominadores[cfg.entrada] = {cfg.entrada}
    mudou = True
    while mudou:
        mudou = False
        for nome in ordem:
            if nome == cfg.entrada:
                continue
            ps = predecessores[nome]
            novos = ({nome} | set.intersection(*(dominadores[p] for p in ps))) if ps else {nome}
            if novos != dominadores[nome]:
                dominadores[nome] = novos
                mudou = True
    return dominadores


def calcular_garantidas(grafo, defs, definicoes_por_variavel):
    cfg = grafo.cfg
    blocos = cfg.blocos
    vivos = grafo.alcancaveis
    ordem = grafo.ordem
    predecessores = grafo.predecessores
    universo = set(definicoes_por_variavel)
    garantidas_entrada = {b: set(universo) if b in vivos else set() for b in blocos}
    garantidas_saida = {b: set(universo) if b in vivos else set() for b in blocos}
    mudou = True
    while mudou:
        mudou = False
        for nome in ordem:
            ps = predecessores[nome]
            entrada = (set.intersection(*(garantidas_saida[p] for p in ps))
                       if ps and nome != cfg.entrada else set())
            saida = entrada | defs[nome]
            if entrada != garantidas_entrada[nome] or saida != garantidas_saida[nome]:
                garantidas_entrada[nome], garantidas_saida[nome] = entrada, saida
                mudou = True
    return garantidas_entrada, garantidas_saida


def calcular_diagnosticos(grafo, usos, definicoes_por_variavel, entradas_def, garantidas_entrada):
    cfg = grafo.cfg
    blocos = cfg.blocos
    vivos = grafo.alcancaveis
    ordem = grafo.ordem
    predecessores = grafo.predecessores
    candidatos = {}
    sem_definicao = {b: set() for b in blocos}
    for nome in ordem:
        if len(predecessores[nome]) >= 2:
            for var, definicoes in definicoes_por_variavel.items():
                chegando = {def_id for def_id in entradas_def[nome] if def_id in definicoes}
                if len(chegando) >= 2:
                    candidatos.setdefault(nome, {})[var] = chegando
        for var in usos[nome]:
            if var not in garantidas_entrada[nome]:
                sem_definicao[nome].add(var)
    return candidatos, sem_definicao
