"""Emissão ELF64 PIE com código executável e dados não executáveis.

Os executáveis usam referências relativas ao ponteiro de instrução
(RIP), não precisam de biblioteca de execução nem de vinculador.
"""
import struct

from .base import alinhar


def montar_elf(g, mensagens):
    inicio_codigo = 0x100
    final_codigo = inicio_codigo + len(g.codigo)
    dados = bytearray()
    externos = {}
    inicio_dados = alinhar(final_codigo, 0x1000) if mensagens else final_codigo
    for indice, mensagem in mensagens.items():
        externos[f'mensagem_{indice}'] = inicio_dados + len(dados)
        dados += mensagem.encode('utf-8')
    g.finalizar(inicio_codigo, externos)

    # ELF64 64 bytes + até 3 cabeçalhos de programa de 56 bytes
    # cabem antes do primeiro byte de código, no deslocamento 0x100.
    imagem = bytearray(inicio_codigo)
    imagem += g.codigo
    cabecalhos = [struct.pack(
        '<IIQQQQQQ',
        1, 5, 0, 0, 0, inicio_dados if dados else len(imagem),
        inicio_dados if dados else len(imagem), 0x1000,
    )]

    if dados:
        # PT_LOAD separado: leitura, SEM escrita e SEM execução.
        # O deslocamento e o endereço virtual têm alinhamento congruente.
        imagem += bytes(inicio_dados - len(imagem))
        imagem += dados
        cabecalhos.append(struct.pack(
            '<IIQQQQQQ', 1, 4, inicio_dados, inicio_dados,
            inicio_dados, len(dados), len(dados), 0x1000,
        ))

    # PT_GNU_STACK: leitura/escrita, sem execução.
    cabecalhos.append(struct.pack(
        '<IIQQQQQQ', 0x6474E551, 6, 0, 0, 0, 0, 0, 16,
    ))

    imagem[:64] = struct.pack(
        '<16sHHIQQQIHHHHHH',
        b'\x7fELF' + bytes([2, 1, 1, 0]) + bytes(8),
        3, 62, 1, inicio_codigo, 64, 0, 0, 64, 56,
        len(cabecalhos), 0, 0, 0,
    )
    for indice, cabecalho in enumerate(cabecalhos):
        posicao = 64 + indice * 56
        imagem[posicao:posicao + 56] = cabecalho
    return bytes(imagem)
