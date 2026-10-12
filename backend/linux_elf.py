"""Emissão direta de ELF64 posicionável (PIE) para Linux x86-64.

O código de máquina referencia instruções e dados com deslocamentos
relativos ao RIP. Assim, a imagem é carregável em diferentes bases sem
tabela dinâmica de realocações ou vinculador externo.

O cabeçalho solicita pilha gravável, porém não executável.
"""
import struct


def montar_elf(g, mensagens):
    inicio_codigo = 0x100
    inicio_dados = inicio_codigo + len(g.codigo)
    dados = bytearray()
    externos = {}
    for indice, mensagem in mensagens.items():
        externos[f'mensagem_{indice}'] = inicio_dados + len(dados)
        dados += mensagem.encode('utf-8')
    g.finalizar(inicio_codigo, externos)

    # 64 bytes de cabeçalho ELF + 2 cabeçalhos de programa (56 bytes cada)
    # terminam em 176, preservando os 256 bytes reservados antes do código.
    imagem = bytearray(inicio_codigo)
    imagem += g.codigo + dados

    # ET_DYN = 3, sem PT_INTERP/PT_DYNAMIC: executável nativo PIE estático.
    # O endereço de entrada é deslocamento dentro da imagem, não 0x400000.
    imagem[:64] = struct.pack(
        '<16sHHIQQQIHHHHHH',
        b'\x7fELF' + bytes([2, 1, 1, 0]) + bytes(8),
        3, 62, 1, inicio_codigo, 64, 0, 0, 64, 56, 2, 0, 0, 0,
    )
    # PT_LOAD: leitura + execução; nenhum segmento pode ser gravado.
    imagem[64:120] = struct.pack(
        '<IIQQQQQQ', 1, 5, 0, 0, 0, len(imagem), len(imagem), 0x1000,
    )
    # PT_GNU_STACK = 0x6474E551. PF_R | PF_W = 6; NÃO executável.
    imagem[120:176] = struct.pack(
        '<IIQQQQQQ', 0x6474E551, 6, 0, 0, 0, 0, 0, 16,
    )
    return bytes(imagem)
