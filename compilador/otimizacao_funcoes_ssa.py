"""Propagação SSA escalar por corpo, conservando chamadas e efeitos."""
from dataclasses import replace

from .ssa_funcoes import construir_ssa_programa
from .ssa_otimizador import analisar_constantes_ssa, _reescrever_expressao


def otimizar_funcoes_com_ssa(ir):
    programa = construir_ssa_programa(ir)

    def reescrever(corpo, ssa):
        constantes = analisar_constantes_ssa(ssa)
        alteracoes = {}
        for bid, bloco in ssa.cfg.blocos.items():
            if not ssa.blocos[bid].alcancavel or not bloco.instrucoes:
                continue
            instr = bloco.instrucoes[0]
            if instr.operacao not in ('atribua', 'imprima_num', 'retorne', 'se', 'enquanto'):
                continue
            expr = ssa.blocos[bid].instrucoes[0].argumentos[0]
            novo = _reescrever_expressao(expr, constantes)
            # Somente resultado totalmente literal volta à IR sem versões.
            # Nenhuma instrução, chamada ou verificação de falha é eliminada.
            if novo.operacao in ('numero', 'logico'):
                alteracoes[id(instr)] = novo

        def bloco(instrucoes):
            novas = []
            for instr in instrucoes:
                op, a = instr.operacao, instr.argumentos
                if id(instr) in alteracoes:
                    n = 1 if op == 'atribua' else 0
                    args = list(a)
                    args[n] = alteracoes[id(instr)]
                    instr = replace(instr, argumentos=tuple(args))
                a = instr.argumentos
                if op == 'se':
                    instr = replace(instr, argumentos=(a[0], bloco(a[1]), bloco(a[2])))
                elif op == 'enquanto':
                    instr = replace(instr, argumentos=(a[0], bloco(a[1])))
                elif op == 'para':
                    instr = replace(instr, argumentos=(*a[:4], bloco(a[4])))
                novas.append(instr)
            return tuple(novas)
        return replace(corpo, instrucoes=bloco(corpo.instrucoes))

    return replace(reescrever(ir, programa.principal), funcoes={
        nome: replace(funcao, programa=reescrever(funcao.programa, programa.funcoes[nome]))
        for nome, funcao in ir.funcoes.items()})
