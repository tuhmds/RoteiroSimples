"""Analisador do RoteiroSimples 0.4 (sem execução em Python)."""
import json
import re
from dataclasses import dataclass


class ErroCompilacao(Exception):
    """Erro de escrita ou uso da linguagem, em português brasileiro."""


@dataclass
class Programa:
    instrucoes: list
    variaveis: dict
    importa_matematica: bool


REGEX = re.compile(r'\s+|"(?:\\.|[^"\\])*"|\d+|[^\W\d]\w*|==|!=|<=|>=|[()+*/%=,;{}<>!-]|.', re.UNICODE)


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
            expr = ('comparacao', operador, expr, self.soma())
        return expr

    def soma(self):
        expr = self.produto()
        while self.olhar() in ('+', '-'):
            op = self.consumir()
            expr = ('bin', op, expr, self.produto())
        return expr

    def produto(self):
        expr = self.unario()
        while self.olhar() in ('*', '/', '%'):
            op = self.consumir()
            expr = ('bin', op, expr, self.unario())
        return expr

    def unario(self):
        if self.olhar() == '-':
            self.consumir('-')
            return ('neg', self.unario())
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
        if token.isascii() and token.isdecimal():
            numero = int(token)
            if numero > (1 << 63):
                raise ErroCompilacao(f'Linha {self.linha}: número inteiro fora do limite de 64 bits.')
            return ('numero', numero)
        if re.fullmatch(r'[^\W\d]\w*', token, re.UNICODE):
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
                return ('bin', OPERACOES[token], a, b)
            if token not in self.variaveis:
                raise ErroCompilacao(f"Linha {self.linha}: variável '{token}' não foi declarada.")
            return ('var', token)
        raise ErroCompilacao(f"Linha {self.linha}: expressão inválida perto de {token!r}.")


def tokens(linha, numero):
    # Comentários são aceitos fora de strings.
    corte, aspas, escape = len(linha), False, False
    for i, ch in enumerate(linha):
        if ch == '"' and not escape:
            aspas = not aspas
        elif ch == '/' and not aspas and linha[i:i+2] == '//':
            corte = i
            break
        escape = ch == '\\' and not escape
    linha = linha[:corte]
    encontrados = []
    for achado in REGEX.finditer(linha):
        valor = achado.group()
        if valor.isspace():
            continue
        if valor.startswith('//'):
            break
        if len(valor) == 1 and valor not in '+-*/%=,;{}()<>!' and not (valor.isdecimal() or valor.isalpha()):
            raise ErroCompilacao(f"Linha {numero}: caractere inválido: {valor!r}.")
        encontrados.append(valor)
    return encontrados


def analisar_programa(fonte):
    linhas = [(n, tokens(l, n)) for n, l in enumerate(fonte.splitlines(), 1)]
    linhas = [(n, t) for n, t in linhas if t]
    importa = False
    if linhas and linhas[0][1] == ['inclua', 'matematica']:
        importa = True
        linhas.pop(0)
    if not linhas or linhas[0][1] != ['início', '{']:
        raise ErroCompilacao("O programa deve começar com 'início {' (após os 'inclua').")
    # Aceita tanto '} senão {' quanto '}' seguido de 'senão {' na linha seguinte.
    normalizadas = []
    for n, t in linhas[1:]:
        if t == ['}', 'senão', '{']:
            normalizadas.extend([(n, ['}']), (n, ['senão', '{'])])
        else:
            normalizadas.append((n, t))
    variaveis = {}
    reservadas = {'início', 'seja', 'escreva', 'inclua', 'se', 'senão', 'enquanto', 'pare', 'continue'}

    def bloco(i, profundidade=0, em_laco=False):
        instrucoes = []
        while i < len(normalizadas):
            n, t = normalizadas[i]
            if t == ['}']:
                return instrucoes, i + 1
            if t[-1] == ';':
                t = t[:-1]
            if not t:
                i += 1
                continue
            if len(t) >= 3 and t[0] == 'se' and t[-1] == '{':
                cond = Expressao(t[1:-1], n, variaveis, importa).analisar()
                verdadeiro, i = bloco(i+1, profundidade+1, em_laco)
                falso = []
                if i < len(normalizadas) and normalizadas[i][1] == ['senão', '{']:
                    falso, i = bloco(i+1, profundidade+1, em_laco)
                instrucoes.append(('se', cond, verdadeiro, falso))
                continue
            if len(t) >= 3 and t[0] == 'enquanto' and t[-1] == '{':
                cond = Expressao(t[1:-1], n, variaveis, importa).analisar()
                corpo, i = bloco(i+1, profundidade+1, True)
                instrucoes.append(('enquanto', cond, corpo))
                continue
            if t in (['pare'], ['continue']):
                if not em_laco:
                    raise ErroCompilacao(f"Linha {n}: '{t[0]}' só pode ser usado dentro de um laço enquanto.")
                instrucoes.append((t[0],))
                i += 1
                continue
            if t[:2] == ['escreva', '('] and t[-1] == ')':
                expr = t[2:-1]
                if len(expr) == 1 and expr[0].startswith('"'):
                    try:
                        valor = json.loads(expr[0])
                    except (ValueError, UnicodeError) as exc:
                        raise ErroCompilacao(f'Linha {n}: texto inválido.') from exc
                    instrucoes.append(('texto', valor + '\n'))
                else:
                    instrucoes.append(('imprima_num', Expressao(expr, n, variaveis, importa).analisar()))
            elif t[0] == 'seja' and len(t) >= 4 and t[2] == '=':
                if profundidade:
                    raise ErroCompilacao(f'Linha {n}: declare variáveis antes dos blocos de decisão ou repetição nesta versão.')
                nome = t[1]
                if not re.fullmatch(r'[^\W\d]\w*', nome, re.UNICODE):
                    raise ErroCompilacao(f'Linha {n}: nome de variável inválido.')
                if nome in variaveis or nome in reservadas:
                    raise ErroCompilacao(f"Linha {n}: variável '{nome}' duplicada ou reservada.")
                expr = Expressao(t[3:], n, variaveis, importa).analisar()
                variaveis[nome] = len(variaveis)
                instrucoes.append(('atribua', nome, expr))
            elif len(t) >= 3 and t[1] == '=':
                nome = t[0]
                if nome not in variaveis:
                    raise ErroCompilacao(f"Linha {n}: variável '{nome}' não foi declarada.")
                instrucoes.append(('atribua', nome, Expressao(t[2:], n, variaveis, importa).analisar()))
            else:
                raise ErroCompilacao(f'Linha {n}: instrução desconhecida ou incompleta.')
            i += 1
        raise ErroCompilacao('Bloco sem fechamento: faltou uma linha com } .')

    instrucoes, proxima = bloco(0)
    if proxima != len(normalizadas):
        n, _ = normalizadas[proxima]
        raise ErroCompilacao(f'Linha {n}: conteúdo após o fim do programa.')
    if not instrucoes:
        raise ErroCompilacao('Escreva pelo menos uma instrução dentro de início.')
    return Programa(instrucoes, variaveis, importa)
