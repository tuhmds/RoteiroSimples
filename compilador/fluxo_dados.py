"""Análise conservadora de fluxo de dados da IR tipada (RS 0.11).

Determina definições que alcançam cada bloco, vivacidade, dominadores e
pontos de junção candidatos a phi. Não transforma o backend em SSA.
"""
from dataclasses import dataclass
from .cfg import GrafoCFG
from .nos_ir import ExpressaoIR
from .medicao_compilacao import etapa
from . import calculos_fluxo


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
    if bloco.papel == 'entrada':
        definicoes.update(i.argumentos[0] for i in bloco.instrucoes if i.operacao == 'parametro')
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
        if not any(a.motivo == 'estouro_incremento' for a in bloco.saidas):
            definicoes.add(args[0])
    elif bloco.papel == 'para:gravar_incremento':
        definicoes.add(args[0])
    elif op == 'atribua':
        usos.update(nomes_lidos(args[1]))
        definicoes.add(args[0])
    elif op == 'leia_int':
        definicoes.add(args[0])
    elif op in ('imprima_num', 'retorne'):
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
    garantidas_entrada: dict
    garantidas_saida: dict

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
        alcancaveis = self.cfg.alcancaveis()
        def fmt(d):
            return {k: sorted(v) for k, v in d.items()}
        return json.dumps({
            'versao': 'RS 0.11',
            'observacao': 'Fluxo de dados para diagnostico; candidatos a phi nao sao SSA construida.',
            'entrada': self.cfg.entrada,
            'saida': self.cfg.saida,
            'blocos': [dict(id=b.id, papel=b.papel,
                            alcancavel=b.id in alcancaveis,
                            usos=sorted(self.usos[b.id]),
                            definicoes=sorted(self.definicoes[b.id]),
                            definicoes_entrada=sorted(self.entradas_def[b.id]),
                            definicoes_saida=sorted(self.saidas_def[b.id]),
                            definicoes_garantidas_entrada=sorted(self.garantidas_entrada[b.id]),
                            definicoes_garantidas_saida=sorted(self.garantidas_saida[b.id]),
                            vivas_entrada=sorted(self.vivos_entrada[b.id]),
                            vivas_saida=sorted(self.vivos_saida[b.id]),
                            dominadores=sorted(self.dominadores[b.id]),
                            phi_candidatos=fmt(self.phi_candidatos.get(b.id, {})),
                            possivel_uso_sem_definicao=sorted(self.sem_definicao[b.id]))
                       for b in self.cfg.blocos.values()],
        }, ensure_ascii=False, indent=2) + '\n'


@dataclass
class AnaliseVivacidade:
    cfg: GrafoCFG
    usos: dict
    definicoes: dict
    vivos_entrada: dict
    vivos_saida: dict


@dataclass
class AnaliseFluxoSSA(AnaliseVivacidade):
    dominadores: dict


def _preparar_fluxo(cfg, medidor):
    with etapa(medidor, 'fluxo_preparacao'):
        grafo = calculos_fluxo.preparar_grafo(cfg)
        usos, definicoes = {}, {}
        for nome, bloco in cfg.blocos.items():
            usos[nome], definicoes[nome] = efeitos_bloco(bloco)
    return grafo, usos, definicoes


def _vivacidade(grafo, usos, definicoes, medidor):
    with etapa(medidor, 'fluxo_vivacidade'):
        return calculos_fluxo.calcular_vivacidade(grafo, usos, definicoes)


def _dominadores(grafo, medidor):
    with etapa(medidor, 'fluxo_dominadores'):
        return calculos_fluxo.calcular_dominadores(grafo)


def analisar_vivacidade(cfg: GrafoCFG, medidor=None):
    """Calcula somente usos/definições locais e variáveis vivas."""
    grafo, usos, definicoes = _preparar_fluxo(cfg, medidor)
    entrada, saida = _vivacidade(grafo, usos, definicoes, medidor)
    if medidor is not None:
        medidor.contar('fluxo_analises_vivacidade', 1)
    return AnaliseVivacidade(cfg, usos, definicoes, entrada, saida)


def analisar_fluxo_ssa(cfg: GrafoCFG, medidor=None):
    """Dados usados pela SSA escalar; não cria diagnósticos completos."""
    grafo, usos, definicoes = _preparar_fluxo(cfg, medidor)
    entrada, saida = _vivacidade(grafo, usos, definicoes, medidor)
    dominadores = _dominadores(grafo, medidor)
    if medidor is not None:
        medidor.contar('fluxo_analises_ssa', 1)
    return AnaliseFluxoSSA(cfg, usos, definicoes, entrada, saida, dominadores)


def analisar_dominadores(cfg: GrafoCFG, medidor=None):
    """Somente dominância, sem examinar efeitos ou calcular vivacidade."""
    with etapa(medidor, 'fluxo_preparacao'):
        grafo = calculos_fluxo.preparar_grafo(cfg)
    resultado = _dominadores(grafo, medidor)
    if medidor is not None:
        medidor.contar('fluxo_analises_dominadores', 1)
    return resultado


def analisar_fluxo(cfg: GrafoCFG, medidor=None):
    """Análise completa para diagnóstico, incluindo definições e garantias."""
    grafo, usos, definicoes = _preparar_fluxo(cfg, medidor)
    with etapa(medidor, 'fluxo_definicoes_alcancam'):
        por_variavel, entradas_def, saidas_def = calculos_fluxo.calcular_definicoes_alcancam(grafo, definicoes)
    vivos_entrada, vivos_saida = _vivacidade(grafo, usos, definicoes, medidor)
    dominadores = _dominadores(grafo, medidor)
    with etapa(medidor, 'fluxo_definicoes_garantidas'):
        garantidas_entrada, garantidas_saida = calculos_fluxo.calcular_garantidas(grafo, definicoes, por_variavel)
    with etapa(medidor, 'fluxo_diagnosticos'):
        candidatos, sem_definicao = calculos_fluxo.calcular_diagnosticos(grafo, usos, por_variavel, entradas_def, garantidas_entrada)
    if medidor is not None:
        medidor.contar('fluxo_analises_completas', 1)
    return AnaliseFluxo(cfg, usos, definicoes, entradas_def, saidas_def,
                        vivos_entrada, vivos_saida, dominadores, candidatos, sem_definicao,
                        garantidas_entrada, garantidas_saida)
