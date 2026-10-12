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
        self.total_slots = 0

    def expressao_tipada(self, partes, linha, exigir=None):
        coluna = partes[0].origem.coluna if partes and hasattr(partes[0], 'origem') else 1
        try:
            analisador = Expressao(partes, linha, self.variaveis, self.importa_matematica)
            analisador.tipos = self.tipos
            arvore = analisador.analisar()
            tipo = tipo_expressao(arvore, self.tipos, linha)
            if exigir is not None and tipo != exigir:
                raise ErroCompilacao(
                    f'Linha {linha}: tipo incompatível: esperava {exigir}, recebeu {tipo}.')
        except ErroCompilacao as erro:
            mensagem = str(erro)
            prefixo = f'Linha {linha}:'
            if mensagem.startswith(prefixo):
                mensagem = f'Linha {linha}, coluna {coluna}:' + mensagem[len(prefixo):]
            raise ErroCompilacao(mensagem) from erro
        return arvore, tipo

    def registrar(self, nome, tipo, linha):
        tamanho = tipo[2] if isinstance(tipo, tuple) and tipo[0] == 'lista' else 1
        if self.total_slots + tamanho > MAX_VARIAVEIS:
            raise ErroCompilacao(
                f'Linha {linha}: limite temporário de {MAX_VARIAVEIS} posições de memória excedido.')
        self.variaveis[nome] = self.total_slots
        self.tipos[nome] = tipo
        self.total_slots += tamanho
