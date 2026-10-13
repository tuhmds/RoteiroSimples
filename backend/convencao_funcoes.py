"""Orçamento de pilha da convenção interna de funções RS.

O executável Windows reserva 1 MiB de pilha. O programa RS usa até 768 KiB,
deixando espaço para entrada do sistema, rotinas auxiliares e saídas por erro.
Argumentos e temporários pendentes são cobrados além do quadro de cada função.
"""
from .base import alinhar

LIMITE_PILHA_SEGURA = 768 * 1024
MARGEM_QUADRO = 128


def tamanho_quadro(palavras, windows, memoria_cache=0):
    """Calcula a reserva local sem alterar o layout existente da ABI RS."""
    memoria = palavras * 8 + memoria_cache
    if windows:
        return alinhar(memoria + 0x38, 16) + 8
    return alinhar(memoria, 16)


def custo_quadro(quadro):
    """Inclui salvamentos, endereço de retorno e margem das rotinas locais."""
    return quadro + MARGEM_QUADRO
