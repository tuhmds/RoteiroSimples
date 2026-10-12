"""Primeiro passo de otimização: dobramento conservador de constantes."""
from .nos_ir import ExpressaoIR, MINIMO, MAXIMO

def dobrar_constantes(node):
    """Dobra apenas constantes 64-bit sem exceção observável na execução."""
    if any(f.operacao not in ('numero', 'logico') for f in node.filhos):
        return node
    if node.operacao == 'neg':
        v = -node.filhos[0].valor
    elif node.operacao in ('bin', 'comparacao'):
        a, b = (x.valor for x in node.filhos)
        op = node.valor
        if node.operacao == 'comparacao':
            v = int({'==': lambda: a == b, '!=': lambda: a != b,
                     '<': lambda: a < b, '<=': lambda: a <= b,
                     '>': lambda: a > b, '>=': lambda: a >= b}[op]())
        elif op == '+': v = a + b
        elif op == '-': v = a - b
        elif op == '*': v = a * b
        elif op in ('/', '%'):
            if b == 0 or (a == MINIMO and b == -1):
                return node  # a verificação de erro permanece em tempo de execução
            q = (abs(a) // abs(b)) * (-1 if (a < 0) != (b < 0) else 1)
            v = q if op == '/' else a - q * b
        else:
            return node
    else:
        return node
    if node.tipo == 'inteiro' and not MINIMO <= v <= MAXIMO:
        return node  # preservar sinalização de overflow em tempo de execução
    return ExpressaoIR(node.tipo, 'logico' if node.tipo == 'logico' else 'numero', v)
