"""Consolidação de cobertura com falha explícita em qualquer comando."""
import argparse
from pathlib import Path
import subprocess
import sys


def main(argv=None):
    parser = argparse.ArgumentParser(description='Consolidar cobertura Python da RS, incluindo subprocessos.')
    parser.add_argument('--saida', type=Path, default=Path('relatorios'))
    op = parser.parse_args(argv)
    op.saida.mkdir(parents=True, exist_ok=True)
    comandos = (
        ('combine',), ('report',),
        ('json', '-o', str(op.saida / 'cobertura.json')),
        ('html', '-d', str(op.saida / 'cobertura')),
    )
    for comando in comandos:
        resultado = subprocess.run([sys.executable, '-m', 'coverage', *comando])
        if resultado.returncode:
            print('Erro: etapa de cobertura falhou: ' + comando[0], file=sys.stderr)
            return resultado.returncode
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
