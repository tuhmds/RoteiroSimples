"""API legada compatível; implementações agora residem em compilador/."""
from compilador.erros import ErroCompilacao
from compilador.ast import Programa
from compilador.expressoes import Expressao
from compilador.lexico import REGEX, tokens
from compilador.tipos import MAX_VARIAVEIS, tipo_expressao
from compilador.parser import analisar_programa

__all__ = ('ErroCompilacao', 'Programa', 'Expressao', 'REGEX', 'tokens',
           'MAX_VARIAVEIS', 'tipo_expressao', 'analisar_programa')
