"""Medidas da parte útil do código em executáveis ELF da RS.

O segmento de dados pode criar preenchimento de páginas. Estes testes
devem comparar código emitido, não o tamanho total do ELF em disco.
"""
import struct


def tamanho_codigo_elf(imagem):
    if imagem[:4] != b'\x7fELF':
        raise ValueError('Arquivo não é ELF64.')
    inicio_tabela, = struct.unpack_from('<Q', imagem, 32)
    tamanho_entrada, quantidade = struct.unpack_from('<HH', imagem, 54)
    for indice in range(quantidade):
        tipo, flags, deslocamento, _, _, tamanho = struct.unpack_from(
            '<IIQQQQ', imagem, inicio_tabela + indice * tamanho_entrada)
        if tipo == 1 and flags & 1:
            trecho = imagem[deslocamento + 0x100:deslocamento + tamanho]
            # O emissor encerra o código com instrução não nula;
            # os zeros finais pertencem ao preenchimento de página.
            return len(trecho.rstrip(b'\0'))
    raise ValueError('ELF64 sem segmento executável.')
