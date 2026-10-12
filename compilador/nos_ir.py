"""Representação imutável de nós da IR tipada, com origem opcional."""
from dataclasses import dataclass

MINIMO = -(1 << 63)
MAXIMO = (1 << 63) - 1


@dataclass(frozen=True)
class ExpressaoIR:
    tipo: str
    operacao: str
    valor: object = None
    filhos: tuple = ()
    origem: object = None


@dataclass(frozen=True)
class InstrucaoIR:
    operacao: str
    argumentos: tuple
    origem: object = None


@dataclass(frozen=True)
class ProgramaIR:
    instrucoes: tuple
    tipos: dict
    variaveis: dict
    importa_matematica: bool
