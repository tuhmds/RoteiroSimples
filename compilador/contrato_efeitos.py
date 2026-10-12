"""Modelo único de efeitos, propriedade e ordenação observável da RS.

Este contrato descreve efeitos conservadores. Não autoriza a aplicação
automática de otimizações nem a eliminação de verificações de execução.
Usado tanto pela análise IR legada quanto pela análise da árvore sintática.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class Efeitos:
    """Resumo cumulativo das dependências observáveis de uma operação.

    Os cinco primeiros campos preservam o contrato da análise IR anterior.
    Campos seguintes representam arquivos, controle e propriedade.
    """
    leituras: frozenset = frozenset()
    escritas: frozenset = frozenset()
    entrada: bool = False
    saida: bool = False
    pode_falhar: bool = False
    arquivos: bool = False
    propriedade: tuple = ()
    encerra: bool = False
    controle: bool = False
    desconhecido: bool = False

    def combinar(self, outro):
        return Efeitos(
            self.leituras | outro.leituras,
            self.escritas | outro.escritas,
            self.entrada or outro.entrada,
            self.saida or outro.saida,
            self.pode_falhar or outro.pode_falhar,
            self.arquivos or outro.arquivos,
            self.propriedade + outro.propriedade,
            self.encerra or outro.encerra,
            self.controle or outro.controle,
            self.desconhecido or outro.desconhecido,
        )

    def para_dict(self):
        """Compatibilidade da análise de memória versionada preexistente."""
        return {
            'leituras': sorted(self.leituras),
            'escritas': sorted(self.escritas),
            'entrada': self.entrada,
            'saida': self.saida,
            'pode_falhar': self.pode_falhar,
        }

    def para_dict_completo(self):
        """Visão pública do contrato expandido, sempre em português."""
        return {
            **self.para_dict(),
            'arquivos': self.arquivos,
            'propriedade': list(self.propriedade),
            'encerra': self.encerra,
            'controle': self.controle,
            'desconhecido': self.desconhecido,
            'barreira_de_reordenacao': self.barreira_de_reordenacao,
        }

    @property
    def barreira_de_reordenacao(self):
        return bool(
            self.entrada or self.saida or self.pode_falhar or self.arquivos
            or self.propriedade or self.encerra or self.controle
            or self.desconhecido
        )


def podem_trocar_de_ordem(primeiro, segundo):
    """Condição necessária e conservadora de independência de duas operações.

    NÃO considera custos, disponibilidade de recursos ou efeitos não
    modelados de chamadas externas; na dúvida as operações não são
    permutáveis. Isto é ferramenta de análise, NÃO um novo otimizador.
    """
    if primeiro.barreira_de_reordenacao or segundo.barreira_de_reordenacao:
        return False
    if primeiro.escritas & (segundo.escritas | segundo.leituras):
        return False
    if segundo.escritas & primeiro.leituras:
        return False
    return True
