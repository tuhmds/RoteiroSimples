"""Escrita do formato PE32+ Windows, sem linker externo."""
import struct
from compilador.erros import ErroCompilacao
from .base import alinhar

def construir_importacoes(base_rva, nomes):
    conteudo = bytearray(40)
    tabela = (len(nomes) + 1) * 8
    inicio_ilt = len(conteudo)
    conteudo += bytes(tabela)
    inicio_iat = len(conteudo)
    conteudo += bytes(tabela)
    nomes_pos = []
    for nome in nomes:
        if len(conteudo) % 2:
            conteudo.append(0)
        nomes_pos.append(len(conteudo))
        conteudo += b'\x00\x00' + nome.encode('ascii') + b'\x00'
    inicio_dll = len(conteudo)
    conteudo += b'KERNEL32.dll\x00'
    while len(conteudo) % 4:
        conteudo.append(0)
    inicio_contador = len(conteudo)
    conteudo += bytes(4)
    for i, p in enumerate(nomes_pos):
        struct.pack_into('<Q', conteudo, inicio_ilt + i * 8, base_rva + p)
        struct.pack_into('<Q', conteudo, inicio_iat + i * 8, base_rva + p)
    struct.pack_into('<IIIII', conteudo, 0, base_rva + inicio_ilt, 0, 0,
                     base_rva + inicio_dll, base_rva + inicio_iat)
    enderecos = {nome: base_rva + inicio_iat + i * 8 for i, nome in enumerate(nomes)}
    enderecos['contador'] = base_rva + inicio_contador
    return conteudo, enderecos, inicio_iat, tabela

def montar_pe(g, mensagens):
    base_codigo = 0x1000
    base_importacoes = alinhar(base_codigo + len(g.codigo), 0x1000)
    nomes = ['GetStdHandle', 'SetConsoleOutputCP', 'WriteFile', 'ExitProcess']
    if any(label in g.rotulos for label in ('ler_inteiro', 'ler_buffer_texto')):
        nomes.extend(['ReadFile', 'GetLastError'])
    if 'ler_buffer_texto' in g.rotulos:
        nomes.append('SetConsoleCP')
    if 'rs_lista_alocar' in g.rotulos:
        nomes.extend(['VirtualAlloc', 'VirtualFree'])
    if 'rs_arquivo_gravar' in g.rotulos:
        nomes.extend(['CreateFileA', 'CloseHandle'])
        if 'ReadFile' not in nomes:
            nomes.append('ReadFile')
    if 'rs_trecho_gravar' in g.rotulos:
        for nome in ('CreateFileA', 'CloseHandle', 'ReadFile', 'SetFilePointerEx'):
            if nome not in nomes:
                nomes.append(nome)
    if 'rs_abrir_recurso' in g.rotulos:
        for nome in ('CreateFileA', 'CloseHandle', 'ReadFile', 'SetFilePointerEx',
                     'FlushFileBuffers'):
            if nome not in nomes:
                nomes.append(nome)
    importacoes, enderecos, inicio_iat, tamanho_iat = construir_importacoes(base_importacoes, nomes)
    base_dados = alinhar(base_importacoes + len(importacoes), 0x1000)
    dados = bytearray()
    for i, msg in mensagens.items():
        enderecos[f'mensagem_{i}'] = base_dados + len(dados)
        dados += msg.encode('utf-8')
    g.finalizar(base_codigo, enderecos)
    secoes = [(b'.text', bytes(g.codigo), base_codigo, 0x60000020),
              (b'.idata', bytes(importacoes), base_importacoes, 0xC0000040),
              (b'.rdata', bytes(dados), base_dados, 0x40000040)]
    descritores = []
    off = 0x200
    for nome, conteudo, virtual, flags in secoes:
        tamanho = alinhar(len(conteudo), 0x200)
        descritores.append((nome, conteudo, virtual, flags, off, tamanho))
        off += tamanho
    cabecalho = bytearray(0x200)
    cabecalho[:2] = b'MZ'
    struct.pack_into('<I', cabecalho, 0x3C, 0x80)
    cabecalho[0x80:0x84] = b'PE\x00\x00'
    struct.pack_into('<HHIIIHH', cabecalho, 0x84, 0x8664, 3, 0, 0, 0, 0xF0, 0x0022)
    opt = bytearray(0xF0)
    struct.pack_into('<H', opt, 0, 0x20B)
    struct.pack_into('<I', opt, 4, descritores[0][5])
    struct.pack_into('<I', opt, 8, descritores[1][5] + descritores[2][5])
    struct.pack_into('<I', opt, 16, base_codigo)
    struct.pack_into('<I', opt, 20, base_codigo)
    struct.pack_into('<Q', opt, 24, 0x140000000)
    struct.pack_into('<I', opt, 32, 0x1000)
    struct.pack_into('<I', opt, 36, 0x200)
    struct.pack_into('<HHHH', opt, 40, 6, 0, 0, 0)
    struct.pack_into('<HH', opt, 48, 6, 0)
    struct.pack_into('<I', opt, 56, alinhar(base_dados + max(1, len(dados)), 0x1000))
    struct.pack_into('<I', opt, 60, 0x200)
    struct.pack_into('<HH', opt, 68, 3, 0x100)
    struct.pack_into('<QQQQ', opt, 72, 0x100000, 0x1000, 0x100000, 0x1000)
    struct.pack_into('<II', opt, 104, 0, 16)
    struct.pack_into('<II', opt, 112 + 8, base_importacoes, 40)
    struct.pack_into('<II', opt, 112 + 8 * 12, base_importacoes + inicio_iat, tamanho_iat)
    cabecalho[0x98:0x98 + 0xF0] = opt
    pos = 0x98 + 0xF0
    for nome, conteudo, virtual, flags, offset, tamanho in descritores:
        struct.pack_into('<8sIIIIIIHHI', cabecalho, pos, nome.ljust(8, b'\0'),
                         len(conteudo), virtual, tamanho, offset, 0, 0, 0, 0, flags)
        pos += 40
    resultado = cabecalho
    for nome, conteudo, virtual, flags, offset, tamanho in descritores:
        resultado += conteudo + bytes(tamanho - len(conteudo))
    return bytes(resultado)
