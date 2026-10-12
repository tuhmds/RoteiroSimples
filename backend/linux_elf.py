"""Escrita do formato ELF64 Linux, sem linker externo."""
import struct

def montar_elf(g, mensagens):
    inicio_codigo = 0x100
    inicio_dados = inicio_codigo + len(g.codigo)
    dados = bytearray()
    externos = {}
    for i, msg in mensagens.items():
        externos[f'mensagem_{i}'] = inicio_dados + len(dados)
        dados += msg.encode('utf-8')
    g.finalizar(inicio_codigo, externos)
    imagem = bytearray(inicio_codigo)
    imagem += g.codigo + dados
    imagem[:64] = struct.pack('<16sHHIQQQIHHHHHH', b'\x7fELF' + bytes([2, 1, 1, 0]) + bytes(8),
                              2, 62, 1, 0x400000 + inicio_codigo, 64, 0, 0, 64, 56, 1, 0, 0, 0)
    imagem[64:120] = struct.pack('<IIQQQQQQ', 1, 5, 0, 0x400000, 0x400000,
                                 len(imagem), len(imagem), 0x1000)
    return bytes(imagem)
