#!/usr/bin/env python3
"""Benchmark real e reproduzível: compara resultados, tempo e tamanho (-O3/4/5/6).

Não infere ganhos por tamanho de arquivos. Compila antes de medir e
executa o mesmo programa repetidamente; mede a mediana das execuções.
"""
import argparse
import json
import os
from pathlib import Path
import platform
import statistics
import subprocess
import sys
import tempfile
import time

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))
from compilador.parser import analisar_programa
from backend import compilar


def medir(fonte, alvo, repeticoes=7):
    programa = analisar_programa(fonte)
    registros = []
    with tempfile.TemporaryDirectory(prefix='rs_benchmark_') as pasta:
        for nivel in (3, 4, 5, 6):
            executavel = Path(pasta) / ('teste_%s.exe' % nivel if alvo == 'windows'
                                         else 'teste_%s' % nivel)
            binario = compilar(programa, alvo, nivel=nivel)
            executavel.write_bytes(binario)
            if alvo == 'linux':
                executavel.chmod(0o755)
            tempos = []
            esperado = None
            for rodada in range(repeticoes + 1):  # primeira execução: aquecimento
                inicio = time.perf_counter_ns()
                resultado = subprocess.run([str(executavel)], input='', capture_output=True,
                                          text=True, encoding='utf-8', timeout=30)
                duracao = (time.perf_counter_ns() - inicio) / 1_000_000
                resultado_tupla = (resultado.returncode, resultado.stdout, resultado.stderr)
                if esperado is None:
                    esperado = resultado_tupla
                elif resultado_tupla != esperado:
                    raise AssertionError('Saída inconsistente nas repetições de -O %d' % nivel)
                if rodada:
                    tempos.append(duracao)
            registros.append({'nivel': nivel, 'bytes': len(binario),
                              'mediana_ms': round(statistics.median(tempos), 3),
                              'mínimo_ms': round(min(tempos), 3),
                              'máximo_ms': round(max(tempos), 3),
                              'tempos_ms': [round(t, 3) for t in tempos],
                              'resultado': esperado})
    if any(r['resultado'] != registros[0]['resultado'] for r in registros[1:]):
        raise AssertionError('Saídas ou códigos de retorno distintos entre O3/O4/O5/O6/O6')
    return {'alvo': alvo, 'sistema': platform.platform(), 'cpu': platform.processor(),
            'repeticoes': repeticoes, 'resultados': registros}


def main():
    p = argparse.ArgumentParser(description='Comparação nativa RS 0.16, O3/O4/O5/O6')
    p.add_argument('--fonte', type=Path, default=RAIZ / 'benchmarks' / 'lacos.rts')
    p.add_argument('--repeticoes', type=int, default=7)
    p.add_argument('--json', type=Path, help='salvar relatório com tempos individuais')
    a = p.parse_args()
    if not 2 <= a.repeticoes <= 1000:
        p.error('Use entre 2 e 1000 repeticoes.')
    if sys.platform == 'win32':
        alvo = 'windows'
    elif sys.platform == 'linux' and platform.machine().lower() in ('x86_64', 'amd64'):
        alvo = 'linux'
    else:
        p.error('Benchmark exige Windows ou Linux em x86-64.')
    res = medir(a.fonte.read_text(encoding='utf-8'), alvo, a.repeticoes)
    for r in res['resultados']:
        print(f"-O {r['nivel']}: {r['bytes']} bytes | mediana {r['mediana_ms']:.3f} ms "
              f"| min {r['mínimo_ms']:.3f} ms | max {r['máximo_ms']:.3f} ms")
    print('Saídas e códigos de retorno idênticos em todos os níveis.')
    if a.json:
        a.json.write_text(json.dumps(res, ensure_ascii=False, indent=2), encoding='utf-8')
        print('Relatório salvo em:', a.json)


if __name__ == '__main__':
    main()
