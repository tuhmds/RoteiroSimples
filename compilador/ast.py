"""AST com localização exata da origem, compatível com as tuplas da RS 0.9.

Os nós continuam equivalentes a tuplas na geração nativa. O atributo origem
não interfere na semântica nem na serialização binária do programa.
"""
from dataclasses import dataclass, field

@dataclass(frozen=True)
class PosicaoFonte:
    linha: int
    coluna: int

    def __post_init__(self):
        if self.linha < 1 or self.coluna < 1:
            raise ValueError('Posição da fonte deve iniciar em 1.')

class NoExpressao(tuple):
    def __new__(cls, campos, origem=None):
        obj = super().__new__(cls, campos)
        obj.origem = origem
        return obj

class NoInstrucao(tuple):
    def __new__(cls, campos, origem=None):
        obj = super().__new__(cls, campos)
        obj.origem = origem
        return obj

@dataclass
class Programa:
    instrucoes: list
    variaveis: dict
    importa_matematica: bool
    tipos: dict  # metadados estáticos; armazenamento de 8 bytes por variável
    funcoes: dict = field(default_factory=dict)
    escopos_locais: bool = False
    registros: dict = field(default_factory=dict)
    campos_registro: dict = field(default_factory=dict)


@dataclass
class Funcao:
    nome: str
    parametros: tuple  # ((nome_interno, tipo), ...)
    retorno: str
    programa: Programa
    recursiva: bool = False


def formatar_ast(programa):
    """Lista os nós AST com posições de origem, sem modificar o programa."""
    linhas = ['RS AST v2 (linha:coluna)']

    def origem(no):
        ponto = getattr(no, 'origem', None)
        return f'{ponto.linha}:{ponto.coluna}' if ponto else '?'

    def exibir_expr(e, nivel):
        linhas.append('  ' * nivel + f'{origem(e)} expressao:{e[0]}')
        tag = e[0]
        if tag in ('neg', 'nao'):
            exibir_expr(e[1], nivel + 1)
        elif tag == 'chamada':
            for argumento in e[2]:
                exibir_expr(argumento, nivel + 1)
        elif tag in ('bin', 'comparacao', 'comparacao_texto', 'logica'):
            exibir_expr(e[2], nivel + 1)
            exibir_expr(e[3], nivel + 1)

    def percorrer(nos, nivel=0):
        for no in nos:
            tag = no[0]
            linhas.append('  ' * nivel + f'{origem(no)} instrucao:{tag}')
            if tag in ('atribua',):
                exibir_expr(no[2], nivel+1)
            elif tag in ('imprima_num', 'se', 'enquanto'):
                exibir_expr(no[1], nivel+1)
            elif tag == 'retorne':
                exibir_expr(no[1], nivel+1)
            elif tag == 'para':
                exibir_expr(no[2], nivel+1)
                exibir_expr(no[3], nivel+1)
            if tag == 'se':
                percorrer(no[2], nivel+1)
                percorrer(no[3], nivel+1)
            elif tag == 'enquanto':
                percorrer(no[2], nivel+1)
            elif tag == 'para':
                percorrer(no[5], nivel+1)

    percorrer(programa.instrucoes)
    for nome, funcao in getattr(programa, 'funcoes', {}).items():
        linhas.append(f'funcao {nome}: retorno {funcao.retorno}; parametros {len(funcao.parametros)}')
        percorrer(funcao.programa.instrucoes, 1)
    return '\n'.join(linhas)
