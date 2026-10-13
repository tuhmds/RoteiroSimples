"""Operações do descritor central de valores dinâmicos com dono único.

A representação contém ponteiro, comprimento e capacidade. O tipo determina
as unidades de tamanho e o descarte; transferência não copia o armazenamento
nem muda a ABI de chamadas da RS. Os donos são listas tipadas e texto UTF-8.
"""
import struct

from compilador.erros import ErroCompilacao
from compilador.propriedade import (
    eh_proprietario, PALAVRAS_DESCRITOR, ESTADO_INATIVO,
    DESLOCAMENTO_PONTEIRO, DESLOCAMENTO_COMPRIMENTO,
    DESLOCAMENTO_CAPACIDADE,
    passo_armazenamento, TIPO_TEXTO_DINAMICO,
)


_DESLOCAMENTOS = (DESLOCAMENTO_PONTEIRO, DESLOCAMENTO_COMPRIMENTO,
                  DESLOCAMENTO_CAPACIDADE)


def deslocamento_local(variaveis, nome, windows):
    """Preserva a posição histórica dos locais nos dois alvos nativos."""
    return -(16 + variaveis[nome] * 8) if windows else -(8 + variaveis[nome] * 8)


def criar_vazio(g, variaveis, nome, windows):
    base = deslocamento_local(variaveis, nome, windows)
    g.bytes(b'\x31\xC0')
    for posicao in _DESLOCAMENTOS:
        g.bytes(b'\x48\x89\x85' + struct.pack('<i', base + posicao))


def inativar(g, variaveis, nome, windows):
    """Retira a propriedade do local sem liberar a memória transferida."""
    base = deslocamento_local(variaveis, nome, windows)
    g.bytes(b'\x31\xC0')
    for posicao in (DESLOCAMENTO_PONTEIRO, DESLOCAMENTO_CAPACIDADE):
        g.bytes(b'\x48\x89\x85' + struct.pack('<i', base + posicao))
    g.bytes(b'\x48\xC7\x85' + struct.pack('<i', base + DESLOCAMENTO_COMPRIMENTO)
            + struct.pack('<i', ESTADO_INATIVO))


def inicializar_inativos(g, variaveis, tipos, windows):
    for nome, tipo in tipos.items():
        if eh_proprietario(tipo):
            inativar(g, variaveis, nome, windows)


def verificar_vivo(g, variaveis, nome, windows, erro='erro_lista_liberada'):
    if getattr(g, 'tipos_atual', {}).get(nome) == TIPO_TEXTO_DINAMICO:
        erro = 'erro_valor_inativo'
    base = deslocamento_local(variaveis, nome, windows)
    g.bytes(b'\x48\x8B\x85' + struct.pack('<i', base + DESLOCAMENTO_COMPRIMENTO))
    g.bytes(b'\x48\x85\xC0')
    g.salto(erro, 'js')


def endereco_descritor(g, variaveis, nome, windows):
    g.bytes(b'\x48\x8D\xBD' + struct.pack('<i', deslocamento_local(
        variaveis, nome, windows)))


def liberar(g, variaveis, nome, windows, explicito=False):
    tipo = _exigir_proprietario(g, nome)
    if explicito:
        verificar_vivo(g, variaveis, nome, windows)
    endereco_descritor(g, variaveis, nome, windows)
    g.bytes(b'\xBE' + struct.pack('<I', passo_armazenamento(tipo, g.registros)))
    g.chamada('rs_valor_liberar_descritor')


def mover(g, variaveis, destino, origem, windows):
    tipo = _exigir_proprietario(g, destino)
    if _exigir_proprietario(g, origem) != tipo or destino == origem:
        raise ErroCompilacao('Movimento exige donos distintos do mesmo tipo.')
    endereco_descritor(g, variaveis, destino, windows)
    g.bytes(b'\x48\x83\xEC\x10\x48\x89\x3C\x24')
    endereco_descritor(g, variaveis, origem, windows)
    g.bytes(b'\x48\x89\xFE\x48\x8B\x3C\x24')
    g.bytes(b'\xBA' + struct.pack('<I', passo_armazenamento(tipo, g.registros)))
    g.chamada('rs_valor_mover_descritor')
    g.bytes(b'\x48\x83\xC4\x10')


def liberar_todos(g, variaveis, tipos, windows, preservar_retorno=False):
    donos = [nome for nome, tipo in tipos.items() if eh_proprietario(tipo)]
    if not donos:
        return
    if preservar_retorno:
        g.bytes(b'\x50\x48\x83\xEC\x08')
    for nome in reversed(donos):
        liberar(g, variaveis, nome, windows)
    if preservar_retorno:
        g.bytes(b'\x48\x83\xC4\x08\x58')


def _exigir_proprietario(g, nome):
    tipo = getattr(g, 'tipos_atual', {}).get(nome)
    if not eh_proprietario(tipo):
        raise ErroCompilacao('Transferencia nativa exige valor dinamico proprietario.')
    if PALAVRAS_DESCRITOR != 3:
        raise ErroCompilacao('Descritor dinamico mudou: revisar a ABI de transferencia.')
    return tipo


def empilhar_transferencia(g, variaveis, origem, windows):
    """Transfere as três palavras para um parâmetro proprietário da chamada."""
    _exigir_proprietario(g, origem)
    verificar_vivo(g, variaveis, origem, windows)
    base = deslocamento_local(variaveis, origem, windows)
    for posicao in _DESLOCAMENTOS:
        g.bytes(b'\x48\x8B\x85' + struct.pack('<i', base + posicao) + b'\x50')
    # Invalidar antes dos argumentos seguintes torna a ordem de avaliação
    # explícita e impede que uma segunda transferência duplique o dono.
    inativar(g, variaveis, origem, windows)


def transferir_para_retorno(g, variaveis, origem, windows):
    """Entrega o descritor ao destino oculto e inativa o dono antes do descarte."""
    _exigir_proprietario(g, origem)
    verificar_vivo(g, variaveis, origem, windows)
    base = deslocamento_local(variaveis, origem, windows)
    g.bytes(b'\x4C\x8B\x5D' + bytes((80 if windows else 24,)))
    for posicao in _DESLOCAMENTOS:
        g.bytes(b'\x48\x8B\x85' + struct.pack('<i', base + posicao))
        if posicao:
            g.bytes(b'\x49\x89\x43' + struct.pack('<b', posicao))
        else:
            g.bytes(b'\x49\x89\x03')
    inativar(g, variaveis, origem, windows)
