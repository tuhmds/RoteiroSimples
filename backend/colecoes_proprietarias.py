"""Coleções de agregados donos: transferência e descarte nativos por tipo."""
import struct
from compilador.erros import ErroCompilacao
from compilador.propriedade import (
    eh_colecao_proprietaria, folhas_proprietarias_tipo, passo_armazenamento,
)
from .desenrolamento_windows import (
    emitir_prologo_auxiliar, emitir_epilogo_auxiliar, registrar_quadro_auxiliar,
)


def rotulo(tipo, operacao):
    return f'rs_colecao_{operacao}_{tipo[1]}'


def liberador(tipo, registros):
    return rotulo(tipo, 'liberar') if eh_colecao_proprietaria(tipo, registros) else 'rs_valor_liberar_descritor'


def preparar(g, tipos):
    g.colecoes_proprietarias = {}
    pendentes = list(tipos)
    while pendentes:
        tipo = pendentes.pop()
        if eh_colecao_proprietaria(tipo, g.registros) and tipo[1] not in g.colecoes_proprietarias:
            g.colecoes_proprietarias[tipo[1]] = tipo
            pendentes.extend(campo for _, campo in folhas_proprietarias_tipo(tipo[1], g.registros))
    profundidades = {}
    def profundidade(tipo, caminho):
        if tipo[1] in caminho or len(caminho) >= 32:
            raise ErroCompilacao('Colecoes proprietarias admitem ate 32 niveis, sem tipos recursivos.')
        if tipo[1] in profundidades:
            return profundidades[tipo[1]]
        filhos = []
        for _, folha in folhas_proprietarias_tipo(tipo[1], g.registros):
            if eh_colecao_proprietaria(folha, g.registros):
                filhos.append(profundidade(folha, caminho + (tipo[1],)))
        total = 1 + max(filhos, default=0)
        if total > 32:
            raise ErroCompilacao('Colecoes proprietarias admitem ate 32 niveis, sem tipos recursivos.')
        profundidades[tipo[1]] = total
        return total
    for tipo in g.colecoes_proprietarias.values():
        profundidade(tipo, ())


def _emitir(g, codigo):
    g.bytes(bytes.fromhex(codigo))


def _terminar(g, windows, nome):
    emitir_epilogo_auxiliar(g, windows)
    if windows:
        registrar_quadro_auxiliar(g, nome)


def _validar_indice(g):
    # RDI=&descritor decrescente; RSI=índice assinado.
    _emitir(g, '48 8B 47 F8 48 85 C0')
    g.salto('erro_lista_liberada', 'js')
    _emitir(g, '48 85 F6')
    g.salto('erro_indice_lista', 'js')
    _emitir(g, '48 39 C6')
    g.salto('erro_indice_lista', 'jge')


def _endereco_indice(g, passo):
    _emitir(g, '48 89 F0')
    g.bytes(b'\x48\x69\xC0' + struct.pack('<i', passo))
    g.salto('erro_lista_memoria', 'jo')
    _emitir(g, '48 03 07')


def emitir_rotinas(g, windows):
    for tipo in g.colecoes_proprietarias.values():
        passo = passo_armazenamento(tipo, g.registros)
        largura = passo // 8
        nome = rotulo(tipo, 'descartar_elemento')
        g.marcar(nome)
        emitir_prologo_auxiliar(g, windows, 64)
        _emitir(g, '48 89 7D F8')  # salva endereço crescente do elemento
        for offset, folha in folhas_proprietarias_tipo(tipo[1], g.registros):
            _emitir(g, '4C 8B 55 F8')
            # A pilha é decrescente e o heap é crescente. A vista temporária
            # adapta as três palavras sem assumir outra disposição do tipo.
            for indice, local in enumerate((-16, -24, -32)):
                g.bytes(b'\x49\x8B\x82' + struct.pack('<i', offset * 8 + indice * 8))
                g.bytes(b'\x48\x89\x45' + struct.pack('<b', local))
            _emitir(g, '48 8D 7D F0')
            g.bytes(b'\xBE' + struct.pack('<I', passo_armazenamento(folha, g.registros)))
            g.chamada(liberador(folha, g.registros))
            _emitir(g, '4C 8B 55 F8')
            for indice, local in enumerate((-16, -24, -32)):
                g.bytes(b'\x48\x8B\x45' + struct.pack('<b', local))
                g.bytes(b'\x49\x89\x82' + struct.pack('<i', offset * 8 + indice * 8))
        _terminar(g, windows, nome)

        nome = rotulo(tipo, 'limpar')
        g.marcar(nome)
        emitir_prologo_auxiliar(g, windows, 32)
        _emitir(g, '48 89 7D F8 48 C7 45 F0 00 00 00 00 48 83 7F F8 00')
        g.salto(nome + '_fim', 'jl')
        g.marcar(nome + '_proximo')
        _emitir(g, '4C 8B 55 F8 48 8B 45 F0 49 3B 42 F8')
        g.salto(nome + '_zerar', 'jge')
        g.bytes(b'\x48\x69\xC0' + struct.pack('<i', passo))
        g.salto('erro_lista_memoria', 'jo')
        _emitir(g, '49 03 02 48 89 C7')
        g.chamada(rotulo(tipo, 'descartar_elemento'))
        _emitir(g, '48 FF 45 F0')
        g.salto(nome + '_proximo')
        g.marcar(nome + '_zerar')
        _emitir(g, '4C 8B 55 F8 49 C7 42 F8 00 00 00 00')
        g.marcar(nome + '_fim')
        _terminar(g, windows, nome)

        nome = rotulo(tipo, 'liberar')
        g.marcar(nome)
        emitir_prologo_auxiliar(g, windows, 32)
        _emitir(g, '48 89 7D F8')
        g.chamada(rotulo(tipo, 'limpar'))
        _emitir(g, '48 8B 7D F8')
        g.bytes(b'\xBE' + struct.pack('<I', passo))
        g.chamada('rs_valor_liberar_descritor')
        _terminar(g, windows, nome)

        nome = rotulo(tipo, 'substituir')
        g.marcar(nome)
        emitir_prologo_auxiliar(g, windows, 32)
        _emitir(g, '48 89 55 F0')  # fonte local permanece viva até a cópia
        _validar_indice(g)
        _endereco_indice(g, passo)
        _emitir(g, '48 89 45 E8 48 89 C7')
        g.chamada(rotulo(tipo, 'descartar_elemento'))
        _emitir(g, '48 8B 7D E8 48 8B 75 F0')
        g.bytes(b'\xB9' + struct.pack('<I', largura))
        g.marcar(nome + '_copiar')
        _emitir(g, '48 8B 06 48 89 07 48 83 EE 08 48 83 C7 08 FF C9')
        g.salto(nome + '_copiar', 'jnz')
        _terminar(g, windows, nome)

        nome = rotulo(tipo, 'retirar')
        g.marcar(nome)
        emitir_prologo_auxiliar(g, windows, 64)
        # Destino nulo descarta o elemento (remova_ultimo); outro destino
        # recebe o agregado completo, em disposição local decrescente.
        _emitir(g, '48 89 7D F8 48 89 75 F0 48 89 55 E8')
        _validar_indice(g)
        _endereco_indice(g, passo)
        _emitir(g, '48 89 45 E0 48 85 D2')
        g.salto(nome + '_descartar', 'jz')
        _emitir(g, '48 89 C6 48 89 D7')
        g.bytes(b'\xB9' + struct.pack('<I', largura))
        g.marcar(nome + '_copiar')
        _emitir(g, '48 8B 06 48 89 07 48 83 C6 08 48 83 EF 08 FF C9')
        g.salto(nome + '_copiar', 'jnz')
        g.salto(nome + '_deslocar')
        g.marcar(nome + '_descartar')
        _emitir(g, '48 89 C7')
        g.chamada(rotulo(tipo, 'descartar_elemento'))
        g.marcar(nome + '_deslocar')
        _emitir(g, '4C 8B 55 F8 49 8B 42 F8 48 FF C8 49 89 42 F8 48 89 C1 48 2B 4D F0')
        g.bytes(b'\x48\x69\xC9' + struct.pack('<i', largura))
        g.salto('erro_lista_memoria', 'jo')
        _emitir(g, '48 8B 7D E0')
        g.bytes(b'\x48\x8D\xB7' + struct.pack('<i', passo))
        _emitir(g, 'FC F3 48 A5')  # desloca palavras de 64 bits para baixo
        _emitir(g, '4C 8B 55 F8 49 8B 42 F8')
        g.bytes(b'\x48\x69\xC0' + struct.pack('<i', passo))
        g.salto('erro_lista_memoria', 'jo')
        _emitir(g, '49 03 02 48 89 C7 31 C0')
        g.bytes(b'\xB9' + struct.pack('<I', largura))
        _emitir(g, 'FC F3 48 AB')  # limpa palavras de 64 bits da antiga última posição
        _terminar(g, windows, nome)
