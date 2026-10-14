"""Observacao opcional de etapas; nunca integra os executaveis gerados."""
from contextlib import contextmanager, nullcontext
import time


class MedicaoCompilacao:
    def __init__(self):
        self.etapas = {}
        self.contadores = {}
        self._pilha = []

    @contextmanager
    def etapa(self, nome):
        quadro = [nome, time.perf_counter_ns(), 0]
        self._pilha.append(quadro)
        try:
            yield
        finally:
            decorrido = time.perf_counter_ns() - quadro[1]
            assert self._pilha.pop() is quadro
            if self._pilha:
                self._pilha[-1][2] += decorrido
            registro = self.etapas.setdefault(nome, {'chamadas': 0, 'total_ns': 0, 'proprio_ns': 0})
            registro['chamadas'] += 1
            registro['total_ns'] += decorrido
            registro['proprio_ns'] += decorrido - quadro[2]

    def contar(self, nome, valor):
        self.contadores[nome] = self.contadores.get(nome, 0) + valor

    def resumo(self):
        if self._pilha:
            raise ValueError('Nao finalizar medicao com etapa aberta.')
        return {'etapas': {nome: dict(registro) for nome, registro in self.etapas.items()},
                'contadores': dict(self.contadores)}


def etapa(medidor, nome):
    return nullcontext() if medidor is None else medidor.etapa(nome)
