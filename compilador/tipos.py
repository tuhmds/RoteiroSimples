"""Tipos simples e checagem estática de expressões."""
from .erros import ErroCompilacao

MAX_VARIAVEIS = 256  # sem sondagem de pilha/stack probing na versão atual


def tipo_expressao(expr, tipos, linha, funcoes=None):
    """Verificação semântica estática; nenhum valor RS é executado em Python."""
    categoria = expr[0]
    if categoria == 'numero':
        if expr[1] > (1 << 63) - 1:
            raise ErroCompilacao(f'Linha {linha}: número inteiro ultrapassa o máximo de 64 bits.')
        return 'inteiro'
    if categoria == 'logico':
        return 'logico'
    if categoria == 'chamada':
        nome, argumentos = expr[1], expr[2]
        assinatura = (funcoes or {}).get(nome)
        if assinatura is None:
            raise ErroCompilacao(f'Linha {linha}: função {nome!r} não existe.')
        parametros, retorno = assinatura
        if len(argumentos) != len(parametros):
            raise ErroCompilacao(f'Linha {linha}: função {nome!r} espera {len(parametros)} argumentos; recebeu {len(argumentos)}.')
        for posicao, (argumento, esperado) in enumerate(zip(argumentos, parametros), 1):
            recebido = tipo_expressao(argumento, tipos, linha, funcoes)
            if recebido != esperado:
                raise ErroCompilacao(f'Linha {linha}: argumento {posicao} de {nome!r} exige {esperado}, recebeu {recebido}.')
        return retorno
    if categoria == 'var':
        tipo = tipos[expr[1]]
        if isinstance(tipo, tuple) and tipo[0] == 'registro':
            return tipo[1]
        # Listas e textos são valores compostos; o contexto da operação
        # decide se podem ser usados (não participam da aritmética).
        return tipo
    if categoria in ('quantidade_lista_dinamica', 'capacidade_lista_dinamica'):
        if tipos.get(expr[1]) != ('lista_dinamica', 'inteiro'):
            raise ErroCompilacao(f'Linha {linha}: operação exige uma lista dinamica valida.')
        return 'inteiro'
    if categoria == 'indice_lista_dinamica':
        nome, indice = expr[1:]
        if tipos.get(nome) != ('lista_dinamica', 'inteiro'):
            raise ErroCompilacao(f'Linha {linha}: índice exige lista dinamica.')
        if tipo_expressao(indice, tipos, linha, funcoes) != 'inteiro':
            raise ErroCompilacao(f'Linha {linha}: índice deve ser inteiro.')
        return 'inteiro'
    if categoria == 'tamanho_texto':
        if not isinstance(tipos.get(expr[1]), tuple) or tipos[expr[1]][0] != 'texto':
            raise ErroCompilacao(f'Linha {linha}: tamanho() exige texto válido.')
        return 'inteiro'
    if categoria == 'indice':
        nome, indice, tamanho = expr[1:]
        if tipos.get(nome) != ('lista', 'inteiro', tamanho):
            raise ErroCompilacao(f'Linha {linha}: acesso a lista inválida.')
        if tipo_expressao(indice, tipos, linha, funcoes) != 'inteiro':
            raise ErroCompilacao(f'Linha {linha}: índice da lista deve ser inteiro.')
        return 'inteiro'
    if categoria == 'neg':
        # -9223372036854775808 cabe em inteiro de 64 bits, mas +9223372036854775808 não.
        if expr[1] == ('numero', 1 << 63):
            return 'inteiro'
        filho = tipo_expressao(expr[1], tipos, linha, funcoes)
        if filho != 'inteiro':
            raise ErroCompilacao(f'Linha {linha}: sinal negativo exige inteiro; recebeu {filho}.')
        return 'inteiro'
    if categoria in ('bin', 'comparacao'):
        _, op, esquerdo, direito = expr
        a = tipo_expressao(esquerdo, tipos, linha, funcoes)
        b = tipo_expressao(direito, tipos, linha, funcoes)
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
