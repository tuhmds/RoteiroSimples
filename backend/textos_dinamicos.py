"""Texto UTF-8 com armazenamento crescente e descritor proprietário comum.

Comprimento e capacidade são bytes; caracteres conta valores escalares
Unicode, sem prometer contagem de grafemas ou normalização implícita.
"""
import struct
from compilador.propriedade import TIPO_TEXTO_DINAMICO, TIPO_TEXTO_EMPRESTADO
from . import valores_dinamicos
from .sequencias_dinamicas import vista
from .desenrolamento_windows import (
    emitir_prologo_auxiliar, emitir_epilogo_auxiliar,
    registrar_quadro_auxiliar, registrar_quadro_empilhado,
)


def _emitir(g, codigo):
    g.bytes(bytes.fromhex(codigo))


def _fechar(g, windows, nome):
    emitir_epilogo_auxiliar(g, windows)
    if windows:
        registrar_quadro_auxiliar(g, nome)


def chamar_alinhado(g, nome, pilha_extra=0):
    if pilha_extra % 2:
        _emitir(g, '48 83 EC 08')
    g.chamada(nome)
    if pilha_extra % 2:
        _emitir(g, '48 83 C4 08')



def modificar(g, modo, nome, origem, variaveis, tipos, windows, mensagens):
    if origem[0] == 'literal':
        numero = len(mensagens)
        mensagens[numero] = origem[1]
        g.relativo(b'\x48\x8D\x35', f'mensagem_{numero}')
        g.bytes(b'\x48\xBA' + struct.pack('<Q', origem[2]))
        _emitir(g, '45 31 C0')
    else:
        vista(g, variaveis, tipos, origem[1], windows)
    valores_dinamicos.endereco_descritor(g, variaveis, nome, windows)
    g.bytes(b'\xB9' + struct.pack('<I', int(modo == 'junte')))
    g.chamada('rs_texto_modificar')


def consulta(g, operacao, nome, variaveis, tipos, windows, pilha_extra=0):
    vista(g, variaveis, tipos, nome, windows)
    if operacao == 'tamanho_texto_dinamico':
        _emitir(g, '48 89 D0')
    elif operacao == 'capacidade_texto_dinamico':
        _emitir(g, '49 8B 40 F0')
    else:
        chamar_alinhado(g, 'rs_validar_utf8', pilha_extra)


def comparar(g, esquerda, direita, diferente, variaveis, tipos, windows, pilha_extra):
    vista(g, variaveis, tipos, esquerda, windows)
    _emitir(g, '48 89 F7 48 89 D1')
    vista(g, variaveis, tipos, direita, windows)
    chamar_alinhado(g, 'rs_texto_igual', pilha_extra)
    if diferente:
        _emitir(g, '83 F0 01')


def imprimir(g, nome, variaveis, tipos, windows):
    vista(g, variaveis, tipos, nome, windows)
    _emitir(g, '48 89 DF' if windows else 'BF 01 00 00 00')
    g.chamada('rs_texto_escrever')


def limpar(g, nome, variaveis, windows):
    valores_dinamicos.verificar_vivo(g, variaveis, nome, windows)
    base = valores_dinamicos.deslocamento_local(variaveis, nome, windows)
    g.bytes(b'\x48\xC7\x85' + struct.pack('<i', base - 8) + b'\x00' * 4)


def emitir_validador(g, windows):
    nome = 'rs_validar_utf8'
    g.marcar(nome)
    emitir_prologo_auxiliar(g, windows, 32)
    # RSI=conteúdo, RDX=bytes. RAX=escalares; ECX=continuações; R11=restrição.
    _emitir(g, '31 C0 31 C9 45 31 DB 49 89 F0')
    g.marcar(nome + '_volta')
    _emitir(g, '48 85 D2')
    g.salto(nome + '_fim', 'jz')
    _emitir(g, '45 0F B6 10 49 FF C0 48 FF CA 85 C9')
    g.salto(nome + '_continuacao', 'jnz')
    _emitir(g, '48 FF C0 41 80 FA 80')
    g.salto(nome + '_volta', 'jb')
    _emitir(g, '41 80 FA C2')
    g.salto('erro_texto_utf8', 'jb')
    _emitir(g, '41 80 FA DF')
    g.salto(nome + '_dois', 'jbe')
    _emitir(g, '41 80 FA EF')
    g.salto(nome + '_tres', 'jbe')
    _emitir(g, '41 80 FA F4')
    g.salto(nome + '_quatro', 'jbe')
    g.salto('erro_texto_utf8')
    g.marcar(nome + '_dois')
    _emitir(g, 'B9 01 00 00 00')
    g.salto(nome + '_volta')
    g.marcar(nome + '_tres')
    _emitir(g, 'B9 02 00 00 00 41 80 FA E0')
    g.salto(nome + '_e0', 'je')
    _emitir(g, '41 80 FA ED')
    g.salto(nome + '_ed', 'je')
    g.salto(nome + '_volta')
    g.marcar(nome + '_quatro')
    _emitir(g, 'B9 03 00 00 00 41 80 FA F0')
    g.salto(nome + '_f0', 'je')
    _emitir(g, '41 80 FA F4')
    g.salto(nome + '_f4', 'je')
    g.salto(nome + '_volta')
    for sufixo, flag in (('e0', 1), ('ed', 2), ('f0', 3), ('f4', 4)):
        g.marcar(nome + '_' + sufixo)
        g.bytes(b'\x41\xBB' + struct.pack('<I', flag))
        g.salto(nome + '_volta')
    g.marcar(nome + '_continuacao')
    _emitir(g, '41 80 FA 80')
    g.salto('erro_texto_utf8', 'jb')
    _emitir(g, '41 80 FA BF')
    g.salto('erro_texto_utf8', 'ja')
    for flag, limite, salto in ((1, 0xA0, 'jb'), (2, 0x9F, 'ja'), (3, 0x90, 'jb'), (4, 0x8F, 'ja')):
        rotulo = nome + f'_restricao_{flag}'
        g.bytes(b'\x41\x83\xFB' + bytes((flag,)))
        g.salto(rotulo, 'jne')
        g.bytes(b'\x41\x80\xFA' + bytes((limite,)))
        g.salto('erro_texto_utf8', salto)
        g.marcar(rotulo)
    _emitir(g, 'FF C9 45 31 DB')
    g.salto(nome + '_volta')
    g.marcar(nome + '_fim')
    _emitir(g, '85 C9')
    g.salto('erro_texto_utf8', 'jnz')
    _fechar(g, windows, nome)


def emitir_rotinas(g, windows, ler_linha=False):
    emitir_validador(g, windows)
    # A validação preserva os argumentos da rotina comum de crescimento.
    nome = 'rs_texto_modificar'
    g.marcar(nome)
    emitir_prologo_auxiliar(g, windows, 48)
    _emitir(g, '48 89 7D F8 48 89 75 F0 48 89 55 E8 48 89 4D E0 4C 89 45 D8')
    _emitir(g, '48 83 7F F8 00')
    g.salto('erro_valor_inativo', 'jl')
    g.chamada('rs_validar_utf8')
    _emitir(g, '48 8B 7D F8 48 8B 75 F0 48 8B 55 E8 48 8B 4D E0 4C 8B 45 D8')
    g.chamada('rs_sequencia_modificar')
    _fechar(g, windows, nome)

    nome = 'rs_texto_igual'
    g.marcar(nome)
    emitir_prologo_auxiliar(g, windows, 32)
    _emitir(g, '31 C0 48 39 D1')
    g.salto(nome + '_fim', 'jne')
    _emitir(g, '48 85 C9')
    g.salto(nome + '_sim', 'jz')
    _emitir(g, 'FC F3 A6')  # igualdade de bytes UTF-8; não normaliza
    g.salto(nome + '_fim', 'jne')
    g.marcar(nome + '_sim')
    _emitir(g, 'B8 01 00 00 00')
    g.marcar(nome + '_fim')
    _fechar(g, windows, nome)

    nome = 'rs_texto_escrever'
    g.marcar(nome)
    emitir_prologo_auxiliar(g, windows, 64)
    _emitir(g, '48 89 7D F8 48 89 75 F0 48 89 55 E8')
    g.marcar(nome + '_volta')
    _emitir(g, '48 83 7D E8 00')
    g.salto(nome + '_fim', 'je')
    if windows:
        _emitir(g, '48 8B 4D F8 48 8B 55 F0 4C 8B 45 E8')
        _emitir(g, '49 81 F8 00 00 10 00')
        g.salto(nome + '_limite', 'jbe')
        _emitir(g, '41 B8 00 00 10 00')
        g.marcar(nome + '_limite')
        _emitir(g, '4C 8D 4D E0 48 83 EC 30 48 C7 44 24 20 00 00 00 00')
        g.relativo(b'\xFF\x15', 'WriteFile')
        _emitir(g, '48 83 C4 30 85 C0')
        g.salto('erro_texto_saida', 'jz')
        _emitir(g, '8B 45 E0')
    else:
        _emitir(g, '48 8B 7D F8 48 8B 75 F0 48 8B 55 E8 48 81 FA 00 00 10 00')
        g.salto(nome + '_limite', 'jbe')
        _emitir(g, 'BA 00 00 10 00')
        g.marcar(nome + '_limite')
        _emitir(g, 'B8 01 00 00 00 0F 05 48 83 F8 FC')
        g.salto(nome + '_volta', 'je')
        _emitir(g, '48 85 C0')
        g.salto('erro_texto_saida', 'js')
    _emitir(g, '48 85 C0')
    g.salto('erro_texto_saida', 'jz')
    _emitir(g, '48 01 45 F0 48 29 45 E8')
    g.salto(nome + '_volta')
    g.marcar(nome + '_fim')
    _fechar(g, windows, nome)
    if ler_linha:
        emitir_leitura(g, windows)


def emitir_leitura(g, windows):
    nome = 'rs_texto_ler_linha'
    g.marcar(nome)
    # Manter RBP principal: entrada_proximo_byte usa o cache desse quadro.
    _emitir(g, '41 55 41 56 41 57 56 57 48 83 EC 40 49 89 FD')
    _emitir(g, '49 83 7D F8 00')
    g.salto('erro_valor_inativo', 'jl')
    _emitir(g, '49 C7 45 F8 00 00 00 00')
    g.marcar(nome + '_volta')
    g.chamada('entrada_proximo_byte')
    _emitir(g, '48 85 C0')
    g.salto('erro_texto_entrada', 'js')
    g.salto(nome + '_concluir', 'jz')
    _emitir(g, '41 80 FA 0A')
    g.salto(nome + '_concluir', 'je')
    _emitir(g, '44 88 54 24 28 4C 89 EF 49 8B 75 F8 48 FF C6')
    g.salto('erro_lista_memoria', 'jo')
    _emitir(g, 'BA 01 00 00 00')
    g.chamada('rs_valor_reservar')
    _emitir(g, '49 8B 75 00 49 8B 4D F8 8A 44 24 28 88 04 0E 49 FF 45 F8')
    g.salto(nome + '_volta')
    g.marcar(nome + '_concluir')
    _emitir(g, '49 8B 75 00 49 8B 55 F8 48 85 D2')
    g.salto(nome + '_validar', 'jz')
    _emitir(g, '80 7C 16 FF 0D')
    g.salto(nome + '_validar', 'jne')
    _emitir(g, '48 FF CA 49 89 55 F8')
    g.marcar(nome + '_validar')
    g.chamada('rs_validar_utf8')
    _emitir(g, '48 83 C4 40 5F 5E 41 5F 41 5E 41 5D C3')
    if windows:
        registrar_quadro_empilhado(g, nome, ['r13', 'r14', 'r15', 'rsi', 'rdi'], 64)
