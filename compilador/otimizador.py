"""Primeiro passo de otimização: dobramento conservador de constantes."""
from .nos_ir import ExpressaoIR, MINIMO, MAXIMO

def dobrar_constantes(node):
    """Dobra constantes e ramos lógicos comprovadamente dispensados.

    Somente o operando ESQUERDO literal pode dispensar o direito. Um
    direito constante nunca autoriza apagar chamada ou falha à esquerda.
    """
    if node.operacao == 'logica' and node.filhos[0].operacao == 'logico':
        esquerdo = bool(node.filhos[0].valor)
        if ((node.valor == 'e' and not esquerdo) or
                (node.valor == 'ou' and esquerdo)):
            return ExpressaoIR('logico', 'logico', int(esquerdo), origem=node.origem)
    if any(f.operacao not in ('numero', 'logico') for f in node.filhos):
        return node
    if node.operacao == 'nao':
        v = int(not node.filhos[0].valor)
    elif node.operacao == 'logica':
        a, b = (bool(x.valor) for x in node.filhos)
        if node.valor not in ('e', 'ou'):
            return node
        v = int(a and b if node.valor == 'e' else a or b)
    elif node.operacao == 'neg':
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
    return ExpressaoIR(node.tipo, 'logico' if node.tipo == 'logico' else 'numero', v, origem=node.origem)
