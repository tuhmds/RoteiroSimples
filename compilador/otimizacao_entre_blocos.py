"""RS 0.22: propagação conservadora de posições de listas entre blocos.

O grafo de fluxo de controle determina quais caminhos chegam a cada instrução.
Um valor só é conhecido quando TODOS os predecessores possíveis concordam.
A memória versionada valida as dependências e os nós de junção; nenhum
acesso potencialmente inválido, leitura externa ou cálculo falhável é removido.
"""
from collections import deque
from dataclasses import replace

from .memory_ssa import construir_memory_ssa
from .nos_ir import ExpressaoIR, ProgramaIR
from .otimizador import dobrar_constantes


def otimizar_entre_blocos(programa: ProgramaIR):
    """Encaminha constantes comprovadas pelas junções de decisões e laços.

    As posições são rastreadas de forma independente. Índices dinâmicos
    invalidam todo o objeto, por não haver referências ou alias nesta versão.
    Não antecipamos instruções e não eliminamos verificações potencialmente
    falháveis. Uma escrita idêntica é removida apenas se ambos os operandos
    forem literais e o índice for comprovadamente válido.
    """
    memoria = construir_memory_ssa(programa)
    memoria.validar()
    grafo = memoria.cfg
    vivos = grafo.alcancaveis()
    tamanhos = {nome: tipo[2] for nome, tipo in programa.tipos.items()
                if isinstance(tipo, tuple) and tipo[0] == 'lista'}
    if not tamanhos:
        return programa

    predecessores = memoria.predecessores
    entradas = {bloco: None for bloco in vivos}
    saidas = {bloco: None for bloco in vivos}
    acessos = {}
    for bloco in vivos:
        no = grafo.blocos[bloco]
        if len(no.instrucoes) == 1:
            acessos[id(no.instrucoes[0])] = (bloco, memoria.blocos[bloco].instrucoes[0])

    def atualizar(instrucao, anteriores):
        """Estado após uma instrução; nunca avalia expressões do programa."""
        atuais = dict(anteriores)
        operacao, args = instrucao.operacao, instrucao.argumentos
        if operacao == 'crie_lista':
            nome, tamanho = args
            # Objetos locais são declarados zerados; cada posição é conhecida.
            for chave in tuple(atuais):
                if chave[0] == nome:
                    del atuais[chave]
            if nome in tamanhos:
                for indice in range(tamanho):
                    atuais[(nome, indice)] = 0
        elif operacao in ('atribua_indice', 'leia_indice'):
            nome, indice = args[:2]
            if nome not in tamanhos:
                return atuais
            if indice.operacao != 'numero' or not 0 <= indice.valor < tamanhos[nome]:
                for chave in tuple(atuais):
                    if chave[0] == nome:
                        del atuais[chave]
            else:
                chave = (nome, indice.valor)
                if (operacao == 'atribua_indice' and args[2].operacao == 'numero'):
                    atuais[chave] = args[2].valor
                else:
                    atuais.pop(chave, None)
        elif operacao not in ('se', 'enquanto', 'para', 'pare', 'continue'):
            # Qualquer escrita desconhecida em lista invalida o objeto inteiro.
            from .efeitos import efeito_instrucao
            for nome in efeito_instrucao(instrucao).escritas:
                if nome in tamanhos:
                    for chave in tuple(atuais):
                        if chave[0] == nome:
                            del atuais[chave]
        return atuais

    def juntar(estados):
        """Interseção por posição e valor; divergências não geram constantes."""
        unidos = dict(estados[0])
        for estado in estados[1:]:
            for chave in tuple(unidos):
                if estado.get(chave) != unidos[chave]:
                    del unidos[chave]
        return unidos

    # Resolver o estado até estabilizar, incluindo as arestas que voltam aos laços.
    # None representa estado ainda não calculado, e não conhecimento vazio.
    pendentes = deque([grafo.entrada])
    agendados = {grafo.entrada}
    while pendentes:
        bloco = pendentes.popleft()
        agendados.discard(bloco)
        if bloco == grafo.entrada:
            anterior = {}
        else:
            disponiveis = [saidas[p] for p in predecessores[bloco] if saidas[p] is not None]
            if not disponiveis:
                continue
            anterior = juntar(disponiveis)
        instrucao = grafo.blocos[bloco].instrucoes
        posterior = atualizar(instrucao[0], anterior) if instrucao else dict(anterior)
        if entradas[bloco] != anterior or saidas[bloco] != posterior:
            entradas[bloco] = anterior
            saidas[bloco] = posterior
            for aresta in grafo.blocos[bloco].saidas:
                if aresta.destino in vivos and aresta.destino not in agendados:
                    pendentes.append(aresta.destino)
                    agendados.add(aresta.destino)

    def reescrever_expressao(expr, valores, acesso):
        if (expr.operacao == 'indice' and expr.valor[0] in tamanhos
                and expr.filhos[0].operacao == 'numero'):
            nome, limite = expr.valor
            indice = expr.filhos[0].valor
            regiao = 'mem:' + nome
            if (0 <= indice < limite and (nome, indice) in valores
                    and acesso is not None and regiao in acesso.usos):
                return ExpressaoIR('inteiro', 'numero', valores[(nome, indice)], origem=expr.origem)
        if not expr.filhos:
            return expr
        filhos = tuple(reescrever_expressao(f, valores, acesso) for f in expr.filhos)
        return dobrar_constantes(replace(expr, filhos=filhos)) if filhos != expr.filhos else expr

    def caminhar(instrucoes):
        alteradas = []
        for instrucao in instrucoes:
            operacao, args = instrucao.operacao, instrucao.argumentos
            if operacao == 'se':
                alteradas.append(replace(instrucao, argumentos=(args[0],
                    tuple(caminhar(args[1])), tuple(caminhar(args[2])))))
                continue
            if operacao == 'enquanto':
                alteradas.append(replace(instrucao, argumentos=(args[0], tuple(caminhar(args[1])))))
                continue
            if operacao == 'para':
                alteradas.append(replace(instrucao, argumentos=(*args[:4], tuple(caminhar(args[4])))))
                continue

            info = acessos.get(id(instrucao))
            if info is None:
                alteradas.append(instrucao)
                continue
            bloco, acesso = info
            valores = entradas.get(bloco) or {}
            if operacao == 'imprima_num':
                alteradas.append(replace(instrucao, argumentos=(
                    reescrever_expressao(args[0], valores, acesso),)))
            elif operacao == 'atribua':
                alteradas.append(replace(instrucao, argumentos=(args[0],
                    reescrever_expressao(args[1], valores, acesso))))
            elif operacao == 'atribua_indice':
                nome, indice, valor, limite = args
                novo_valor = reescrever_expressao(valor, valores, acesso)
                # Somente literal em posição comprovadamente válida: remover a
                # escrita não pode suprimir erro, efeito observável ou leitura.
                if (indice.operacao == 'numero' and 0 <= indice.valor < limite
                        and novo_valor.operacao == 'numero'
                        and valores.get((nome, indice.valor)) == novo_valor.valor
                        and 'mem:' + nome in acesso.usos):
                    continue
                alteradas.append(replace(instrucao, argumentos=(nome, indice, novo_valor, limite)))
            else:
                alteradas.append(instrucao)
        return alteradas

    return replace(programa, instrucoes=tuple(caminhar(programa.instrucoes)))
