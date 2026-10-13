"""Memory SSA por objeto e por efeito observavel, RS 0.20.

Analise estatica nao-executavel: identificadores nomeados, sem aliases/ponteiros.
Cada lista/buffer tem sua propria cadeia de memoria; E/S e falhas usam
cadeias explicitas e uma cadeia comum de ordem para impedir reordenacoes.
A SSA de memoria NAO e consumida pelo backend nesta versao.
"""
from collections import defaultdict
from dataclasses import dataclass, field
import json

from .cfg import GrafoCFG, construir_cfg
from .efeitos import Efeitos, efeito_expressao, efeito_instrucao
from .fluxo_dados import analisar_fluxo
from .nos_ir import ProgramaIR


_ORDEM = 'efeito:ordem'
_ENTRADA = 'io:entrada'
_SAIDA = 'io:saida'
_FALHA = 'efeito:falha'


def _chave(bloco):
    return int(bloco[1:])


@dataclass(frozen=True)
class AcessoMemoria:
    operacao: str
    usos: dict
    definicoes: dict
    efeitos: Efeitos

    def para_dict(self):
        return {'operacao': self.operacao, 'usos': dict(sorted(self.usos.items())),
                'definicoes': dict(sorted(self.definicoes.items())),
                'efeitos': self.efeitos.para_dict()}


@dataclass
class PhiMemoria:
    regiao: str
    destino: str = ''
    entradas: dict = field(default_factory=dict)

    def para_dict(self):
        return {'regiao': self.regiao, 'destino': self.destino,
                'entradas': {p: self.entradas[p] for p in sorted(self.entradas, key=_chave)}}


@dataclass
class BlocoMemoria:
    id: str
    papel: str
    alcancavel: bool
    phis: dict = field(default_factory=dict)
    instrucoes: list = field(default_factory=list)


@dataclass
class ProgramaMemorySSA:
    cfg: GrafoCFG
    regioes: tuple
    blocos: dict
    predecessores: dict
    dominadores: dict
    idom: dict
    fronteiras: dict

    def validar(self):
        """Valida SSA de memoria, todas as arestas phi e ordem das definicoes."""
        vivos = self.cfg.alcancaveis()
        defs = {f'{r}@0': (self.cfg.entrada, r) for r in self.regioes}
        for bid in vivos:
            bb = self.blocos[bid]
            for regiao, phi in bb.phis.items():
                if regiao not in self.regioes or phi.regiao != regiao:
                    raise ValueError(f'Phi de memoria em regiao desconhecida: {regiao}')
                if phi.destino in defs:
                    raise ValueError(f'Versao de memoria redefinida: {phi.destino}')
                defs[phi.destino] = (bid, regiao)
                if set(phi.entradas) != self.predecessores[bid]:
                    raise ValueError(f'Phi incompleto de {regiao} em {bid}')
            for instr in bb.instrucoes:
                for regiao, versao in instr.definicoes.items():
                    if regiao not in self.regioes or versao in defs:
                        raise ValueError(f'Definicao de memoria invalida: {regiao} -> {versao}')
                    defs[versao] = (bid, regiao)
        for bid in vivos:
            bb = self.blocos[bid]
            for phi in bb.phis.values():
                for pred, versao in phi.entradas.items():
                    if versao not in defs:
                        raise ValueError(f'Phi de memoria usa versao inexistente: {versao}')
                    bloco_def, regiao = defs[versao]
                    if regiao != phi.regiao or bloco_def not in self.dominadores[pred]:
                        raise ValueError(f'Phi de memoria usa versao que nao domina {pred}: {versao}')
            ultimo = {r: bb.phis[r].destino for r in bb.phis}
            for instr in bb.instrucoes:
                # Numa instrucao com escrita a versao anterior deve sempre ser consumida.
                if not set(instr.definicoes).issubset(instr.usos):
                    raise ValueError(f'Escrita sem dependencia de memoria em {bid}')
                for regiao, versao in instr.usos.items():
                    if versao not in defs:
                        raise ValueError(f'Leitura de versao de memoria inexistente: {versao}')
                    bloco_def, regiao_def = defs[versao]
                    if regiao != regiao_def or bloco_def not in self.dominadores[bid]:
                        raise ValueError(f'Leitura de memoria nao dominada: {versao} em {bid}')
                    if regiao in ultimo and ultimo[regiao] != versao:
                        raise ValueError(f'Leitura ultrapassa a escrita anterior: {versao} em {bid}')
                ultimo.update(instr.definicoes)
        return True

    def para_dict(self):
        vivos = self.cfg.alcancaveis()
        return {
            'versao': 'RS 0.20',
            'escopo': 'Memory SSA de analise; nao habilita otimizacoes de memoria',
            'modelo_de_alias': 'listas e textos locais independentes; sem referencias/ponteiros',
            'entrada': self.cfg.entrada,
            'saida': self.cfg.saida,
            'regioes': list(self.regioes),
            'versoes_iniciais': {r: f'{r}@0' for r in self.regioes},
            'blocos': [{
                'id': bid, 'papel': bb.papel, 'alcancavel': bid in vivos,
                'idom': self.idom.get(bid),
                'predecessores': sorted(self.predecessores.get(bid, ()), key=_chave),
                'phis': [bb.phis[r].para_dict() for r in sorted(bb.phis)],
                'instrucoes': [i.para_dict() for i in bb.instrucoes],
            } for bid, bb in self.blocos.items()],
        }

    def formatar_ptbr(self):
        """Relatório com termos em português, sem alterar a saída legada."""
        texto = self.formatar()
        return (texto.replace('RS 0.20 - Memory SSA (analise, sem alteracao no backend)',
                              'RS 0.22 - Memoria versionada em atribuicao unica (analise)')
                    .replace(' idom=', ' dominador_imediato=')
                    .replace(' = phi(', ' = juncao('))

    def para_json(self):
        return json.dumps(self.para_dict(), ensure_ascii=False, indent=2) + '\n'

    def formatar(self):
        linhas = ['RS 0.20 - Memory SSA (analise, sem alteracao no backend)']
        for bid, bloco in self.blocos.items():
            if not bloco.alcancavel:
                linhas.append(f'{bid} [{bloco.papel}]: inacessivel')
                continue
            linhas.append(f'{bid} [{bloco.papel}] idom={self.idom.get(bid) or "-"}')
            for regiao in sorted(bloco.phis):
                phi = bloco.phis[regiao]
                origens = ', '.join(f'{p}: {phi.entradas[p]}' for p in sorted(phi.entradas, key=_chave))
                linhas.append(f'  {phi.destino} = phi({origens})')
            for inst in bloco.instrucoes:
                usados = ', '.join(f'{r}={v}' for r, v in sorted(inst.usos.items())) or '-'
                definidos = ', '.join(f'{r}={v}' for r, v in sorted(inst.definicoes.items())) or '-'
                linhas.append(f'  {inst.operacao}: usa [{usados}] -> define [{definidos}]')
        return '\n'.join(linhas)


def _efeitos_do_bloco(bloco):
    if not bloco.instrucoes:
        return Efeitos()
    instr = bloco.instrucoes[0]
    if instr.operacao == 'para':
        args = instr.argumentos
        if bloco.papel == 'para:inicio':
            return efeito_expressao(args[1])
        if bloco.papel == 'para:condicao':
            return efeito_expressao(args[2])
        if bloco.papel == 'para:incremento':
            # Incremento nativo protegido contra estouro.
            return Efeitos(pode_falhar=True)
    return efeito_instrucao(instr)


def construir_memory_ssa(ir: ProgramaIR, cfg: GrafoCFG | None = None) -> ProgramaMemorySSA:
    """Constroi SSA de efeitos reais por objeto com nos phi em juncoes e lacos."""
    if not isinstance(ir, ProgramaIR):
        raise TypeError('Memory SSA exige ProgramaIR tipado.')
    cfg = cfg if cfg is not None else construir_cfg(ir)
    if ir.funcoes:
        raise ValueError('Memória versionada de funções ainda não está disponível; use CFG e fluxo.')
    if cfg.nome_funcao is not None or cfg.chamadas:
        raise ValueError('Memória versionada de funções ainda não está disponível; use SSA e fluxo.')
    cfg.validar_para_ssa()
    cfg.validar()
    vivos = cfg.alcancaveis()
    ordem = sorted(vivos, key=_chave)
    preds = {b: set() for b in vivos}
    for bid in ordem:
        for aresta in cfg.blocos[bid].saidas:
            if aresta.destino in vivos:
                preds[aresta.destino].add(bid)
    # Regioes independentes de memoria: nomes de objetos locais nao sao aliases.
    objetos = {nome for nome, tipo in ir.tipos.items()
               if isinstance(tipo, tuple) and tipo[0] in ('lista', 'texto')}
    efeitos = {bid: _efeitos_do_bloco(cfg.blocos[bid]) for bid in vivos}
    leitura, escrita = {}, {}
    for bid, e in efeitos.items():
        lr = {f'mem:{nome}' for nome in e.leituras & objetos}
        wr = {f'mem:{nome}' for nome in e.escritas & objetos}
        if e.entrada:
            wr.add(_ENTRADA)
        if e.saida:
            wr.add(_SAIDA)
        if e.pode_falhar:
            wr.add(_FALHA)
        if e.entrada or e.saida or e.pode_falhar:
            wr.add(_ORDEM)  # impõe a ordem das operações observáveis
        leitura[bid], escrita[bid] = lr, wr
    regioes = tuple(sorted(set().union(*(leitura[b] | escrita[b] for b in vivos))))

    dominadores = analisar_fluxo(cfg).dominadores
    idom = {cfg.entrada: None}
    for bid in ordem:
        if bid == cfg.entrada:
            continue
        candidatos = dominadores[bid] - {bid}
        if not candidatos:
            raise ValueError(f'Bloco sem dominador imediato: {bid}')
        idom[bid] = max(candidatos, key=lambda x: len(dominadores[x]))
    filhos = {bid: [] for bid in vivos}
    for bid, pai in idom.items():
        if pai is not None:
            filhos[pai].append(bid)
    for itens in filhos.values():
        itens.sort(key=_chave)
    fronteiras = {bid: set() for bid in vivos}
    for bid in ordem:
        if len(preds[bid]) < 2:
            continue
        for p in preds[bid]:
            atual = p
            while atual != idom[bid]:
                fronteiras[atual].add(bid)
                atual = idom[atual]
                if atual is None:
                    raise ValueError('Fronteira de dominancia inconsistente.')
    blocos = {bid: BlocoMemoria(bid, cfg.blocos[bid].papel, bid in vivos)
              for bid in cfg.blocos}
    defs_por_regiao = defaultdict(set)
    for bid in ordem:
        for regiao in escrita[bid]:
            defs_por_regiao[regiao].add(bid)
    for regiao in regioes:
        pendentes = set(defs_por_regiao[regiao])
        colocados = set()
        while pendentes:
            x = min(pendentes, key=_chave)
            pendentes.remove(x)
            for y in sorted(fronteiras[x], key=_chave):
                if y not in colocados:
                    colocados.add(y)
                    blocos[y].phis[regiao] = PhiMemoria(regiao)
                    if y not in defs_por_regiao[regiao]:
                        pendentes.add(y)
    pilhas = {r: [f'{r}@0'] for r in regioes}
    contadores = {r: 0 for r in regioes}

    def criar(regiao):
        contadores[regiao] += 1
        versao = f'{regiao}@{contadores[regiao]}'
        pilhas[regiao].append(versao)
        return versao

    # DFS explicita evita limite de recursao com programas longos.
    eventos = [('entrar', cfg.entrada, ())]
    while eventos:
        tipo, bid, criadas = eventos.pop()
        if tipo == 'sair':
            for regiao in reversed(criadas):
                pilhas[regiao].pop()
            continue
        bb = blocos[bid]
        criadas = []
        for regiao in sorted(bb.phis):
            bb.phis[regiao].destino = criar(regiao)
            criadas.append(regiao)
        if cfg.blocos[bid].instrucoes:
            instr = cfg.blocos[bid].instrucoes[0]
            usados = {r: pilhas[r][-1] for r in sorted(leitura[bid] | escrita[bid])}
            definidos = {}
            for regiao in sorted(escrita[bid]):
                definidos[regiao] = criar(regiao)
                criadas.append(regiao)
            bb.instrucoes.append(AcessoMemoria(instr.operacao, usados, definidos, efeitos[bid]))
        for aresta in cfg.blocos[bid].saidas:
            destino = aresta.destino
            if destino in vivos:
                for regiao, phi in blocos[destino].phis.items():
                    phi.entradas[bid] = pilhas[regiao][-1]
        eventos.append(('sair', bid, criadas))
        for filho in reversed(filhos[bid]):
            eventos.append(('entrar', filho, ()))
    programa = ProgramaMemorySSA(cfg, regioes, blocos, preds, dominadores, idom, fronteiras)
    programa.validar()
    return programa
