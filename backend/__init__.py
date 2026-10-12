"""Backend x86-64: a IR ainda e convertida para a AST legada (RS 0.9)."""
from compilador.ir import construir_ir, programa_para_backend
from .x86_64 import montar_codigo
from .windows_pe import montar_pe
from .linux_elf import montar_elf


def compilar(programa, alvo, otimizar=True):
    if alvo not in ('windows', 'linux'):
        raise ValueError('Alvo desconhecido: use windows ou linux.')
    ir = construir_ir(programa, otimizar=otimizar)
    legado = programa_para_backend(ir)
    gerador, mensagens = montar_codigo(legado, alvo == 'windows')
    return montar_pe(gerador, mensagens) if alvo == 'windows' else montar_elf(gerador, mensagens)
