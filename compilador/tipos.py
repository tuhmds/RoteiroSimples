"""Tipos simples e checagem estática de expressões."""
from .erros import ErroCompilacao

MAX_VARIAVEIS = 256  # máximo provisório para evitar frames grandes sem sondagem de pilha


def tipo_expressao(expr, tipos, linha):
    """Analisa o tipo estaticamente; nunca executa expressões RS no compilador."""
    categoria = expr[0]
    if categoria == 'numero':
        if expr[1] > (1 << 63) - 1:
            raise ErroCompilacao(f'Linha {linha}: número inteiro ultrapassa o máximo de 64 bits.')
        return 'inteiro'
    if categoria == 'logico':
        return 'logico'
    if categoria == 'var':
        return tipos[expr[1]]
    if categoria == 'neg':
        if expr[1] == ('numero', 1 << 63):
            return 'inteiro'
        filho = tipo_expressao(expr[1], tipos, linha)
        if filho != 'inteiro':
            raise ErroCompilacao(f'Linha {linha}: sinal negativo exige inteiro; recebeu {filho}.')
        return 'inteiro'
    if categoria in ('bin', 'comparacao'):
        _, op, esquerda, direita = expr
        a = tipo_expressao(esquerda, tipos, linha)
        b = tipo_expressao(direita, tipos, linha)
        if categoria == 'bin':
            if a != 'inteiro' or b != 'inteiro':
                raise ErroCompilacao(f'Linha {linha}: operação {op} exige dois inteiros; recebeu {a} e {b}.')
            return 'inteiro'
        if op in ('==', '!='):
            if a != b:
                raise ErroCompilacao(f'Linha {linha}: comparação {op} exige tipos iguais; recebeu {a} e {b}.')
        elif a != 'inteiro' or b != 'inteiro':
            raise ErroCompilacao(f'Linha {linha}: comparação {op} exige inteiros; recebeu {a} e {b}.')
        return 'logico'
    raise ErroCompilacao(f'Linha {linha}: expressão com tipo desconhecido.')
