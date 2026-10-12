"""Backend x86-64: a IR ainda e convertida para a AST legada (RS 0.9)."""
from compilador.ir import construir_ir, programa_para_backend
from .x86_64 import montar_codigo, percorrer_instrucoes
from .windows_pe import montar_pe
from .linux_elf import montar_elf


def compilar(programa, alvo, otimizar=True, nivel=1):
    if alvo not in ('windows', 'linux'):
        raise ValueError('Alvo desconhecido: use windows ou linux.')
    # Funções e variáveis locais de blocos usam o backend conservador.
    # Os níveis -O existentes permanecem aceitos, sem aplicar análises
    # que ainda não modelam chamadas ou tempos de vida dos novos escopos.
    def contem_copia_composta(instrucoes):
        for instrucao in instrucoes:
            if instrucao[0] == 'copie_composto':
                return True
            if instrucao[0] == 'se' and (contem_copia_composta(instrucao[2]) or contem_copia_composta(instrucao[3])):
                return True
            if instrucao[0] == 'enquanto' and contem_copia_composta(instrucao[2]):
                return True
            if instrucao[0] == 'para' and contem_copia_composta(instrucao[5]):
                return True
        return False

    if (any(op[0] in ('grave_arquivo', 'carregue_arquivo')
            for op in percorrer_instrucoes(programa.instrucoes))
            or getattr(programa, 'funcoes', None) or getattr(programa, 'registros', None)
            or getattr(programa, 'escopos_locais', False) or contem_copia_composta(programa.instrucoes)
            or any(isinstance(t, tuple) and t[0] == 'lista_dinamica' for t in programa.tipos.values())):
        gerador, mensagens = montar_codigo(programa, alvo == 'windows')
        return montar_pe(gerador, mensagens) if alvo == 'windows' else montar_elf(gerador, mensagens)
    ir = construir_ir(programa, otimizar=otimizar, nivel=(nivel if nivel >= 7 else min(nivel, 3)))
    legado = programa_para_backend(ir)
    tem_listas = any(isinstance(t, tuple) and t[0] in ('lista', 'texto') for t in programa.tipos.values())
    if nivel >= 4 and otimizar and not tem_listas:
        from .ssa_x86_64 import construir_backend_ssa, emissor_ssa
        ssa, aloc = construir_backend_ssa(ir, coalescer=(nivel >= 6))
        # Uma vaga extra na pilha serve de temporario para copias circulares.
        legado.variaveis = {f'slot{i}': i for i in range(aloc.vagas_pilha + 1)}
        gerador, mensagens = montar_codigo(
            legado, alvo == 'windows', emissor_ssa(ir, ssa, aloc, otimizar_layout=(nivel >= 5),
                                           otimizar_copias=(nivel >= 6), saltos_curtos=(nivel >= 6)))
    else:
        gerador, mensagens = montar_codigo(legado, alvo == 'windows')
    if nivel >= 6 and otimizar and not tem_listas:
        gerador.compactar_saltos_ssa()
    return montar_pe(gerador, mensagens) if alvo == 'windows' else montar_elf(gerador, mensagens)
