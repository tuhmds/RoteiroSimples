"""RS 0.35: acesso binário por posição com erros recuperáveis.

Chamadas internas: RDI=caminho, RSI=buffer, RDX=bytes, RCX=posição.
Retorno: quantidade transferida >=0; -1 abrir; -2 transferência;
-3 posição/argumentos; -4 fechamento. Não há transação ou fsync.
"""
import struct
from . import politica_caminhos
from .desenrolamento_windows import (
    registrar_quadro_auxiliar, emitir_prologo_auxiliar,
    emitir_epilogo_auxiliar,
)


def bytes_nativos(g, trecho):
    g.bytes(bytes.fromhex(trecho))


def emitir_comando(g, instrucao, variaveis, tipos, windows, mensagens,
                   endereco_buffer, deslocamento_variavel, expressao):
    gravar = instrucao[0] == 'grave_trecho'
    _, caminho, nome = instrucao[:3]
    estado = instrucao[4] if gravar else instrucao[5]
    dados, comprimento, capacidade = endereco_buffer(variaveis, nome, tipos, windows)

    expressao(g, instrucao[3], variaveis, windows)
    bytes_nativos(g, '50')  # push posicao
    if gravar:
        g.bytes(b'\x48\x8B\x85' + struct.pack('<i', comprimento))
    else:
        expressao(g, instrucao[4], variaveis, windows, pilha_extra=1)
    bytes_nativos(g, '50 5A 59')  # push bytes; pop rdx, pop rcx

    ident = g.proxima_condicao
    g.proxima_condicao += 1
    fim_chamada = f'trecho_fim_chamada_{ident}'
    if not gravar:
        invalido = f'trecho_quantidade_invalida_{ident}'
        valido = f'trecho_quantidade_valida_{ident}'
        bytes_nativos(g, '48 85 D2')
        g.salto(invalido, 'js')
        g.bytes(b'\x48\x81\xFA' + struct.pack('<I', capacidade))
        g.salto(invalido, 'ja')
        g.salto(valido)
        g.marcar(invalido)
        bytes_nativos(g, '48 C7 C0 FD FF FF FF')  # -3
        g.salto(fim_chamada)
        g.marcar(valido)

    indice = len(mensagens)
    mensagens[indice] = caminho + '\x00'
    g.relativo(b'\x48\x8D\x3D', f'mensagem_{indice}')
    g.bytes(b'\x48\x8D\xB5' + struct.pack('<i', dados))
    g.chamada('rs_trecho_gravar' if gravar else 'rs_trecho_carregar')
    g.marcar(fim_chamada)

    g.bytes(b'\x48\x89\x85' + struct.pack('<i', deslocamento_variavel(variaveis, estado, windows)))
    if not gravar:
        erro = f'trecho_resultado_erro_{ident}'
        fim = f'trecho_resultado_fim_{ident}'
        bytes_nativos(g, '48 85 C0')
        g.salto(erro, 'js')
        g.bytes(b'\x48\x89\x85' + struct.pack('<i', comprimento))
        g.salto(fim)
        g.marcar(erro)
        bytes_nativos(g, '31 C0')
        g.bytes(b'\x48\x89\x85' + struct.pack('<i', comprimento))
        g.marcar(fim)


def _abrir(g, windows, gravar, erro_abrir, erro_posicao, erro_rejeitado):
    if windows:
        bytes_nativos(g, '48 8B 4D F8')
        g.bytes(b'\xBA' + struct.pack('<I', 0x40000000 if gravar else 0x80000000))
        bytes_nativos(g, '45 31 C0 45 31 C9 48 83 EC 40')
        bytes_nativos(g, 'C7 44 24 20 04 00 00 00' if gravar else
                          'C7 44 24 20 03 00 00 00') # OPEN_ALWAYS/OPEN_EXISTING
        g.bytes(b'\xC7\x44\x24\x28' + politica_caminhos.atributos_windows())
        bytes_nativos(g, '48 C7 44 24 30 00 00 00 00')
        g.relativo(b'\xFF\x15', 'CreateFileA')
        bytes_nativos(g, '48 83 C4 40 48 83 F8 FF')
        g.salto(erro_abrir, 'je')
        bytes_nativos(g, '48 89 45 D8')
        bytes_nativos(g, '48 89 C7')
        g.chamada('rs_verificar_arquivo_regular')
        bytes_nativos(g, '48 85 C0')
        g.salto(erro_rejeitado, 'jnz')  # rejeita como falha de abertura
        # HANDLE, LARGE_INTEGER deslocamento, saida nula, FILE_BEGIN
        bytes_nativos(g, '48 8B 4D D8 48 8B 55 E0 45 31 C0 45 31 C9')
        bytes_nativos(g, '48 83 EC 20')
        g.relativo(b'\xFF\x15', 'SetFilePointerEx')
        bytes_nativos(g, '48 83 C4 20 85 C0')
        g.salto(erro_posicao, 'jz')
    else:
        bytes_nativos(g, 'B8 01 01 00 00 48 C7 C7 9C FF FF FF')
        bytes_nativos(g, '48 8B 75 F8')
        g.bytes(b'\xBA' + politica_caminhos.sinalizadores_linux(
            'gravacao_posicional' if gravar else 'leitura'))
        bytes_nativos(g, '41 BA 80 01 00 00 0F 05 48 85 C0')
        g.salto(erro_abrir, 'js')
        bytes_nativos(g, '48 89 45 D8')


def _transferir(g, windows, gravar, laco, erro):
    if windows:
        bytes_nativos(g, '48 8B 4D D8 48 8B 55 F0 48 03 55 D0')
        bytes_nativos(g, '4C 8B 45 E8 4C 2B 45 D0 4C 8D 4D C8')
        bytes_nativos(g, '48 83 EC 30')
        bytes_nativos(g, '48 C7 44 24 20 00 00 00 00')
        g.relativo(b'\xFF\x15', 'WriteFile' if gravar else 'ReadFile')
        bytes_nativos(g, '48 83 C4 30 85 C0')
        g.salto(erro, 'jz')
        bytes_nativos(g, '8B 45 C8')
    else:
        bytes_nativos(g, 'B8 12 00 00 00' if gravar else 'B8 11 00 00 00')
        bytes_nativos(g, '48 8B 7D D8 48 8B 75 F0 48 03 75 D0')
        bytes_nativos(g, '48 8B 55 E8 48 2B 55 D0')
        bytes_nativos(g, '4C 8B 55 E0 4C 03 55 D0 0F 05')
        bytes_nativos(g, '48 83 F8 FC') # EINTR
        g.salto(laco, 'je')
        bytes_nativos(g, '48 85 C0')
        g.salto(erro, 'js')


def _fechar(g, windows, erro):
    if windows:
        bytes_nativos(g, '48 8B 4D D8 48 83 EC 20')
        g.relativo(b'\xFF\x15', 'CloseHandle')
        bytes_nativos(g, '48 83 C4 20 85 C0')
        g.salto(erro, 'jz')
    else:
        bytes_nativos(g, 'B8 03 00 00 00 48 8B 7D D8 0F 05 48 85 C0')
        g.salto(erro, 'js')


def _rotina(g, windows, gravar):
    nome = 'rs_trecho_gravar' if gravar else 'rs_trecho_carregar'
    laco = f'{nome}_laco'
    sucesso = f'{nome}_sucesso'
    falha_argumentos = f'{nome}_argumentos'
    falha_abertura = f'{nome}_abertura'
    falha_posicao = f'{nome}_posicao'
    falha_rejeitado = f'{nome}_rejeitado'
    falha_transferencia = f'{nome}_transferencia'
    falha_fechamento = f'{nome}_fechamento'
    fechar = f'{nome}_fechar'
    fim = f'{nome}_fim'

    g.marcar(nome)
    emitir_prologo_auxiliar(g, windows, 96)
    # nome, buffer, quantidade, posicao: -8,-16,-24,-32
    bytes_nativos(g, '48 89 7D F8 48 89 75 F0 48 89 55 E8 48 89 4D E0')
    bytes_nativos(g, '48 C7 45 D0 00 00 00 00') # progresso -48
    bytes_nativos(g, '48 83 7D E0 00')
    g.salto(falha_argumentos, 'js')
    bytes_nativos(g, '48 83 7D E8 00')
    g.salto(falha_argumentos, 'js')
    bytes_nativos(g, '48 8B 45 E0 48 03 45 E8') # posicao + tamanho
    g.salto(falha_argumentos, 'jo')

    _abrir(g, windows, gravar, falha_abertura, falha_posicao, falha_rejeitado)

    g.marcar(laco)
    bytes_nativos(g, '48 8B 45 D0 48 3B 45 E8')
    g.salto(sucesso, 'je')
    _transferir(g, windows, gravar, laco, falha_transferencia)
    bytes_nativos(g, '48 85 C0')
    g.salto(falha_transferencia if gravar else sucesso, 'jz')
    bytes_nativos(g, '48 01 45 D0')
    g.salto(laco)

    g.marcar(sucesso)
    bytes_nativos(g, '48 8B 45 D0 48 89 45 C0') # resultado -64
    g.salto(fechar)
    g.marcar(falha_transferencia)
    bytes_nativos(g, '48 C7 C0 FE FF FF FF 48 89 45 C0')
    g.salto(fechar)
    g.marcar(falha_posicao)
    bytes_nativos(g, '48 C7 C0 FD FF FF FF 48 89 45 C0')
    g.salto(fechar)
    g.marcar(falha_rejeitado)
    bytes_nativos(g, '48 C7 C0 FF FF FF FF 48 89 45 C0')
    g.salto(fechar)

    g.marcar(fechar)
    _fechar(g, windows, falha_fechamento)
    bytes_nativos(g, '48 8B 45 C0')
    g.salto(fim)
    g.marcar(falha_fechamento)
    bytes_nativos(g, '48 C7 C0 FC FF FF FF') # -4
    g.salto(fim)
    g.marcar(falha_abertura)
    bytes_nativos(g, '48 C7 C0 FF FF FF FF') # -1
    g.salto(fim)
    g.marcar(falha_argumentos)
    bytes_nativos(g, '48 C7 C0 FD FF FF FF') # -3
    g.marcar(fim)
    emitir_epilogo_auxiliar(g, windows)


def emitir_rotinas(g, windows):
    _rotina(g, windows, gravar=True)
    if windows:
        registrar_quadro_auxiliar(g, 'rs_trecho_gravar')
    _rotina(g, windows, gravar=False)
    if windows:
        registrar_quadro_auxiliar(g, 'rs_trecho_carregar')
