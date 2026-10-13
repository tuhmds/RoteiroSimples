"""Tipos simples e checagem estática de expressões."""
from .erros import ErroCompilacao
from .propriedade import eh_proprietario, eh_emprestimo

MAX_VARIAVEIS = 256  # sem sondagem de pilha/stack probing na versão atual


def _validar_consumos_chamada(expr, linha):
    """Uma árvore de chamada não pode consumir ou emprestar o mesmo dono.

    A verificação inclui argumentos aninhados, independentemente da ordem
    de avaliação, sem inventar empréstimos persistentes ou copiar donos.
    """
    consumidos, emprestados = set(), set()
    pendentes = [expr]
    while pendentes:
        no = pendentes.pop()
        if not isinstance(no, (tuple, list)):
            continue
        if no and no[0] == 'mova_valor_dinamico':
            nome = no[1]
            if nome in consumidos:
                raise ErroCompilacao(f'Linha {linha}: lista {nome!r} consumida mais de uma vez na mesma chamada.')
            consumidos.add(nome)
        elif no and no[0] == 'empreste_lista_dinamica':
            emprestados.add(no[1])
        pendentes.extend(filho for filho in no if isinstance(filho, (tuple, list)))
    conflitos = consumidos & emprestados
    if conflitos:
        nome = sorted(conflitos)[0]
        raise ErroCompilacao(f'Linha {linha}: nao pode emprestar e mover o mesmo dono {nome!r} na mesma chamada.')


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
        _validar_consumos_chamada(expr, linha)
        for posicao, (argumento, esperado) in enumerate(zip(argumentos, parametros), 1):
            recebido = tipo_expressao(argumento, tipos, linha, funcoes)
            if eh_proprietario(esperado) and argumento[0] not in ('mova_valor_dinamico', 'chamada'):
                raise ErroCompilacao(f'Linha {linha}: argumento {posicao} de {nome!r} exige mova(origem) ou resultado proprietario de funcao; copiar dono unico nao e permitido.')
            if recebido != esperado:
                raise ErroCompilacao(f'Linha {linha}: argumento {posicao} de {nome!r} exige {esperado}, recebeu {recebido}.')
        return retorno
    if categoria == 'mova_valor_dinamico':
        tipo = tipos.get(expr[1])
        if not eh_proprietario(tipo):
            raise ErroCompilacao(f'Linha {linha}: mova(origem) exige lista dinamica proprietaria.')
        return tipo
    if categoria == 'temporario_composto':
        return tipos[expr[1]]
    if categoria == 'var':
        tipo = tipos[expr[1]]
        if isinstance(tipo, tuple) and tipo[0] == 'registro':
            return tipo[1]
        # Listas e textos são valores compostos; o contexto da operação
        # decide se podem ser usados (não participam da aritmética).
        return tipo
    if categoria == 'empreste_lista_dinamica':
        tipo = tipos.get(expr[1])
        if not isinstance(tipo, tuple) or tipo[0] != 'lista_dinamica':
            raise ErroCompilacao(f'Linha {linha}: empreste() exige lista dinamica proprietaria.')
        return ('lista_emprestada', tipo[1])
    if categoria in ('quantidade_lista_emprestada', 'capacidade_lista_emprestada'):
        if not isinstance(tipos.get(expr[1]), tuple) or tipos[expr[1]][0] != 'lista_emprestada':
            raise ErroCompilacao(f'Linha {linha}: consulta exige emprestimo[lista].')
        return 'inteiro'
    if categoria == 'indice_lista_emprestada':
        nome, indice = expr[1:]
        if not isinstance(tipos.get(nome), tuple) or tipos[nome][0] != 'lista_emprestada':
            raise ErroCompilacao(f'Linha {linha}: indice exige emprestimo[lista].')
        if tipo_expressao(indice, tipos, linha, funcoes) != 'inteiro':
            raise ErroCompilacao(f'Linha {linha}: indice da lista emprestada deve ser inteiro.')
        return tipos[nome][1]
    if categoria in ('quantidade_lista_dinamica', 'capacidade_lista_dinamica'):
        if not isinstance(tipos.get(expr[1]), tuple) or tipos[expr[1]][0] != 'lista_dinamica':
            raise ErroCompilacao(f'Linha {linha}: operação exige uma lista dinamica valida.')
        return 'inteiro'
    if categoria == 'indice_lista_dinamica':
        nome, indice = expr[1:]
        if not isinstance(tipos.get(nome), tuple) or tipos[nome][0] != 'lista_dinamica':
            raise ErroCompilacao(f'Linha {linha}: índice exige lista dinamica.')
        if tipo_expressao(indice, tipos, linha, funcoes) != 'inteiro':
            raise ErroCompilacao(f'Linha {linha}: índice deve ser inteiro.')
        return tipos[nome][1]
    if categoria == 'tamanho_bytes':
        if not isinstance(tipos.get(expr[1]), tuple) or tipos[expr[1]][0] != 'bytes':
            raise ErroCompilacao(f'Linha {linha}: tamanho() exige bytes[N].')
        return 'inteiro'
    if categoria == 'indice_bytes':
        nome, indice = expr[1:]
        if not isinstance(tipos.get(nome), tuple) or tipos[nome][0] != 'bytes':
            raise ErroCompilacao(f'Linha {linha}: indice exige bytes[N].')
        if tipo_expressao(indice, tipos, linha, funcoes) != 'inteiro':
            raise ErroCompilacao(f'Linha {linha}: indice de bytes deve ser inteiro.')
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
        if eh_proprietario(a) or eh_proprietario(b):
            raise ErroCompilacao(f'Linha {linha}: lista proprietaria com dono unico nao admite comparacao nem copia.')
        if eh_emprestimo(a) or eh_emprestimo(b):
            raise ErroCompilacao(f'Linha {linha}: emprestimos nao podem ser comparados diretamente.')
        if a == 'arquivo' or b == 'arquivo':
            raise ErroCompilacao(f'Linha {linha}: recurso arquivo nao admite comparacao nem copia.')
        if op in ('==', '!='):
            if a != b:
                raise ErroCompilacao(f'Linha {linha}: comparação {op} exige tipos iguais; recebeu {a} e {b}.')
        elif a != 'inteiro' or b != 'inteiro':
            raise ErroCompilacao(f'Linha {linha}: comparação {op} exige inteiros; recebeu {a} e {b}.')
        return 'logico'
    raise ErroCompilacao(f'Linha {linha}: expressão com tipo desconhecido.')
