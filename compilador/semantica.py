"""Escopos léxicos e verificação estática dos símbolos do RoteiroSimples."""
from .erros import ErroCompilacao
from .expressoes import Expressao
from .lexico import Token
from .ast import NoExpressao
from .tipos import MAX_VARIAVEIS, tipo_expressao


class ContextoSemantico:
    def __init__(self, importa_matematica=False, funcoes=None):
        self.importa_matematica = importa_matematica
        self.funcoes = funcoes or {}
        self.variaveis = {}  # nomes internos -> deslocamentos de pilha
        self.tipos = {}      # nomes internos -> tipos
        self.escopos = [{}]
        self.total_slots = 0
        self.contador = 0
        self.usou_locais = False

    def entrar_escopo(self):
        self.escopos.append({})

    def sair_escopo(self):
        if len(self.escopos) == 1:
            raise RuntimeError('Não é permitido encerrar o escopo principal.')
        self.escopos.pop()

    def declarado_neste_escopo(self, nome):
        return nome in self.escopos[-1]

    def resolver(self, nome):
        for escopo in reversed(self.escopos):
            if nome in escopo:
                return escopo[nome]
        return nome  # Produz erro normal de variável não declarada.

    def _renomear_tokens(self, partes):
        return [Token(self.resolver(str(t)), t.origem.linha, t.origem.coluna)
                if hasattr(t, 'origem') and str(t) != self.resolver(str(t))
                else t for t in partes]

    def expressao_tipada(self, partes, linha, exigir=None):
        coluna = partes[0].origem.coluna if partes and hasattr(partes[0], 'origem') else 1
        try:
            analisador = Expressao(self._renomear_tokens(partes), linha, self.variaveis, self.importa_matematica)
            analisador.tipos = self.tipos
            analisador.funcoes = self.funcoes
            arvore = analisador.analisar()
            tipo = tipo_expressao(arvore, self.tipos, linha, self.funcoes)
            if exigir is not None and tipo != exigir:
                raise ErroCompilacao(f'Linha {linha}: tipo incompatível: esperava {exigir}, recebeu {tipo}.')
        except ErroCompilacao as erro:
            mensagem = str(erro)
            prefixo = f'Linha {linha}:'
            if mensagem.startswith(prefixo):
                mensagem = f'Linha {linha}, coluna {coluna}:' + mensagem[len(prefixo):]
            raise ErroCompilacao(mensagem) from erro
        return arvore, tipo

    def registrar(self, nome, tipo, linha):
        if self.declarado_neste_escopo(nome):
            raise ErroCompilacao(f'Linha {linha}: variável {nome!r} duplicada no mesmo escopo.')
        tamanho = (tipo[2] if isinstance(tipo, tuple) and tipo[0] == 'lista'
                   else 1+(tipo[1]+7)//8 if isinstance(tipo, tuple) and tipo[0] == 'texto'
                   else 1)
        if (self.total_slots + tamanho)*8 >= 0x7FFF0000:
            raise ErroCompilacao(f'Linha {linha}: quadro local excede endereçamento de 32 bits do gerador x86-64.')
        self.contador += 1
        interno = nome if len(self.escopos) == 1 else f'__escopo_{self.contador}_{nome}'
        self.escopos[-1][nome] = interno
        self.variaveis[interno] = self.total_slots
        self.tipos[interno] = tipo
        self.total_slots += tamanho
        if len(self.escopos) > 1:
            self.usou_locais = True
        return interno
