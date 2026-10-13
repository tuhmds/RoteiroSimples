"""Parser de expressões (precedência e chamadas a biblioteca matematica)."""
import re
from .erros import ErroCompilacao
from .ast import NoExpressao
from .propriedade import eh_proprietario, eh_texto, TIPO_TEXTO_DINAMICO, TIPO_TEXTO_EMPRESTADO
from .propriedade import eh_bytes, TIPO_BYTES_DINAMICOS, TIPO_BYTES_EMPRESTADOS
from .propriedade import eh_registro_proprietario

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
            if token == 'mova' and self.olhar() == '(':
                self.consumir('(')
                nome = self.consumir()
                self.consumir(')')
                if eh_registro_proprietario(getattr(self, 'tipos', {}).get(nome), getattr(self, 'registros', {})):
                    return NoExpressao(('mova_registro_proprietario', str(nome)), getattr(token, 'origem', None))
                if not eh_proprietario(getattr(self, 'tipos', {}).get(nome)):
                    raise ErroCompilacao(f'Linha {self.linha}: mova(origem) exige valor dinamico proprietario com dono unico.')
                return NoExpressao(('mova_valor_dinamico', str(nome)), getattr(token, 'origem', None))
            if token == 'empreste' and self.olhar() == '(':
                self.consumir('(')
                nome = self.consumir()
                self.consumir(')')
                if getattr(self, 'tipos', {}).get(nome) == TIPO_TEXTO_DINAMICO:
                    return NoExpressao(('empreste_texto_dinamico', nome), getattr(token, 'origem', None))
                if getattr(self, 'tipos', {}).get(nome) == TIPO_BYTES_DINAMICOS:
                    return NoExpressao(('empreste_bytes_dinamicos', nome), getattr(token, 'origem', None))
                if (not isinstance(getattr(self, 'tipos', {}).get(nome), tuple) or
                        self.tipos[nome][0] != 'lista_dinamica'):
                    raise ErroCompilacao(f'Linha {self.linha}: empreste() exige lista[] com propriedade.')
                return NoExpressao(('empreste_lista_dinamica', nome), getattr(token, 'origem', None))
            if token == 'tamanho' and self.olhar() == '(':
                self.consumir('(')
                nome = self.consumir()
                self.consumir(')')
                tipo = getattr(self, 'tipos', {}).get(nome)
                if tipo in (TIPO_TEXTO_DINAMICO, TIPO_TEXTO_EMPRESTADO):
                    return NoExpressao(('tamanho_texto_dinamico', nome), getattr(token, 'origem', None))
                if tipo in (TIPO_BYTES_DINAMICOS, TIPO_BYTES_EMPRESTADOS):
                    return NoExpressao(('tamanho_bytes_dinamicos', nome), getattr(token, 'origem', None))
                if isinstance(tipo, tuple) and tipo[0] == 'lista_dinamica':
                    return NoExpressao(('quantidade_lista_dinamica', nome), getattr(token, 'origem', None))
                if isinstance(tipo, tuple) and tipo[0] == 'lista_emprestada':
                    return NoExpressao(('quantidade_lista_emprestada', nome), getattr(token, 'origem', None))
                if isinstance(tipo, tuple) and tipo[0] == 'lista':
                    return NoExpressao(('numero', tipo[2]), getattr(token, 'origem', None))
                if isinstance(tipo, tuple) and tipo[0] == 'texto':
                    return NoExpressao(('tamanho_texto', nome), getattr(token, 'origem', None))
                if isinstance(tipo, tuple) and tipo[0] == 'bytes':
                    return NoExpressao(('tamanho_bytes', nome), getattr(token, 'origem', None))
                raise ErroCompilacao(f'Linha {self.linha}: tamanho() exige lista, texto ou bytes.')
            if token == 'capacidade' and self.olhar() == '(': 
                self.consumir('(')
                nome = self.consumir()
                self.consumir(')')
                tipo = getattr(self, 'tipos', {}).get(nome)
                if tipo in (TIPO_TEXTO_DINAMICO, TIPO_TEXTO_EMPRESTADO):
                    return NoExpressao(('capacidade_texto_dinamico', nome), getattr(token, 'origem', None))
                if tipo in (TIPO_BYTES_DINAMICOS, TIPO_BYTES_EMPRESTADOS):
                    return NoExpressao(('capacidade_bytes_dinamicos', nome), getattr(token, 'origem', None))
                if isinstance(tipo, tuple) and tipo[0] == 'lista_dinamica':
                    return NoExpressao(('capacidade_lista_dinamica', nome), getattr(token, 'origem', None))
                if isinstance(tipo, tuple) and tipo[0] == 'lista_emprestada':
                    return NoExpressao(('capacidade_lista_emprestada', nome), getattr(token, 'origem', None))
                if not isinstance(tipo, tuple) or tipo[0] not in ('texto', 'bytes'):
                    raise ErroCompilacao(f'Linha {self.linha}: capacidade() exige texto, bytes ou lista dinamica.')
                return NoExpressao(('numero', tipo[1]), getattr(token, 'origem', None))
            if token in ('caracteres', 'byte_em') and self.olhar() == '(' and token not in getattr(self, 'funcoes', {}):
                self.consumir('(')
                nome = self.consumir()
                if not eh_texto(getattr(self, 'tipos', {}).get(nome)):
                    raise ErroCompilacao(f'Linha {self.linha}: {token} exige variavel de texto UTF-8.')
                if token == 'byte_em':
                    self.consumir(',')
                    indice = self.comparacao()
                    self.consumir(')')
                    return NoExpressao(('byte_texto', nome, indice), getattr(token, 'origem', None))
                self.consumir(')')
                return NoExpressao(('caracteres_texto', nome), getattr(token, 'origem', None))
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
                if isinstance(tipo, tuple) and tipo[0] == 'lista_emprestada':
                    return NoExpressao(('indice_lista_emprestada', token, indice), getattr(token, 'origem', None))
                if eh_bytes(tipo):
                    return NoExpressao(('indice_bytes', token, indice), getattr(token, 'origem', None))
                if not isinstance(tipo, tuple) or tipo[0] != 'lista':
                    raise ErroCompilacao(f'Linha {self.linha}: {token} não é uma lista ou bytes[N].')
                return NoExpressao(('indice', token, indice, tipo[2]), getattr(token, 'origem', None))
            return NoExpressao(('var', token), getattr(token, 'origem', None))
        raise ErroCompilacao(f"Linha {self.linha}: expressão inválida perto de {token!r}.")
