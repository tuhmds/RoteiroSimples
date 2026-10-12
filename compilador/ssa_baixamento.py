"""RS 0.13: plano de copias nas arestas para futuro baixamento SSA.

Uma instrucao phi e paralela: todos os destinos de uma mesma aresta recebem
as fontes do predecessor de maneira simultanea. Este modulo apenas registra
o plano; a emissao de copias paralelas e a alocacao de registradores ainda nao
fazem parte do backend. O nivel -O 3 usa o phi para constantes, nao estas copias.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class CopiaPhi:
    origem: str
    destino: str
    tipo: str


def planejar_copias_phi(ssa):
    """Retorna {(predecessor, sucessor): (CopiaPhi, ...)} com ordem estavel."""
    ssa.validar()
    planos = {}
    def ordem(v):
        return int(v[1:])
    for bid, bloco in ssa.blocos.items():
        if not bloco.alcancavel:
            continue
        for phi in sorted(bloco.phis.values(), key=lambda p: p.variavel):
            for pred, origem in sorted(phi.entradas.items(), key=lambda kv: ordem(kv[0])):
                if origem != phi.destino:
                    planos.setdefault((pred, bid), []).append(
                        CopiaPhi(origem, phi.destino, phi.tipo))
    return {aresta: tuple(copias) for aresta, copias in sorted(
        planos.items(), key=lambda kv: (ordem(kv[0][0]), ordem(kv[0][1])))}


def formatar_copias_phi(ssa):
    planos = planejar_copias_phi(ssa)
    linhas = ['RS 0.13 - plano de copias phi por aresta (ainda nao emitido no backend)']
    for (de, para), copias in planos.items():
        linhas.append(f'{de} -> {para} (copias paralelas):')
        for copia in copias:
            linhas.append(f'  {copia.destino}:{copia.tipo} <- {copia.origem}')
    return '\n'.join(linhas)
