"""Campanha nativa reproduzível com oráculo e redução de casos divergentes."""
import argparse
from dataclasses import asdict
import hashlib
import json
import platform
from pathlib import Path
import subprocess
import sys
import tempfile

from backend import compilar
from compilador.estrategia import decidir_estrategia
from compilador.parser import analisar_programa
from .casos_gerados import gerar_caso, montar_caso, Operacao, reduzir_caso


def alvo_nativo():
    if sys.platform == 'win32' and platform.machine().lower() in ('amd64', 'x86_64'):
        return 'windows'
    if sys.platform == 'linux' and platform.machine().lower() in ('amd64', 'x86_64'):
        return 'linux'
    raise ValueError('Campanha exige Windows AMD64 ou Linux x86-64.')


def avaliar(caso, nivel, alvo=None):
    alvo = alvo or alvo_nativo()
    try:
        programa = analisar_programa(caso.fonte)
        imagem = compilar(programa, alvo, nivel=nivel, otimizar=nivel > 0)
    except Exception as erro:
        return {'classe': 'compilacao:' + type(erro).__name__, 'erro': str(erro)}
    with tempfile.TemporaryDirectory(prefix='rs_campanha_') as pasta:
        executavel = Path(pasta) / ('programa.exe' if alvo == 'windows' else 'programa')
        executavel.write_bytes(imagem)
        if alvo == 'linux':
            executavel.chmod(0o700)
        try:
            retorno = subprocess.run([str(executavel)], cwd=pasta, capture_output=True,
                encoding='utf-8', errors='replace', timeout=15)
        except subprocess.TimeoutExpired:
            return {'classe': 'tempo_excedido'}
        observados = {arquivo.name: arquivo.read_bytes() for arquivo in Path(pasta).iterdir()
                      if arquivo.is_file() and arquivo != executavel}
        if retorno.returncode != 0:
            classe = 'execucao:' + str(retorno.returncode)
        elif retorno.stdout != caso.saida or retorno.stderr:
            classe = 'saida_divergente'
        elif observados != caso.arquivos:
            classe = 'arquivos_divergentes'
        else:
            classe = 'aprovado'
        estrategia = decidir_estrategia(programa, nivel, nivel > 0)
        return {'classe': classe, 'codigo_retorno': retorno.returncode,
            'saida': retorno.stdout, 'erros': retorno.stderr,
            'arquivos': {nome: dados.hex() for nome, dados in observados.items()},
            'gerador': estrategia.gerador, 'nivel_ir': estrategia.nivel_ir,
            'sha256': hashlib.sha256(imagem).hexdigest()}


def salvar_falha(pasta, caso, nivel, resultado, reduzir=True):
    pasta.mkdir(parents=True, exist_ok=True)
    original = pasta / f'falha_{caso.semente}_O{nivel}'
    original.with_suffix('.rts').write_text(caso.fonte, encoding='utf-8')
    dados = {'semente': caso.semente, 'nivel': nivel,
        'operacoes': [asdict(op) for op in caso.operacoes],
        'esperado': {'saida': caso.saida, 'arquivos': {n: b.hex() for n, b in caso.arquivos.items()}},
        'observado': resultado}
    if reduzir:
        reduzido = reduzir_caso(caso, lambda novo: avaliar(novo, nivel)['classe'] == resultado['classe'])
        original.with_name(original.name + '_reduzido.rts').write_text(reduzido.fonte, encoding='utf-8')
        dados['operacoes_reduzidas'] = [asdict(op) for op in reduzido.operacoes]
    original.with_suffix('.json').write_text(json.dumps(dados, ensure_ascii=False, indent=2), encoding='utf-8')


def main(argv=None):
    parser = argparse.ArgumentParser(description='Verificação estruturada nativa da RS com oráculo independente.')
    parser.add_argument('--semente', type=int, default=42010)
    parser.add_argument('--casos', type=int, default=12)
    parser.add_argument('--passos', type=int, default=40)
    parser.add_argument('--niveis', default='0,8')
    parser.add_argument('--saida', type=Path, default=Path('relatorios/campanha'))
    parser.add_argument('--reproduzir', type=Path, help='arquivo JSON de uma falha salva')
    op = parser.parse_args(argv)
    try:
        niveis = tuple(int(n) for n in op.niveis.split(','))
        if not niveis or any(not 0 <= n <= 8 for n in niveis):
            raise ValueError('Níveis devem estar entre 0 e 8.')
        if not 1 <= op.casos <= 10000 or not 9 <= op.passos <= 1000:
            raise ValueError('Use 1–10000 casos e 9–1000 passos.')
        alvo = alvo_nativo()
        if op.reproduzir:
            salvo = json.loads(op.reproduzir.read_text(encoding='utf-8'))
            operacoes = salvo.get('operacoes_reduzidas', salvo['operacoes'])
            casos = [montar_caso(salvo['semente'], [Operacao(**a) for a in operacoes])]
            niveis = (salvo['nivel'],)
        else:
            casos = [gerar_caso(op.semente + numero, op.passos) for numero in range(op.casos)]
        resultados = []
        for caso in casos:
            for nivel in niveis:
                observado = avaliar(caso, nivel, alvo)
                resultados.append({'semente': caso.semente, 'nivel': nivel, **observado})
                if observado['classe'] != 'aprovado':
                    salvar_falha(op.saida, caso, nivel, observado)
                    raise ValueError(f'Falha na semente {caso.semente}, O{nivel}: {observado["classe"]}. Caso salvo para reprodução.')
        op.saida.mkdir(parents=True, exist_ok=True)
        resumo = {'versao': 'RS 0.42T', 'alvo': alvo, 'semente_inicial': op.semente,
            'casos': len(casos), 'execucoes': len(resultados), 'passos': op.passos, 'resultados': resultados}
        (op.saida / 'resumo.json').write_text(json.dumps(resumo, ensure_ascii=False, indent=2), encoding='utf-8')
        print(f'{len(casos)} programas, {len(resultados)} execuções nativas aprovadas ({alvo}).')
        return 0
    except (ValueError, OSError) as erro:
        print(f'Erro: {erro}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
