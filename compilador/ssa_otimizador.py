"""RS 0.13: propagacao global *conservadora* de constantes guiada por SSA.

A SSA e usada para identificar versoes e valores de cada predecessor, inclusive
nas juncoes phi. Apenas reescrevemos as expressoes originais; o backend ainda
usa as variaveis na pilha, sem baixar phi para copias de registradores.

A semantica de erros e preservada: overflow, divisao por zero e a divisao de
INT64_MIN por -1 NUNCA sao dobrados. Nao removemos atribuicoes nem I/O.
"""
from dataclasses import replace

from .cfg import construir_cfg
from .fluxo_dados import analisar_fluxo
from .nos_ir import ExpressaoIR, ProgramaIR
from .otimizador import dobrar_constantes
from .ssa import construir_ssa


# Objetos distintos evitam confundir o inteiro 0 com um estado desconhecido.
_INDEFINIDO = object()
_VARIAVEL = object()


def _expressao_constante(expr, valores):
    """Retorna inteiro, estado indefinido ou variavel, sem avaliar codigo do usuario."""
    if expr.operacao in ('numero', 'logico'):
        return expr.valor
    if expr.operacao == 'var':
        return valores.get(expr.valor, _INDEFINIDO)
    if expr.operacao == 'chamada':
        return _VARIAVEL  # nunca avaliar, remover nem presumir resultado de chamada
    filhos = [_expressao_constante(f, valores) for f in expr.filhos]
    if _VARIAVEL in filhos:
        return _VARIAVEL
    if _INDEFINIDO in filhos:
        return _INDEFINIDO
    nos = tuple(ExpressaoIR(f.tipo, 'logico' if f.tipo == 'logico' else 'numero', v)
                for f, v in zip(expr.filhos, filhos))
    reduzida = dobrar_constantes(replace(expr, filhos=nos))
    if reduzida.operacao in ('numero', 'logico'):
        return reduzida.valor
    return _VARIAVEL  # possivel erro de runtime: nao pode ser eliminado


def _atualizar(valores, chave, novo):
    """Reticulado monotono: indefinido -> constante -> variavel."""
    anterior = valores.get(chave, _INDEFINIDO)
    if novo is _INDEFINIDO or anterior is _VARIAVEL:
        return False
    if anterior is _INDEFINIDO:
        valores[chave] = novo
        return True
    if novo is _VARIAVEL or novo != anterior:
        valores[chave] = _VARIAVEL
        return True
    return False


def analisar_constantes_ssa(ssa):
    """Resolve valores por versao SSA; um phi so e constante se todos concordam.

    A solucao e deliberadamente conservadora para ciclos: um phi pendente fica
    indefinido, nunca se presume constante a partir de apenas um predecessor.
    """
    valores = {}
    total = sum(len(b.phis) + len(b.instrucoes) for b in ssa.blocos.values())
    # Cada definicao sobe no reticulado no maximo duas vezes.
    for _ in range(max(1, 2 * total + 1)):
        houve_mudanca = False
        for bloco in ssa.blocos.values():
            if not bloco.alcancavel:
                continue
            for phi in bloco.phis.values():
                entradas = [valores.get(v, _INDEFINIDO) for v in phi.entradas.values()]
                if any(v is _VARIAVEL for v in entradas):
                    val = _VARIAVEL
                elif any(v is _INDEFINIDO for v in entradas):
                    val = _INDEFINIDO
                elif entradas and all(v == entradas[0] for v in entradas):
                    val = entradas[0]
                else:
                    val = _VARIAVEL
                houve_mudanca |= _atualizar(valores, phi.destino, val)
            for instr in bloco.instrucoes:
                if not instr.destino:
                    continue
                if instr.operacao in ('atribua', 'para:inicio'):
                    val = _expressao_constante(instr.argumentos[0], valores)
                else:
                    # leia_int, incremento e outros efeitos nao tem valor constante.
                    val = _VARIAVEL
                houve_mudanca |= _atualizar(valores, instr.destino, val)
        if not houve_mudanca:
            break
    else:
        raise ValueError('SSA nao convergiu durante a propagacao de constantes.')
    return {k: v for k, v in valores.items() if v is not _INDEFINIDO and v is not _VARIAVEL}


def _reescrever_expressao(expr, constantes):
    if expr.operacao == 'var' and expr.valor in constantes:
        return ExpressaoIR(expr.tipo, 'logico' if expr.tipo == 'logico' else 'numero',
                           constantes[expr.valor], origem=expr.origem)
    if not expr.filhos:
        return expr
    filhos = tuple(_reescrever_expressao(x, constantes) for x in expr.filhos)
    return dobrar_constantes(replace(expr, filhos=filhos))


def otimizar_com_ssa(ir: ProgramaIR):
    """Usa definicoes SSA para reescrever atribuicoes e impressao de inteiros.

    Cada instrucao fonte ocorre em um unico bloco CFG. Fazemos correspondencia
    por identidade do proprio no InstrucaoIR, nunca pela linha (que pode repetir
    em codigo gerado) nem pelo nome nao-versionado da variavel.
    """
    cfg = construir_cfg(ir)
    ssa = construir_ssa(cfg)
    constantes = analisar_constantes_ssa(ssa)
    alteracoes = {}
    for bid, bloco in cfg.blocos.items():
        if bid not in ssa.blocos or not ssa.blocos[bid].alcancavel or not bloco.instrucoes:
            continue
        instr = bloco.instrucoes[0]
        if instr.operacao not in ('atribua', 'imprima_num'):
            continue
        versao = ssa.blocos[bid].instrucoes[0].argumentos[0]
        if not isinstance(versao, ExpressaoIR):
            continue
        novo = _reescrever_expressao(versao, constantes)
        # Nomes restantes devem voltar a forma da IR original; somente aceitar
        # reescrita total para literal, que garante ausencia de renomeacoes SSA.
        if novo.operacao in ('numero', 'logico'):
            original = instr.argumentos[1] if instr.operacao == 'atribua' else instr.argumentos[0]
            if novo != original:
                alteracoes[id(instr)] = novo

    def percorrer(instrucoes):
        saida = []
        for instr in instrucoes:
            op, args = instr.operacao, instr.argumentos
            if id(instr) in alteracoes:
                novo = alteracoes[id(instr)]
                if op == 'atribua':
                    instr = replace(instr, argumentos=(args[0], novo))
                else:
                    instr = replace(instr, argumentos=(novo,))
            elif op == 'se':
                instr = replace(instr, argumentos=(args[0], percorrer(args[1]), percorrer(args[2])))
            elif op == 'enquanto':
                instr = replace(instr, argumentos=(args[0], percorrer(args[1])))
            elif op == 'para':
                instr = replace(instr, argumentos=(*args[:4], percorrer(args[4])))
            saida.append(instr)
        return tuple(saida)

    propagado = ProgramaIR(percorrer(ir.instrucoes), dict(ir.tipos),
                           dict(ir.variaveis), ir.importa_matematica)

    # Elimina somente gravacoes CONSTANTES cujos valores nao sao observados.
    # Divisao, overflow, leia e qualquer outra operacao com efeito sao mantidos.
    grafo = construir_cfg(propagado)
    fluxo = analisar_fluxo(grafo)
    mortos = set()
    for bid, bloco in grafo.blocos.items():
        if bid not in grafo.alcancaveis() or not bloco.instrucoes:
            continue
        instr = bloco.instrucoes[0]
        if instr.operacao != 'atribua':
            continue
        nome, rhs = instr.argumentos
        if rhs.operacao in ('numero', 'logico') and nome not in fluxo.vivos_saida[bid]:
            mortos.add(id(instr))

    def eliminar(instrucoes):
        saida = []
        for ins in instrucoes:
            if id(ins) in mortos:
                continue
            op, a = ins.operacao, ins.argumentos
            if op == 'se':
                ins = replace(ins, argumentos=(a[0], eliminar(a[1]), eliminar(a[2])))
            elif op == 'enquanto':
                ins = replace(ins, argumentos=(a[0], eliminar(a[1])))
            elif op == 'para':
                ins = replace(ins, argumentos=(*a[:4], eliminar(a[4])))
            saida.append(ins)
        return tuple(saida)
    return ProgramaIR(eliminar(propagado.instrucoes), dict(ir.tipos),
                      dict(ir.variaveis), ir.importa_matematica)
