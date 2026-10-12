"""Microbenchmark reprodutivel de entrada via pipe (nao mede teclado humano)."""
import argparse
from pathlib import Path
import statistics
import subprocess
import sys
import tempfile
import time

RAIZ = Path(__file__).resolve().parents[1]


def medir(raiz, quantidade=30000, repeticoes=9):
    fonte = f'''inicio {{
        seja i = 0
        seja valor = 0
        seja total = 0
        enquanto i < {quantidade} {{
            leia(valor)
            total = total + valor
            i = i + 1
        }}
        escreva(total)
    }}'''
    with tempfile.TemporaryDirectory() as pasta:
        p = Path(pasta)
        origem = p / 'benchmark.rts'
        exe = p / ('benchmark.exe' if sys.platform == 'win32' else 'benchmark')
        origem.write_text(fonte, encoding='utf-8')
        alvo = 'windows' if sys.platform == 'win32' else 'linux'
        compilacao = subprocess.run([sys.executable, str(raiz / 'compilar.py'),
                                     str(origem), '--alvo', alvo, '-O', '6', '-o', str(exe)],
                                    capture_output=True, text=True, timeout=20)
        if compilacao.returncode:
            raise RuntimeError(f'Falha ao compilar em {raiz}: {compilacao.stderr}')
        entrada = b'2\n' * quantidade
        tempos = []
        for i in range(repeticoes + 1):
            inicio = time.perf_counter()
            r = subprocess.run([str(exe)], input=entrada, capture_output=True, timeout=20)
            duracao_ms = (time.perf_counter() - inicio) * 1000
            if (r.returncode, r.stdout) != (0, f'{2 * quantidade}\n'.encode()):
                raise RuntimeError(f'Resultado incorreto: codigo {r.returncode}, saida {r.stdout!r}')
            if i:  # primeira medicao = aquecimento
                tempos.append(duracao_ms)
        return statistics.median(tempos), exe.stat().st_size


def main():
    p = argparse.ArgumentParser(description='Mede leia(int) pelo stdin em pipe; nao mede teclado real.')
    p.add_argument('--linhas', type=int, default=30000)
    p.add_argument('--repeticoes', type=int, default=9)
    p.add_argument('--comparar-com', type=Path, help='pasta do compilador RS 0.18, opcional')
    a = p.parse_args()
    if a.linhas < 1 or a.repeticoes < 2:
        p.error('linhas deve ser >= 1 e repeticoes >= 2')
    if a.comparar_com:
        ms, tam = medir(a.comparar_com.resolve(), a.linhas, a.repeticoes)
        print(f'Anterior: mediana={ms:.3f}ms, executavel={tam} bytes')
    ms, tam = medir(RAIZ, a.linhas, a.repeticoes)
    print(f'RS 0.19: mediana={ms:.3f}ms, executavel={tam} bytes')


if __name__ == '__main__':
    main()
