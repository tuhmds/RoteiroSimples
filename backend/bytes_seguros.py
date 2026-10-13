"""Operações nativas de bytes fixos e dinâmicos, separadas de texto UTF-8.

Fixo: comprimento e ceil(N/8) palavras de conteúdo. Dinâmico: descritor comum.
Os bytes de dados são armazenados em ordem crescente de endereço.
Nunca se lê um byte >= tamanho; nunca se grava além de capacidade.
"""
import struct
from compilador.propriedade import TIPO_BYTES_DINAMICOS, TIPO_BYTES_EMPRESTADOS
from . import valores_dinamicos, sequencias_dinamicas


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
    if tipos[nome] == TIPO_BYTES_DINAMICOS:
        expressao(g, valor, variaveis, windows)
        _validar_valor(g)
        # A expressão pode consumir o destino: verificar antes de acessar o heap.
        g.bytes(bytes.fromhex('50 48 83 EC 08'))
        valores_dinamicos.verificar_vivo(g, variaveis, nome, windows)
        valores_dinamicos.endereco_descritor(g, variaveis, nome, windows)
        g.bytes(bytes.fromhex('48 8B 77 F8 48 FF C6'))
        g.salto('erro_lista_memoria', 'jo')
        g.bytes(bytes.fromhex('BA 01 00 00 00'))
        g.chamada('rs_valor_reservar')
        g.bytes(bytes.fromhex('48 83 C4 08 58'))
        sequencias_dinamicas.vista(g, variaveis, tipos, nome, windows)
        g.bytes(bytes.fromhex('88 04 16 49 FF 40 F8'))
        return
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
    if tipos[nome] == TIPO_BYTES_DINAMICOS:
        expressao(g, indice, variaveis, windows)
        g.bytes(b'\x50')
        expressao(g, valor, variaveis, windows, pilha_extra=1)
        g.bytes(b'\x59')
        _validar_valor(g)
        # Refazer a vista depois das DUAS expressões, sem repetir seus efeitos.
        sequencias_dinamicas.vista(g, variaveis, tipos, nome, windows)
        g.bytes(bytes.fromhex('48 85 C9'))
        g.salto('erro_indice_bytes', 'js')
        g.bytes(bytes.fromhex('48 39 D1'))
        g.salto('erro_indice_bytes', 'jae')
        g.bytes(bytes.fromhex('88 04 0E'))
        return
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
    if tipos[nome] in (TIPO_BYTES_DINAMICOS, TIPO_BYTES_EMPRESTADOS):
        expressao(g, indice, variaveis, windows, pilha_extra=pilha_extra)
        g.bytes(bytes.fromhex('48 89 C1'))
        sequencias_dinamicas.vista(g, variaveis, tipos, nome, windows)
        g.bytes(bytes.fromhex('48 85 C9'))
        g.salto('erro_indice_bytes', 'js')
        g.bytes(bytes.fromhex('48 39 D1'))
        g.salto('erro_indice_bytes', 'jae')
        g.bytes(bytes.fromhex('0F B6 04 0E'))
        return
    dados, comprimento, _ = _offsets(nome, variaveis, tipos, windows, deslocamento_variavel)
    expressao(g, indice, variaveis, windows, pilha_extra=pilha_extra)
    g.bytes(b'\x48\x85\xC0')
    g.salto('erro_indice_bytes', 'js')
    g.bytes(b'\x48\x3B\x85' + struct.pack('<i', comprimento))
    g.salto('erro_indice_bytes', 'jae')
    g.bytes(b'\x48\x89\xC1')  # rcx = indice
    _endereco(g, dados)
    g.bytes(b'\x41\x0F\xB6\x02')  # movzx eax,byte ptr [r10]


def modificar(g, modo, destino, origem, variaveis, tipos, windows, deslocamento_variavel):
    """Cópia explícita entre buffers binários, incluindo autoacréscimo."""
    sequencias_dinamicas.vista(g, variaveis, tipos, origem, windows)
    if tipos[destino] == TIPO_BYTES_DINAMICOS:
        valores_dinamicos.endereco_descritor(g, variaveis, destino, windows)
        g.bytes(b'\xB9' + struct.pack('<I', int(modo == 'junte')))
        g.chamada('rs_sequencia_modificar')
        return
    dados, comprimento, capacidade = _offsets(destino, variaveis, tipos, windows, deslocamento_variavel)
    if modo == 'junte':
        g.bytes(b'\x48\x8B\x8D' + struct.pack('<i', comprimento))
    else:
        g.bytes(bytes.fromhex('31 C9'))
    g.bytes(bytes.fromhex('49 89 C9 49 01 D1'))
    g.salto('erro_bytes_capacidade', 'jo')
    g.bytes(b'\x49\x81\xF9' + struct.pack('<I', capacidade))
    g.salto('erro_bytes_capacidade', 'ja')
    g.bytes(b'\x48\x8D\xBD' + struct.pack('<i', dados))
    g.bytes(bytes.fromhex('48 01 CF 48 89 D1 FC F3 A4'))
    g.bytes(b'\x4C\x89\x8D' + struct.pack('<i', comprimento))
