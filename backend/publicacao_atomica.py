"""Publicação de um arquivo provisório já sincronizado por renomeação.

Contratos: RDI -> nome provisório, RSI -> nome final, ambos literais
ASCII sem separador de diretório; RAX=0 ou -8 (troca) / -9 (diretório).
Linux: renameat + fsync de '.'; Windows: MoveFileExA(REPLACE|WRITE_THROUGH).
O chamador deve fechar arquivos e sincronizar o provisório ANTES da troca.
"""
import struct


def _em(g, texto):
    g.bytes(bytes.fromhex(texto))


def emitir_comando(g, op, variaveis, windows, mensagens, deslocamento_variavel):
    _, origem, destino, estado = op
    nomes = []
    for caminho in (origem, destino):
        identificador = len(mensagens)
        mensagens[identificador] = caminho + '\x00'
        nomes.append(identificador)
    g.relativo(b'\x48\x8D\x3D', f'mensagem_{nomes[0]}')
    g.relativo(b'\x48\x8D\x35', f'mensagem_{nomes[1]}')
    g.chamada('rs_publicar_arquivo')
    offset = deslocamento_variavel(variaveis, estado, windows)
    g.bytes(b'\x48\x89\x85' + struct.pack('<i', offset))


def emitir_rotina(g, windows, mensagens):
    g.marcar('rs_publicar_arquivo')
    _em(g, '55 48 89 E5 48 83 EC 30')
    _em(g, '48 89 7D F8 48 89 75 F0')
    falha_troca = 'rs_publicar_falha_troca'
    falha_persistencia = 'rs_publicar_falha_persistencia'
    fim = 'rs_publicar_fim'
    if windows:
        # MoveFileExA(origem, destino, MOVEFILE_REPLACE_EXISTING |
        # MOVEFILE_WRITE_THROUGH), sem MOVEFILE_COPY_ALLOWED.
        _em(g, '48 89 F9 48 8B 55 F0 41 B8 09 00 00 00 48 83 EC 20')
        g.relativo(b'\xFF\x15', 'MoveFileExA')
        _em(g, '48 83 C4 20 85 C0')
        g.salto(falha_troca, 'jz')
        _em(g, '31 C0')
        g.salto(fim)
    else:
        # sys_renameat(AT_FDCWD, origem, AT_FDCWD, destino)
        repetir='rs_publicar_repetir'
        g.marcar(repetir)
        _em(g, 'B8 08 01 00 00 48 C7 C7 9C FF FF FF')
        _em(g, '48 8B 75 F8 49 C7 C0 9C FF FF FF 48 8B 4D F0')
        _em(g, '4C 89 C2') # RDX = AT_FDCWD, RCX = destination; R10 needed
        _em(g, '49 89 CA') # R10 = destination
        _em(g, '0F 05 48 83 F8 FC')
        g.salto(repetir, 'je')
        _em(g, '48 85 C0')
        g.salto(falha_troca, 'js')
        # Abre o diretorio corrente para sincronizar a mudança de nome.
        indice = len(mensagens)
        mensagens[indice] = '.\x00'
        _em(g, 'B8 01 01 00 00 48 C7 C7 9C FF FF FF')
        g.relativo(b'\x48\x8D\x35', f'mensagem_{indice}')
        _em(g, 'BA 00 00 09 00 45 31 D2 0F 05 48 85 C0')
        g.salto(falha_persistencia, 'js')
        _em(g, '48 89 45 E8') # fd do diretorio
        laco='rs_publicar_sincronizar'
        g.marcar(laco)
        _em(g, 'B8 4A 00 00 00 48 8B 7D E8 0F 05')
        _em(g, '48 83 F8 FC')
        g.salto(laco, 'je')
        _em(g, '48 85 C0')
        falha_sync='rs_publicar_sync_falhou'
        g.salto(falha_sync, 'js')
        _em(g, '48 C7 45 E0 00 00 00 00') # codigo sucesso 0
        fechar='rs_publicar_fechar_dir'
        g.salto(fechar)
        g.marcar(falha_sync)
        _em(g, '48 C7 45 E0 F7 FF FF FF') # -9
        g.marcar(fechar)
        _em(g, 'B8 03 00 00 00 48 8B 7D E8 0F 05')
        _em(g, '48 85 C0')
        g.salto(falha_persistencia, 'js')
        _em(g, '48 8B 45 E0')
        g.salto(fim)
    g.marcar(falha_troca)
    _em(g, '48 C7 C0 F8 FF FF FF') # -8
    g.salto(fim)
    g.marcar(falha_persistencia)
    _em(g, '48 C7 C0 F7 FF FF FF') # -9
    g.marcar(fim)
    _em(g, '48 89 EC 5D C3')
