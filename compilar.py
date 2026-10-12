#!/usr/bin/env python3
"""Compilador RS 0.41.5: .rts -> código de máquina AMD64 ELF64/PE32+ sem ferramentas externas."""
import argparse
import os
import re
import sys
from pathlib import Path
from compilador.erros import ErroCompilacao
from compilador.parser import analisar_programa
from compilador.modulos import carregar_fontes, apresentar_erro
from backend import compilar
from compilador.estrategia import decidir_estrategia, descrever_estrategia
from compilador.cobertura_intermediaria import analisar_cobertura, formatar_cobertura


def main(argv=None):
    # Garante UTF-8 mesmo quando a saída é capturada ou redirecionada no
    # Windows, evitando depender da codificação regional do computador.
    for canal in (sys.stdout, sys.stderr):
        if canal is not None and hasattr(canal, 'reconfigure'):
            canal.reconfigure(encoding='utf-8')
    parser = argparse.ArgumentParser(description='Compilador RoteiroSimples (RS) 0.41.5')
    parser.add_argument('fonte', type=Path, help='arquivo .rts em UTF-8')
    parser.add_argument('--mostrar-modulos', action='store_true', help='lista os módulos e a ordem de importação')
    parser.add_argument('--mostrar-estrategia', action='store_true', help='explica quais otimizações serão aplicadas de fato')
    parser.add_argument('--mostrar-cobertura-intermediaria', action='store_true',
                        help='mostra instruções e expressões cobertas pela IR e motivos do gerador conservador')
    parser.add_argument('--alvo', choices=['windows', 'linux'], default='windows')
    parser.add_argument('-o', '--saida', type=Path, help='arquivo executável de saída')
    parser.add_argument('-O', '--otimizacao', choices=['0', '1', '2', '3', '4', '5', '6', '7', '8'], default='1', help='otimização (0 = sem, 1 = constantes, 2 = propagação local, 3 = SSA, 4 = SSA nativa, 5 = layout, 6 = coalescencia e saltos curtos, 7 = memoria versionada local, 8 = propagacao entre blocos)' )
    parser.add_argument('--mostrar-representacao-intermediaria', '--mostrar-ir', dest='mostrar_ir', action='store_true', help='mostra a representacao intermediaria tipada')
    parser.add_argument('--mostrar-efeitos', action='store_true', help='exibe leituras/escritas de memoria, E/S e falhas por instrucao')
    parser.add_argument('--mostrar-efeitos-do-programa', action='store_true',
                        help='exibe efeitos e propriedade de todos os comandos, inclusive sem IR/SSA')
    parser.add_argument('--salvar-efeitos-do-programa', type=Path,
                        help='salva analise completa da arvore sintatica em JSON')
    parser.add_argument('--mostrar-memoria-versionada', '--mostrar-memory-ssa', dest='mostrar_memory_ssa', action='store_true', help='exibe versoes de memoria, dependencias e nos de juncao')
    parser.add_argument('--salvar-memoria-versionada', '--salvar-memory-ssa', dest='salvar_memory_ssa', type=Path, help='salva a analise de memoria versionada em JSON')
    parser.add_argument('--salvar-efeitos', type=Path, help='salva a analise de efeitos em JSON')
    parser.add_argument('--mostrar-arvore-sintatica', '--mostrar-ast', dest='mostrar_ast', action='store_true', help='mostra a arvore sintatica com linha e coluna')
    parser.add_argument('--mostrar-fluxo', action='store_true', help='mostra análise de dados por bloco')
    parser.add_argument('--salvar-fluxo', type=Path, help='salva análise em JSON')
    parser.add_argument('--mostrar-alocacao', action='store_true', help='mostra registradores e spills planejados pelo backend -O 4/5')
    parser.add_argument('--mostrar-copias-juncao', '--mostrar-copias-phi', dest='mostrar_copias_phi', action='store_true', help='exibe o plano de copias paralelas de cada aresta phi (nao emitidas)')
    parser.add_argument('--mostrar-atribuicao-unica', '--mostrar-ssa', dest='mostrar_ssa', action='store_true', help='mostra atribuicoes unicas e nos de juncao')
    parser.add_argument('--salvar-atribuicao-unica', '--salvar-ssa', dest='salvar_ssa', type=Path, help='salva a analise de atribuicoes unicas em JSON')
    parser.add_argument('--mostrar-grafo-fluxo', '--mostrar-cfg', dest='mostrar_cfg', action='store_true', help='exibe grafo de controle em texto')
    parser.add_argument('--salvar-grafo-fluxo', '--salvar-cfg', dest='salvar_cfg', type=Path, help='salva grafo de controle em formato DOT')
    argumentos = sys.argv[1:] if argv is None else argv
    op = parser.parse_args(argumentos)
    saida = op.saida or op.fonte.with_suffix('.exe' if op.alvo == 'windows' else '')
    fonte_texto = ''
    fontes = None
    try:
        fontes = carregar_fontes(op.fonte)
        from compilador.resultados_genericos import preparar_resultados_genericos
        fontes = preparar_resultados_genericos(fontes)
        fonte_texto = fontes.texto
        programa = analisar_programa(fonte_texto)
        if op.mostrar_modulos:
            for arquivo in fontes.arquivos:
                print(f'Módulo: {arquivo}')
        nivel = int(op.otimizacao)
        decisao = decidir_estrategia(programa, nivel, otimizar=nivel > 0)
        if op.mostrar_cobertura_intermediaria:
            print(formatar_cobertura(analisar_cobertura(programa), decisao))
        if op.mostrar_efeitos_do_programa or op.salvar_efeitos_do_programa:
            from compilador.efeitos_programa import (
                formatar_efeitos_programa, efeitos_programa_para_json,
            )
            if op.mostrar_efeitos_do_programa:
                print(formatar_efeitos_programa(programa))
            if op.salvar_efeitos_do_programa:
                op.salvar_efeitos_do_programa.write_text(
                    efeitos_programa_para_json(programa), encoding='utf-8')
                print(f'Efeitos completos salvos em: {op.salvar_efeitos_do_programa}')
        if op.mostrar_estrategia:
            print(descrever_estrategia(decisao))
        analises_ir = (
            op.mostrar_ir or op.mostrar_cfg or op.salvar_cfg
            or op.mostrar_fluxo or op.salvar_fluxo
            or op.mostrar_ssa or op.salvar_ssa
            or op.mostrar_copias_phi or op.mostrar_alocacao
            or op.mostrar_memory_ssa or op.salvar_memory_ssa
            or op.mostrar_efeitos or op.salvar_efeitos
        )
        if analises_ir and decisao.gerador == 'conservador':
            raise ErroCompilacao(
                'A análise solicitada requer a representação intermediária, '
                'mas este programa usa o gerador conservador: '
                + '; '.join(decisao.motivos)
                + '. Compile normalmente ou utilize '
                  '--mostrar-cobertura-intermediaria para examinar os limites.')
        if op.mostrar_ast:
            from compilador.ast import formatar_ast
            print(formatar_ast(programa))
        tem_listas = any(isinstance(t, tuple) and t[0] in ('lista', 'texto') for t in programa.tipos.values())
        if tem_listas and (op.mostrar_cfg or op.salvar_cfg or op.mostrar_fluxo
                or op.salvar_fluxo or op.mostrar_ssa or op.salvar_ssa
                or op.mostrar_copias_phi or op.mostrar_alocacao):
            raise ErroCompilacao('A análise CFG/SSA com listas ou textos ainda não está disponível nesta versão.')
        if op.mostrar_memory_ssa or op.salvar_memory_ssa:
            from compilador.ir import construir_ir
            from compilador.memory_ssa import construir_memory_ssa
            mssa = construir_memory_ssa(construir_ir(programa, otimizar=nivel > 0, nivel=nivel))
            if op.mostrar_memory_ssa:
                print(mssa.formatar_ptbr() if '--mostrar-memoria-versionada' in argumentos else mssa.formatar())
            if op.salvar_memory_ssa:
                op.salvar_memory_ssa.write_text(mssa.para_json(), encoding='utf-8')
                print(f'Análise de memória versionada salva em: {op.salvar_memory_ssa}')
        if op.mostrar_efeitos or op.salvar_efeitos:
            from compilador.ir import construir_ir
            from compilador.efeitos import formatar_efeitos, efeitos_para_json
            ir_efeitos = construir_ir(programa, otimizar=nivel > 0, nivel=nivel)
            if op.mostrar_efeitos:
                print(formatar_efeitos(ir_efeitos))
            if op.salvar_efeitos:
                op.salvar_efeitos.write_text(efeitos_para_json(ir_efeitos), encoding='utf-8')
                print(f'Efeitos salvos em: {op.salvar_efeitos}')
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
                print(f'Grafo de fluxo de controle salvo em: {op.salvar_cfg}')
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
        mensagem = str(erro)
        origem = None
        coluna = None
        if fontes is not None and len(fontes.arquivos) > 1:
            mensagem, origem, coluna = apresentar_erro(erro, fontes.origens)
        print(f'Erro: {mensagem}', file=sys.stderr)
        if origem is not None and coluna is not None:
            print('    ' + origem.texto, file=sys.stderr)
            print('    ' + ' '*(coluna-1) + '^', file=sys.stderr)
        detalhe = re.search(r'Linha (\d+), coluna (\d+):', str(erro))
        if detalhe and fonte_texto and origem is None:
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
