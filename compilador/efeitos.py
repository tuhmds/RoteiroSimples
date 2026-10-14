"""RS 0.19: resumo conservador de efeitos na IR tipada.

Classificacao para diagnostico e para preparar Memory SSA. Nao autoriza mover,
substituir nem remover operacoes: o backend continua respeitando sua ordem.
"""
import json

from dataclasses import replace
from .nos_ir import ExpressaoIR, InstrucaoIR
from .contrato_efeitos import Efeitos


def efeito_expressao(expr, resumos=None):
    if not isinstance(expr, ExpressaoIR):
        return Efeitos()
    e = Efeitos()
    for filho in expr.filhos:
        e = e.combinar(efeito_expressao(filho, resumos))
    if expr.operacao in ('var', 'tamanho_texto'):
        nome = expr.valor
        return e.combinar(Efeitos(leituras=frozenset((nome,))))
    if expr.operacao == 'indice':
        return e.combinar(Efeitos(leituras=frozenset((expr.valor[0],)),
                                 pode_falhar=True))
    if expr.operacao in ('neg', 'bin'):
        # Overflow, divisão por zero e divisão fora do intervalo são observáveis.
        return e.combinar(Efeitos(pode_falhar=True))
    if expr.operacao == 'chamada':
        chamado = (resumos or {}).get(expr.valor)
        if chamado is None:
            return e.combinar(Efeitos(pode_falhar=True, desconhecido=True, controle=True))
        # Locais e retorno pertencem ao callee. Não vazam para o chamador.
        # Toda chamada conserva a verificação de orçamento de pilha.
        return e.combinar(replace(chamado, leituras=frozenset(), escritas=frozenset(),
                                 encerra=False)).combinar(Efeitos(pode_falhar=True, controle=True))
    if expr.operacao == 'logica':
        # União conservadora: o direito pode não executar, mas suas leituras,
        # falhas e efeitos nunca ficam disponíveis para especulação.
        return e.combinar(Efeitos(controle=True))
    if expr.operacao in ('numero', 'logico', 'comparacao', 'nao'):
        return e
    # Falha segura: novas expressões IR não se tornam puras por omissão.
    return e.combinar(Efeitos(pode_falhar=True, desconhecido=True))


def efeito_instrucao(instr, resumos=None):
    """Descreve efeitos diretos; efeitos dos blocos são relatados à parte."""
    tag, a = instr.operacao, instr.argumentos
    exprs = ()
    if tag == 'atribua':
        exprs = (a[1],)
    elif tag in ('imprima_num', 'retorne', 'se', 'enquanto'):
        exprs = (a[0],)
    elif tag == 'para':
        exprs = (a[1], a[2])
    elif tag == 'atribua_indice':
        exprs = (a[1], a[2])
    elif tag == 'leia_indice':
        exprs = (a[1],)
    e = Efeitos()
    for ex in exprs:
        e = e.combinar(efeito_expressao(ex, resumos))
    if tag in ('parametro', 'atribua', 'crie_lista', 'crie_texto', 'limpe_texto'):
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
    elif tag == 'retorne':
        e = e.combinar(Efeitos(controle=True, encerra=True))
    elif tag == 'para':
        e = e.combinar(Efeitos(escritas=frozenset((a[0],)),
                              pode_falhar=True, controle=True))
    elif tag in ('se', 'enquanto', 'pare', 'continue'):
        e = e.combinar(Efeitos(controle=True))
    elif tag not in ('parametro', 'atribua', 'crie_lista', 'crie_texto', 'limpe_texto'):
        # Os nós IR futuros precisam ser declarados explicitamente.
        # Não assumir ausência de efeitos em instruções desconhecidas.
        e = e.combinar(Efeitos(pode_falhar=True, desconhecido=True))
    return e


def efeito_bloco_cfg(bloco, resumos=None):
    """Efeitos da fase real do laço; não reavalia limites no incremento."""
    if bloco.papel.startswith('para:') and bloco.instrucoes:
        a = bloco.instrucoes[0].argumentos
        if bloco.papel == 'para:inicio':
            return efeito_expressao(a[1], resumos).combinar(Efeitos(escritas=frozenset((a[0],))))
        if bloco.papel == 'para:condicao':
            return efeito_expressao(a[2], resumos).combinar(
                Efeitos(leituras=frozenset((a[0],)), controle=True))
        if bloco.papel == 'para:gravar_incremento':
            return Efeitos(escritas=frozenset((a[0],)))
        return Efeitos(leituras=frozenset((a[0],)),
                       escritas=(frozenset() if any(a.motivo == 'estouro_incremento' for a in bloco.saidas)
                                 else frozenset((a[0],))),
                       controle=True)
    efeito = Efeitos()
    for instr in bloco.instrucoes:
        efeito = efeito.combinar(efeito_instrucao(instr, resumos))
    return efeito


def resumir_funcoes(ir, grafos=None):
    """Ponto fixo de efeitos entre funções escalares, inclusive ciclos.

    Usa apenas blocos alcançáveis. Resumos nunca autorizam transformação
    de chamadas; ausência de falha no corpo não elimina a guarda de pilha.
    """
    from .cfg import construir_cfg_programa
    grafos = grafos or construir_cfg_programa(ir)
    alcancaveis = {nome: grafo.alcancaveis() for nome, grafo in grafos.funcoes.items()}
    resumos = {nome: Efeitos() for nome in ir.funcoes}
    mudou = True
    while mudou:
        mudou = False
        for nome, grafo in grafos.funcoes.items():
            efeito = Efeitos()
            for bid in grafo.blocos:
                if bid not in alcancaveis[nome]:
                    continue
                efeito = efeito.combinar(efeito_bloco_cfg(grafo.blocos[bid], resumos))
            efeito = replace(efeito, leituras=frozenset(), escritas=frozenset(), encerra=False)
            if efeito != resumos[nome]:
                resumos[nome] = efeito
                mudou = True
    return resumos


def listar_efeitos(ir):
    itens = []
    resumos = resumir_funcoes(ir) if ir.funcoes else None
    def caminhar(instrucoes, caminho):
        for n, instr in enumerate(instrucoes):
            atual = f'{caminho}.{n}' if caminho else str(n)
            info = {'caminho': atual, 'operacao': instr.operacao,
                    **efeito_instrucao(instr, resumos).para_dict_completo()}
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
    for nome, funcao in ir.funcoes.items():
        caminhar(funcao.programa.instrucoes, 'funcao:' + nome)
    return itens


def efeitos_para_json(ir):
    dados = {'versao': 'RS 0.19', 'escopo': 'analise conservadora',
             'instrucoes': listar_efeitos(ir)}
    if ir.funcoes:
        dados['versao'] = 'RS 0.42K'
        dados['funcoes'] = {nome: e.para_dict_completo() for nome, e in resumir_funcoes(ir).items()}
    return json.dumps(dados, ensure_ascii=False, indent=2) + '\n'


def formatar_efeitos(ir):
    linhas = ['RS 0.19 - efeitos observaveis de memoria e E/S (analise)']
    if ir.funcoes:
        linhas.append('RS 0.42K - resumos de efeitos por função (chamadas conservam a guarda de pilha)')
        for nome, e in resumir_funcoes(ir).items():
            flags = [campo for campo in ('entrada', 'saida', 'pode_falhar', 'controle', 'desconhecido')
                     if getattr(e, campo)]
            linhas.append(f'funcao {nome}: ' + (', '.join(flags) or 'sem efeitos observáveis no corpo'))
    for e in listar_efeitos(ir):
        flags = []
        if e['leituras']: flags.append('le=' + ','.join(e['leituras']))
        if e['escritas']: flags.append('grava=' + ','.join(e['escritas']))
        if e['entrada']: flags.append('stdin')
        if e['saida']: flags.append('stdout')
        if e['pode_falhar']: flags.append('pode_falhar')
        linhas.append(f"  [{e['caminho']}] {e['operacao']}: " + (', '.join(flags) or 'sem efeitos'))
    return '\n'.join(linhas)
