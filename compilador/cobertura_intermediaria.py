"""Contrato verificável de cobertura entre árvore sintática e IR da RS.

A lista de instruções e expressões abaixo corresponde às operações que
compilador/ir.py consegue converter e reconstruir hoje. Novos comandos
precisam ser classificados antes de acessar o caminho IR/SSA.
"""
from collections import Counter
from dataclasses import dataclass


INSTRUCOES_IR = frozenset((
    'texto', 'atribua', 'leia_int', 'crie_texto', 'modifique_texto',
    'limpe_texto', 'imprima_texto', 'leia_texto', 'crie_lista',
    'atribua_indice', 'leia_indice', 'imprima_num', 'se', 'enquanto',
    'para', 'pare', 'continue', 'retorne',
))

EXPRESSOES_IR = frozenset((
    'numero', 'logico', 'var', 'tamanho_texto', 'indice',
    'neg', 'bin', 'comparacao', 'chamada', 'nao', 'logica',
))

# Posicionamento dos filhos que são expressões nos nós suportados.
EXPRESSOES_DA_INSTRUCAO = {
    'atribua': (2,),
    'atribua_indice': (2, 3),
    'leia_indice': (2,),
    'imprima_num': (1,),
    'retorne': (1,),
    'se': (1,),
    'enquanto': (1,),
    'para': (2, 3),
}

BLOCOS_DA_INSTRUCAO = {
    'se': (2, 3),
    'enquanto': (2,),
    'para': (5,),
}


@dataclass(frozen=True)
class CoberturaIntermediaria:
    """Resumo de operações encontradas, com contagens e lacunas explícitas."""
    instrucoes: tuple
    expressoes: tuple
    instrucoes_ausentes: tuple
    expressoes_ausentes: tuple

    @property
    def completa(self):
        return not self.instrucoes_ausentes and not self.expressoes_ausentes


def analisar_cobertura(programa):
    """Varre o programa e corpos das funções sem executar otimizações."""
    instrucoes = Counter()
    expressoes = Counter()

    def expressao(no):
        nome = str(no[0])
        expressoes[nome] += 1
        if nome in ('neg', 'nao'):
            expressao(no[1])
        elif nome in ('bin', 'comparacao', 'comparacao_texto', 'logica'):
            expressao(no[2])
            expressao(no[3])
        elif nome in ('indice', 'indice_bytes', 'byte_texto'):
            expressao(no[2])
        elif nome == 'chamada':
            for argumento in no[2]:
                expressao(argumento)

    def bloco(instrucoes_atuais):
        for no in instrucoes_atuais:
            nome = str(no[0])
            instrucoes[nome] += 1
            if nome in INSTRUCOES_IR:
                for indice in EXPRESSOES_DA_INSTRUCAO.get(nome, ()):
                    expressao(no[indice])
            # Mesmo blocos de comandos mais novos devem ser visitados
            # para que o relatório não esconda operações aninhadas.
            for indice in BLOCOS_DA_INSTRUCAO.get(nome, ()):
                bloco(no[indice])

    bloco(programa.instrucoes)
    for funcao in getattr(programa, 'funcoes', {}).values():
        bloco(funcao.programa.instrucoes)

    return CoberturaIntermediaria(
        tuple(sorted(instrucoes.items())),
        tuple(sorted(expressoes.items())),
        tuple(sorted(nome for nome in instrucoes if nome not in INSTRUCOES_IR)),
        tuple(sorted(nome for nome in expressoes if nome not in EXPRESSOES_IR)),
    )


def motivos_de_cobertura(cobertura):
    """Explica somente a ausência de representação, sem mascarar outras restrições."""
    return tuple(
        [f'instrução ainda sem representação intermediária: {nome}'
         for nome in cobertura.instrucoes_ausentes] +
        [f'expressão ainda sem representação intermediária: {nome}'
         for nome in cobertura.expressoes_ausentes]
    )


def funcoes_escalares_representaveis(programa):
    """Primeiro contrato de funções IR: todos os valores são escalares.

    Chamadas não recebem referências nem donos; ainda não entram no
    alocador SSA. Operações desconhecidas são rejeitadas pela cobertura.
    """
    escalares = ('inteiro', 'logico')
    if getattr(programa, 'registros', None):
        return False
    if any(tipo not in escalares for tipo in programa.tipos.values()):
        return False
    for funcao in getattr(programa, 'funcoes', {}).values():
        if (funcao.retorno not in escalares or
                any(tipo not in escalares for _, tipo in funcao.parametros) or
                any(tipo not in escalares for tipo in funcao.programa.tipos.values())):
            return False
    return analisar_cobertura(programa).completa


def formatar_cobertura(cobertura, decisao=None):
    """Relatório estável em português brasileiro para CI e linha de comando."""
    linhas = ['Cobertura da representação intermediária da RS']
    for categoria, contagens in (('Instruções', cobertura.instrucoes),
                                 ('Expressões', cobertura.expressoes)):
        linhas.append(f'{categoria} encontradas:')
        if not contagens:
            linhas.append('  (nenhuma)')
        for nome, quantidade in contagens:
            linhas.append(f'  {nome}: {quantidade}')

    if cobertura.completa:
        linhas.append('Representação dos nós: completa para as operações encontradas.')
    else:
        linhas.append('Representação dos nós: incompleta.')
        linhas.extend(f'  {motivo}' for motivo in motivos_de_cobertura(cobertura))
    if decisao is not None:
        linhas.append(f'Gerador selecionado: {decisao.gerador}.')
        if decisao.motivos:
            linhas.append('Restrições adicionais de otimização:')
            linhas.extend(f'  {motivo}' for motivo in decisao.motivos)
    if dict(cobertura.expressoes).get('logica'):
        linhas.append('Operadores e/ou: expressões com curto-circuito na emissão nativa; '
                      'o CFG de análise conserva os dois filhos como efeitos potenciais, '
                      'sem expandir seus desvios internos.')
    return '\n'.join(linhas)
