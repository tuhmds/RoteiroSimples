"""Tokenizador: palavras reservadas e identificadores ASCII, textos UTF-8."""
import re
from .erros import ErroCompilacao

REGEX = re.compile(r'\s+|"(?:\\.|[^"\\])*"|\d+|[^\W\d]\w*|==|!=|<=|>=|[()+*/%=,;{}<>!:-]|.', re.UNICODE)

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
        if not valor.startswith('"') and not valor.isascii():
            raise ErroCompilacao(
                f"Linha {numero}: comando ou identificador com caractere nao ASCII: {valor!r}. "
                "Escreva comandos e nomes sem acentos (ex.: inicio, senao, preco)."
            )
        if valor.startswith('//'):
            break
        if len(valor) == 1 and valor not in '+-*/%=,;{}()<>!:' and not (valor.isdecimal() or valor.isalpha()):
            raise ErroCompilacao(f"Linha {numero}: caractere inválido: {valor!r}.")
        encontrados.append(valor)
    return encontrados
