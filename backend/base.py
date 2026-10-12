"""Gerador de bytes e referências relativas, comum aos formatos executáveis."""
import struct

def alinhar(valor, multiplo):
    return (valor + multiplo - 1) // multiplo * multiplo


class Emissor:
    def __init__(self):
        self.codigo = bytearray()
        self.pendencias = []

    def bytes(self, dados):
        self.codigo += dados

    def relativo(self, prefixo, identificador):
        self.bytes(prefixo)
        posicao = len(self.codigo)
        self.bytes(b"\x00" * 4)
        self.pendencias.append((posicao, identificador))

    def resolver(self, base_codigo_rva, enderecos_rva):
        for posicao, identificador in self.pendencias:
            if identificador not in enderecos_rva:
                raise ValueError(f"Referência interna desconhecida: {identificador}")
            delta = enderecos_rva[identificador] - (base_codigo_rva + posicao + 4)
            struct.pack_into('<i', self.codigo, posicao, delta)
