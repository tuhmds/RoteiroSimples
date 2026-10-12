"""Grafo de fluxo de controle (CFG) da IR tipada da RS 0.10.

CFG somente para análise/depuração: não reordena instruções nem altera o
backend nativo. O levantamento inclui saída de laços via pare/continue.
"""
from collections import deque
from dataclasses import dataclass, field
from .nos_ir import InstrucaoIR, ProgramaIR


@dataclass(frozen=True)
class ArestaCFG:
    destino: str
    motivo: str = 'proximo'


@dataclass
class BlocoBasico:
    id: str
    papel: str
    instrucoes: tuple = ()
    saidas: tuple = ()
    origem: object = None


@dataclass
class GrafoCFG:
    blocos: dict
    entrada: str
    saida: str

    def alcancaveis(self):
        visitados = set()
        fila = deque([self.entrada])
        while fila:
            atual = fila.popleft()
            if atual in visitados:
                continue
            visitados.add(atual)
            for aresta in self.blocos[atual].saidas:
                fila.append(aresta.destino)
        return visitados

    def inalcancaveis(self):
        return set(self.blocos) - self.alcancaveis()

    def validar(self):
        assert self.entrada in self.blocos and self.saida in self.blocos
        for bloco in self.blocos.values():
            for aresta in bloco.saidas:
                assert aresta.destino in self.blocos, (bloco.id, aresta.destino)
        return True

    def formatar(self):
        saida = ['RS CFG v1 (analise de fluxo)']
        for ident, bloco in self.blocos.items():
            pos = (f' [linha {bloco.origem.linha}, coluna {bloco.origem.coluna}]'
                   if bloco.origem else '')
            caminhos = ', '.join(f'{a.motivo}->{a.destino}' for a in bloco.saidas) or '(fim)'
            saida.append(f'{ident}: {bloco.papel}{pos} | {caminhos}')
        return '\n'.join(saida)

    def para_dot(self):
        """Emite DOT puro, abrível no Graphviz (sem depender da ferramenta)."""
        def quote(s):
            return '"' + str(s).replace('\\', '\\\\').replace('"', '\\"').replace('\n','\\n') + '"'
        linhas = ['digraph RoteiroSimples {', '  rankdir=TB;', '  node [shape=box, fontname="Arial"];']
        vivos = self.alcancaveis()
        for ident, b in self.blocos.items():
            texto = f'{ident}: {b.papel}'
            if b.origem:
                texto += f'\nlinha {b.origem.linha}:{b.origem.coluna}'
            extra = ', style="dashed"' if ident not in vivos else ''
            linhas.append(f'  {quote(ident)} [label={quote(texto)}{extra}];')
            for a in b.saidas:
                linhas.append(f'  {quote(ident)} -> {quote(a.destino)} [label={quote(a.motivo)}];')
        linhas.append('}')
        return '\n'.join(linhas) + '\n'


def construir_cfg(ir: ProgramaIR):
    """Expande se, enquanto e para em blocos com arestas explícitas."""
    if not isinstance(ir, ProgramaIR):
        raise TypeError('CFG recebe ProgramaIR tipado, não AST legada.')

    blocos = {}
    contador = 0

    def novo(papel, instr=(), origem=None):
        nonlocal contador
        nome = f'b{contador}'
        contador += 1
        blocos[nome] = BlocoBasico(nome, papel, tuple(instr), (), origem)
        return nome

    def ligacoes(nome, *pares):
        blocos[nome].saidas = tuple(ArestaCFG(destino, motivo) for motivo, destino in pares)

    saida = novo('saida')

    def sequencia(instrucoes, sucessor, laco=None):
        """Construção reversa: cada comando conhece seu sucessor efetivo."""
        proximo = sucessor
        for instr in reversed(instrucoes):
            tag, args = instr.operacao, instr.argumentos
            origem = instr.origem
            if tag == 'se':
                nome = novo('se:condicao', (instr,), origem)
                sim = sequencia(args[1], proximo, laco)
                nao = sequencia(args[2], proximo, laco)
                ligacoes(nome, ('verdadeiro', sim), ('falso', nao))
            elif tag == 'enquanto':
                nome = novo('enquanto:condicao', (instr,), origem)
                corpo = sequencia(args[1], nome, (proximo, nome))
                ligacoes(nome, ('verdadeiro', corpo), ('falso', proximo))
            elif tag == 'para':
                inicio = novo('para:inicio', (instr,), origem)
                cond = novo('para:condicao', (instr,), origem)
                incremento = novo('para:incremento', (instr,), origem)
                corpo = sequencia(args[4], incremento, (proximo, incremento))
                ligacoes(inicio, ('proximo', cond))
                ligacoes(cond, ('verdadeiro', corpo), ('falso', proximo))
                ligacoes(incremento, ('proximo', cond))
                nome = inicio
            elif tag == 'pare':
                if laco is None:
                    raise ValueError('IR com pare fora de um laco.')
                nome = novo('pare', (instr,), origem)
                ligacoes(nome, ('pare', laco[0]))
            elif tag == 'continue':
                if laco is None:
                    raise ValueError('IR com continue fora de um laco.')
                nome = novo('continue', (instr,), origem)
                ligacoes(nome, ('continue', laco[1]))
            else:
                nome = novo(tag, (instr,), origem)
                ligacoes(nome, ('proximo', proximo))
            proximo = nome
        return proximo

    primeiro = sequencia(ir.instrucoes, saida)
    entrada = novo('entrada')
    ligacoes(entrada, ('proximo', primeiro))
    # Percorrer começando pela entrada ajuda a leitura humana do CFG.
    ordem = []
    fila = deque([entrada])
    vistos = set()
    while fila:
        item = fila.popleft()
        if item in vistos:
            continue
        vistos.add(item)
        ordem.append(item)
        fila.extend(a.destino for a in blocos[item].saidas)
    ordem.extend(b for b in blocos if b not in vistos)
    renomear = {antigo:f'b{n}' for n,antigo in enumerate(ordem)}
    ordenados = {}
    for velho in ordem:
        bloco = blocos[velho]
        bloco.id = renomear[velho]
        bloco.saidas = tuple(ArestaCFG(renomear[a.destino],a.motivo) for a in bloco.saidas)
        ordenados[bloco.id] = bloco
    cfg = GrafoCFG(ordenados, renomear[entrada], renomear[saida])
    cfg.validar()
    return cfg
