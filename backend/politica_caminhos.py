"""Política comum de abertura de arquivos nativos da RS.

Linux: protege o componente final contra links simbólicos, com
O_NOFOLLOW e O_CLOEXEC. Windows: abre o próprio ponto de nova análise
sem atravessá-lo; verifica seu tipo em identificador já aberto.

ATENÇÃO: isso NÃO confina diretórios ancestrais não confiáveis.
"""


import struct
from .desenrolamento_windows import (
    registrar_quadro_auxiliar, emitir_prologo_auxiliar,
    emitir_epilogo_auxiliar,
)


# Linux x86-64: O_NOFOLLOW (0x20000), O_CLOEXEC (0x80000).
_ABERTURA_SEGURA_LINUX = 0x000A0000

SINALIZADORES_LINUX = {
    'leitura': _ABERTURA_SEGURA_LINUX,
    'gravacao_completa': _ABERTURA_SEGURA_LINUX | 0x241,
    'gravacao_posicional': _ABERTURA_SEGURA_LINUX | 0x41,
    'alteracao': _ABERTURA_SEGURA_LINUX | 0x42,
    'novo': _ABERTURA_SEGURA_LINUX | 0xC2,
}

# FILE_ATTRIBUTE_NORMAL | FILE_FLAG_OPEN_REPARSE_POINT.
ATRIBUTOS_WINDOWS_SEM_SEGUIR_LINK = 0x00200080


def sinalizadores_linux(modo):
    """Devolve os sinalizadores de abertura em formato imediato x86-64."""
    return struct.pack('<I', SINALIZADORES_LINUX[modo])


def atributos_windows():
    """Devolve sinalizadores Windows sem seguir o ponto final de nova análise."""
    return struct.pack('<I', ATRIBUTOS_WINDOWS_SEM_SEGUIR_LINK)


def emitir_verificacao_windows(g):
    """Rotina nativa que rejeita diretórios e pontos de nova análise.

    Entrada: RDI = identificador Windows aberto com OPEN_REPARSE_POINT.
    Saída: RAX = 0 (regular) ou -1 (falha/atributo recusado).

    GetFileInformationByHandleEx(FileAttributeTagInfo=9) devolve
    DWORD FileAttributes + DWORD ReparseTag em [RBP-8..RBP-1].
    Não usa bibliotecas de execução externas.
    """
    g.marcar('rs_verificar_arquivo_regular')
    emitir_prologo_auxiliar(g, True, 64)
    g.bytes(bytes.fromhex('48 89 F9'))             # rcx = handle
    g.bytes(bytes.fromhex('BA 09 00 00 00'))       # edx = FileAttributeTagInfo
    g.bytes(bytes.fromhex('4C 8D 45 F8'))          # r8 = &informacoes
    g.bytes(bytes.fromhex('41 B9 08 00 00 00'))    # r9d = 8 bytes
    g.relativo(b'\xFF\x15', 'GetFileInformationByHandleEx')
    g.bytes(bytes.fromhex('85 C0'))                # test eax,eax
    g.salto('rs_verificar_rejeitado', 'jz')
    # FILE_ATTRIBUTE_DIRECTORY | FILE_ATTRIBUTE_REPARSE_POINT
    g.bytes(bytes.fromhex('F7 45 F8 10 04 00 00'))
    g.salto('rs_verificar_rejeitado', 'jnz')
    g.bytes(bytes.fromhex('31 C0'))                # sucesso
    g.salto('rs_verificar_fim')
    g.marcar('rs_verificar_rejeitado')
    g.bytes(bytes.fromhex('48 C7 C0 FF FF FF FF')) # -1
    g.marcar('rs_verificar_fim')
    emitir_epilogo_auxiliar(g, True)
    registrar_quadro_auxiliar(g, 'rs_verificar_arquivo_regular')
