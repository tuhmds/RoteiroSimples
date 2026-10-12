"""Tipos simples e checagem estática de expressões."""
from .erros import ErroCompilacao

MAX_VARIAVEIS = 256  # sem sondagem de pilha/stack probing na versão atual


def tipo_expressao(expr, tipos, linha):
    """Verificação semântica estática; nenhum valor RS é executado em Python."""
    categoria = expr[0]
    if categoria == 'numero':
        if expr[1] > (1 << 63) - 1:
            raise ErroCompilacao(f'Linha {linha}: número inteiro ultrapassa o máximo de 64 bits.')
        return 'inteiro'
    if categoria == 'logico':
        return 'logico'
    if categoria == 'var':
        tipo = tipos[expr[1]]
        if isinstance(tipo, tuple):
            raise ErroCompilacao(f'Linha {linha}: {tipo[0]} {expr[1]!r} não é um valor numérico.')
        return tipo
    if categoria == 'tamanho_texto':
        if not isinstance(tipos.get(expr[1]), tuple) or tipos[expr[1]][0] != 'texto':
            raise ErroCompilacao(f'Linha {linha}: tamanho() exige texto válido.')
        return 'inteiro'
    if categoria == 'indice':
        nome, indice, tamanho = expr[1:]
        if tipos.get(nome) != ('lista', 'inteiro', tamanho):
            raise ErroCompilacao(f'Linha {linha}: acesso a lista inválida.')
        if tipo_expressao(indice, tipos, linha) != 'inteiro':
            raise ErroCompilacao(f'Linha {linha}: índice da lista deve ser inteiro.')
        return 'inteiro'
    if categoria == 'neg':
        # -9223372036854775808 cabe em inteiro de 64 bits, mas +9223372036854775808 não.
        if expr[1] == ('numero', 1 << 63):
            return 'inteiro'
        filho = tipo_expressao(expr[1], tipos, linha)
        if filho != 'inteiro':
            raise ErroCompilacao(f'Linha {linha}: sinal negativo exige inteiro; recebeu {filho}.')
        return 'inteiro'
    if categoria in ('bin', 'comparacao'):
        _, op, esquerdo, direito = expr
        a = tipo_expressao(esquerdo, tipos, linha)
        b = tipo_expressao(direito, tipos, linha)
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
