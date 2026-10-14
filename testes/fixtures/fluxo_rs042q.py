"""Algoritmos da RS 0.42Q, commit 47eb322; referência de desenvolvimento.

Compartilha apenas tipos e auxiliares sem mudança semântica.
"""
from collections import defaultdict
from dataclasses import replace
from compilador.cfg import GrafoCFG, construir_cfg
from compilador.fluxo_dados import AnaliseFluxo, efeitos_bloco
from compilador.medicao_compilacao import etapa
from compilador.nos_ir import ExpressaoIR, ProgramaIR
from compilador.ssa import (ProgramaSSA, BlocoSSA, PhiSSA, InstrucaoSSA,
                            _ordenar_bloco, _usos, cfg_tipo, _posicionar_phis)
from compilador.ssa_otimizador import analisar_constantes_ssa, _reescrever_expressao


def analisar_fluxo_antes(cfg: GrafoCFG, medidor=None):
    """Ponto fixo sobre arestas reais, incluindo retroarestas e continue/pare."""
    with etapa(medidor, 'fluxo_preparacao'):
        cfg.validar()
        vivos = cfg.alcancaveis()
        blocos = cfg.blocos
        ordem = [nome for nome in blocos if nome in vivos]
        predecessores = defaultdict(set)
        for nome in ordem:
            for aresta in blocos[nome].saidas:
                if aresta.destino in vivos:
                    predecessores[aresta.destino].add(nome)

        usos, defs = {}, {}
        for nome, bloco in blocos.items():
            usos[nome], defs[nome] = efeitos_bloco(bloco)
    with etapa(medidor, 'fluxo_definicoes_alcancam'):
        # Identificadores de definição estáveis: bX:variavel.
        definicoes_por_variavel = defaultdict(set)
        for nome in ordem:
            for variavel in defs[nome]:
                definicoes_por_variavel[variavel].add(f'{nome}:{variavel}')
        geradas = {b: {f'{b}:{var}' for var in defs[b]} for b in ordem}
        eliminadas = {b: set().union(*(definicoes_por_variavel[var] for var in defs[b])) - geradas[b]
                      for b in ordem}
        entradas_def = {b: set() for b in blocos}
        saidas_def = {b: set() for b in blocos}
        mudou = True
        while mudou:
            mudou = False
            for nome in ordem:
                entrada = set().union(*(saidas_def[p] for p in predecessores[nome])) if predecessores[nome] else set()
                saida = geradas[nome] | (entrada - eliminadas[nome])
                if entrada != entradas_def[nome] or saida != saidas_def[nome]:
                    entradas_def[nome], saidas_def[nome] = entrada, saida
                    mudou = True

    with etapa(medidor, 'fluxo_vivacidade'):
        vivos_entrada = {b: set() for b in blocos}
        vivos_saida = {b: set() for b in blocos}
        mudou = True
        while mudou:
            mudou = False
            for nome in reversed(ordem):
                saida = set().union(*(vivos_entrada[e.destino] for e in blocos[nome].saidas
                                      if e.destino in vivos)) if blocos[nome].saidas else set()
                entrada = usos[nome] | (saida - defs[nome])
                if entrada != vivos_entrada[nome] or saida != vivos_saida[nome]:
                    vivos_entrada[nome], vivos_saida[nome] = entrada, saida
                    mudou = True

    with etapa(medidor, 'fluxo_dominadores'):
        dominadores = {b: set(vivos) if b in vivos else set() for b in blocos}
        dominadores[cfg.entrada] = {cfg.entrada}
        mudou = True
        while mudou:
            mudou = False
            for nome in ordem:
                if nome == cfg.entrada:
                    continue
                ps = predecessores[nome]
                novos = ({nome} | set.intersection(*(dominadores[p] for p in ps))) if ps else {nome}
                if novos != dominadores[nome]:
                    dominadores[nome] = novos
                    mudou = True

    with etapa(medidor, 'fluxo_definicoes_garantidas'):
        # Definições possíveis não comprovam definição em TODOS os caminhos.
        # Interseção com ponto fixo descendente, entrada vazia e parâmetros gerados.
        universo = set(definicoes_por_variavel)
        garantidas_entrada = {b: set(universo) if b in vivos else set() for b in blocos}
        garantidas_saida = {b: set(universo) if b in vivos else set() for b in blocos}
        mudou = True
        while mudou:
            mudou = False
            for nome in ordem:
                ps = predecessores[nome]
                entrada = (set.intersection(*(garantidas_saida[p] for p in ps))
                           if ps and nome != cfg.entrada else set())
                saida = entrada | defs[nome]
                if entrada != garantidas_entrada[nome] or saida != garantidas_saida[nome]:
                    garantidas_entrada[nome], garantidas_saida[nome] = entrada, saida
                    mudou = True

    with etapa(medidor, 'fluxo_diagnosticos'):
        candidatos = {}
        sem_definicao = {b: set() for b in blocos}
        for nome in ordem:
            if len(predecessores[nome]) >= 2:
                for var, definicoes in definicoes_por_variavel.items():
                    chegando = {def_id for def_id in entradas_def[nome] if def_id in definicoes}
                    if len(chegando) >= 2:
                        candidatos.setdefault(nome, {})[var] = chegando
            for var in usos[nome]:
                if var not in garantidas_entrada[nome]:
                    sem_definicao[nome].add(var)

    return AnaliseFluxo(cfg, usos, defs, entradas_def, saidas_def,
                        vivos_entrada, vivos_saida, dominadores, candidatos, sem_definicao,
                        garantidas_entrada, garantidas_saida)


def construir_ssa_antes(cfg: GrafoCFG, medidor=None) -> ProgramaSSA:
    """Phi pruned via dominance frontiers; renomeação via árvore de dominadores."""
    cfg.validar_para_ssa()
    with etapa(medidor, 'ssa_fluxo'):
        fluxo = analisar_fluxo_antes(cfg, medidor=medidor)
    with etapa(medidor, 'ssa_dominancia'):
        alcancaveis = cfg.alcancaveis()
        preds = {b: set() for b in alcancaveis}
        for bid in alcancaveis:
            for a in cfg.blocos[bid].saidas:
                if a.destino in alcancaveis:
                    preds[a.destino].add(bid)
        idom = {cfg.entrada: None}
        for b in sorted(alcancaveis, key=_ordenar_bloco):
            if b == cfg.entrada:
                continue
            candidatos = fluxo.dominadores[b] - {b}
            if not candidatos:
                raise ValueError(f'Sem dominador imediato para {b}')
            idom[b] = max(candidatos, key=lambda x: len(fluxo.dominadores[x]))
        filhos = {b: [] for b in alcancaveis}
        for b, pai in idom.items():
            if pai is not None:
                filhos[pai].append(b)
        for lista in filhos.values():
            lista.sort(key=_ordenar_bloco)

        fronteiras = {b: set() for b in alcancaveis}
        for bloco in alcancaveis:
            if len(preds[bloco]) < 2:
                continue
            for p in preds[bloco]:
                atual = p
                while atual != idom[bloco]:
                    fronteiras[atual].add(bloco)
                    atual = idom[atual]
                    if atual is None:
                        raise ValueError('CFG inconsistente ao calcular fronteiras de dominância.')

    with etapa(medidor, 'ssa_preparacao_phi'):
        blocos = {bid: BlocoSSA(bid, cfg.blocos[bid].papel, alcancavel=bid in alcancaveis)
                  for bid in cfg.blocos}
        tipos = {nome: cfg_tipo(fluxo, nome)
                 for nome in sorted(set().union(*(fluxo.definicoes[b] for b in alcancaveis)))}
        incrementos = {bid: f'__rs_incremento_{bid}' for bid in alcancaveis
                       if cfg.blocos[bid].papel == 'para:incremento'
                       and any(a.motivo == 'estouro_incremento' for a in cfg.blocos[bid].saidas)}
        tipos.update({nome: 'inteiro' for nome in incrementos.values()})
        gravacoes = {next(a.destino for a in cfg.blocos[bid].saidas if a.motivo == 'proximo'): nome
                    for bid, nome in incrementos.items()}
        definicoes_por_nome = defaultdict(set)
        for bid in alcancaveis:
            for nome in fluxo.definicoes[bid]:
                definicoes_por_nome[nome].add(bid)

    with etapa(medidor, 'ssa_posicionamento_phi'):
        _posicionar_phis(definicoes_por_nome, fronteiras, fluxo.vivos_entrada,
                        blocos, tipos, medidor)

    pilhas = defaultdict(list)
    contador = defaultdict(int)

    def nova(nome):
        versao = f'{nome}@{contador[nome]}'
        contador[nome] += 1
        pilhas[nome].append(versao)
        return versao

    def ler(nome):
        if not pilhas[nome]:
            raise ValueError(f'Uso de {nome} antes de definição dominadora na SSA.')
        return pilhas[nome][-1]

    def renomear_expressao(x):
        if not isinstance(x, ExpressaoIR):
            return x
        if x.operacao == 'var':
            return ExpressaoIR(x.tipo, 'var', ler(x.valor), (), x.origem)
        return ExpressaoIR(x.tipo, x.operacao, x.valor,
                           tuple(renomear_expressao(f) for f in x.filhos), x.origem)

    def visitar(bid):
        bb = blocos[bid]
        original = cfg.blocos[bid]
        criadas = []
        for nome in sorted(bb.phis):
            bb.phis[nome].destino = nova(nome)
            criadas.append(nome)
        if original.instrucoes and original.papel == 'entrada':
            for parametro in original.instrucoes:
                if parametro.operacao != 'parametro':
                    raise ValueError('Entrada SSA contém instrução que não define parâmetro.')
                nome, tipo = parametro.argumentos
                destino = nova(nome)
                criadas.append(nome)
                bb.instrucoes.append(InstrucaoSSA('parametro', destino, (nome, tipo), (), parametro.origem))
        if original.instrucoes and original.papel != 'entrada':
            ir = original.instrucoes[0]
            op, a = ir.operacao, ir.argumentos
            funcao = original.papel
            destino, operandos = None, ()
            if funcao == 'para:inicio':
                inicial = renomear_expressao(a[1])
                destino = nova(a[0]); criadas.append(a[0])
                operandos = (inicial,)
            elif funcao == 'para:condicao':
                operandos = (ler(a[0]), renomear_expressao(a[2]), a[3])
            elif funcao == 'para:incremento':
                corrente = ler(a[0])
                nome = incrementos.get(bid, a[0])
                destino = nova(nome); criadas.append(nome)
                operandos = (corrente, a[3])
            elif funcao == 'para:gravar_incremento':
                resultado = ExpressaoIR('inteiro', 'var', ler(gravacoes[bid]), origem=ir.origem)
                destino = nova(a[0]); criadas.append(a[0])
                operandos = (resultado,)
            elif op == 'atribua':
                expr = renomear_expressao(a[1])
                destino = nova(a[0]); criadas.append(a[0])
                operandos = (expr,)
            elif op == 'leia_int':
                destino = nova(a[0])
                criadas.append(a[0])
            elif op in ('imprima_num', 'retorne'):
                operandos = (renomear_expressao(a[0]),)
            elif funcao in ('se:condicao', 'enquanto:condicao'):
                operandos = (renomear_expressao(a[0]),)
            elif op == 'texto':
                operandos = (a[0],)
            elif op not in ('pare', 'continue'):
                raise ValueError(f'Papel não reconhecido na SSA: {funcao}')
            fontes = _usos(operandos)
            bb.instrucoes.append(InstrucaoSSA(funcao, destino, operandos, fontes, ir.origem))
        # Cada aresta recebe exatamente a versão vigente ao sair do bloco.
        for a in original.saidas:
            if a.destino not in alcancaveis:
                continue
            destino_bb = blocos[a.destino]
            for nome, phi in destino_bb.phis.items():
                phi.entradas[bid] = ler(nome)
        return criadas

    with etapa(medidor, 'ssa_renomeacao'):
        # A árvore de dominância pode ser profunda mesmo sem laços aninhados.
        # Percurso iterativo evita esgotar a pilha do compilador Python.
        pendentes = [(cfg.entrada, False, ())]
        while pendentes:
            bid, saindo, criadas = pendentes.pop()
            if saindo:
                for nome in reversed(criadas):
                    pilhas[nome].pop()
                continue
            criadas = visitar(bid)
            pendentes.append((bid, True, criadas))
            for filho in reversed(filhos[bid]):
                pendentes.append((filho, False, ()))
    ssa = ProgramaSSA(cfg, blocos, tipos,
                      fluxo.dominadores, idom, fronteiras, preds)
    # Tipo de cada phi é mantido no próprio nó; os tipos vêm da IR.
    with etapa(medidor, 'ssa_validacao'):
        ssa.validar()
    return ssa


def otimizar_com_ssa_antes(ir: ProgramaIR, medidor=None):
    """Usa definicoes SSA para reescrever atribuicoes e impressao de inteiros.

    Cada instrucao fonte ocorre em um unico bloco CFG. Fazemos correspondencia
    por identidade do proprio no InstrucaoIR, nunca pela linha (que pode repetir
    em codigo gerado) nem pelo nome nao-versionado da variavel.
    """
    with etapa(medidor, 'otimizacao_cfg_inicial'):
        cfg = construir_cfg(ir)
    with etapa(medidor, 'otimizacao_ssa_inicial'):
        ssa = construir_ssa_antes(cfg, medidor=medidor)
    with etapa(medidor, 'otimizacao_constantes'):
        constantes = analisar_constantes_ssa(ssa)
    with etapa(medidor, 'otimizacao_identificar_constantes'):
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

    with etapa(medidor, 'otimizacao_reescrita_ir'):
        propagado = ProgramaIR(percorrer(ir.instrucoes), dict(ir.tipos),
                               dict(ir.variaveis), ir.importa_matematica)

    # Elimina somente gravacoes CONSTANTES cujos valores nao sao observados.
    # Divisao, overflow, leia e qualquer outra operacao com efeito sao mantidos.
    with etapa(medidor, 'otimizacao_cfg_vivacidade'):
        grafo = construir_cfg(propagado)
    with etapa(medidor, 'otimizacao_fluxo_vivacidade'):
        fluxo = analisar_fluxo_antes(grafo, medidor=medidor)
    with etapa(medidor, 'otimizacao_identificar_mortos'):
        alcancaveis = grafo.alcancaveis()
        if medidor is not None:
            medidor.contar('otimizacao_buscas_alcancaveis', 1)
        mortos = set()
        for bid, bloco in grafo.blocos.items():
            if bid not in alcancaveis or not bloco.instrucoes:
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
    with etapa(medidor, 'otimizacao_eliminacao_ir'):
        return ProgramaIR(eliminar(propagado.instrucoes), dict(ir.tipos),
                          dict(ir.variaveis), ir.importa_matematica)
