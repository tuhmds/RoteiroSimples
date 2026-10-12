"""Operações nativas de bytes[N], separadas de texto e de seu UTF-8.

Layout: palavra de comprimento seguida de ceil(N/8) palavras de conteúdo.
Os bytes de dados são armazenados em ordem crescente de endereço.
Nunca se lê um byte >= tamanho; nunca se grava além de capacidade.
"""
import struct


def _offsets(nome, variaveis, tipos, windows, deslocamento_variavel):
    capacidade = tipos[nome][1]
    comprimento = deslocamento_variavel(variaveis, nome, windows)
    dados = comprimento - 8 * ((capacidade + 7) // 8)
    return dados, comprimento, capacidade


def _validar_valor(g):
    # RAX é um inteiro assinado; não aceite conversão por truncamento.
    g.bytes(b'\x48\x85\xC0')  # test rax,rax
    g.salto('erro_valor_byte', 'js')
    g.bytes(b'\x48\x3D\xFF\x00\x00\x00')  # cmp rax,255
    g.salto('erro_valor_byte', 'ja')


def _endereco(g, dados):
    g.bytes(b'\x4C\x8D\x95' + struct.pack('<i', dados))  # r10 = &dados[0]
    g.bytes(b'\x49\x01\xCA')  # add r10,rcx (indice)


def acrescentar(g, nome, valor, variaveis, tipos, windows, expressao, deslocamento_variavel):
    dados, comprimento, capacidade = _offsets(nome, variaveis, tipos, windows, deslocamento_variavel)
    expressao(g, valor, variaveis, windows)
    _validar_valor(g)
    g.bytes(b'\x48\x8B\x8D' + struct.pack('<i', comprimento))  # rcx = tamanho
    g.bytes(b'\x48\x81\xF9' + struct.pack('<I', capacidade))
    g.salto('erro_bytes_capacidade', 'jae')
    _endereco(g, dados)
    g.bytes(b'\x41\x88\x02')  # mov byte ptr [r10],al
    g.bytes(b'\x48\xFF\x85' + struct.pack('<i', comprimento))  # inc qword [rbp+len]


def substituir(g, nome, indice, valor, variaveis, tipos, windows,
                expressao, deslocamento_variavel):
    dados, comprimento, _ = _offsets(nome, variaveis, tipos, windows, deslocamento_variavel)
    expressao(g, indice, variaveis, windows)
    g.bytes(b'\x50')  # salva índice para avaliar expressões que fazem chamadas
    expressao(g, valor, variaveis, windows, pilha_extra=1)
    g.bytes(b'\x59')  # rcx = indice
    _validar_valor(g)
    g.bytes(b'\x48\x85\xC9')  # test rcx,rcx
    g.salto('erro_indice_bytes', 'js')
    g.bytes(b'\x48\x3B\x8D' + struct.pack('<i', comprimento))  # cmp rcx,tamanho
    g.salto('erro_indice_bytes', 'jae')
    _endereco(g, dados)
    g.bytes(b'\x41\x88\x02')


def ler(g, nome, indice, variaveis, tipos, windows,
        expressao, deslocamento_variavel, pilha_extra=0):
    dados, comprimento, _ = _offsets(nome, variaveis, tipos, windows, deslocamento_variavel)
    expressao(g, indice, variaveis, windows, pilha_extra=pilha_extra)
    g.bytes(b'\x48\x85\xC0')
    g.salto('erro_indice_bytes', 'js')
    g.bytes(b'\x48\x3B\x85' + struct.pack('<i', comprimento))
    g.salto('erro_indice_bytes', 'jae')
    g.bytes(b'\x48\x89\xC1')  # rcx = indice
    _endereco(g, dados)
    g.bytes(b'\x41\x0F\xB6\x02')  # movzx eax,byte ptr [r10]
