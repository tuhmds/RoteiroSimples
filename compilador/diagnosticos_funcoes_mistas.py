"""Diagnósticos que identificam explicitamente o subconjunto representado."""
from .erros import ErroCompilacao
from .funcoes_mistas import construir_ir_funcoes
from .ir import formatar_ir
from .ssa_funcoes import construir_ssa_funcoes


def mostrar_analises_parciais(programa, decisao, op):
    if (op.mostrar_cfg or op.salvar_cfg or op.mostrar_fluxo or op.salvar_fluxo or
            op.mostrar_efeitos or op.salvar_efeitos or op.mostrar_memory_ssa or op.salvar_memory_ssa):
        raise ErroCompilacao(
            'O programa misto oferece IR/SSA/alocação somente das funções escalares elegíveis. '
            'CFG, fluxo e efeitos IR do programa completo ainda não estão disponíveis. '
            'Use --mostrar-estrategia ou --mostrar-efeitos-do-programa para a árvore completa.')
    if op.mostrar_alocacao and decisao.nivel_solicitado < 4:
        raise ErroCompilacao('Use -O 4 até -O 8 com --mostrar-alocacao.')
    grupo = construir_ir_funcoes(programa, (f.nome for f in decisao.funcoes if f.elegivel),
        otimizar=decisao.nivel_solicitado > 0, nivel=min(decisao.nivel_solicitado, 3))
    if op.mostrar_ir:
        print('IR parcial: início e funções conservadoras não representados.')
        for nome, funcao in grupo.funcoes.items():
            print(f'funcao {nome}: parametros {funcao.parametros}; retorno {funcao.retorno}')
            print(formatar_ir(funcao.programa))
    if op.mostrar_ssa or op.salvar_ssa or op.mostrar_copias_phi:
        ssa = construir_ssa_funcoes(grupo)
        if op.mostrar_ssa:
            print(ssa.formatar())
        if op.salvar_ssa:
            op.salvar_ssa.write_text(ssa.para_json(), encoding='utf-8')
            print(f'SSA parcial salva em: {op.salvar_ssa}')
        if op.mostrar_copias_phi:
            print(ssa.formatar_copias())
    if op.mostrar_alocacao:
        from backend.funcoes_mistas import preparar_funcoes_mistas
        _, _, plano = preparar_funcoes_mistas(programa, decisao, op.alvo == 'windows')
        print('Alocação parcial: início e funções conservadoras não representados.')
        print(plano.relatorio())
