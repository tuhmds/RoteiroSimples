"""Contrato compartilhado de armazenamento e propriedade da RS 0.42A.

A propriedade dinâmica desta entrega pertence às listas já implementadas.
Texto e bytes de tamanho fixo continuam valores copiáveis. Empréstimos são
referências temporárias de parâmetros, nunca proprietários do armazenamento.
"""
from dataclasses import dataclass


PALAVRAS_DESCRITOR = 3
ESTADO_INATIVO = -1
DESLOCAMENTO_PONTEIRO = 0
DESLOCAMENTO_COMPRIMENTO = -8
DESLOCAMENTO_CAPACIDADE = -16


def eh_proprietario(tipo):
    """Identifica os descritores dinâmicos com dono exclusivo disponíveis."""
    return isinstance(tipo, tuple) and len(tipo) == 2 and tipo[0] == 'lista_dinamica'


def eh_emprestimo(tipo):
    """Identifica a referência temporária de leitura de um descritor."""
    return isinstance(tipo, tuple) and len(tipo) == 2 and tipo[0] == 'lista_emprestada'


def classe_valor(tipo):
    """Distingue valores copiáveis, donos, empréstimos e recursos de arquivo."""
    if eh_proprietario(tipo):
        return 'proprietario'
    if eh_emprestimo(tipo):
        return 'emprestimo'
    if tipo == 'arquivo':
        return 'recurso'
    return 'valor'


@dataclass(frozen=True)
class ContratoValor:
    """Capacidades de um tipo concreto; largura em palavras de oito bytes.

    Retransmitir um empréstimo entre parâmetros não constitui uma cópia
    implícita armazenável. Recursos de arquivo mantêm seu descarte próprio
    e não passam a admitir a movimentação de descritores desta entrega.
    """
    classe: str
    pode_copiar: bool
    precisa_descartar: bool
    palavras: int


def contrato_valor(tipo, registros=None):
    """Obtém capacidades e largura pela disposição nativa já compartilhada."""
    # A disposição usa as constantes deste módulo; resolver localmente
    # evita um ciclo de importação sem manter um segundo cálculo de tamanho.
    from .disposicao_tipos import palavras_tipo
    registros = {} if registros is None else registros
    classe = classe_valor(tipo)
    palavras = palavras_tipo(tipo, registros)
    pode_copiar = classe == 'valor'
    precisa_descartar = classe in ('proprietario', 'recurso')
    campos = (registros[tipo] if isinstance(tipo, str) and tipo in registros
              else tipo[2] if isinstance(tipo, tuple) and len(tipo) == 3
              and tipo[0] == 'registro' else ())
    for _, tipo_campo in campos:
        campo = contrato_valor(tipo_campo, registros)
        pode_copiar = pode_copiar and campo.pode_copiar
        precisa_descartar = precisa_descartar or campo.precisa_descartar
    return ContratoValor(classe, pode_copiar, precisa_descartar, palavras)
