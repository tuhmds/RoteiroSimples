#!/usr/bin/env python3
"""Compilador RS 0.8: .rts -> código de máquina AMD64 ELF64/PE32+ sem ferramentas externas."""
import argparse
import os
import sys
from pathlib import Path
from sintaxe import ErroCompilacao, analisar_programa
from codigo_nativo import compilar


def main(argv=None):
    parser = argparse.ArgumentParser(description='Compilador RoteiroSimples (RS) 0.8')
    parser.add_argument('fonte', type=Path, help='arquivo .rts em UTF-8')
    parser.add_argument('--alvo', choices=['windows', 'linux'], default='windows')
    parser.add_argument('-o', '--saida', type=Path, help='arquivo executável de saída')
    parser.add_argument('-O', '--otimizacao', choices=['0', '1'], default='1', help='nível de otimização (0 = desativada, 1 = constantes)')
    parser.add_argument('--mostrar-ir', action='store_true', help='mostra a IR tipada antes de gerar código')
    op = parser.parse_args(argv)
    saida = op.saida or op.fonte.with_suffix('.exe' if op.alvo == 'windows' else '')
    try:
        programa = analisar_programa(op.fonte.read_text(encoding='utf-8-sig'))
        if op.mostrar_ir:
            from ir import construir_ir, formatar_ir
            print(formatar_ir(construir_ir(programa, otimizar=op.otimizacao == '1')))
        binario = compilar(programa, op.alvo, otimizar=op.otimizacao == '1')
        saida.write_bytes(binario)
        if op.alvo == 'linux':
            os.chmod(saida, saida.stat().st_mode | 0o111)
    except (ErroCompilacao, OSError, ValueError, OverflowError) as erro:
        print(f'Erro: {erro}', file=sys.stderr)
        return 1
    print(f'Compilado: {saida} ({len(binario)} bytes, {op.alvo}).')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
