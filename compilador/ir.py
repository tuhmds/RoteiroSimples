"""Conversão AST -> IR tipada -> AST temporária do backend."""
from dataclasses import replace
from .ast import Programa, Funcao, NoExpressao, NoInstrucao
from .erros import ErroCompilacao
from .nos_ir import MINIMO, MAXIMO, ExpressaoIR, InstrucaoIR, ProgramaIR, FuncaoIR
from .otimizador import dobrar_constantes
from .cobertura_intermediaria import analisar_cobertura, motivos_de_cobertura, funcoes_escalares_representaveis

def converter_expressao(expr, tipos, otimizar=True, literal_minimo=False, assinaturas=None):
    tag = expr[0]
    origem = getattr(expr, 'origem', None)
    converter = lambda no: converter_expressao(no, tipos, otimizar, assinaturas=assinaturas)
    if tag == 'chamada':
        assinatura = (assinaturas or {}).get(expr[1])
        if assinatura is None:
            raise ErroCompilacao(f'Chamada IR sem assinatura: {expr[1]}.')
        return ExpressaoIR(assinatura[1], 'chamada', expr[1],
                           tuple(converter(no) for no in expr[2]), origem)
    if tag == 'numero':
        if expr[1] == 1 << 63 and not literal_minimo:
            raise ErroCompilacao('Número positivo fora do intervalo de 64 bits.')
        return ExpressaoIR('inteiro', 'numero', expr[1], origem=origem)
    if tag == 'logico':
        return ExpressaoIR('logico', 'logico', expr[1], origem=origem)
    if tag == 'var':
        return ExpressaoIR(tipos[expr[1]], 'var', expr[1], origem=origem)
    if tag == 'tamanho_texto':
        return ExpressaoIR('inteiro', 'tamanho_texto', expr[1], origem=origem)
    if tag == 'indice':
        return ExpressaoIR('inteiro', 'indice', (expr[1], expr[3]),
                           filhos=(converter(expr[2]),), origem=origem)
    if tag == 'neg':
        filho = converter_expressao(expr[1], tipos, otimizar,
                                   literal_minimo=expr[1] == ('numero', 1 << 63), assinaturas=assinaturas)
        node = ExpressaoIR('inteiro', 'neg', filhos=(filho,), origem=origem)
    elif tag in ('bin', 'comparacao'):
        esquerdo = converter(expr[2])
        direito = converter(expr[3])
        node = ExpressaoIR('inteiro' if tag == 'bin' else 'logico', tag,
                           expr[1], (esquerdo, direito), origem=origem)
    else:
        raise ErroCompilacao(f'Expressão IR desconhecida: {tag}.')
    return dobrar_constantes(node) if otimizar else node

def converter_instrucao(instr, tipos, otimizar, assinaturas=None):
    tag = instr[0]
    origem = getattr(instr, 'origem', None)
    expr = lambda n: converter_expressao(n, tipos, otimizar, assinaturas=assinaturas)
    bloco = lambda b: tuple(converter_instrucao(x, tipos, otimizar, assinaturas) for x in b)
    if tag == 'retorne': return InstrucaoIR(tag, (expr(instr[1]),), origem)
    if tag == 'texto': return InstrucaoIR(tag, (instr[1],), origem)
    if tag in ('atribua',): return InstrucaoIR(tag, (instr[1], expr(instr[2])), origem)
    if tag == 'leia_int': return InstrucaoIR(tag, (instr[1],), origem)
    if tag in ('crie_texto', 'modifique_texto', 'limpe_texto', 'imprima_texto', 'leia_texto'):
        return InstrucaoIR(tag, tuple(instr[1:]), origem)
    if tag == 'crie_lista': return InstrucaoIR(tag, (instr[1], instr[2]), origem)
    if tag == 'atribua_indice':
        return InstrucaoIR(tag, (instr[1], expr(instr[2]), expr(instr[3]), instr[4]), origem)
    if tag == 'leia_indice':
        return InstrucaoIR(tag, (instr[1], expr(instr[2]), instr[3]), origem)
    if tag == 'imprima_num': return InstrucaoIR(tag, (expr(instr[1]),), origem)
    if tag == 'se': return InstrucaoIR(tag, (expr(instr[1]), bloco(instr[2]), bloco(instr[3])), origem)
    if tag == 'enquanto': return InstrucaoIR(tag, (expr(instr[1]), bloco(instr[2])), origem)
    if tag == 'para':
        return InstrucaoIR(tag, (instr[1], expr(instr[2]), expr(instr[3]),
                                 instr[4], bloco(instr[5])), origem)
    if tag in ('pare', 'continue'): return InstrucaoIR(tag, (), origem)
    raise ErroCompilacao(f'Instrução IR desconhecida: {tag}.')


def construir_ir(programa, otimizar=True, nivel=1):
    """Constrói IR somente quando a tradução é representável sem perdas."""
    cobertura = analisar_cobertura(programa)
    impedimentos = list(motivos_de_cobertura(cobertura))
    tem_funcoes = bool(getattr(programa, 'funcoes', None))
    if tem_funcoes and not funcoes_escalares_representaveis(programa):
        impedimentos.append('funções fora do contrato escalar da IR')
    if getattr(programa, 'registros', None):
        impedimentos.append('registros não são representados na IR atual')
    # Escopos com variáveis já renomeadas internamente podem ter
    # uma IR útil para análise quando todas as operações são conhecidas.
    # Funções escalares usam esses nomes; escopos com recursos continuam
    # selecionando o gerador conservador pelo contrato de estratégia.
    if impedimentos:
        raise ErroCompilacao(
            'A representação intermediária não está disponível para este programa: '
            + '; '.join(impedimentos) + '. '
            'A compilação nativa permanece disponível pelo gerador conservador.')
    assinaturas = {nome: (funcao.parametros, funcao.retorno)
                   for nome, funcao in getattr(programa, 'funcoes', {}).items()}
    def converter_corpo(corpo):
        ir = ProgramaIR(tuple(converter_instrucao(i, corpo.tipos, otimizar, assinaturas)
                              for i in corpo.instrucoes),
                        dict(corpo.tipos), dict(corpo.variaveis),
                        corpo.importa_matematica, escopos_locais=corpo.escopos_locais)
        if tem_funcoes and otimizar and nivel >= 2:
            from .propagacao import propagar_constantes_locais
            ir = propagar_constantes_locais(ir)
        return ir
    ir = converter_corpo(programa)
    if tem_funcoes:
        ir = replace(ir, funcoes={nome: FuncaoIR(nome, funcao.parametros, funcao.retorno,
            converter_corpo(funcao.programa), funcao.recursiva)
            for nome, funcao in programa.funcoes.items()})
        if otimizar and nivel >= 3:
            from .otimizacao_funcoes_ssa import otimizar_funcoes_com_ssa
            ir = otimizar_funcoes_com_ssa(ir)
        return ir
    if otimizar and nivel >= 2 and not any(isinstance(t, tuple) and t[0] in ('lista', 'texto') for t in programa.tipos.values()):
        from .propagacao import propagar_constantes_locais
        ir = propagar_constantes_locais(ir)
        if nivel >= 3:
            from .ssa_otimizador import otimizar_com_ssa
            ir = otimizar_com_ssa(ir)
    if otimizar and nivel >= 7 and any(isinstance(t, tuple) and t[0] == 'lista'
                                       for t in programa.tipos.values()):
        from .otimizador_memoria import otimizar_acessos_memoria
        ir = otimizar_acessos_memoria(ir)
    if otimizar and nivel >= 8 and any(isinstance(t, tuple) and t[0] == 'lista'
                                        for t in programa.tipos.values()):
        from .otimizacao_entre_blocos import otimizar_entre_blocos
        ir = otimizar_entre_blocos(ir)
    return ir


def expressao_para_ast(node):
    return NoExpressao(_expressao_para_ast(node), node.origem)


def _expressao_para_ast(node):
    if node.operacao == 'chamada':
        return NoExpressao(('chamada', node.valor, tuple(expressao_para_ast(x) for x in node.filhos)), node.origem)
    if node.operacao in ('numero', 'logico', 'var'):
        return (node.operacao, node.valor)
    if node.operacao == 'tamanho_texto':
        return ('tamanho_texto', node.valor)
    if node.operacao == 'indice':
        return ('indice', node.valor[0], expressao_para_ast(node.filhos[0]), node.valor[1])
    if node.operacao == 'neg': return ('neg', expressao_para_ast(node.filhos[0]))
    return (node.operacao, node.valor, *(expressao_para_ast(x) for x in node.filhos))


def instrucao_para_ast(node):
    return NoInstrucao(_instrucao_para_ast(node), node.origem)


def _instrucao_para_ast(node):
    t, a = node.operacao, node.argumentos
    bloco = lambda xs: [instrucao_para_ast(x) for x in xs]
    if t == 'texto': return (t, a[0])
    if t == 'leia_int': return (t, a[0])
    if t in ('crie_texto', 'modifique_texto', 'limpe_texto', 'imprima_texto', 'leia_texto'): return (t, *a)
    if t == 'crie_lista': return (t, a[0], a[1])
    if t == 'atribua_indice': return (t, a[0], expressao_para_ast(a[1]), expressao_para_ast(a[2]), a[3])
    if t == 'leia_indice': return (t, a[0], expressao_para_ast(a[1]), a[2])
    if t == 'atribua': return (t, a[0], expressao_para_ast(a[1]))
    if t == 'imprima_num': return (t, expressao_para_ast(a[0]))
    if t == 'retorne': return NoInstrucao((t, expressao_para_ast(a[0])), node.origem)
    if t == 'se': return (t, expressao_para_ast(a[0]), bloco(a[1]), bloco(a[2]))
    if t == 'enquanto': return (t, expressao_para_ast(a[0]), bloco(a[1]))
    if t == 'para':
        return (t, a[0], expressao_para_ast(a[1]), expressao_para_ast(a[2]), a[3], bloco(a[4]))
    if t in ('pare', 'continue'): return (t,)
    raise ErroCompilacao(f'Instrução IR desconhecida: {t}.')


def programa_para_backend(ir):
    return Programa([instrucao_para_ast(i) for i in ir.instrucoes],
                    dict(ir.variaveis), ir.importa_matematica, dict(ir.tipos),
                    funcoes={nome: Funcao(nome, funcao.parametros, funcao.retorno,
                        programa_para_backend(funcao.programa), funcao.recursiva)
                        for nome, funcao in ir.funcoes.items()}, escopos_locais=ir.escopos_locais)


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
    for nome, funcao in ir.funcoes.items():
        saida.append(f'funcao {nome}: parametros {funcao.parametros}; retorno {funcao.retorno}')
        percorrer(funcao.programa.instrucoes, 1)
    return '\n'.join(saida)
