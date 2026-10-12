"""Operações nativas de persistência de texto com comprimento explícito.

O chamador passa RDI=caminho NUL ASCII, RSI=bytes e RDX=tamanho/capacidade.
Ambas rotinas devolvem em RAX o número efetivo de bytes gravados/lidos.
Erros encerram o processo com diagnóstico; nunca há truncamento silencioso.
"""
import struct


def _emitir(g, hexadecimais):
    g.bytes(bytes.fromhex(hexadecimais))


def emitir_comando(g, instrucao, variaveis, tipos, windows, mensagens,
                    endereco_buffer, deslocamento_variavel):
    modo, caminho, nome = instrucao
    dados, comprimento, capacidade = endereco_buffer(variaveis, nome, tipos, windows)
    numero = len(mensagens)
    mensagens[numero] = caminho + '\x00'
    g.relativo(b'\x48\x8D\x3D', f'mensagem_{numero}')  # RDI = caminho
    g.bytes(b'\x48\x8D\xB5' + struct.pack('<i', dados))  # RSI = dados
    if modo == 'grave_arquivo':
        g.bytes(b'\x48\x8B\x95' + struct.pack('<i', comprimento))
        g.chamada('rs_arquivo_gravar')
    else:
        g.bytes(b'\xBA' + struct.pack('<I', capacidade))
        g.chamada('rs_arquivo_carregar')
        g.bytes(b'\x48\x89\x85' + struct.pack('<i', comprimento))


def _prologo(g):
    _emitir(g, '55 48 89 E5 48 83 EC 60')
    _emitir(g, '48 89 7D F8 48 89 75 F0 48 89 55 E8')  # caminho, dados, limite
    _emitir(g, '48 C7 45 D8 00 00 00 00')  # bytes transferidos


def _fecho(g):
    _emitir(g, '48 89 EC 5D C3')


def _abrir_linux(g, gravar):
    _emitir(g, 'B8 01 01 00 00')  # openat
    _emitir(g, '48 C7 C7 9C FF FF FF')  # AT_FDCWD = -100
    _emitir(g, '48 8B 75 F8')  # path
    _emitir(g, 'BA 41 02 00 00' if gravar else '31 D2')  # WRONLY|CREAT|TRUNC
    _emitir(g, '41 BA 80 01 00 00')  # 0600
    _emitir(g, '0F 05 48 85 C0')
    g.salto('erro_arquivo_abrir', 'js')
    _emitir(g, '48 89 45 E0')  # fd


def _abrir_windows(g, gravar):
    _emitir(g, '48 8B 4D F8')  # RCX nome
    g.bytes(b'\xBA' + struct.pack('<I', 0x40000000 if gravar else 0x80000000))
    _emitir(g, '45 31 C0 45 31 C9')  # sem partilha, segurança NULL
    _emitir(g, '48 83 EC 40')
    _emitir(g, 'C7 44 24 20 02 00 00 00' if gravar else
                 'C7 44 24 20 03 00 00 00')  # CREATE_ALWAYS / OPEN_EXISTING
    _emitir(g, 'C7 44 24 28 80 00 00 00')  # FILE_ATTRIBUTE_NORMAL
    _emitir(g, '48 C7 44 24 30 00 00 00 00')  # handle modelo=NULL
    g.relativo(b'\xFF\x15', 'CreateFileA')
    _emitir(g, '48 83 C4 40 48 83 F8 FF')  # INVALID_HANDLE_VALUE
    g.salto('erro_arquivo_abrir', 'je')
    _emitir(g, '48 89 45 E0')  # HANDLE


def _abrir(g, windows, gravar):
    if windows:
        _abrir_windows(g, gravar)
    else:
        _abrir_linux(g, gravar)


def _fechar(g, windows):
    if windows:
        _emitir(g, '48 8B 4D E0 48 83 EC 20')
        g.relativo(b'\xFF\x15', 'CloseHandle')
        _emitir(g, '48 83 C4 20 85 C0')
        g.salto('erro_arquivo_fechar', 'jz')
    else:
        _emitir(g, 'B8 03 00 00 00 48 8B 7D E0 0F 05 48 85 C0')
        g.salto('erro_arquivo_fechar', 'js')
    _emitir(g, '48 8B 45 D8')  # RAX = total


def _leitura_windows(g, limite):
    _emitir(g, '48 8B 4D E0')  # RCX handle
    if limite:
        _emitir(g, '48 8D 55 C8 41 B8 01 00 00 00')  # um byte de prova
    else:
        _emitir(g, '48 8B 55 F0 48 03 55 D8')  # RDX = destino + pos
        _emitir(g, '4C 8B 45 E8 4C 2B 45 D8')  # R8 = espaço restante
    _emitir(g, '4C 8D 4D D0')  # R9 = &DWORD lidos
    _emitir(g, '48 83 EC 30')
    _emitir(g, '48 C7 44 24 20 00 00 00 00')
    g.relativo(b'\xFF\x15', 'ReadFile')
    _emitir(g, '48 83 C4 30 85 C0')
    g.salto('erro_arquivo_leitura', 'jz')
    _emitir(g, '8B 45 D0')  # DWORD bytes lidos


def _escrita_windows(g):
    _emitir(g, '48 8B 4D E0 48 8B 55 F0 48 03 55 D8')
    _emitir(g, '4C 8B 45 E8 4C 2B 45 D8')
    _emitir(g, '4C 8D 4D D0 48 83 EC 30')
    _emitir(g, '48 C7 44 24 20 00 00 00 00')
    g.relativo(b'\xFF\x15', 'WriteFile')
    _emitir(g, '48 83 C4 30 85 C0')
    g.salto('erro_arquivo_gravacao', 'jz')
    _emitir(g, '8B 45 D0')


def _leitura_linux(g, limite):
    _emitir(g, '31 C0 48 8B 7D E0')  # read(fd...)
    if limite:
        _emitir(g, '48 8D 75 C8 BA 01 00 00 00')
    else:
        _emitir(g, '48 8B 75 F0 48 03 75 D8')
        _emitir(g, '48 8B 55 E8 48 2B 55 D8')
    _emitir(g, '0F 05')


def _escrita_linux(g):
    _emitir(g, 'B8 01 00 00 00 48 8B 7D E0')  # write(fd...)
    _emitir(g, '48 8B 75 F0 48 03 75 D8')
    _emitir(g, '48 8B 55 E8 48 2B 55 D8')
    _emitir(g, '0F 05')


def _rotina(g, windows, gravar):
    nome = 'rs_arquivo_gravar' if gravar else 'rs_arquivo_carregar'
    loop = nome + '_volta'
    termino = nome + '_termino'
    prova = nome + '_prova'
    _prologo(g)
    _abrir(g, windows, gravar)
    g.marcar(loop)
    _emitir(g, '48 8B 45 E8 48 3B 45 D8')  # limite vs total
    g.salto(prova if not gravar else termino, 'je')
    if windows:
        if gravar:
            _escrita_windows(g)
        else:
            _leitura_windows(g, False)
        _emitir(g, '48 85 C0')
        if gravar:
            g.salto('erro_arquivo_gravacao', 'jz')
        else:
            g.salto(termino, 'jz')
    else:
        if gravar:
            _escrita_linux(g)
        else:
            _leitura_linux(g, False)
        _emitir(g, '48 83 F8 FC')  # errno EINTR (Linux)
        g.salto(loop, 'je')
        _emitir(g, '48 85 C0')
        g.salto('erro_arquivo_gravacao' if gravar else 'erro_arquivo_leitura', 'js')
        if gravar:
            g.salto('erro_arquivo_gravacao', 'jz')
        else:
            g.salto(termino, 'jz')
    _emitir(g, '48 01 45 D8')  # bytes confirmados
    g.salto(loop)
    if not gravar:
        g.marcar(prova)
        if windows:
            _leitura_windows(g, True)
        else:
            _leitura_linux(g, True)
            _emitir(g, '48 83 F8 FC')
            g.salto(prova, 'je')
            _emitir(g, '48 85 C0')
            g.salto('erro_arquivo_leitura', 'js')
        _emitir(g, '48 85 C0')
        g.salto('erro_arquivo_capacidade', 'jnz')
    g.marcar(termino)
    _fechar(g, windows)
    _fecho(g)


def emitir_rotinas(g, windows):
    _rotina(g, windows, True)
    _rotina(g, windows, False)
