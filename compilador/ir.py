"""Conversão AST -> IR tipada -> AST temporária do backend."""
from .ast import Programa
from .erros import ErroCompilacao
from .nos_ir import MINIMO, MAXIMO, ExpressaoIR, InstrucaoIR, ProgramaIR
from .otimizador import dobrar_constantes

def converter_expressao(expr, tipos, otimizar=True, literal_minimo=False):
    tag = expr[0]
    origem = getattr(expr, 'origem', None)
    if tag == 'numero':
        if expr[1] == 1 << 63 and not literal_minimo:
            raise ErroCompilacao('Número positivo fora do intervalo de 64 bits.')
        return ExpressaoIR('inteiro', 'numero', expr[1], origem=origem)
    if tag == 'logico':
        return ExpressaoIR('logico', 'logico', expr[1], origem=origem)
    if tag == 'var':
        return ExpressaoIR(tipos[expr[1]], 'var', expr[1], origem=origem)
    if tag == 'neg':
        filho = converter_expressao(expr[1], tipos, otimizar,
                                   literal_minimo=expr[1] == ('numero', 1 << 63))
        node = ExpressaoIR('inteiro', 'neg', filhos=(filho,), origem=origem)
    elif tag in ('bin', 'comparacao'):
        esquerdo = converter_expressao(expr[2], tipos, otimizar)
        direito = converter_expressao(expr[3], tipos, otimizar)
        node = ExpressaoIR('inteiro' if tag == 'bin' else 'logico', tag,
                           expr[1], (esquerdo, direito), origem=origem)
    else:
        raise ErroCompilacao(f'Expressão IR desconhecida: {tag}.')
    return dobrar_constantes(node) if otimizar else node

def converter_instrucao(instr, tipos, otimizar):
    tag = instr[0]
    origem = getattr(instr, 'origem', None)
    expr = lambda n: converter_expressao(n, tipos, otimizar)
    bloco = lambda b: tuple(converter_instrucao(x, tipos, otimizar) for x in b)
    if tag == 'texto': return InstrucaoIR(tag, (instr[1],), origem)
    if tag in ('atribua',): return InstrucaoIR(tag, (instr[1], expr(instr[2])), origem)
    if tag == 'leia_int': return InstrucaoIR(tag, (instr[1],), origem)
    if tag == 'imprima_num': return InstrucaoIR(tag, (expr(instr[1]),), origem)
    if tag == 'se': return InstrucaoIR(tag, (expr(instr[1]), bloco(instr[2]), bloco(instr[3])), origem)
    if tag == 'enquanto': return InstrucaoIR(tag, (expr(instr[1]), bloco(instr[2])), origem)
    if tag == 'para':
        return InstrucaoIR(tag, (instr[1], expr(instr[2]), expr(instr[3]),
                                 instr[4], bloco(instr[5])), origem)
    if tag in ('pare', 'continue'): return InstrucaoIR(tag, (), origem)
    raise ErroCompilacao(f'Instrução IR desconhecida: {tag}.')


def construir_ir(programa, otimizar=True, nivel=1):
    ir = ProgramaIR(tuple(converter_instrucao(i, programa.tipos, otimizar)
                          for i in programa.instrucoes),
                    dict(programa.tipos), dict(programa.variaveis),
                    programa.importa_matematica)
    if otimizar and nivel >= 2:
        from .propagacao import propagar_constantes_locais
        ir = propagar_constantes_locais(ir)
        if nivel >= 3:
            from .ssa_otimizador import otimizar_com_ssa
            ir = otimizar_com_ssa(ir)
    return ir


def expressao_para_ast(node):
    if node.operacao in ('numero', 'logico', 'var'):
        return (node.operacao, node.valor)
    if node.operacao == 'neg': return ('neg', expressao_para_ast(node.filhos[0]))
    return (node.operacao, node.valor, *(expressao_para_ast(x) for x in node.filhos))


def instrucao_para_ast(node):
    t, a = node.operacao, node.argumentos
    bloco = lambda xs: [instrucao_para_ast(x) for x in xs]
    if t == 'texto': return (t, a[0])
    if t == 'leia_int': return (t, a[0])
    if t == 'atribua': return (t, a[0], expressao_para_ast(a[1]))
    if t == 'imprima_num': return (t, expressao_para_ast(a[0]))
    if t == 'se': return (t, expressao_para_ast(a[0]), bloco(a[1]), bloco(a[2]))
    if t == 'enquanto': return (t, expressao_para_ast(a[0]), bloco(a[1]))
    if t == 'para':
        return (t, a[0], expressao_para_ast(a[1]), expressao_para_ast(a[2]), a[3], bloco(a[4]))
    if t in ('pare', 'continue'): return (t,)
    raise ErroCompilacao(f'Instrução IR desconhecida: {t}.')


def programa_para_backend(ir):
    return Programa([instrucao_para_ast(i) for i in ir.instrucoes],
                    dict(ir.variaveis), ir.importa_matematica, dict(ir.tipos))


def formatar_ir(ir):
    """Representação textual estável e legível para depuração da IR tipada."""
    def expr(e):
        if not e.filhos: return f'{e.operacao}:{e.tipo}({e.valor})'
        filhos = ', '.join(expr(f) for f in e.filhos)
        return f'{e.operacao}:{e.tipo}({e.valor}, {filhos})'
    saida = ['RS IR v1 (tipada)']
    for nome, tipo in ir.tipos.items(): saida.append(f'var {nome}: {tipo}')
    def percorrer(bloco, nivel=0):
        for i in bloco:
            args = []
            for x in i.argumentos:
                if isinstance(x, ExpressaoIR): args.append(expr(x))
                elif isinstance(x, tuple) and (not x or isinstance(x[0], InstrucaoIR)):
                    args.append('{')
                else: args.append(repr(x))
            saida.append('  '*nivel + i.operacao + ' ' + ', '.join(args))
            for x in i.argumentos:
                if isinstance(x, tuple) and (not x or isinstance(x[0], InstrucaoIR)):
                    percorrer(x, nivel+1)
    percorrer(ir.instrucoes)
    return '\n'.join(saida)
