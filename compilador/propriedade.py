"""Contrato compartilhado de armazenamento e propriedade da RS 0.42A.

A propriedade dinâmica pertence às listas tipadas e ao texto UTF-8.
Texto e bytes de tamanho fixo continuam valores copiáveis. Empréstimos são
referências temporárias de parâmetros, nunca proprietários do armazenamento.
"""
from dataclasses import dataclass


PALAVRAS_DESCRITOR = 3
ESTADO_INATIVO = -1
DESLOCAMENTO_PONTEIRO = 0
DESLOCAMENTO_COMPRIMENTO = -8
DESLOCAMENTO_CAPACIDADE = -16
TIPO_TEXTO_DINAMICO = ('texto_dinamico', 'utf8')
TIPO_TEXTO_EMPRESTADO = ('texto_emprestado', 'utf8')


def eh_proprietario(tipo):
    """Identifica os descritores dinâmicos com dono exclusivo disponíveis."""
    return (isinstance(tipo, tuple) and len(tipo) == 2 and tipo[0] == 'lista_dinamica'
            or tipo == TIPO_TEXTO_DINAMICO)


def eh_emprestimo(tipo):
    """Identifica a referência temporária de leitura de um descritor."""
    return (isinstance(tipo, tuple) and len(tipo) == 2 and tipo[0] == 'lista_emprestada'
            or tipo == TIPO_TEXTO_EMPRESTADO)


def eh_texto(tipo):
    """Conteúdo UTF-8 fixo, proprietário ou emprestado; não inclui bytes."""
    return (tipo in (TIPO_TEXTO_DINAMICO, TIPO_TEXTO_EMPRESTADO)
            or isinstance(tipo, tuple) and len(tipo) == 2 and tipo[0] == 'texto')


def passo_armazenamento(tipo, registros):
    """Bytes por unidade do comprimento/capacidade no armazenamento dinâmico."""
    if tipo == TIPO_TEXTO_DINAMICO:
        return 1
    if isinstance(tipo, tuple) and len(tipo) == 2 and tipo[0] == 'lista_dinamica':
        from .disposicao_tipos import palavras_tipo
        palavras = palavras_tipo(tipo[1], registros)
        if not 1 <= palavras <= 0x0FFFFFFF:
            from .erros import ErroCompilacao
            raise ErroCompilacao('Largura do registro excede o limite de armazenamento do gerador nativo.')
        return 8 * palavras
    raise ValueError('Tipo sem armazenamento dinamico proprietario.')


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
