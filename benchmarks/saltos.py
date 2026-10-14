"""Medicao isolada da compactacao; montagem fica fora do cronometro."""
import argparse
import hashlib
import json
from pathlib import Path
import platform
import random
import statistics
import time

from backend.x86_64 import Gerador


def montar(quantidade):
    if not 1 <= quantidade <= 100000:
        raise ValueError('Use 1 a 100000 saltos.')
    gerador = Gerador()
    gerador.ativar_saltos_curtos_ssa()
    for indice in range(quantidade):
        nome = f'ssa_proximo_{indice}'
        gerador.salto(nome)
        gerador.bytes(b'\x90')
        gerador.marcar(nome)
    return gerador


def medir_saltos(tamanhos=(128, 256, 512, 1024, 2048), repeticoes=5,
                 comparar_legado=False, semente=424201):
    if (not tamanhos or len(set(tamanhos)) != len(tamanhos)
            or any(not 1 <= n <= 100000 for n in tamanhos) or not 2 <= repeticoes <= 31):
        raise ValueError('Use tamanhos distintos e 2 a 31 repeticoes.')
    metodos = {'atual': lambda g: g.compactar_saltos_ssa()}
    if comparar_legado:
        from testes.fixtures.compactacao_rs042o import compactar_antes
        metodos['referencia_rs042o'] = compactar_antes
    registros = {(tamanho, nome): {'saltos': tamanho, 'metodo': nome, 'amostras_ms': []}
                 for tamanho in tamanhos for nome in metodos}
    aleatorio = random.Random(semente)
    ordens = []
    for rodada in range(repeticoes + 1):
        ordem = list(registros)
        aleatorio.shuffle(ordem)
        ordens.append(ordem)
        for tamanho, nome in ordem:
            g = montar(tamanho)
            inicio = time.perf_counter_ns()
            compactados = metodos[nome](g)
            decorrido = (time.perf_counter_ns() - inicio) / 1e6
            esperado = b'\xeb\x01\x90' * tamanho
            if compactados != tamanho or bytes(g.codigo) != esperado or g.pendencias:
                raise AssertionError('Compactacao divergiu do oraculo de bytes/destinos.')
            registro = registros[tamanho, nome]
            registro.update({'sha256': hashlib.sha256(g.codigo).hexdigest(), 'bytes': len(g.codigo)})
            if nome == 'atual':
                registro['contadores'] = dict(g.estatisticas_compactacao)
            if rodada:
                registro['amostras_ms'].append(decorrido)
    for registro in registros.values():
        amostras = registro['amostras_ms']
        registro.update({'mediana_ms': statistics.median(amostras), 'minimo_ms': min(amostras),
                         'maximo_ms': max(amostras)})
    return {'versao': 'RS 0.42P', 'sistema': platform.platform(), 'python': platform.python_version(),
            'semente': semente, 'repeticoes': repeticoes, 'ordens': ordens,
            'cenario': 'saltos locais consecutivos para frente, todos encurtaveis; microbenchmark sintetico',
            'medida': 'somente compactacao; montagem, validacao e hash fora do cronometro',
            'referencia_commit': 'e79d41c8e75a13494f8a12ac18d2b0a57e3f15eb' if comparar_legado else None,
            'resultados': list(registros.values())}


def main():
    parser = argparse.ArgumentParser(description='Crescimento da compactacao de saltos RS 0.42P')
    parser.add_argument('--tamanhos', default='128,256,512,1024,2048')
    parser.add_argument('--repeticoes', type=int, default=5)
    parser.add_argument('--comparar-legado', action='store_true')
    parser.add_argument('--json', type=Path)
    op = parser.parse_args()
    try:
        resultado = medir_saltos(tuple(map(int, op.tamanhos.split(','))), op.repeticoes, op.comparar_legado)
    except (ValueError, AssertionError) as erro:
        parser.error(str(erro))
    for registro in resultado['resultados']:
        print(f"{registro['metodo']} {registro['saltos']}: {registro['mediana_ms']:.3f} ms")
    if op.json:
        op.json.parent.mkdir(parents=True, exist_ok=True)
        op.json.write_text(json.dumps(resultado, ensure_ascii=False, indent=2), encoding='utf-8')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
