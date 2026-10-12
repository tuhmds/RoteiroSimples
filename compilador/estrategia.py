"""Decisão explícita sobre quais otimizações o compilador RS aplica.

Aceitar -O 8 não significa necessariamente usar SSA nesse programa.
O gerador conservador protege construções ainda não representadas pela IR.
"""
from dataclasses import dataclass
from .cobertura_intermediaria import analisar_cobertura, motivos_de_cobertura


@dataclass(frozen=True)
class Estrategia:
    gerador: str
    nivel_solicitado: int
    nivel_ir: int
    motivos: tuple[str, ...]
    otimiza: bool


def percorrer(bloco):
    """Itera pelas operações de um bloco e de seus blocos aninhados."""
    for instrucao in bloco:
        yield instrucao
        if instrucao[0] == 'se':
            yield from percorrer(instrucao[2])
            yield from percorrer(instrucao[3])
        elif instrucao[0] == 'enquanto':
            yield from percorrer(instrucao[2])
        elif instrucao[0] == 'para':
            yield from percorrer(instrucao[5])


def decidir_estrategia(programa, nivel=1, otimizar=True):
    """Uma única fonte de decisão usada pelo compilador e pelo diagnóstico."""
    if not 0 <= nivel <= 8:
        raise ValueError('Nível de otimização deve estar entre 0 e 8.')
    tipos = getattr(programa, 'tipos', {})
    instrucoes = tuple(percorrer(programa.instrucoes))
    motivos = []
    if getattr(programa, 'funcoes', None):
        motivos.append('funções')
    if getattr(programa, 'registros', None):
        motivos.append('registros')
    if getattr(programa, 'escopos_locais', False):
        motivos.append('escopos locais')
    if any(i[0] == 'copie_composto' for i in instrucoes):
        motivos.append('cópias compostas')
    if any(isinstance(t, tuple) and t[0] == 'lista_dinamica'
           for t in tipos.values()):
        motivos.append('listas dinâmicas')
    if any(isinstance(t, tuple) and t[0] == 'bytes' for t in tipos.values()): 
        motivos.append('buffers binários tipados')
    if any(i[0] in ('encerre',) for i in instrucoes):
        motivos.append('saída do processo')
    if any(t == 'arquivo' for t in tipos.values()):
        motivos.append('recursos de arquivo')
    if any(i[0] in ('abra_recurso', 'feche_recurso', 'sincronize_recurso', 'bloqueie_recurso', 'grave_em', 'carregue_de', 'publique_arquivo')
           for i in instrucoes):
        motivos.append('operacoes com arquivo aberto')
    if any(i[0] in ('grave_arquivo', 'carregue_arquivo',
                    'grave_trecho', 'carregue_trecho') for i in instrucoes):
        motivos.append('arquivos nativos')

    # Uma operação nova nunca deve entrar silenciosamente na IR antiga.
    # O relatório percorre expressões e blocos aninhados e cobre funções.
    motivos.extend(motivos_de_cobertura(analisar_cobertura(programa)))
    if motivos:
        return Estrategia('conservador', nivel, 0,
                          tuple(dict.fromkeys(motivos)), False)

    listas_ou_textos = any(isinstance(t, tuple) and t[0] in ('lista', 'texto')
                           for t in tipos.values())
    nivel_ir = (nivel if nivel >= 7 else min(nivel, 3)) if otimizar else 0
    if otimizar and nivel >= 4 and not listas_ou_textos:
        return Estrategia('ssa', nivel, nivel_ir, (), True)
    return Estrategia('intermediario', nivel, nivel_ir, (), otimizar and nivel > 0)


def descrever_estrategia(decisao):
    """Explica a diferença entre a solicitação e a execução efetiva."""
    if decisao.gerador == 'conservador':
        return (f'Gerador: nativo conservador ({", ".join(decisao.motivos)}).\n'
                f'Otimização solicitada: -O {decisao.nivel_solicitado}; '
                'transformações IR/SSA não aplicadas a este programa.')
    if decisao.gerador == 'ssa':
        return (f'Gerador: nativo com alocação SSA.\n'
                f'Otimização solicitada: -O {decisao.nivel_solicitado}; '
                'aplica as transformações disponíveis deste caminho.')
    if decisao.otimiza:
        return (f'Gerador: intermediário tipado com backend nativo.\n'
                f'Otimização solicitada: -O {decisao.nivel_solicitado}; '
                f'análises IR até o nível {decisao.nivel_ir}, '
                'sem o backend SSA.')
    return ('Gerador: intermediário tipado com backend nativo.\n'
            'Otimização solicitada: -O 0; sem transformações otimizadoras.')
