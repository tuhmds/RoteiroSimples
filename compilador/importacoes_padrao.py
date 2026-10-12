"""Localização segura dos módulos da Biblioteca Padrão RoteiroSimples.

A sintaxe importe "padrao/numeros.rts" consulta exclusivamente a biblioteca
distribuída com o compilador. Importações relativas de projetos continuam
limitadas à pasta principal; módulos padrão podem importar seus vizinhos.
"""
from pathlib import Path
from .erros import ErroCompilacao

RAIZ_PADRAO = (Path(__file__).resolve().parent.parent / 'biblioteca_padrao').resolve()


def resolver_importacao(nome, arquivo_origem, raiz_projeto):
    """Retorna um arquivo .rts válido, sem permitir fugas por .. ou atalhos."""
    if not isinstance(nome, str) or not nome or '\\' in nome or Path(nome).is_absolute():
        raise ErroCompilacao('use um caminho relativo de módulo com barras /.')
    if Path(nome).suffix.lower() != '.rts':
        raise ErroCompilacao('importação exige arquivo terminado em .rts.')
    origem = Path(arquivo_origem).resolve()
    raiz = Path(raiz_projeto).resolve()
    if nome.startswith('padrao/'):
        parte = nome[len('padrao/'):]
        if not parte or any(s in ('.', '..', '') for s in parte.split('/')):
            raise ErroCompilacao('caminho inválido na Biblioteca Padrão.')
        destino = (RAIZ_PADRAO / parte).resolve()
        if not destino.is_relative_to(RAIZ_PADRAO):
            raise ErroCompilacao('importação não pode sair da Biblioteca Padrão.')
    else:
        destino = (origem.parent / nome).resolve()
        if not destino.is_relative_to(raiz) and not (
                origem.is_relative_to(RAIZ_PADRAO) and destino.is_relative_to(RAIZ_PADRAO)):
            raise ErroCompilacao('importação não pode sair da pasta do projeto.')
    if not destino.is_file():
        raise ErroCompilacao(f'módulo não encontrado: {nome}.')
    return destino
