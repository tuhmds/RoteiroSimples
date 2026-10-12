"""Backend x86-64: a IR ainda e convertida para a AST legada (RS 0.9)."""
from compilador.ir import construir_ir, programa_para_backend
from .x86_64 import montar_codigo
from .windows_pe import montar_pe
from .linux_elf import montar_elf


def compilar(programa, alvo, otimizar=True, nivel=1):
    if alvo not in ('windows', 'linux'):
        raise ValueError('Alvo desconhecido: use windows ou linux.')
    ir = construir_ir(programa, otimizar=otimizar, nivel=min(nivel, 3))
    legado = programa_para_backend(ir)
    if nivel >= 4 and otimizar:
        from .ssa_x86_64 import construir_backend_ssa, emissor_ssa
        ssa, aloc = construir_backend_ssa(ir)
        # Uma vaga extra na pilha serve de temporario para copias circulares.
        legado.variaveis = {f'slot{i}': i for i in range(aloc.vagas_pilha + 1)}
        gerador, mensagens = montar_codigo(
            legado, alvo == 'windows', emissor_ssa(ir, ssa, aloc))
    else:
        gerador, mensagens = montar_codigo(legado, alvo == 'windows')
    return montar_pe(gerador, mensagens) if alvo == 'windows' else montar_elf(gerador, mensagens)
