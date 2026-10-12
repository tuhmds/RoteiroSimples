"""Análise conservadora de fluxo de dados da IR tipada (RS 0.11).

Determina definições que alcançam cada bloco, vivacidade, dominadores e
pontos de junção candidatos a phi. Não transforma o backend em SSA.
"""
from collections import defaultdict
from dataclasses import dataclass
from .cfg import GrafoCFG
from .nos_ir import ExpressaoIR


def nomes_lidos(expressao):
    if not isinstance(expressao, ExpressaoIR):
        return set()
    if expressao.operacao == 'var':
        return {expressao.valor}
    retorno = set()
    for filho in expressao.filhos:
        retorno.update(nomes_lidos(filho))
    return retorno


def efeitos_bloco(bloco):
    """Usos/definições exclusivos deste bloco, sem englobar os ramos da IR."""
    usos, definicoes = set(), set()
    if not bloco.instrucoes:
        return usos, definicoes
    instr = bloco.instrucoes[0]
    op, args = instr.operacao, instr.argumentos
    if bloco.papel == 'para:inicio':
        usos.update(nomes_lidos(args[1]))
        definicoes.add(args[0])
    elif bloco.papel == 'para:condicao':
        usos.add(args[0])
        usos.update(nomes_lidos(args[2]))
    elif bloco.papel == 'para:incremento':
        usos.add(args[0])
        definicoes.add(args[0])
    elif op == 'atribua':
        usos.update(nomes_lidos(args[1]))
        definicoes.add(args[0])
    elif op == 'leia_int':
        definicoes.add(args[0])
    elif op == 'imprima_num':
        usos.update(nomes_lidos(args[0]))
    elif bloco.papel in ('se:condicao', 'enquanto:condicao'):
        usos.update(nomes_lidos(args[0]))
    return usos, definicoes


@dataclass
class AnaliseFluxo:
    cfg: GrafoCFG
    usos: dict
    definicoes: dict
    entradas_def: dict
    saidas_def: dict
    vivos_entrada: dict
    vivos_saida: dict
    dominadores: dict
    phi_candidatos: dict
    sem_definicao: dict

    def formatar(self):
        linhas = ['RS 0.11 - Fluxo de dados (analise conservadora)']
        vivos = self.cfg.alcancaveis()
        for ident, bloco in self.cfg.blocos.items():
            if ident not in vivos:
                linhas.append(f'{ident} [{bloco.papel}]: inacessivel')
                continue
            def ordem(valor):
                return ', '.join(sorted(map(str, valor))) or '-'
            linhas.append(f'{ident} [{bloco.papel}] | usa: {ordem(self.usos[ident])} | '
                          f'define: {ordem(self.definicoes[ident])} | '
                          f'vivas entrada: {ordem(self.vivos_entrada[ident])} | '
                          f'vivas saida: {ordem(self.vivos_saida[ident])}')
            for nome, ids in sorted(self.phi_candidatos.get(ident, {}).items()):
                linhas.append(f'  juntura phi? {nome} <- {ordem(ids)}')
            if self.sem_definicao[ident]:
                linhas.append(f'  aviso: possivel uso sem definicao: {ordem(self.sem_definicao[ident])}')
        linhas.append('Obs.: phi? e apenas diagnostico, nao transforma a IR em SSA.')
        return '\n'.join(linhas)

    def para_json(self):
        import json
        def fmt(d):
            return {k: sorted(v) for k, v in d.items()}
        return json.dumps({
            'versao': 'RS 0.11',
            'observacao': 'Fluxo de dados para diagnostico; candidatos a phi nao sao SSA construida.',
            'entrada': self.cfg.entrada,
            'saida': self.cfg.saida,
            'blocos': [dict(id=b.id, papel=b.papel,
                            alcancavel=b.id in self.cfg.alcancaveis(),
                            usos=sorted(self.usos[b.id]),
                            definicoes=sorted(self.definicoes[b.id]),
                            definicoes_entrada=sorted(self.entradas_def[b.id]),
                            definicoes_saida=sorted(self.saidas_def[b.id]),
                            vivas_entrada=sorted(self.vivos_entrada[b.id]),
                            vivas_saida=sorted(self.vivos_saida[b.id]),
                            dominadores=sorted(self.dominadores[b.id]),
                            phi_candidatos=fmt(self.phi_candidatos.get(b.id, {})),
                            possivel_uso_sem_definicao=sorted(self.sem_definicao[b.id]))
                       for b in self.cfg.blocos.values()],
        }, ensure_ascii=False, indent=2) + '\n'


def analisar_fluxo(cfg: GrafoCFG):
    """Ponto fixo sobre arestas reais, incluindo retroarestas e continue/pare."""
    cfg.validar()
    vivos = cfg.alcancaveis()
    blocos = cfg.blocos
    ordem = [nome for nome in blocos if nome in vivos]
    predecessores = defaultdict(set)
    for nome in ordem:
        for aresta in blocos[nome].saidas:
            if aresta.destino in vivos:
                predecessores[aresta.destino].add(nome)

    usos, defs = {}, {}
    for nome, bloco in blocos.items():
        usos[nome], defs[nome] = efeitos_bloco(bloco)
    # Identificadores de definição estáveis: bX:variavel.
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

    candidatos = {}
    sem_definicao = {b: set() for b in blocos}
    for nome in ordem:
        if len(predecessores[nome]) >= 2:
            for var, definicoes in definicoes_por_variavel.items():
                chegando = {def_id for def_id in entradas_def[nome] if def_id in definicoes}
                if len(chegando) >= 2:
                    candidatos.setdefault(nome, {})[var] = chegando
        for var in usos[nome]:
            if not any(def_id in definicoes_por_variavel[var] for def_id in entradas_def[nome]):
                sem_definicao[nome].add(var)

    return AnaliseFluxo(cfg, usos, defs, entradas_def, saidas_def,
                        vivos_entrada, vivos_saida, dominadores, candidatos, sem_definicao)
