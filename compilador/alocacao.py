"""RS 0.14: liveness SSA e coloracao conservadora de registradores AMD64.

R13, R14 e R15 sobrevivem a syscalls e as rotinas de leitura/escrita
atuais. Outros registradores sao reservados ao ABI e aos temporarios.
"""
from collections import Counter
from dataclasses import dataclass

REGS = ('r13', 'r14', 'r15')


@dataclass(frozen=True)
class Local:
    classe: str  # 'reg' ou 'pilha'
    indice: object


@dataclass
class Alocacao:
    locais: dict
    vagas_pilha: int
    vivos_entrada: dict
    vivos_saida: dict
    interferencias: dict

    def relatorio(self):
        regs = sum(l.classe == 'reg' for l in self.locais.values())
        spills = len(self.locais) - regs
        return (f'RS 0.14: {regs} versoes em registradores, {spills} em pilha, '
                f'{self.vagas_pilha} slots de pilha.\n' +
                '\n'.join(f'{v} -> {l.indice if l.classe == "reg" else "pilha[" + str(l.indice) + "]"}'
                          for v, l in sorted(self.locais.items())))


def alocar_registradores(ssa):
    ssa.validar()
    alc = {b for b, block in ssa.blocos.items() if block.alcancavel}
    nomes = set()
    contagem = Counter()
    usos = {}
    defs = {}
    phis = {}
    for b in alc:
        bb = ssa.blocos[b]
        phis[b] = {p.destino for p in bb.phis.values()}
        defs[b] = phis[b] | {i.destino for i in bb.instrucoes if i.destino}
        # Leituras por bloco, desconsiderando definicoes anteriores locais.
        vistos = set(phis[b]); lidos = set()
        for i in bb.instrucoes:
            for v in i.usos:
                contagem[v] += 1
                if v not in vistos:
                    lidos.add(v)
            if i.destino:
                vistos.add(i.destino)
        usos[b] = lidos
        nomes |= defs[b]

    # phi-uses acontecem NA ARESTA, nao no inicio do bloco sucessor.
    entradas_phi = {}
    for b in alc:
        for p in ssa.blocos[b].phis.values():
            for pred, v in p.entradas.items():
                entradas_phi.setdefault((pred, b), set()).add(v)
                contagem[v] += 1

    vivos_in = {b:set() for b in alc}
    vivos_out = {b:set() for b in alc}
    for _ in range(max(1, 2 * len(alc) * (len(nomes) + 1))):
        mudou = False
        for b in reversed(list(ssa.blocos)):
            if b not in alc:
                continue
            out = set()
            for edge in ssa.cfg.blocos[b].saidas:
                succ = edge.destino
                if succ not in alc:
                    continue
                out |= (vivos_in[succ] - phis[succ]) | entradas_phi.get((b, succ), set())
            ins = usos[b] | (out - defs[b])
            if ins != vivos_in[b] or out != vivos_out[b]:
                vivos_in[b], vivos_out[b] = ins, out
                mudou = True
        if not mudou:
            break
    else:
        raise ValueError('Vivacidade SSA nao convergiu.')

    grafo = {v:set() for v in nomes}
    def conectar(valores):
        valores = sorted(valores)
        for i, a in enumerate(valores):
            for b in valores[i + 1:]:
                if a != b:
                    grafo[a].add(b); grafo[b].add(a)

    for b in alc:
        bloco = ssa.blocos[b]
        vivos = set(vivos_out[b]); conectar(vivos)
        for i in reversed(bloco.instrucoes):
            if i.destino:
                for v in vivos:
                    if v != i.destino:
                        grafo[i.destino].add(v); grafo[v].add(i.destino)
                vivos.discard(i.destino)
            vivos.update(i.usos)
            conectar(vivos)
        for phi in bloco.phis.values():
            for v in vivos:
                if v != phi.destino:
                    grafo[v].add(phi.destino); grafo[phi.destino].add(v)
            vivos.discard(phi.destino)
        conectar(vivos)

    locais = {}
    # Maior numero de leituras, entao maior grau de interferencia.
    ordem = sorted(nomes, key=lambda v: (-contagem[v], -len(grafo[v]), v))
    for v in ordem:
        ocupados = {locais[x].indice for x in grafo[v]
                    if x in locais and locais[x].classe == 'reg'}
        disponiveis = [r for r in REGS if r not in ocupados]
        if disponiveis and contagem[v]:
            locais[v] = Local('reg', disponiveis[0])
        else:
            ocupados_pilha = {locais[x].indice for x in grafo[v]
                              if x in locais and locais[x].classe == 'pilha'}
            vaga = next(i for i in range(len(nomes) + 1) if i not in ocupados_pilha)
            locais[v] = Local('pilha', vaga)
    qtd_slots = 1 + max((loc.indice for loc in locais.values()
                          if loc.classe == 'pilha'), default=-1)
    # Mesmo no Windows, sem stack probing: reserva conservadora de ate 2 KiB.
    if qtd_slots > 256:
        raise ValueError('SSA excede limite temporario de pilha segura (256 slots).')
    return Alocacao(locais, qtd_slots, vivos_in, vivos_out, grafo)
