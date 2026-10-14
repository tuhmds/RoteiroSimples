"""Comparação intercalada de SSA e otimização com referências anteriores."""
import argparse
import hashlib
import json
from pathlib import Path
import platform
import random
import statistics
import tempfile
import time

from benchmarks.crescimento import gerar_caso, identidade_codigo
from compilador.cfg import construir_cfg
from compilador.ir import construir_ir, formatar_ir
from compilador.modulos import carregar_fontes
from compilador.parser import analisar_programa
from compilador.ssa import construir_ssa
from compilador.ssa_otimizador import otimizar_com_ssa



def identidade_ferramenta(referencia="rs042p"):
    resumo = hashlib.sha256()
    for caminho in (Path(__file__), Path(__file__).parents[1] / ('testes/fixtures/ssa_rs042p.py' if referencia == 'rs042p' else 'testes/fixtures/fluxo_rs042q.py')):
        resumo.update(caminho.read_bytes())
    return resumo.hexdigest()


def medir_analise(tamanhos=(32, 128, 512), repeticoes=5, semente=424210, referencia="rs042p"):
    if (not tamanhos or len(set(tamanhos)) != len(tamanhos)
            or any(not 1 <= n <= 2048 for n in tamanhos) or not 2 <= repeticoes <= 31):
        raise ValueError('Use tamanhos distintos de 1 a 2048 e 2 a 31 repetições.')
    if referencia not in ('rs042p', 'rs042q'):
        raise ValueError('Referência desconhecida.')
    if referencia == 'rs042p':
        from testes.fixtures.ssa_rs042p import construir_ssa_antes, otimizar_com_ssa_antes
        revisao = '3c6acf54b47e56076bdaa94db5ff01074f601161'
    else:
        from testes.fixtures.fluxo_rs042q import construir_ssa_antes, otimizar_com_ssa_antes
        revisao = '47eb322107b41fd9c675fdb3d243df66794f4e2b'
    codigo = identidade_codigo()
    ferramenta = identidade_ferramenta(referencia)
    metodos = {'construcao_atual': construir_ssa, 'construcao_' + referencia: construir_ssa_antes,
               'otimizacao_atual': otimizar_com_ssa, 'otimizacao_' + referencia: otimizar_com_ssa_antes}
    registros = {(n, nome): {'tamanho': n, 'metodo': nome, 'amostras_ms': []}
                 for n in tamanhos for nome in metodos}
    aleatorio = random.Random(semente)
    ordens = []
    with tempfile.TemporaryDirectory(prefix='rs_analise_ssa_') as pasta:
        preparados = {}
        for tamanho in tamanhos:
            caso = gerar_caso(Path(pasta) / str(tamanho), 'desvios', tamanho)
            programa = analisar_programa(carregar_fontes(Path(caso['fonte'])).texto)
            ir = construir_ir(programa, nivel=2)
            preparados[tamanho] = ir, construir_cfg(ir)
        for rodada in range(repeticoes + 1):
            ordem = list(registros)
            aleatorio.shuffle(ordem)
            ordens.append(ordem)
            for tamanho, nome in ordem:
                ir, cfg = preparados[tamanho]
                entrada = cfg if nome.startswith('construcao') else ir
                inicio = time.perf_counter_ns()
                resultado = metodos[nome](entrada)
                decorrido = (time.perf_counter_ns() - inicio) / 1e6
                # Formatação e validação ficam fora do intervalo medido.
                if nome.startswith('construcao'):
                    resultado.validar()
                    texto = resultado.para_json()
                    detalhes = {'dominadores': {b: sorted(ds) for b, ds in resultado.dominadores.items()},
                                'predecessores': {b: sorted(ps) for b, ps in resultado.predecessores.items()}}
                    texto += json.dumps(detalhes, sort_keys=True)
                else:
                    texto = formatar_ir(resultado)
                digest = hashlib.sha256(texto.encode('utf-8')).hexdigest()
                registro = registros[tamanho, nome]
                if 'sha256' in registro and registro['sha256'] != digest:
                    raise AssertionError('Resultado variou entre amostras.')
                registro['sha256'] = digest
                if rodada:
                    registro['amostras_ms'].append(decorrido)
                del resultado
    for tamanho in tamanhos:
        for fase in ('construcao', 'otimizacao'):
            if registros[tamanho, fase + '_atual']['sha256'] != registros[tamanho, fase + '_' + referencia]['sha256']:
                raise AssertionError('Análise divergiu da referência selecionada.')
    for registro in registros.values():
        amostras = registro['amostras_ms']
        registro.update({'mediana_ms': statistics.median(amostras),
                         'minimo_ms': min(amostras), 'maximo_ms': max(amostras)})
    if identidade_codigo() != codigo or identidade_ferramenta(referencia) != ferramenta:
        raise AssertionError('Código alterado durante a medição.')
    return {'versao': 'RS 0.42S', 'sistema': platform.platform(), 'python': platform.python_version(),
            'semente': semente, 'repeticoes': repeticoes, 'ordens': ordens,
            'referencia_commit': revisao, 'referencia': referencia,
            'codigo_sha256': codigo,
            'ferramenta_sha256': ferramenta,
            'medida': 'construção SSA ou otimização sobre IR preparada; sem observador; preparação e conferência fora',
            'cenario': 'condições consecutivas; referência compartilha tipos e auxiliares sem alteração semântica',
            'resultados': list(registros.values())}


def main():
    parser = argparse.ArgumentParser(description='Comparação de análise SSA RS 0.42S com referência selecionada')
    parser.add_argument('--tamanhos', default='32,128,512')
    parser.add_argument('--referencia', choices=('rs042p', 'rs042q'), default='rs042p')
    parser.add_argument('--repeticoes', type=int, default=5)
    parser.add_argument('--json', type=Path)
    op = parser.parse_args()
    try:
        resultado = medir_analise(tuple(map(int, op.tamanhos.split(','))), op.repeticoes, referencia=op.referencia)
    except (ValueError, AssertionError) as erro:
        parser.error(str(erro))
    for registro in resultado['resultados']:
        print(f"{registro['metodo']} {registro['tamanho']}: {registro['mediana_ms']:.3f} ms")
    if op.json:
        op.json.parent.mkdir(parents=True, exist_ok=True)
        op.json.write_text(json.dumps(resultado, ensure_ascii=False, indent=2), encoding='utf-8')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
