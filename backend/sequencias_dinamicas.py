"""Vistas e cópia explícita de sequências de bytes com memória compartilhada.

UTF-8 é validado pelo módulo de texto antes de chamar a rotina comum.
Sequências binárias preservam qualquer byte, incluindo NUL e UTF-8 inválido.
"""
import struct
from compilador.propriedade import eh_proprietario, eh_emprestimo
from . import valores_dinamicos
from .desenrolamento_windows import (
    emitir_prologo_auxiliar, emitir_epilogo_auxiliar, registrar_quadro_auxiliar,
)


def _emitir(g, codigo):
    g.bytes(bytes.fromhex(codigo))


def _fechar(g, windows, nome):
    emitir_epilogo_auxiliar(g, windows)
    if windows:
        registrar_quadro_auxiliar(g, nome)


def vista(g, variaveis, tipos, nome, windows):
    """RSI=bytes, RDX=comprimento, R8=descritor ou zero para sequência fixa."""
    tipo = tipos[nome]
    base = valores_dinamicos.deslocamento_local(variaveis, nome, windows)
    if eh_proprietario(tipo) or eh_emprestimo(tipo):
        g.bytes((b'\x4C\x8D\x85' if eh_proprietario(tipo) else b'\x4C\x8B\x85')
                + struct.pack('<i', base))
        _emitir(g, '49 83 78 F8 00')
        g.salto('erro_valor_inativo', 'jl')
        _emitir(g, '49 8B 30 49 8B 50 F8')
    else:
        dados = base - 8 * ((tipo[1] + 7) // 8)
        g.bytes(b'\x48\x8D\xB5' + struct.pack('<i', dados))
        g.bytes(b'\x48\x8B\x95' + struct.pack('<i', base))
        _emitir(g, '45 31 C0')


def emitir_rotinas(g, windows):
    nome = 'rs_sequencia_modificar'
    g.marcar(nome)
    emitir_prologo_auxiliar(g, windows, 64)
    # Preservar vistas: fonte pode ser o próprio destino realocado.
    _emitir(g, '48 89 7D F8 48 89 75 F0 48 89 55 E8 48 89 4D E0 4C 89 45 D8')
    _emitir(g, '48 83 7F F8 00')
    g.salto('erro_valor_inativo', 'jl')
    _emitir(g, '48 8B 7D F8 31 F6 48 83 7D E0 00')
    g.salto(nome + '_comprimento', 'je')
    _emitir(g, '48 8B 77 F8')
    g.marcar(nome + '_comprimento')
    _emitir(g, '48 89 75 D0 48 03 75 E8')
    g.salto('erro_lista_memoria', 'jo')
    _emitir(g, '48 89 75 C8 BA 01 00 00 00')
    g.chamada('rs_valor_reservar')
    _emitir(g, '48 8B 75 F0 4C 8B 45 D8 4D 85 C0')
    g.salto(nome + '_copiar', 'jz')
    _emitir(g, '49 8B 30')
    g.marcar(nome + '_copiar')
    _emitir(g, '4C 8B 55 F8 49 8B 3A 48 03 7D D0 48 8B 4D E8 FC F3 A4')
    _emitir(g, '48 8B 45 C8 49 89 42 F8')
    _fechar(g, windows, nome)

