"""Decisão explícita sobre quais otimizações o compilador RS aplica.

Aceitar -O 8 não significa necessariamente usar SSA nesse programa.
O gerador conservador protege construções ainda não representadas pela IR.
"""
from dataclasses import dataclass
from .cobertura_intermediaria import (
    BLOCOS_DA_INSTRUCAO, analisar_cobertura, motivos_de_cobertura,
    funcoes_escalares_representaveis,
)
from .propriedade import eh_proprietario
from .funcoes_mistas import classificar_funcoes


@dataclass(frozen=True)
class EstrategiaFuncao:
    nome: str
    elegivel: bool
    gerador: str
    nivel_ir: int
    motivos: tuple[str, ...]


@dataclass(frozen=True)
class Estrategia:
    gerador: str
    nivel_solicitado: int
    nivel_ir: int
    motivos: tuple[str, ...]
    otimiza: bool
    funcoes: tuple[EstrategiaFuncao, ...] = ()


def _estrategia_de_funcao(nome, motivos, nivel, otimizar):
    """Seleciona o caminho de uma função sem alterar sua elegibilidade."""
    elegivel = not motivos
    otimizacao_ativa = otimizar and nivel > 0

    if not elegivel or not otimizacao_ativa:
        gerador = 'conservador'
    elif nivel >= 4:
        gerador = 'ssa'
    else:
        gerador = 'intermediario'

    nivel_ir = min(nivel, 3) if elegivel and otimizar else 0
    if motivos:
        justificativas = motivos
    elif not otimizacao_ativa:
        justificativas = ('otimização desativada',)
    else:
        justificativas = ()

    return EstrategiaFuncao(nome, elegivel, gerador, nivel_ir, justificativas)


def estrategias_funcoes(programa, nivel, otimizar):
    """Mantém a decisão por função na mesma ordem das declarações."""
    classificacao = classificar_funcoes(programa)
    return tuple(
        _estrategia_de_funcao(nome, motivos, nivel, otimizar)
        for nome, motivos in classificacao.items()
    )


def percorrer(bloco):
    """Itera pelas operações de um bloco e de seus blocos aninhados."""
    for instrucao in bloco:
        yield instrucao
        for indice in BLOCOS_DA_INSTRUCAO.get(instrucao[0], ()):
            yield from percorrer(instrucao[indice])


def decidir_estrategia(programa, nivel=1, otimizar=True):
    """Uma única fonte de decisão usada pelo compilador e pelo diagnóstico."""
    if not 0 <= nivel <= 8:
        raise ValueError('Nível de otimização deve estar entre 0 e 8.')
    tipos = getattr(programa, 'tipos', {})
    instrucoes = tuple(percorrer(programa.instrucoes))
    motivos = []
    tem_funcoes = bool(getattr(programa, 'funcoes', None))
    funcoes_escalares = tem_funcoes and funcoes_escalares_representaveis(programa)
    if tem_funcoes and not funcoes_escalares:
        motivos.append('funções fora do contrato escalar da IR')
    if getattr(programa, 'registros', None):
        motivos.append('registros')
    if getattr(programa, 'escopos_locais', False) and not funcoes_escalares:
        motivos.append('escopos locais')
    if any(i[0] == 'copie_composto' for i in instrucoes):
        motivos.append('cópias compostas')
    if any(eh_proprietario(t) for t in tipos.values()):
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

    # A interface grafica exige emissao conservadora, inclusive em programas com funcoes.
    if any(i[0] == 'janela_mensagem' for i in instrucoes):
        motivos.append('interface grafica Win32')

    # Uma operação nova nunca deve entrar silenciosamente na IR antiga.
    # O relatório percorre expressões e blocos aninhados e cobre funções.
    motivos.extend(motivos_de_cobertura(analisar_cobertura(programa)))
    if motivos:
        funcoes = estrategias_funcoes(programa, nivel, otimizar)
        misto = (otimizar and nivel > 0 and any(f.elegivel for f in funcoes)
                 and not any(i[0] == 'janela_mensagem' for i in instrucoes))
        return Estrategia('misto' if misto else 'conservador', nivel, 0,
                          tuple(dict.fromkeys(motivos)), bool(misto), funcoes)

    if tem_funcoes:
        # O3 propaga constantes por SSA; O4–O8 emitem os corpos alocados.
        # Chamadas mantêm a convenção RS e os salvamentos nativos.
        nivel_ir = min(nivel, 3) if otimizar else 0
        if otimizar and nivel >= 4:
            return Estrategia('ssa', nivel, nivel_ir, (), True)
        return Estrategia('intermediario', nivel, nivel_ir, (), otimizar and nivel > 0)

    listas_ou_textos = any(isinstance(t, tuple) and t[0] in ('lista', 'texto')
                           for t in tipos.values())
    nivel_ir = (nivel if nivel >= 7 else min(nivel, 3)) if otimizar else 0
    if otimizar and nivel >= 4 and not listas_ou_textos:
        return Estrategia('ssa', nivel, nivel_ir, (), True)
    return Estrategia('intermediario', nivel, nivel_ir, (), otimizar and nivel > 0)


def descrever_estrategia(decisao):
    """Explica a diferença entre a solicitação e a execução efetiva."""
    if decisao.funcoes:
        linhas = [f'Gerador: nativo {decisao.gerador}; início conservador.',
                  f'Otimização solicitada: -O {decisao.nivel_solicitado}.',
                  'Funções (decisão por corpo):']
        for funcao in decisao.funcoes:
            motivo = '; '.join(funcao.motivos) or 'contrato escalar fechado'
            linhas.append(f'  {funcao.nome}: {funcao.gerador} (IR {funcao.nivel_ir}); {motivo}.')
        linhas.append('Registros, donos, empréstimos e arquivos permanecem sem transformações IR/SSA.')
        return '\n'.join(linhas)
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
