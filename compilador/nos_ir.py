"""Representação imutável de nós da IR tipada, com origem opcional."""
from dataclasses import dataclass, field

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
    funcoes: dict = field(default_factory=dict)
    escopos_locais: bool = False


@dataclass(frozen=True)
class FuncaoIR:
    nome: str
    parametros: tuple
    retorno: str
    programa: ProgramaIR
    recursiva: bool = False


@dataclass(frozen=True)
class GrupoFuncoesIR:
    """Parte representável de um programa misto; não representa o início."""
    funcoes: dict
