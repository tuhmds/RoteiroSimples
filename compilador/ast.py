"""AST da RS 0.9: nos legados de tuplas, contêiner tipado de Programa."""
from dataclasses import dataclass

@dataclass
class Programa:
    instrucoes: list
    variaveis: dict
    importa_matematica: bool
    tipos: dict  # mapa de tipos verificados durante a compilação
