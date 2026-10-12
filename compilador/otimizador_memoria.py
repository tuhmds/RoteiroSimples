"""RS 0.21 — propagacao segura por versoes da Memory SSA.

Apenas elementos de listas locais com indices *literais* comprovadamente validos.
Nao antecipa acessos, E/S, falhas ou operacoes com possiveis aliases. Um
controle de fluxo invalida o estado; cada corpo comeca sem conhecimentos.
"""
from dataclasses import replace

from .memory_ssa import construir_memory_ssa
from .nos_ir import ExpressaoIR, InstrucaoIR, ProgramaIR
from .otimizador import dobrar_constantes


def otimizar_acessos_memoria(ir: ProgramaIR):
    """Utiliza as versoes da Memory SSA para encaminhar valores e cortar stores.

    A cadeia por objeto e validada antes da transformacao. O conhecimento de
    elementos nunca cruza juncoes de controle, retroarestas nem indices
    dinamicos, mesmo quando uma analise posterior poderia prova-los seguros.
    """
    memoria = construir_memory_ssa(ir)
    memoria.validar()
    acessos = {}
    for bloco in memoria.blocos.values():
        if bloco.alcancavel:
            for info, instr in zip(bloco.instrucoes, memoria.cfg.blocos[bloco.id].instrucoes):
                acessos[id(instr)] = info

    tamanhos = {nome: tipo[1] for nome, tipo in ir.tipos.items()
                if isinstance(tipo, tuple) and tipo[0] == 'lista'}

    def processar(instrucoes, conhecidos=None, versoes=None):
        conhecidos = {} if conhecidos is None else conhecidos
        versoes = {} if versoes is None else versoes
        saida = []
        for instr in instrucoes:
            op, a = instr.operacao, instr.argumentos
            acesso = acessos.get(id(instr))

            def permitido(nome):
                regiao = 'mem:' + nome
                return (acesso is not None and nome in versoes
                        and acesso.usos.get(regiao) == versoes[nome])

            def exp(e):
                if e.operacao == 'indice' and e.valor[0] in tamanhos:
                    nome, tamanho = e.valor
                    indice = e.filhos[0]
                    if (indice.operacao == 'numero' and 0 <= indice.valor < tamanho
                            and permitido(nome) and indice.valor in conhecidos.get(nome, {})):
                        return ExpressaoIR('inteiro', 'numero', conhecidos[nome][indice.valor], origem=e.origem)
                if not e.filhos:
                    return e
                filhos = tuple(exp(f) for f in e.filhos)
                if filhos == e.filhos:
                    return e
                return dobrar_constantes(replace(e, filhos=filhos))

            if op in ('se', 'enquanto', 'para'):
                if op == 'se':
                    nova = (a[0], tuple(processar(a[1])), tuple(processar(a[2])))
                elif op == 'enquanto':
                    nova = (a[0], tuple(processar(a[1])))
                else:
                    nova = (*a[:4], tuple(processar(a[4])))
                saida.append(replace(instr, argumentos=nova))
                conhecidos.clear()
                versoes.clear()
                continue

            if op == 'crie_lista':
                nome, tamanho = a
                conhecidos[nome] = {i: 0 for i in range(tamanho)}
                if acesso and ('mem:' + nome) in acesso.definicoes:
                    versoes[nome] = acesso.definicoes['mem:' + nome]
                saida.append(instr)
                continue

            if op == 'atribua_indice':
                nome, indice, valor, tamanho = a
                # A ordem original valida o indice antes de avaliar o valor.
                # A nova expressao mantem essa ordem no backend.
                novo_valor = exp(valor)
                idx = indice.valor if indice.operacao == 'numero' else None
                in_range = isinstance(idx, int) and 0 <= idx < tamanho
                regiao = 'mem:' + nome
                ja_conhecido = (in_range and novo_valor.operacao == 'numero'
                                 and permitido(nome)
                                 and conhecidos.get(nome, {}).get(idx) == novo_valor.valor)
                if not ja_conhecido:
                    saida.append(replace(instr, argumentos=(nome, indice, novo_valor, tamanho)))
                # Registrar a versao original mesmo quando o store foi omitido:
                # a Memory SSA ainda modela o grafo ANTES da transformacao.
                if in_range and novo_valor.operacao == 'numero':
                    conhecidos.setdefault(nome, {})[idx] = novo_valor.valor
                else:
                    conhecidos.pop(nome, None)
                if acesso and regiao in acesso.definicoes:
                    versoes[nome] = acesso.definicoes[regiao]
                else:
                    versoes.pop(nome, None)
                continue

            if op == 'leia_indice':
                conhecidos.pop(a[0], None)
                if acesso and 'mem:' + a[0] in acesso.definicoes:
                    versoes[a[0]] = acesso.definicoes['mem:' + a[0]]
                else:
                    versoes.pop(a[0], None)
                saida.append(instr)
                continue

            if op == 'imprima_num':
                saida.append(replace(instr, argumentos=(exp(a[0]),)))
            elif op == 'atribua':
                saida.append(replace(instr, argumentos=(a[0], exp(a[1]))))
            else:
                # Futuras instrucoes que escrevam listas invalidam o cache;
                # o codigo nao deve supor que todos os efeitos sao conhecidos.
                if acesso:
                    for regiao in acesso.definicoes:
                        if regiao.startswith('mem:') and regiao[4:] in tamanhos:
                            conhecidos.pop(regiao[4:], None)
                            versoes.pop(regiao[4:], None)
                saida.append(instr)
        return saida

    return replace(ir, instrucoes=tuple(processar(ir.instrucoes)))
