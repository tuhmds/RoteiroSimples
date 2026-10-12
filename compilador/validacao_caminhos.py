"""Validação uniforme de caminhos literais nas operações de arquivo RS.

Os caminhos são relativos e não podem escapar usando '..' ou nomes DOS
reservados. Isso NÃO confina links em diretórios ancestrais.
"""
import json
import re
from .erros import ErroCompilacao


def validar_literal_arquivo(literal, linha):
    """Decodifica e verifica nome literal, sem autorizar caminhos absolutos."""
    try:
        caminho = json.loads(str(literal))
    except (ValueError, UnicodeError) as exc:
        raise ErroCompilacao(f'Linha {linha}: nome de arquivo invalido.') from exc
    if (not isinstance(caminho, str) or not 1 <= len(caminho) <= 240
            or not re.fullmatch(r'[A-Za-z0-9_./-]+', caminho, re.ASCII)
            or caminho.startswith('/') or caminho.endswith('/')
            or any(parte in ('', '.', '..') for parte in caminho.split('/'))):
        raise ErroCompilacao(
            f'Linha {linha}: caminho de arquivo deve ser relativo e ASCII, '
            'sem . ou .. como segmento.')
    ultimo = caminho.split('/')[-1].split('.')[0].upper()
    if ultimo in ('CON', 'PRN', 'AUX', 'NUL') or (
            len(ultimo) == 4 and ultimo[:3] in ('COM', 'LPT')
            and ultimo[3] in '123456789'):
        raise ErroCompilacao(
            f'Linha {linha}: nome de dispositivo reservado: {ultimo}.')
    return caminho
