#!/usr/bin/env python3
"""Benchmark nativo O0–O8 com estratégia efetiva, hashes e tempos individuais.

Não infere ganhos por tamanho de arquivos. Compila antes de medir e
executa o mesmo programa repetidamente; mede a mediana das execuções.
"""
import argparse
import hashlib
import json
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
from compilador.estrategia import decidir_estrategia
from compilador.modulos import carregar_fontes


def medir(fonte, alvo, repeticoes=7, niveis=tuple(range(9))):
    if repeticoes < 2 or not niveis or any(not 0 <= nivel <= 8 for nivel in niveis):
        raise ValueError('Use pelo menos duas repetições e níveis entre 0 e 8.')
    programa = analisar_programa(fonte)
    registros = []
    binarios = {}
    arquivos_esperados = None
    with tempfile.TemporaryDirectory(prefix='rs_benchmark_') as pasta:
        for nivel in niveis:
            executavel = Path(pasta) / ('teste_%s.exe' % nivel if alvo == 'windows'
                                         else 'teste_%s' % nivel)
            estrategia = decidir_estrategia(programa, nivel, nivel > 0)
            inicio_compilacao = time.perf_counter_ns()
            binario = compilar(programa, alvo, nivel=nivel, otimizar=nivel > 0)
            compilacao_ms = (time.perf_counter_ns() - inicio_compilacao) / 1_000_000
            resumo_binario = hashlib.sha256(binario).hexdigest()
            executavel.write_bytes(binario)
            if alvo == 'linux':
                executavel.chmod(0o755)
            tempos = []
            esperado = None
            for rodada in range(repeticoes + 1):  # primeira execução: aquecimento
                # Preparação e leitura de arquivos ficam fora do cronômetro.
                # Cada execução recebe diretório vazio, sem estado da anterior.
                with tempfile.TemporaryDirectory(dir=pasta, prefix='rodada_') as trabalho:
                    inicio = time.perf_counter_ns()
                    resultado = subprocess.run([str(executavel)], cwd=trabalho, input='', capture_output=True,
                                              text=True, encoding='utf-8', timeout=30)
                    duracao = (time.perf_counter_ns() - inicio) / 1_000_000
                    arquivos = {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                                for p in Path(trabalho).iterdir() if p.is_file()}
                if resultado.returncode:
                    raise AssertionError(f'Benchmark encerrou com erro em O{nivel}: {resultado.returncode}; {resultado.stderr or resultado.stdout}')
                if arquivos_esperados is None:
                    arquivos_esperados = arquivos
                elif arquivos != arquivos_esperados:
                    raise AssertionError('Arquivos divergentes entre execuções do benchmark.')
                resultado_tupla = (resultado.returncode, resultado.stdout, resultado.stderr)
                if esperado is None:
                    esperado = resultado_tupla
                elif resultado_tupla != esperado:
                    raise AssertionError('Saída inconsistente nas repetições de -O %d' % nivel)
                if rodada:
                    tempos.append(duracao)
            registros.append({'nivel': nivel, 'bytes': len(binario),
                              'gerador': estrategia.gerador, 'nivel_ir': estrategia.nivel_ir,
                              'otimiza': estrategia.otimiza, 'motivos': estrategia.motivos,
                              'sha256': resumo_binario, 'mesmo_binario_que': binarios.get(resumo_binario),
                              'compilacao_ms': round(compilacao_ms, 3),
                              'mediana_ms': round(statistics.median(tempos), 3),
                              'mínimo_ms': round(min(tempos), 3),
                              'máximo_ms': round(max(tempos), 3),
                              'tempos_ms': [round(t, 3) for t in tempos],
                              'resultado': esperado})
            binarios.setdefault(resumo_binario, nivel)
    if any(r['resultado'] != registros[0]['resultado'] for r in registros[1:]):
        raise AssertionError('Saídas ou códigos de retorno distintos entre os níveis medidos.')
    return {'versao': 'RS 0.42J', 'alvo': alvo, 'sistema': platform.platform(), 'cpu': platform.processor(),
            'python': platform.python_version(), 'fonte_sha256': hashlib.sha256(fonte.encode('utf-8')).hexdigest(),
            'medida': 'tempo do processo nativo, incluindo sua inicialização; compilação separada',
            'arquivos_sha256': arquivos_esperados,
            'repeticoes': repeticoes, 'resultados': registros}


def main():
    p = argparse.ArgumentParser(description='Comparação nativa RS 0.42J, O0–O8 e gerador efetivo')
    p.add_argument('--fonte', type=Path, default=RAIZ / 'benchmarks' / 'lacos.rts')
    p.add_argument('--repeticoes', type=int, default=7)
    p.add_argument('--niveis', default='0,1,2,3,4,5,6,7,8')
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
    try:
        niveis = tuple(int(nivel) for nivel in a.niveis.split(','))
        res = medir(carregar_fontes(a.fonte).texto, alvo, a.repeticoes, niveis)
    except (ValueError, OSError, AssertionError) as erro:
        p.error(str(erro))
    for r in res['resultados']:
        print(f"-O {r['nivel']}: {r['gerador']} (IR {r['nivel_ir']}) | {r['bytes']} bytes | mediana {r['mediana_ms']:.3f} ms "
              f"| min {r['mínimo_ms']:.3f} ms | max {r['máximo_ms']:.3f} ms")
    print('Saídas, códigos de retorno e arquivos idênticos nos níveis medidos.')
    if a.json:
        a.json.write_text(json.dumps(res, ensure_ascii=False, indent=2), encoding='utf-8')
        print('Relatório salvo em:', a.json)


if __name__ == '__main__':
    main()
