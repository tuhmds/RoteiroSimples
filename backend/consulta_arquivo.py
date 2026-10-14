"""Consulta recuperavel: arquivo regular=0, ausente=1, falha/tipo recusado=-1.

Nomes simples ASCII, sem seguir links no componente final. A consulta nao
abre nem altera o arquivo e nao substitui a verificacao na abertura real.
"""
import struct
from .desenrolamento_windows import emitir_prologo_auxiliar, emitir_epilogo_auxiliar, registrar_quadro_auxiliar


def emitir_comando(g, op, variaveis, windows, mensagens, deslocamento_variavel):
    _, caminho, estado = op
    indice = len(mensagens)
    mensagens[indice] = caminho + '\0'
    g.relativo(b'\x48\x8D\x3D', f'mensagem_{indice}')
    g.chamada('rs_consultar_arquivo')
    offset = deslocamento_variavel(variaveis, estado, windows)
    g.bytes(b'\x48\x89\x85' + struct.pack('<i', offset))


def emitir_rotina(g, windows):
    nome = 'rs_consultar_arquivo'
    def emitir(hexa):
        g.bytes(bytes.fromhex(hexa))
    g.marcar(nome)
    emitir_prologo_auxiliar(g, windows, 160)
    emitir('48 89 7D F8')
    if windows:
        emitir('48 89 F9')
        g.relativo(b'\xFF\x15', 'GetFileAttributesA')
        emitir('83 F8 FF')
        g.salto(nome + '_erro_windows', 'je')
        emitir('A9 10 04 00 00')  # DIRECTORY | REPARSE_POINT
        g.salto(nome + '_falha', 'jnz')
        g.salto(nome + '_regular')
        g.marcar(nome + '_erro_windows')
        g.relativo(b'\xFF\x15', 'GetLastError')
        emitir('83 F8 02')  # ERROR_FILE_NOT_FOUND, nao qualquer falha de abertura
        g.salto(nome + '_ausente', 'je')
        g.salto(nome + '_falha')
    else:
        g.marcar(nome + '_repetir')
        # newfstatat(AT_FDCWD, nome, stat[144], AT_SYMLINK_NOFOLLOW).
        emitir('B8 06 01 00 00 48 C7 C7 9C FF FF FF 48 8B 75 F8')
        emitir('48 8D 95 60 FF FF FF 41 BA 00 01 00 00 0F 05')
        emitir('48 83 F8 FC')
        g.salto(nome + '_repetir', 'je')
        emitir('48 83 F8 FE')  # -ENOENT
        g.salto(nome + '_ausente', 'je')
        emitir('48 85 C0')
        g.salto(nome + '_falha', 'js')
        emitir('8B 85 78 FF FF FF 25 00 F0 00 00 3D 00 80 00 00')
        g.salto(nome + '_falha', 'jne')  # (st_mode & S_IFMT) == S_IFREG
    g.marcar(nome + '_regular')
    emitir('31 C0')
    g.salto(nome + '_fim')
    g.marcar(nome + '_ausente')
    emitir('B8 01 00 00 00')
    g.salto(nome + '_fim')
    g.marcar(nome + '_falha')
    emitir('48 C7 C0 FF FF FF FF')
    g.marcar(nome + '_fim')
    emitir_epilogo_auxiliar(g, windows)
    if windows:
        registrar_quadro_auxiliar(g, nome)
