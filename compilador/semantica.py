"""Escopo de símbolos e semântica de expressões antes da geração nativa.

Ainda não há escopos léxicos reais; declarações são locais ao programa.
"""
from .erros import ErroCompilacao
from .expressoes import Expressao
from .tipos import MAX_VARIAVEIS, tipo_expressao


class ContextoSemantico:
    def __init__(self, importa_matematica=False):
        self.importa_matematica = importa_matematica
        self.variaveis = {}
        self.tipos = {}

    def expressao_tipada(self, partes, linha, exigir=None):
        arvore = Expressao(partes, linha, self.variaveis,
                            self.importa_matematica).analisar()
        tipo = tipo_expressao(arvore, self.tipos, linha)
        if exigir is not None and tipo != exigir:
            raise ErroCompilacao(
                f'Linha {linha}: tipo incompatível: esperava {exigir}, recebeu {tipo}.')
        return arvore, tipo

    def registrar(self, nome, tipo, linha):
        if len(self.variaveis) >= MAX_VARIAVEIS:
            raise ErroCompilacao(
                f'Linha {linha}: limite temporário de {MAX_VARIAVEIS} variáveis locais excedido.')
        self.variaveis[nome] = len(self.variaveis)
        self.tipos[nome] = tipo
