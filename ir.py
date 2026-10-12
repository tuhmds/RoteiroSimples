"""Compatibilidade pública de importação: implementação em compilador/."""
from compilador.ir import (
    MINIMO, MAXIMO, ExpressaoIR, InstrucaoIR, ProgramaIR, converter_expressao,
    dobrar_constantes, converter_instrucao, construir_ir, expressao_para_ast,
    instrucao_para_ast, programa_para_backend, formatar_ir,
)
