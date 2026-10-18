"""Benchmark comparativo Linux: mremap real versus fallback forçado (ENOSYS)."""
import argparse
import json
from pathlib import Path
import platform
import random
import statistics
import subprocess
import sys
import tempfile
import time

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))
from backend import compilar
from compilador.modulos import carregar_fontes
from compilador.parser import analisar_programa

MREMAP = bytes.fromhex('B8 19 00 00 00 0F 05')
FALLBACK = bytes.fromhex('B8 FF FF FF FF 0F 05')


def medir(fonte, repeticoes=9):
    if sys.platform != 'linux' or platform.machine() not in ('x86_64', 'AMD64'):
        raise ValueError('Este benchmark exige Linux x86-64.')
    if repeticoes < 3:
        raise ValueError('Use pelo menos três repetições.')
    binario = compilar(analisar_programa(carregar_fontes(fonte).texto),
                      'linux', nivel=8)
    if binario.count(MREMAP) != 1:
        raise AssertionError('Assinatura da syscall mremap não é única.')
    versoes = {'mremap': binario, 'fallback': binario.replace(MREMAP, FALLBACK, 1)}
    amostras = {nome: [] for nome in versoes}
    rng = random.Random(420110)
    esperado = None
    with tempfile.TemporaryDirectory() as temp:
        caminhos = {}
        for nome, conteudo in versoes.items():
            caminho = Path(temp) / nome
            caminho.write_bytes(conteudo)
            caminho.chmod(0o755)
            caminhos[nome] = caminho
        for rodada in range(repeticoes + 1):
            ordem = list(versoes)
            rng.shuffle(ordem)
            for nome in ordem:
                inicio = time.perf_counter_ns()
                resultado = subprocess.run([str(caminhos[nome])], cwd=temp,
                                           capture_output=True, timeout=30)
                ms = (time.perf_counter_ns() - inicio) / 1_000_000
                atual = (resultado.returncode, resultado.stdout, resultado.stderr)
                if resultado.returncode:
                    raise AssertionError('Falha na variante ' + nome)
                if esperado is None:
                    esperado = atual
                elif esperado != atual:
                    raise AssertionError('Resultados distintos entre variantes.')
                if rodada:
                    amostras[nome].append(round(ms, 3))
    medianas = {nome: round(statistics.median(tempos), 3)
                for nome, tempos in amostras.items()}
    return {'metodo': 'processos completos, ordem intercalada, um aquecimento',
            'alvo': 'linux', 'repeticoes': repeticoes, 'medianas_ms': medianas,
            'tempos_ms': amostras, 'razao_mremap_fallback':
            round(medianas['mremap']/medianas['fallback'], 4)
            if medianas['fallback'] else None}


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--fonte', type=Path,
                   default=RAIZ / 'benchmarks/realocacao_rs_mem.rts')
    p.add_argument('--repeticoes', type=int, default=9)
    p.add_argument('--json', type=Path)
    a = p.parse_args()
    resultado = medir(a.fonte, a.repeticoes)
    print(json.dumps(resultado, indent=2, ensure_ascii=False))
    if a.json:
        a.json.parent.mkdir(parents=True, exist_ok=True)
        a.json.write_text(json.dumps(resultado, indent=2, ensure_ascii=False) + '\n',
                          encoding='utf-8')


if __name__ == '__main__':
    main()
