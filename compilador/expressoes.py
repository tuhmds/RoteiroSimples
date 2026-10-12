"""Parser de expressões (precedência e chamadas a biblioteca matematica)."""
import re
from .erros import ErroCompilacao
from .ast import NoExpressao

class Expressao:
    def __init__(self, tokens, linha, variaveis, importa):
        self.tokens, self.linha = tokens, linha
        self.variaveis, self.importa = variaveis, importa
        self.indice = 0

    def olhar(self):
        return self.tokens[self.indice] if self.indice < len(self.tokens) else None

    def consumir(self, esperado=None):
        atual = self.olhar()
        if atual is None or (esperado is not None and atual != esperado):
            raise ErroCompilacao(f"Linha {self.linha}: esperava {esperado or 'uma expressão'}.")
        self.indice += 1
        return atual

    def analisar(self):
        expr = self.comparacao()
        if self.olhar() is not None:
            raise ErroCompilacao(f"Linha {self.linha}: trecho inesperado: {self.olhar()!r}.")
        return expr

    def comparacao(self):
        expr = self.soma()
        if self.olhar() in ('==', '!=', '<', '<=', '>', '>='):
            operador = self.consumir()
            expr = NoExpressao(('comparacao', operador, expr, self.soma()), getattr(operador, 'origem', None))
        return expr

    def soma(self):
        expr = self.produto()
        while self.olhar() in ('+', '-'):
            op = self.consumir()
            expr = NoExpressao(('bin', op, expr, self.produto()), getattr(op, 'origem', None))
        return expr

    def produto(self):
        expr = self.unario()
        while self.olhar() in ('*', '/', '%'):
            op = self.consumir()
            expr = NoExpressao(('bin', op, expr, self.unario()), getattr(op, 'origem', None))
        return expr

    def unario(self):
        if self.olhar() == '-':
            operador = self.consumir('-')
            return NoExpressao(('neg', self.unario()), getattr(operador, 'origem', None))
        if self.olhar() == '+':
            self.consumir('+')
            return self.unario()
        return self.primario()

    def primario(self):
        token = self.consumir()
        if token == '(':
            expr = self.comparacao()
            self.consumir(')')
            return expr
        if token in ('verdadeiro', 'falso'):
            return NoExpressao(('logico', 1 if token == 'verdadeiro' else 0), getattr(token, 'origem', None))
        if token.isascii() and token.isdecimal():
            numero = int(token)
            if numero > (1 << 63):
                raise ErroCompilacao(f'Linha {self.linha}: número inteiro fora do limite de 64 bits.')
            return NoExpressao(('numero', numero), getattr(token, 'origem', None))
        if re.fullmatch(r'[^\W\d]\w*', token, re.UNICODE):
            if token == 'empreste' and self.olhar() == '(':
                self.consumir('(')
                nome = self.consumir()
                self.consumir(')')
                if getattr(self, 'tipos', {}).get(nome) != ('lista_dinamica', 'inteiro'):
                    raise ErroCompilacao(f'Linha {self.linha}: empreste() exige lista[] com propriedade.')
                return NoExpressao(('empreste_lista_dinamica', nome), getattr(token, 'origem', None))
            if token == 'tamanho' and self.olhar() == '(':
                self.consumir('(')
                nome = self.consumir()
                self.consumir(')')
                tipo = getattr(self, 'tipos', {}).get(nome)
                if isinstance(tipo, tuple) and tipo[0] == 'lista_dinamica':
                    return NoExpressao(('quantidade_lista_dinamica', nome), getattr(token, 'origem', None))
                if tipo == ('lista_emprestada', 'inteiro'):
                    return NoExpressao(('quantidade_lista_emprestada', nome), getattr(token, 'origem', None))
                if isinstance(tipo, tuple) and tipo[0] == 'lista':
                    return NoExpressao(('numero', tipo[2]), getattr(token, 'origem', None))
                if isinstance(tipo, tuple) and tipo[0] == 'texto':
                    return NoExpressao(('tamanho_texto', nome), getattr(token, 'origem', None))
                raise ErroCompilacao(f'Linha {self.linha}: tamanho() exige lista ou texto.')
            if token == 'capacidade' and self.olhar() == '(': 
                self.consumir('(')
                nome = self.consumir()
                self.consumir(')')
                tipo = getattr(self, 'tipos', {}).get(nome)
                if isinstance(tipo, tuple) and tipo[0] == 'lista_dinamica':
                    return NoExpressao(('capacidade_lista_dinamica', nome), getattr(token, 'origem', None))
                if tipo == ('lista_emprestada', 'inteiro'):
                    return NoExpressao(('capacidade_lista_emprestada', nome), getattr(token, 'origem', None))
                if not isinstance(tipo, tuple) or tipo[0] != 'texto':
                    raise ErroCompilacao(f'Linha {self.linha}: capacidade() exige buffer de texto ou lista dinamica.')
                return NoExpressao(('numero', tipo[1]), getattr(token, 'origem', None))
            if self.olhar() == '(' and token in getattr(self, 'funcoes', {}):
                self.consumir('(')
                argumentos = []
                if self.olhar() != ')':
                    while True:
                        argumentos.append(self.comparacao())
                        if self.olhar() != ',':
                            break
                        self.consumir(',')
                self.consumir(')')
                return NoExpressao(('chamada', str(token), tuple(argumentos)), getattr(token, 'origem', None))
            if self.olhar() == '(': 
                if not self.importa:
                    raise ErroCompilacao(f"Linha {self.linha}: use 'inclua matematica' para chamar {token}.")
                from bibliotecas.matematica import OPERACOES
                if token not in OPERACOES:
                    raise ErroCompilacao(f"Linha {self.linha}: função matemática desconhecida: {token}.")
                self.consumir('(')
                a = self.comparacao()
                self.consumir(',')
                b = self.comparacao()
                self.consumir(')')
                return NoExpressao(('bin', OPERACOES[token], a, b), getattr(token, 'origem', None))
            if token not in self.variaveis:
                raise ErroCompilacao(f"Linha {self.linha}: variável '{token}' não foi declarada.")
            if self.olhar() == '[':
                self.consumir('[')
                indice = self.comparacao()
                self.consumir(']')
                tipo = getattr(self, 'tipos', {}).get(token)
                if isinstance(tipo, tuple) and tipo[0] == 'lista_dinamica':
                    return NoExpressao(('indice_lista_dinamica', token, indice), getattr(token, 'origem', None))
                if tipo == ('lista_emprestada', 'inteiro'):
                    return NoExpressao(('indice_lista_emprestada', token, indice), getattr(token, 'origem', None))
                if not isinstance(tipo, tuple) or tipo[0] != 'lista':
                    raise ErroCompilacao(f'Linha {self.linha}: {token} não é uma lista.')
                return NoExpressao(('indice', token, indice, tipo[2]), getattr(token, 'origem', None))
            return NoExpressao(('var', token), getattr(token, 'origem', None))
        raise ErroCompilacao(f"Linha {self.linha}: expressão inválida perto de {token!r}.")
