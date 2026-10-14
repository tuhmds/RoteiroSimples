"""Backend x86-64: a IR ainda e convertida para a AST legada (RS 0.9)."""
from compilador.ir import construir_ir, programa_para_backend
from compilador.estrategia import decidir_estrategia
from compilador.medicao_compilacao import etapa
from .x86_64 import montar_codigo, percorrer_instrucoes
from .windows_pe import montar_pe
from .linux_elf import montar_elf


def compilar(programa, alvo, otimizar=True, nivel=1, medidor=None):
    if alvo not in ('windows', 'linux'):
        raise ValueError('Alvo desconhecido: use windows ou linux.')
    with etapa(medidor, 'estrategia'):
        decisao = decidir_estrategia(programa, nivel, otimizar)
    if decisao.gerador == 'conservador':
        with etapa(medidor, 'emissao_nativa'):
            gerador, mensagens = montar_codigo(programa, alvo == 'windows')
    else:
        with etapa(medidor, 'ir_e_otimizacoes'):
            ir = construir_ir(programa, otimizar=otimizar, nivel=decisao.nivel_ir)
        with etapa(medidor, 'ponte_emissor'):
            legado = programa_para_backend(ir)
        if decisao.gerador == 'ssa' and ir.funcoes:
            from .funcoes_ssa import montar_funcoes_ssa
            gerador, mensagens = montar_funcoes_ssa(ir, alvo == 'windows', nivel, medidor=medidor)
        elif decisao.gerador == 'ssa':
            from .ssa_x86_64 import construir_backend_ssa, emissor_ssa
            ssa, aloc = construir_backend_ssa(ir, coalescer=(nivel >= 6), medidor=medidor)
            # Uma vaga extra na pilha serve de temporario para copias circulares.
            legado.variaveis = {f'slot{i}': i for i in range(aloc.vagas_pilha + 1)}
            with etapa(medidor, 'emissao_nativa'):
                gerador, mensagens = montar_codigo(
                    legado, alvo == 'windows', emissor_ssa(ir, ssa, aloc, otimizar_layout=(nivel >= 5),
                                                   otimizar_copias=(nivel >= 6), saltos_curtos=(nivel >= 6)))
        else:
            with etapa(medidor, 'emissao_nativa'):
                gerador, mensagens = montar_codigo(legado, alvo == 'windows')
    if decisao.gerador == 'ssa' and nivel >= 6:
        with etapa(medidor, 'compactacao_saltos'):
            gerador.compactar_saltos_ssa()
        if medidor is not None:
            for nome, valor in gerador.estatisticas_compactacao.items():
                medidor.contar('saltos_' + nome, valor)
    if medidor is not None:
        medidor.contar('bytes_codigo', len(gerador.codigo))
    with etapa(medidor, 'montagem_executavel'):
        return montar_pe(gerador, mensagens) if alvo == 'windows' else montar_elf(gerador, mensagens)
