"""Tipos simples e checagem estática de expressões."""
from .erros import ErroCompilacao
from .propriedade import eh_proprietario, eh_emprestimo, eh_texto, TIPO_TEXTO_DINAMICO, TIPO_TEXTO_EMPRESTADO
from .propriedade import eh_bytes, TIPO_BYTES_DINAMICOS, TIPO_BYTES_EMPRESTADOS

from .propriedade import eh_registro_proprietario, eh_valor_proprietario, donos_do_agregado
from .propriedade import ORIGENS_PROPRIETARIAS, eh_colecao_proprietaria

MAX_VARIAVEIS = 256  # Constante histórica de compatibilidade; não limita o programa inteiro.


def _validar_consumos_chamada(expr, linha, tipos, campos):
    """Uma árvore de chamada não pode consumir ou emprestar o mesmo dono.

    A verificação inclui argumentos aninhados, independentemente da ordem
    de avaliação, sem inventar empréstimos persistentes ou copiar donos.
    """
    consumidos, emprestados, retiradas = set(), set(), set()
    pendentes = [expr]
    while pendentes:
        no = pendentes.pop()
        if not isinstance(no, (tuple, list)):
            continue
        if no and no[0] in ('mova_valor_dinamico', 'mova_registro_proprietario'):
            nome = no[1]
            folhas = set(donos_do_agregado(nome, tipos, campos)) if no[0] == 'mova_registro_proprietario' else {nome}
            if consumidos & folhas:
                raise ErroCompilacao(f'Linha {linha}: propriedade de {nome!r} consumida mais de uma vez na mesma chamada, inclusive por campos sobrepostos.')
            consumidos.update(folhas)
        elif no and no[0] in ('empreste_lista_dinamica', 'empreste_texto_dinamico', 'empreste_bytes_dinamicos'):
            emprestados.add(no[1])
        elif no and no[0] in ('empreste_registro_lista', 'empreste_texto_lista'):
            emprestados.add(no[1])
        elif no and no[0] == 'empreste_registro':
            emprestados.update(donos_do_agregado(no[1], tipos, campos))
        elif no and no[0] == 'retire_registro_lista':
            retiradas.add(no[1])
        pendentes.extend(filho for filho in no if isinstance(filho, (tuple, list)))
    conflitos = consumidos & emprestados
    if conflitos:
        nome = sorted(conflitos)[0]
        raise ErroCompilacao(f'Linha {linha}: nao pode emprestar e mover o mesmo dono {nome!r} na mesma chamada.')
    if retiradas & (consumidos | emprestados):
        raise ErroCompilacao(f'Linha {linha}: retire nao pode compartilhar a lista com consumo ou emprestimo na mesma chamada.')


def tipo_expressao(expr, tipos, linha, funcoes=None, registros=None, campos=None):
    """Verificação semântica estática; nenhum valor RS é executado em Python."""
    registros = {} if registros is None else registros
    campos = {} if campos is None else campos
    categoria = expr[0]
    if categoria == 'empreste_texto_lista':
        tipo = tipos.get(expr[1])
        if (not isinstance(tipo, tuple) or tipo[0] not in ('lista_dinamica', 'lista_emprestada')
                or tipo[1] != TIPO_TEXTO_DINAMICO):
            raise ErroCompilacao(f'Linha {linha}: empréstimo de texto exige lista[texto].')
        _validar_consumos_chamada(expr, linha, tipos, campos)
        if tipo_expressao(expr[2], tipos, linha, funcoes, registros, campos) != 'inteiro':
            raise ErroCompilacao(f'Linha {linha}: índice do empréstimo deve ser inteiro.')
        return TIPO_TEXTO_EMPRESTADO
    if categoria in ('empreste_registro', 'empreste_registro_lista'):
        tipo = tipos.get(expr[1])
        if categoria == 'empreste_registro_lista':
            if (not isinstance(tipo, tuple) or tipo[0] not in ('lista_dinamica', 'lista_emprestada')
                    or tipo[1] not in registros):
                raise ErroCompilacao(f'Linha {linha}: emprestimo do elemento exige lista de registros.')
            _validar_consumos_chamada(expr, linha, tipos, campos)
            if tipo_expressao(expr[2], tipos, linha, funcoes, registros, campos) != 'inteiro':
                raise ErroCompilacao(f'Linha {linha}: indice do emprestimo deve ser inteiro.')
        elif not isinstance(tipo, tuple) or tipo[0] not in ('registro', 'registro_emprestado'):
            raise ErroCompilacao(f'Linha {linha}: emprestimo exige registro.')
        return ('registro_emprestado', tipo[1])
    if categoria == 'numero':
        if expr[1] > (1 << 63) - 1:
            raise ErroCompilacao(f'Linha {linha}: número inteiro ultrapassa o máximo de 64 bits.')
        return 'inteiro'
    if categoria == 'logico':
        return 'logico'
    if categoria == 'nao':
        filho = tipo_expressao(expr[1], tipos, linha, funcoes, registros, campos)
        if filho != 'logico':
            raise ErroCompilacao(f'Linha {linha}: operador nao exige logico; recebeu {filho}.')
        return 'logico'
    if categoria == 'logica':
        _, operador, esquerdo, direito = expr
        a = tipo_expressao(esquerdo, tipos, linha, funcoes, registros, campos)
        b = tipo_expressao(direito, tipos, linha, funcoes, registros, campos)
        if a != 'logico' or b != 'logico':
            raise ErroCompilacao(f'Linha {linha}: operador {operador} exige dois logicos; recebeu {a} e {b}.')
        return 'logico'
    if categoria == 'chamada':
        nome, argumentos = expr[1], expr[2]
        assinatura = (funcoes or {}).get(nome)
        if assinatura is None:
            raise ErroCompilacao(f'Linha {linha}: função {nome!r} não existe.')
        parametros, retorno = assinatura
        if len(argumentos) != len(parametros):
            raise ErroCompilacao(f'Linha {linha}: função {nome!r} espera {len(parametros)} argumentos; recebeu {len(argumentos)}.')
        _validar_consumos_chamada(expr, linha, tipos, campos)
        for posicao, (argumento, esperado) in enumerate(zip(argumentos, parametros), 1):
            recebido = tipo_expressao(argumento, tipos, linha, funcoes, registros, campos)
            if eh_valor_proprietario(esperado, registros) and argumento[0] not in ORIGENS_PROPRIETARIAS:
                raise ErroCompilacao(f'Linha {linha}: argumento {posicao} de {nome!r} exige mova(origem) ou resultado proprietario de funcao; copiar dono unico nao e permitido.')
            if recebido != esperado:
                raise ErroCompilacao(f'Linha {linha}: argumento {posicao} de {nome!r} exige {esperado}, recebeu {recebido}.')
        return retorno
    if categoria == 'retire_registro_lista':
        tipo = tipos.get(expr[1])
        if not eh_colecao_proprietaria(tipo, registros):
            raise ErroCompilacao(f'Linha {linha}: retire exige colecao proprietaria.')
        _validar_consumos_chamada(expr, linha, tipos, campos)
        if tipo_expressao(expr[2], tipos, linha, funcoes, registros, campos) != 'inteiro':
            raise ErroCompilacao(f'Linha {linha}: indice de retire deve ser inteiro.')
        return tipo[1]
    if categoria == 'mova_registro_proprietario':
        tipo = tipos.get(expr[1])
        if not eh_registro_proprietario(tipo, registros):
            raise ErroCompilacao(f'Linha {linha}: mova exige registro com campos proprietarios.')
        return tipo[1]
    if categoria == 'mova_valor_dinamico':
        tipo = tipos.get(expr[1])
        if not eh_proprietario(tipo):
            raise ErroCompilacao(f'Linha {linha}: mova(origem) exige lista dinamica proprietaria.')
        return tipo
    if categoria == 'temporario_composto':
        return tipos[expr[1]]
    if categoria == 'empreste_bytes_dinamicos':
        if tipos.get(expr[1]) != TIPO_BYTES_DINAMICOS:
            raise ErroCompilacao(f'Linha {linha}: empreste() exige bytes proprietarios.')
        return TIPO_BYTES_EMPRESTADOS
    if categoria in ('tamanho_bytes_dinamicos', 'capacidade_bytes_dinamicos'):
        if tipos.get(expr[1]) not in (TIPO_BYTES_DINAMICOS, TIPO_BYTES_EMPRESTADOS):
            raise ErroCompilacao(f'Linha {linha}: consulta exige descritor de bytes.')
        return 'inteiro'
    if categoria == 'empreste_texto_dinamico':
        if tipos.get(expr[1]) != TIPO_TEXTO_DINAMICO:
            raise ErroCompilacao(f'Linha {linha}: empreste() exige texto proprietario.')
        return TIPO_TEXTO_EMPRESTADO
    if categoria in ('tamanho_texto_dinamico', 'capacidade_texto_dinamico', 'caracteres_texto', 'byte_texto'):
        if not eh_texto(tipos.get(expr[1])):
            raise ErroCompilacao(f'Linha {linha}: consulta exige texto UTF-8.')
        if categoria in ('tamanho_texto_dinamico', 'capacidade_texto_dinamico') and tipos[expr[1]] not in (TIPO_TEXTO_DINAMICO, TIPO_TEXTO_EMPRESTADO):
            raise ErroCompilacao(f'Linha {linha}: consulta dinamica exige descritor de texto.')
        if categoria == 'byte_texto' and tipo_expressao(expr[2], tipos, linha, funcoes, registros, campos) != 'inteiro':
            raise ErroCompilacao(f'Linha {linha}: byte_em exige indice inteiro em bytes.')
        return 'inteiro'
    if categoria == 'var':
        tipo = tipos[expr[1]]
        if isinstance(tipo, tuple) and tipo[0] == 'registro_emprestado':
            return ('registro_emprestado', tipo[1])
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
        if eh_valor_proprietario(tipos[nome][1], registros):
            raise ErroCompilacao(f'Linha {linha}: registro proprietario nao pode ser copiado por indice; use retire na lista dona.')
        if tipo_expressao(indice, tipos, linha, funcoes, registros, campos) != 'inteiro':
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
        if eh_colecao_proprietaria(tipos[nome], registros):
            raise ErroCompilacao(f'Linha {linha}: registro proprietario nao pode ser copiado por indice; use retire(lista, indice).')
        if tipo_expressao(indice, tipos, linha, funcoes, registros, campos) != 'inteiro':
            raise ErroCompilacao(f'Linha {linha}: índice deve ser inteiro.')
        return tipos[nome][1]
    if categoria == 'tamanho_bytes':
        if not isinstance(tipos.get(expr[1]), tuple) or tipos[expr[1]][0] != 'bytes':
            raise ErroCompilacao(f'Linha {linha}: tamanho() exige bytes[N].')
        return 'inteiro'
    if categoria == 'indice_bytes':
        nome, indice = expr[1:]
        if not eh_bytes(tipos.get(nome)):
            raise ErroCompilacao(f'Linha {linha}: indice exige bytes.')
        if tipo_expressao(indice, tipos, linha, funcoes, registros, campos) != 'inteiro':
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
        if tipo_expressao(indice, tipos, linha, funcoes, registros, campos) != 'inteiro':
            raise ErroCompilacao(f'Linha {linha}: índice da lista deve ser inteiro.')
        return 'inteiro'
    if categoria == 'neg':
        # -9223372036854775808 cabe em inteiro de 64 bits, mas +9223372036854775808 não.
        if expr[1] == ('numero', 1 << 63):
            return 'inteiro'
        filho = tipo_expressao(expr[1], tipos, linha, funcoes, registros, campos)
        if filho != 'inteiro':
            raise ErroCompilacao(f'Linha {linha}: sinal negativo exige inteiro; recebeu {filho}.')
        return 'inteiro'
    if categoria in ('bin', 'comparacao', 'comparacao_texto'):
        _, op, esquerdo, direito = expr
        a = tipo_expressao(esquerdo, tipos, linha, funcoes, registros, campos)
        b = tipo_expressao(direito, tipos, linha, funcoes, registros, campos)
        if categoria == 'bin':
            if a != 'inteiro' or b != 'inteiro':
                raise ErroCompilacao(f'Linha {linha}: operação {op} exige dois inteiros; recebeu {a} e {b}.')
            return 'inteiro'
        if (eh_texto(a) and eh_texto(b) and
                (a in (TIPO_TEXTO_DINAMICO, TIPO_TEXTO_EMPRESTADO) or
                 b in (TIPO_TEXTO_DINAMICO, TIPO_TEXTO_EMPRESTADO))):
            if op not in ('==', '!=') or esquerdo[0] != 'var' or direito[0] != 'var':
                raise ErroCompilacao(f'Linha {linha}: compare textos por == ou != usando variaveis; nao ha ordenacao Unicode implicita.')
            return 'logico'
        if eh_valor_proprietario(a, registros) or eh_valor_proprietario(b, registros):
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
