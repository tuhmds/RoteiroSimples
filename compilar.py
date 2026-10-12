#!/usr/bin/env python3
"""Compilador RS 0.17: .rts -> código de máquina AMD64 ELF64/PE32+ sem ferramentas externas."""
import argparse
import os
import re
import sys
from pathlib import Path
from compilador.erros import ErroCompilacao
from compilador.parser import analisar_programa
from backend import compilar


def main(argv=None):
    parser = argparse.ArgumentParser(description='Compilador RoteiroSimples (RS) 0.17')
    parser.add_argument('fonte', type=Path, help='arquivo .rts em UTF-8')
    parser.add_argument('--alvo', choices=['windows', 'linux'], default='windows')
    parser.add_argument('-o', '--saida', type=Path, help='arquivo executável de saída')
    parser.add_argument('-O', '--otimizacao', choices=['0', '1', '2', '3', '4', '5', '6'], default='1', help='otimização (0 = sem, 1 = constantes, 2 = propagação local, 3 = SSA, 4 = SSA nativa, 5 = layout, 6 = coalescencia e saltos curtos)' )
    parser.add_argument('--mostrar-ir', action='store_true', help='mostra a IR tipada antes de gerar código')
    parser.add_argument('--mostrar-ast', action='store_true', help='mostra a AST com linha e coluna')
    parser.add_argument('--mostrar-fluxo', action='store_true', help='mostra análise de dados por bloco')
    parser.add_argument('--salvar-fluxo', type=Path, help='salva análise em JSON')
    parser.add_argument('--mostrar-alocacao', action='store_true', help='mostra registradores e spills planejados pelo backend -O 4/5')
    parser.add_argument('--mostrar-copias-phi', action='store_true', help='exibe o plano de copias paralelas de cada aresta phi (nao emitidas)')
    parser.add_argument('--mostrar-ssa', action='store_true', help='mostra renomeação SSA e nós phi')
    parser.add_argument('--salvar-ssa', type=Path, help='salva SSA tipada em arquivo JSON')
    parser.add_argument('--mostrar-cfg', action='store_true', help='exibe grafo de controle em texto')
    parser.add_argument('--salvar-cfg', type=Path, help='salva grafo de controle em formato DOT')
    op = parser.parse_args(argv)
    saida = op.saida or op.fonte.with_suffix('.exe' if op.alvo == 'windows' else '')
    fonte_texto = ''
    try:
        fonte_texto = op.fonte.read_text(encoding='utf-8-sig')
        programa = analisar_programa(fonte_texto)
        if op.mostrar_ast:
            from compilador.ast import formatar_ast
            print(formatar_ast(programa))
        nivel = int(op.otimizacao)
        tem_listas = any(isinstance(t, tuple) and t[0] == 'lista' for t in programa.tipos.values())
        if tem_listas and (op.mostrar_cfg or op.salvar_cfg or op.mostrar_fluxo
                or op.salvar_fluxo or op.mostrar_ssa or op.salvar_ssa
                or op.mostrar_copias_phi or op.mostrar_alocacao):
            raise ErroCompilacao('A análise CFG/SSA com listas ainda não está disponível nesta versão.')
        if op.mostrar_ir:
            from compilador.ir import construir_ir, formatar_ir
            print(formatar_ir(construir_ir(programa, otimizar=nivel > 0, nivel=nivel)))
        if (op.mostrar_cfg or op.salvar_cfg or op.mostrar_fluxo or op.salvar_fluxo
                or op.mostrar_ssa or op.salvar_ssa or op.mostrar_copias_phi
                or op.mostrar_alocacao):
            from compilador.ir import construir_ir
            from compilador.cfg import construir_cfg
            grafo = construir_cfg(construir_ir(programa, otimizar=nivel > 0, nivel=nivel))
            if op.mostrar_ssa or op.salvar_ssa or op.mostrar_copias_phi:
                from compilador.ssa import construir_ssa
                ssa = construir_ssa(grafo)
                if op.mostrar_copias_phi:
                    from compilador.ssa_baixamento import formatar_copias_phi
                    # Exibe o plano do CFG antes de O3 eliminar atribuicoes mortas.
                    from compilador.ssa import construir_ssa as montar_ssa
                    cfg_original = construir_cfg(construir_ir(
                        programa, otimizar=nivel > 0, nivel=min(nivel, 2)))
                    print(formatar_copias_phi(montar_ssa(cfg_original)))
                if op.mostrar_ssa:
                    print(ssa.formatar())
                if op.salvar_ssa:
                    op.salvar_ssa.write_text(ssa.para_json(), encoding='utf-8')
                    print(f'SSA salva em: {op.salvar_ssa}')
            if op.mostrar_fluxo or op.salvar_fluxo:
                from compilador.fluxo_dados import analisar_fluxo
                analise = analisar_fluxo(grafo)
                if op.mostrar_fluxo:
                    print(analise.formatar())
                if op.salvar_fluxo:
                    op.salvar_fluxo.write_text(analise.para_json(), encoding='utf-8')
                    print(f'Fluxo salvo em: {op.salvar_fluxo}')
            if op.mostrar_cfg:
                print(grafo.formatar())
            if op.salvar_cfg:
                op.salvar_cfg.write_text(grafo.para_dot(), encoding='utf-8')
                print(f'CFG salvo em: {op.salvar_cfg}')
        if op.mostrar_alocacao:
            if nivel not in (4, 5, 6):
                raise ErroCompilacao('Use -O 4, -O 5 ou -O 6 com --mostrar-alocacao.')
            from compilador.ir import construir_ir
            from backend.ssa_x86_64 import construir_backend_ssa
            _, aloc = construir_backend_ssa(construir_ir(programa, nivel=3), coalescer=(nivel >= 6))
            print(aloc.relatorio())
        binario = compilar(programa, op.alvo, otimizar=nivel > 0, nivel=nivel)
        saida.write_bytes(binario)
        if op.alvo == 'linux':
            os.chmod(saida, saida.stat().st_mode | 0o111)
    except (ErroCompilacao, OSError, ValueError, OverflowError) as erro:
        print(f'Erro: {erro}', file=sys.stderr)
        detalhe = re.search(r'Linha (\d+), coluna (\d+):', str(erro))
        if detalhe and fonte_texto:
            linha, coluna = map(int, detalhe.groups())
            linhas = fonte_texto.splitlines()
            if 1 <= linha <= len(linhas):
                print('    ' + linhas[linha-1], file=sys.stderr)
                print('    ' + ' '*(coluna-1) + '^', file=sys.stderr)
        return 1
    print(f'Compilado: {saida} ({len(binario)} bytes, {op.alvo}).')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
