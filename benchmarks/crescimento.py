"""Crescimento da compilacao completa em processos isolados, sem dependencias."""
import argparse
from dataclasses import asdict
import ctypes
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import random
import statistics
import subprocess
import sys
import tempfile
import time
import tracemalloc

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))
from backend import compilar
from compilador.erros import ErroCompilacao
from compilador.estrategia import decidir_estrategia
from compilador.medicao_compilacao import MedicaoCompilacao
from compilador.modulos import carregar_fontes
from compilador.parser import analisar_programa
from compilador.resultados_genericos import preparar_resultados_genericos

FAMILIAS = ('instrucoes', 'desvios', 'funcoes', 'misto', 'modulos')
VERSAO = 'RS 0.42T'


def identidade_codigo():
    resumo = hashlib.sha256()
    arquivos = [p for nome in ('compilador', 'backend', 'bibliotecas')
                for p in (RAIZ / nome).glob('*.py')]
    arquivos.append(Path(__file__).resolve())
    for caminho in sorted(arquivos):
        resumo.update(caminho.relative_to(RAIZ).as_posix().encode('utf-8') + b'\0' + caminho.read_bytes())
    return resumo.hexdigest()


def gerar_caso(pasta, familia, tamanho):
    if familia not in FAMILIAS or not 1 <= tamanho <= 10000:
        raise ValueError('Familia desconhecida ou tamanho fora de 1 a 10000.')
    pasta.mkdir(parents=True, exist_ok=True)
    principal = pasta / 'principal.rts'
    entrada = '3\n'
    cabecalho = ''
    corpo = ['seja numero = 0', 'leia(numero)']
    if familia == 'instrucoes':
        corpo += ['numero = numero + 1'] * tamanho
        corpo += ['escreva(numero)']
        esperado = 3 + tamanho
    elif familia == 'desvios':
        corpo += ['seja total = 0']
        for indice in range(tamanho):
            corpo += [f'se numero >= {indice} {{', 'total = total + 1',
                      '} senao {', 'total = total + 2', '}']
        corpo += ['escreva(total)']
        esperado = sum(1 if 3 >= indice else 2 for indice in range(tamanho))
    elif familia in ('funcoes', 'misto'):
        for indice in range(tamanho):
            cabecalho += (f'funcao calcular_{indice}(numero: inteiro) -> inteiro {{\n'
                          f' se numero < 0 {{\n  retorne numero - {indice}\n }}\n'
                          f' retorne numero + {indice}\n}}\n')
        corpo += [f'escreva(calcular_0(numero) + calcular_{tamanho - 1}(numero))']
        esperado = 6 + tamanho - 1
        if familia == 'misto':
            cabecalho = ('tipo Documento {\n titulo: texto\n}\n' + cabecalho +
                          'funcao consultar_documento() -> inteiro {\n'
                          ' seja documento: Documento\n copie(documento.titulo, "RS")\n'
                          ' retorne tamanho(documento.titulo)\n}\n')
    else:
        for indice in range(tamanho):
            nome = f'parte_{indice}.rts'
            (pasta / nome).write_text(
                'publico funcao calcular(numero: inteiro) -> inteiro {\n'
                f' retorne numero + {indice}\n}}\n', encoding='utf-8')
            cabecalho += f'importe "{nome}" como modulo_{indice}\n'
        corpo += [f'escreva(modulo_0.calcular(numero) + modulo_{tamanho - 1}.calcular(numero))']
        esperado = 6 + tamanho - 1
    principal.write_text(cabecalho + 'inicio {\n' + '\n'.join(' ' + linha for linha in corpo) + '\n}\n', encoding='utf-8')
    arquivos = sorted(pasta.glob('*.rts'))
    resumo = hashlib.sha256()
    for arquivo in arquivos:
        resumo.update(arquivo.name.encode('utf-8') + b'\0' + arquivo.read_bytes())
    return {'fonte': str(principal), 'entrada': entrada, 'esperado': f'{esperado}\n',
            'familia': familia, 'tamanho': tamanho, 'arquivos': len(arquivos),
            'linhas': sum(len(a.read_text(encoding='utf-8').splitlines()) for a in arquivos),
            'bytes_fonte': sum(a.stat().st_size for a in arquivos),
            'fontes_sha256': resumo.hexdigest()}


def pico_residente():
    if sys.platform == 'linux':
        import resource
        return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024
    if sys.platform == 'win32':
        from ctypes import wintypes
        class Contadores(ctypes.Structure):
            _fields_ = [('cb', wintypes.DWORD), ('PageFaultCount', wintypes.DWORD)] + [
                (nome, ctypes.c_size_t) for nome in ('PeakWorkingSetSize', 'WorkingSetSize',
                'QuotaPeakPagedPoolUsage', 'QuotaPagedPoolUsage', 'QuotaPeakNonPagedPoolUsage',
                'QuotaNonPagedPoolUsage', 'PagefileUsage', 'PeakPagefileUsage')]
        kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        psapi = ctypes.WinDLL('psapi', use_last_error=True)
        kernel.GetCurrentProcess.argtypes = []
        kernel.GetCurrentProcess.restype = wintypes.HANDLE
        psapi.GetProcessMemoryInfo.argtypes = [wintypes.HANDLE, ctypes.POINTER(Contadores), wintypes.DWORD]
        psapi.GetProcessMemoryInfo.restype = wintypes.BOOL
        dados = Contadores()
        dados.cb = ctypes.sizeof(dados)
        if not psapi.GetProcessMemoryInfo(kernel.GetCurrentProcess(), ctypes.byref(dados), dados.cb):
            raise OSError(ctypes.get_last_error(), 'GetProcessMemoryInfo falhou.')
        return dados.PeakWorkingSetSize
    return None


def compilar_caso(configuracao, memoria=False):
    medidor = None if memoria else MedicaoCompilacao()
    residente_inicial = pico_residente() if memoria else None
    if memoria:
        tracemalloc.start()
    inicio = time.perf_counter_ns()
    try:
        def etapa(nome):
            from compilador.medicao_compilacao import etapa as observar
            return observar(medidor, nome)
        with etapa('carregar_modulos'):
            fontes = carregar_fontes(Path(configuracao['fonte']))
        with etapa('preparar_resultados'):
            fontes = preparar_resultados_genericos(fontes)
        with etapa('analise_sintatica_semantica'):
            programa = analisar_programa(fontes.texto)
        imagem = compilar(programa, configuracao['alvo'], nivel=configuracao['nivel'],
                          otimizar=configuracao['nivel'] > 0, medidor=medidor)
        with etapa('gravar_executavel'):
            saida = Path(configuracao['executavel'])
            saida.write_bytes(imagem)
            if configuracao['alvo'] == 'linux':
                saida.chmod(0o755)
        duracao = time.perf_counter_ns() - inicio
        decisao = decidir_estrategia(programa, configuracao['nivel'], configuracao['nivel'] > 0)
        resultado = {'estado': 'aprovado', 'bytes_executavel': len(imagem),
                     'sha256_executavel': hashlib.sha256(imagem).hexdigest(),
                     'gerador': decisao.gerador, 'nivel_ir': decisao.nivel_ir,
                     'estrategias_funcoes': [asdict(f) for f in decisao.funcoes],
                     'motivos': list(decisao.motivos), 'funcoes': len(programa.funcoes)}
        if memoria:
            atual, pico = tracemalloc.get_traced_memory()
            resultado['memoria'] = {'python_atual_bytes': atual, 'python_pico_bytes': pico,
                                    'residente_inicial_bytes': residente_inicial,
                                    'residente_pico_bytes': pico_residente()}
        else:
            resultado.update({'compilacao_ms': duracao / 1e6, **medidor.resumo()})
        return resultado
    except Exception as erro:
        return {'estado': 'recusado' if isinstance(erro, ErroCompilacao) else 'erro',
                'tipo_erro': type(erro).__name__, 'erro': str(erro)[:2000],
                'etapas': medidor.resumo()['etapas'] if medidor is not None else {}}
    finally:
        if memoria:
            tracemalloc.stop()


def executar_trabalhador(configuracao, arquivo_configuracao, timeout, memoria=False):
    arquivo_configuracao.write_text(json.dumps(configuracao), encoding='utf-8')
    comando = [sys.executable, '-I', '-S', str(Path(__file__).resolve()),
               '--trabalhador', str(arquivo_configuracao)]
    if memoria:
        comando.append('--memoria')
    inicio = time.perf_counter_ns()
    try:
        processo = subprocess.run(comando, capture_output=True, text=True,
                                 encoding='utf-8', timeout=timeout)
    except subprocess.TimeoutExpired:
        return {'estado': 'tempo_esgotado', 'limite_segundos': timeout}
    if processo.returncode != 0:
        return {'estado': 'erro_processo', 'codigo_retorno': processo.returncode,
                'erros': processo.stderr[:2000]}
    try:
        resultado = json.loads(processo.stdout)
    except ValueError:
        return {'estado': 'erro_protocolo', 'erros': processo.stdout[:2000]}
    resultado['processo_ms'] = (time.perf_counter_ns() - inicio) / 1e6
    return resultado


def medir_crescimento(tamanhos=(10, 50, 100), familias=FAMILIAS, niveis=(0, 8),
                      repeticoes=3, timeout=30, semente=424200, arquivo=None):
    if (not tamanhos or len(set(tamanhos)) != len(tamanhos) or any(not 1 <= n <= 10000 for n in tamanhos)
            or not familias or len(set(familias)) != len(familias) or any(f not in FAMILIAS for f in familias)
            or not niveis or len(set(niveis)) != len(niveis) or any(not 0 <= n <= 8 for n in niveis)
            or not 2 <= repeticoes <= 31 or not 1 <= timeout <= 300):
        raise ValueError('Use familias/niveis/tamanhos distintos, 2 a 31 repeticoes e timeout de 1 a 300 segundos.')
    alvo = 'windows' if sys.platform == 'win32' else 'linux'
    if platform.machine().lower() not in ('amd64', 'x86_64') or sys.platform not in ('win32', 'linux'):
        raise ValueError('Medicao e execucao exigem Windows/Linux AMD64.')
    relatorio = {'versao': VERSAO, 'alvo': alvo, 'sistema': platform.platform(),
                 'revisao_ci': os.environ.get('GITHUB_SHA'), 'codigo_sha256': identidade_codigo(),
                 'python': platform.python_version(), 'semente': semente,
                 'repeticoes': repeticoes, 'tamanhos': list(tamanhos), 'niveis': list(niveis),
                 'familias': list(familias), 'ordens': [], 'resultados': [],
                 'medida': 'compilacao instrumentada de leitura dos modulos ate gravacao; imports/inicio do Python fora',
                 'memoria': 'amostra separada com tracemalloc; RSS de vida do processo inclui imports e rastreamento'}
    aleatorio = random.Random(semente)
    def salvar():
        if arquivo:
            arquivo.parent.mkdir(parents=True, exist_ok=True)
            arquivo.write_text(json.dumps(relatorio, ensure_ascii=False, indent=2), encoding='utf-8')
    with tempfile.TemporaryDirectory(prefix='rs_crescimento_') as temporaria:
        base = Path(temporaria)
        registros = []
        for familia in familias:
            for tamanho in tamanhos:
                caso = gerar_caso(base / f'{familia}_{tamanho}', familia, tamanho)
                for nivel in niveis:
                    registro = {k: v for k, v in caso.items() if k not in ('fonte', 'entrada', 'esperado')}
                    registro.update({'nivel': nivel, 'amostras': [], 'estado': 'pendente'})
                    configuracao = {**caso, 'nivel': nivel, 'alvo': alvo,
                                    'executavel': str(base / ('programa.exe' if alvo == 'windows' else 'programa'))}
                    registros.append((registro, configuracao))
                    relatorio['resultados'].append(registro)
        for rodada in range(repeticoes + 1):
            ordem = list(range(len(registros)))
            aleatorio.shuffle(ordem)
            relatorio['ordens'].append(ordem)
            for indice in ordem:
                registro, configuracao = registros[indice]
                if registro['estado'] not in ('pendente', 'aprovado'):
                    continue
                resultado = executar_trabalhador(configuracao, base / 'configuracao.json', timeout)
                if resultado['estado'] == 'aprovado':
                    try:
                        processo = subprocess.run([configuracao['executavel']], input=configuracao['entrada'],
                                                  capture_output=True, text=True, encoding='utf-8', timeout=timeout)
                        if (processo.returncode, processo.stdout, processo.stderr) != (0, configuracao['esperado'], ''):
                            resultado = {'estado': 'divergencia_execucao', 'codigo_retorno': processo.returncode,
                                         'saida': processo.stdout[:2000], 'esperado': configuracao['esperado']}
                    except subprocess.TimeoutExpired:
                        resultado = {'estado': 'tempo_execucao_esgotado', 'limite_segundos': timeout}
                if resultado['estado'] != 'aprovado':
                    registro.update(resultado)
                else:
                    registro['estado'] = 'aprovado'
                    identidade = (resultado['sha256_executavel'], resultado['gerador'], resultado['nivel_ir'])
                    if 'identidade' in registro and tuple(registro['identidade']) != identidade:
                        registro.update({'estado': 'divergencia_compilacao', 'erro': 'Bytes ou estrategia variaram entre amostras.'})
                    else:
                        registro['identidade'] = identidade
                        registro['aquecimento' if rodada == 0 else 'ultima'] = resultado
                        if rodada:
                            registro['amostras'].append(resultado)
                salvar()
        for registro, configuracao in registros:
            if registro['estado'] == 'aprovado':
                memoria = executar_trabalhador(configuracao, base / 'configuracao.json', timeout, memoria=True)
                if memoria['estado'] != 'aprovado' or memoria.get('sha256_executavel') != registro['identidade'][0]:
                    registro.update({'estado': 'falha_amostra_memoria', 'amostra_memoria': memoria})
                else:
                    registro['memoria'] = memoria['memoria']
                    registro['mediana_compilacao_ms'] = statistics.median(a['compilacao_ms'] for a in registro['amostras'])
                    registro['minimo_compilacao_ms'] = min(a['compilacao_ms'] for a in registro['amostras'])
                    registro['maximo_compilacao_ms'] = max(a['compilacao_ms'] for a in registro['amostras'])
            salvar()
    relatorio['conclusao'] = 'aprovado' if all(r['estado'] == 'aprovado' for r in relatorio['resultados']) else 'com_falhas'
    if identidade_codigo() != relatorio['codigo_sha256']:
        relatorio['conclusao'] = 'codigo_alterado_durante_medicao'
    relatorio['alertas_crescimento'] = []
    for familia in familias:
        for nivel in niveis:
            serie = sorted((r for r in relatorio['resultados'] if r['familia'] == familia and r['nivel'] == nivel
                            and r['estado'] == 'aprovado'), key=lambda r: r['tamanho'])
            for menor, maior in ((a, b) for indice, a in enumerate(serie) for b in serie[indice + 1:]):
                razao_tamanho = maior['tamanho'] / menor['tamanho']
                razao_tempo = maior['mediana_compilacao_ms'] / menor['mediana_compilacao_ms']
                if razao_tamanho >= 2 and razao_tempo > 2 * razao_tamanho:
                    relatorio['alertas_crescimento'].append({'familia': familia, 'nivel': nivel,
                        'de': menor['tamanho'], 'para': maior['tamanho'],
                        'razao_tamanho': razao_tamanho, 'razao_tempo': razao_tempo,
                        'expoente_aparente': math.log(razao_tempo) / math.log(razao_tamanho)})
    salvar()
    return relatorio


def main():
    parser = argparse.ArgumentParser(description='Crescimento da compilacao RS 0.42T; tempos, fases, memoria e oraculo.')
    parser.add_argument('--tamanhos', default='10,50,100')
    parser.add_argument('--familias', default=','.join(FAMILIAS))
    parser.add_argument('--niveis', default='0,8')
    parser.add_argument('--repeticoes', type=int, default=3)
    parser.add_argument('--timeout', type=float, default=30)
    parser.add_argument('--semente', type=int, default=424200)
    parser.add_argument('--json', type=Path)
    parser.add_argument('--exploratorio', action='store_true', help='preserva falhas no relatorio sem aprovar os casos')
    parser.add_argument('--trabalhador', type=Path, help=argparse.SUPPRESS)
    parser.add_argument('--memoria', action='store_true', help=argparse.SUPPRESS)
    op = parser.parse_args()
    if op.trabalhador:
        print(json.dumps(compilar_caso(json.loads(op.trabalhador.read_text(encoding='utf-8')), op.memoria)))
        return 0
    try:
        res = medir_crescimento(tuple(map(int, op.tamanhos.split(','))), tuple(op.familias.split(',')),
            tuple(map(int, op.niveis.split(','))), op.repeticoes, op.timeout, op.semente, op.json)
    except (ValueError, OSError) as erro:
        parser.error(str(erro))
    for registro in res['resultados']:
        print(f"{registro['familia']} {registro['tamanho']} O{registro['nivel']}: {registro['estado']} "
              f"{registro.get('mediana_compilacao_ms', 0):.3f} ms")
    print('Conclusao:', res['conclusao'], '| Alertas de crescimento:', len(res['alertas_crescimento']))
    return 0 if res['conclusao'] == 'aprovado' or op.exploratorio else 1


if __name__ == '__main__':
    raise SystemExit(main())
