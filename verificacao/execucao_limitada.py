"""RS-MEM: executar um binário ELF com orçamento real de memória virtual.

Linux x86-64: RLIMIT_AS aplicado ao processo filho antes de execve.
Não altera o compilador nem o executável nativo gerado pela RS.
"""
import argparse
import json
import os
from pathlib import Path
import resource
import subprocess
import sys
import tempfile
import time

MIB = 1024 * 1024
LIMITE_SAIDA = 65536


def validar_orcamento(limite_mib, timeout):
    if not isinstance(limite_mib, int) or not 16 <= limite_mib <= 65536:
        raise ValueError('O limite precisa estar entre 16 e 65536 MiB.')
    if timeout <= 0 or timeout > 3600:
        raise ValueError('O tempo limite precisa estar entre 0 e 3600 segundos.')
    if sys.platform != 'linux':
        raise OSError('Limite por RLIMIT_AS disponível somente no Linux.')


def _configurar_limite(limite_bytes):
    # Chamado APENAS no processo filho, imediatamente antes do exec.
    resource.setrlimit(resource.RLIMIT_AS, (limite_bytes, limite_bytes))


def executar(comando, limite_mib, timeout=15.0):
    """Produz diagnóstico sem ocultar falhas de alocação/tempo do binário."""
    validar_orcamento(limite_mib, timeout)
    if not comando:
        raise ValueError('Informe um executável e argumentos.')
    comando = [str(x) for x in comando]
    if comando[0] == '--':
        comando = comando[1:]
    if not comando:
        raise ValueError('Informe um executável e argumentos.')
    inicial = time.perf_counter_ns()
    antes = resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss
    com_tempo_esgotado = False
    with tempfile.TemporaryFile() as saida, tempfile.TemporaryFile() as erro:
        processo = subprocess.Popen(
            comando, stdout=saida, stderr=erro, stdin=subprocess.DEVNULL,
            preexec_fn=lambda: _configurar_limite(limite_mib * MIB),
        )
        try:
            codigo = processo.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            com_tempo_esgotado = True
            processo.kill()
            codigo = processo.wait()
        segundos = (time.perf_counter_ns() - inicial) / 1_000_000_000
        saida.seek(0)
        erro.seek(0)
        previa_saida = saida.read(LIMITE_SAIDA)
        previa_erro = erro.read(LIMITE_SAIDA)
        truncou_saida = bool(saida.read(1))
        truncou_erro = bool(erro.read(1))
    # ru_maxrss é o MAXIMO de todos os filhos já encerrados por este
    # processo supervisor. Para medição isolada, use 1 execução por CLI.
    pico_rss_kib = resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss
    return {
        'plataforma': sys.platform,
        'comando': comando,
        'limite_virtual_mib': limite_mib,
        'tipo_limite': 'RLIMIT_AS (espaco virtual, NAO RSS fisico)',
        'segundos': round(segundos, 6),
        'codigo_saida': codigo,
        'tempo_esgotado': com_tempo_esgotado,
        'pico_rss_filhos_kib': pico_rss_kib,
        'observacao_rss': 'Pico dos filhos da sessao supervisora; nao isola outras execucoes no mesmo Python.',
        'saida_inicio': previa_saida.decode('utf-8', errors='replace'),
        'erro_inicio': previa_erro.decode('utf-8', errors='replace'),
        'saida_truncada': truncou_saida,
        'erro_truncado': truncou_erro,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(
        description='Executa binário Linux com limite real de endereço virtual.')
    parser.add_argument('--limite-mib', type=int, required=True)
    parser.add_argument('--timeout', type=float, default=15)
    parser.add_argument('--json', type=Path, dest='arquivo_json')
    parser.add_argument('comando', nargs=argparse.REMAINDER)
    args = parser.parse_args(argv)
    try:
        resultado = executar(args.comando, args.limite_mib, args.timeout)
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        parser.error(str(exc))
    saida_json = json.dumps(resultado, ensure_ascii=False, indent=2) + '\n'
    print(saida_json, end='')
    if args.arquivo_json:
        args.arquivo_json.parent.mkdir(parents=True, exist_ok=True)
        args.arquivo_json.write_text(saida_json, encoding='utf-8')
    return 124 if resultado['tempo_esgotado'] else (
        0 if resultado['codigo_saida'] == 0 else 1)


if __name__ == '__main__':
    sys.exit(main())
