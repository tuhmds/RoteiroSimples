"""RS 0.19: resumo conservador de efeitos na IR tipada.

Classificacao para diagnostico e para preparar Memory SSA. Nao autoriza mover,
substituir nem remover operacoes: o backend continua respeitando sua ordem.
"""
import json

from .nos_ir import ExpressaoIR, InstrucaoIR
from .contrato_efeitos import Efeitos


def efeito_expressao(expr):
    if not isinstance(expr, ExpressaoIR):
        return Efeitos()
    e = Efeitos()
    for filho in expr.filhos:
        e = e.combinar(efeito_expressao(filho))
    if expr.operacao in ('var', 'tamanho_texto'):
        nome = expr.valor
        return e.combinar(Efeitos(leituras=frozenset((nome,))))
    if expr.operacao == 'indice':
        return e.combinar(Efeitos(leituras=frozenset((expr.valor[0],)),
                                 pode_falhar=True))
    if expr.operacao in ('neg', 'bin'):
        # Overflow, divisão por zero e divisão fora do intervalo são observáveis.
        return e.combinar(Efeitos(pode_falhar=True))
    return e


def efeito_instrucao(instr):
    """Descreve efeitos diretos; efeitos dos blocos são relatados à parte."""
    tag, a = instr.operacao, instr.argumentos
    exprs = ()
    if tag == 'atribua':
        exprs = (a[1],)
    elif tag in ('imprima_num', 'se', 'enquanto'):
        exprs = (a[0],)
    elif tag == 'para':
        exprs = (a[1], a[2])
    elif tag == 'atribua_indice':
        exprs = (a[1], a[2])
    elif tag == 'leia_indice':
        exprs = (a[1],)
    e = Efeitos()
    for ex in exprs:
        e = e.combinar(efeito_expressao(ex))
    if tag in ('atribua', 'crie_lista', 'crie_texto', 'limpe_texto'):
        e = e.combinar(Efeitos(escritas=frozenset((a[0],))))
    elif tag == 'modifique_texto':
        _, modo, nome, origem = (tag, *a)
        leituras = set()
        if modo == 'junte':
            leituras.add(nome)
        if isinstance(origem, tuple) and origem[0] == 'buffer':
            leituras.add(origem[1])
        e = e.combinar(Efeitos(leituras=frozenset(leituras),
                              escritas=frozenset((nome,)), pode_falhar=True))
    elif tag == 'atribua_indice':
        e = e.combinar(Efeitos(escritas=frozenset((a[0],)), pode_falhar=True))
    elif tag in ('leia_int', 'leia_texto', 'leia_indice'):
        e = e.combinar(Efeitos(escritas=frozenset((a[0],)), entrada=True, pode_falhar=True))
    elif tag == 'imprima_texto':
        e = e.combinar(Efeitos(leituras=frozenset((a[0],)), saida=True))
    elif tag in ('imprima_num', 'texto'):
        e = e.combinar(Efeitos(saida=True))
    elif tag == 'para':
        e = e.combinar(Efeitos(escritas=frozenset((a[0],)), pode_falhar=True))
    return e


def listar_efeitos(ir):
    itens = []
    def caminhar(instrucoes, caminho):
        for n, instr in enumerate(instrucoes):
            atual = f'{caminho}.{n}' if caminho else str(n)
            info = {'caminho': atual, 'operacao': instr.operacao,
                    **efeito_instrucao(instr).para_dict()}
            itens.append(info)
            t, a = instr.operacao, instr.argumentos
            if t == 'se':
                caminhar(a[1], atual + '.entao')
                caminhar(a[2], atual + '.senao')
            elif t == 'enquanto':
                caminhar(a[1], atual + '.corpo')
            elif t == 'para':
                caminhar(a[4], atual + '.corpo')
    caminhar(ir.instrucoes, '')
    return itens


def efeitos_para_json(ir):
    return json.dumps({'versao': 'RS 0.19', 'escopo': 'analise conservadora',
                       'instrucoes': listar_efeitos(ir)}, ensure_ascii=False, indent=2) + '\n'


def formatar_efeitos(ir):
    linhas = ['RS 0.19 - efeitos observaveis de memoria e E/S (analise)']
    for e in listar_efeitos(ir):
        flags = []
        if e['leituras']: flags.append('le=' + ','.join(e['leituras']))
        if e['escritas']: flags.append('grava=' + ','.join(e['escritas']))
        if e['entrada']: flags.append('stdin')
        if e['saida']: flags.append('stdout')
        if e['pode_falhar']: flags.append('pode_falhar')
        linhas.append(f"  [{e['caminho']}] {e['operacao']}: " + (', '.join(flags) or 'sem efeitos'))
    return '\n'.join(linhas)
