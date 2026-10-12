"""RS 0.14: backend SSA real, com copias phi emitidas em cada aresta.

As localizacoes sao r13/r14/r15 e slots rbp-relativos; uma copia
paralela pode formar ciclos apos alocacao, portanto usamos um slot
separado de temporario. O caminho anterior permanece intacto em -O 0..3.
"""
import struct

from compilador.alocacao import Local, alocar_registradores
from compilador.cfg import ArestaCFG, construir_cfg
from compilador.ir import expressao_para_ast, programa_para_backend
from compilador.ssa import construir_ssa
from .x86_64 import (carregar_numero, deslocamento_variavel, escreve_literal,
                     expressao)

REG_NUM = {'r13': 13, 'r14': 14, 'r15': 15}


def _emite_mov(g, destino, origem):
    """mov destino <- origem para registradores AMD64 r13,r14,r15,rax."""
    # REX.W=1, REX.R/B extensoes de registradores, opcode 89 /r.
    def numero(nome):
        return 0 if nome == 'rax' else REG_NUM[nome]
    a, b = numero(destino), numero(origem)
    rex = 0x48 | ((b >> 3) << 2) | (a >> 3)
    modrm = 0xC0 | ((b & 7) << 3) | (a & 7)
    g.bytes(bytes((rex, 0x89, modrm)))


def _carregar(g, local, windows):
    if local.classe == 'reg':
        _emite_mov(g, 'rax', local.indice)
    else:
        offset = deslocamento_variavel({local.indice: local.indice}, local.indice, windows)
        g.bytes(b'\x48\x8B\x85' + struct.pack('<i', offset))


def _gravar(g, local, windows):
    if local.classe == 'reg':
        _emite_mov(g, local.indice, 'rax')
    else:
        offset = deslocamento_variavel({local.indice: local.indice}, local.indice, windows)
        g.bytes(b'\x48\x89\x85' + struct.pack('<i', offset))


def copias_paralelas(g, copias, locais, temporario, windows):
    """Baixa simultaneidade dos phi, quebrando ciclos por slot reservado.

    copias: [(destinoSSA, fonteSSA)]. Retorna numero de instrucoes logicas.
    """
    pendentes = {}
    for destino, fonte in copias:
        a, b = locais[destino], locais[fonte]
        if a == b:
            continue
        if a in pendentes and pendentes[a] != b:
            raise ValueError('Copias phi colidem no mesmo destino fisico.')
        pendentes[a] = b
    qtd = 0
    while pendentes:
        fontes = set(pendentes.values())
        pronto = next((dest for dest in pendentes if dest not in fontes), None)
        if pronto is not None:
            fonte = pendentes.pop(pronto)
            _carregar(g, fonte, windows)
            _gravar(g, pronto, windows)
            qtd += 1
        else:
            # Em um ciclo, preservar o valor original de um destino.
            preservado = next(iter(pendentes))
            _carregar(g, preservado, windows)
            _gravar(g, temporario, windows)
            pendentes = {dest: (temporario if fonte == preservado else fonte)
                         for dest, fonte in pendentes.items()}
            qtd += 1
    return qtd


def construir_backend_ssa(ir):
    cfg = construir_cfg(ir)
    # O para sai também quando o incremento aritmetico ultrapassa 64 bits.
    # Essa aresta e necessaria para calcular phis corretos na saida do laco.
    for b in cfg.blocos.values():
        if b.papel == 'para:incremento':
            cond = b.saidas[0].destino
            saida_laco = next(a.destino for a in cfg.blocos[cond].saidas
                              if a.motivo == 'falso')
            b.saidas = (*b.saidas, ArestaCFG(saida_laco, 'overflow'))
    cfg.validar()
    ssa = construir_ssa(cfg)
    aloc = alocar_registradores(ssa)
    return ssa, aloc


def emissor_ssa(ir, ssa, aloc):
    """Retorna callback executavel para montar_codigo, com arquivo nativo real."""
    locais = aloc.locais
    pilha = {v: loc.indice for v, loc in locais.items() if loc.classe == 'pilha'}
    regs = {v: loc.indice for v, loc in locais.items() if loc.classe == 'reg'}
    temporario = Local('pilha', aloc.vagas_pilha)
    alcancaveis = {b for b, bloco in ssa.blocos.items() if bloco.alcancavel}
    def emissor(g, mensagens, windows):
        from .x86_64 import expressao  # aceita registradores em modo SSA

        def avaliar(exp):
            expressao(g, expressao_para_ast(exp), pilha, windows, regs)

        def rotulo(bid):
            return f'ssa_{bid}'

        def aresta(de, para):
            destino = ssa.blocos[para]
            copias = [(p.destino, p.entradas[de])
                      for p in sorted(destino.phis.values(), key=lambda p: p.variavel)]
            copias_paralelas(g, copias, locais, temporario, windows)
            g.salto(rotulo(para))

        g.salto(rotulo(ssa.cfg.entrada))
        for bid, bloco in ssa.blocos.items():
            if bid not in alcancaveis:
                continue
            g.marcar(rotulo(bid))
            cfgb = ssa.cfg.blocos[bid]
            if cfgb.papel == 'saida':
                g.salto('ssa_saida_geral')
                continue
            inst = bloco.instrucoes[0] if bloco.instrucoes else None
            if inst:
                nome = inst.operacao
                args = inst.argumentos
                if nome == 'texto':
                    n = len(mensagens)
                    mensagens[n] = args[0]
                    escreve_literal(g, n, args[0], windows)
                elif nome in ('atribua', 'para:inicio'):
                    avaliar(args[0])
                    _gravar(g, locais[inst.destino], windows)
                elif nome == 'leia_int':
                    g.chamada('ler_inteiro')
                    _gravar(g, locais[inst.destino], windows)
                elif nome == 'imprima_num':
                    avaliar(args[0])
                    g.chamada('imprimir_inteiro')
                elif nome == 'para:incremento':
                    atual, passo = args
                    _carregar(g, locais[atual], windows)
                    g.bytes(b'\x48\x89\xC1')  # mov rcx,rax
                    carregar_numero(g, passo)
                    g.bytes(b'\x48\x01\xC8')  # add rax,rcx
                    overflow = next((a.destino for a in cfgb.saidas if a.motivo == 'overflow'), None)
                    if overflow is None:
                        raise ValueError('Aresta de overflow obrigatoria no incremento para.')
                    rotulo_erro = f'ssa_overflow_{bid}'
                    g.salto(rotulo_erro, 'jo')
                    _gravar(g, locais[inst.destino], windows)
                    proximo = next(a.destino for a in cfgb.saidas if a.motivo == 'proximo')
                    aresta(bid, proximo)
                    g.marcar(rotulo_erro)
                    # No overflow, manter o contador anterior, como no backend legado.
                    _carregar(g, locais[atual], windows)
                    _gravar(g, locais[inst.destino], windows)
                    aresta(bid, overflow)
                    continue
                elif nome in ('se:condicao', 'enquanto:condicao'):
                    avaliar(args[0])
                    g.bytes(b'\x48\x85\xC0')  # test rax,rax
                    falso = next(a.destino for a in cfgb.saidas if a.motivo == 'falso')
                    verdadeiro = next(a.destino for a in cfgb.saidas if a.motivo == 'verdadeiro')
                    rotulo_falso = f'ssa_falso_{bid}'
                    g.salto(rotulo_falso, 'jz')
                    aresta(bid, verdadeiro)
                    g.marcar(rotulo_falso)
                    aresta(bid, falso)
                    continue
                elif nome == 'para:condicao':
                    contador, limite, passo = args
                    avaliar(limite)  # o limite e reavaliado a cada passagem
                    g.bytes(b'\x50')  # push rax = limite
                    _carregar(g, locais[contador], windows)
                    g.bytes(b'\x59\x48\x39\xC8')  # pop rcx; cmp rax,rcx
                    falso = next(a.destino for a in cfgb.saidas if a.motivo == 'falso')
                    verdadeiro = next(a.destino for a in cfgb.saidas if a.motivo == 'verdadeiro')
                    rotulo_falso = f'ssa_falso_{bid}'
                    g.salto(rotulo_falso, 'jg' if passo > 0 else 'jl')
                    aresta(bid, verdadeiro)
                    g.marcar(rotulo_falso)
                    aresta(bid, falso)
                    continue
                elif nome not in ('pare', 'continue'):
                    raise ValueError(f'Instrucao SSA nao emitida: {nome}.')
            saidas = cfgb.saidas
            if len(saidas) == 1:
                aresta(bid, saidas[0].destino)
            elif not saidas:
                g.salto('ssa_saida_geral')
            else:
                raise ValueError(f'Bloco SSA sem emissao de condicao: {bid}.')
        g.marcar('ssa_saida_geral')
    return emissor
