"""Contrato compartilhado de armazenamento e propriedade da RS 0.42H.

A propriedade dinâmica pertence às listas tipadas, texto UTF-8 e bytes.
Texto e bytes de tamanho fixo continuam valores copiáveis. Empréstimos são
referências temporárias de parâmetros, nunca proprietários do armazenamento.
Registros com folhas proprietárias conservam sua disposição completa e
transferem todos os donos internos, sem assumir a largura de um descritor.
"""
from dataclasses import dataclass


PALAVRAS_DESCRITOR = 3
ESTADO_INATIVO = -1
DESLOCAMENTO_PONTEIRO = 0
DESLOCAMENTO_COMPRIMENTO = -8
DESLOCAMENTO_CAPACIDADE = -16
TIPO_TEXTO_DINAMICO = ('texto_dinamico', 'utf8')
TIPO_TEXTO_EMPRESTADO = ('texto_emprestado', 'utf8')
TIPO_BYTES_DINAMICOS = ('bytes_dinamicos', 'binario')
TIPO_BYTES_EMPRESTADOS = ('bytes_emprestados', 'binario')
ORIGENS_PROPRIETARIAS = ('mova_valor_dinamico', 'mova_registro_proprietario',
                        'chamada', 'retire_registro_lista')


def eh_proprietario(tipo):
    """Identifica os descritores dinâmicos com dono exclusivo disponíveis."""
    return (isinstance(tipo, tuple) and len(tipo) == 2 and tipo[0] == 'lista_dinamica'
            or tipo in (TIPO_TEXTO_DINAMICO, TIPO_BYTES_DINAMICOS))


def eh_emprestimo(tipo):
    """Identifica a referência temporária de leitura de um descritor."""
    return (isinstance(tipo, tuple) and len(tipo) == 2 and tipo[0] == 'lista_emprestada'
            or tipo in (TIPO_TEXTO_EMPRESTADO, TIPO_BYTES_EMPRESTADOS))


def eh_registro_proprietario(tipo, registros):
    """Agregado com folhas donas; não é um descritor de três palavras."""
    campos = (registros.get(tipo, ()) if isinstance(tipo, str)
              else tipo[2] if isinstance(tipo, tuple) and len(tipo) == 3
              and tipo[0] == 'registro' else ())
    return any(eh_proprietario(campo) or eh_registro_proprietario(campo, registros)
               for _, campo in campos)


def eh_valor_proprietario(tipo, registros):
    """Valores transferíveis: descritores ou agregados com donos internos."""
    return eh_proprietario(tipo) or eh_registro_proprietario(tipo, registros)


def eh_colecao_proprietaria(tipo, registros):
    return (isinstance(tipo, tuple) and len(tipo) == 2 and
            tipo[0] == 'lista_dinamica' and eh_registro_proprietario(tipo[1], registros))


def folhas_proprietarias_tipo(tipo, registros):
    """Folhas e offsets em palavras, conforme a disposição comum do agregado."""
    from .disposicao_tipos import palavras_tipo
    folhas = []
    def visitar(atual, inicio):
        if eh_proprietario(atual):
            folhas.append((inicio, atual))
            return
        campos = registros.get(atual, ()) if isinstance(atual, str) else (
            atual[2] if isinstance(atual, tuple) and atual[0] == 'registro' else ())
        deslocamento = inicio
        for _, campo in campos:
            visitar(campo, deslocamento)
            deslocamento += palavras_tipo(campo, registros)
    visitar(tipo, 0)
    return tuple(folhas)


def donos_do_agregado(nome, tipos, campos):
    """Resolve folhas proprietárias pelos aliases compartilhados do registro."""
    donos = []
    def visitar(atual):
        for filho in campos.get(atual, {}).values():
            if eh_proprietario(tipos[filho]):
                donos.append(filho)
            elif filho in campos:
                visitar(filho)
    visitar(nome)
    return tuple(donos)


def eh_texto(tipo):
    """Conteúdo UTF-8 fixo, proprietário ou emprestado; não inclui bytes."""
    return (tipo in (TIPO_TEXTO_DINAMICO, TIPO_TEXTO_EMPRESTADO)
            or isinstance(tipo, tuple) and len(tipo) == 2 and tipo[0] == 'texto')


def passo_armazenamento(tipo, registros):
    """Bytes por unidade do armazenamento apontado pelo dono ou empréstimo."""
    if tipo in (TIPO_TEXTO_DINAMICO, TIPO_TEXTO_EMPRESTADO,
                TIPO_BYTES_DINAMICOS, TIPO_BYTES_EMPRESTADOS):
        return 1
    if isinstance(tipo, tuple) and len(tipo) == 2 and tipo[0] in ('lista_dinamica', 'lista_emprestada'):
        from .disposicao_tipos import palavras_tipo
        palavras = palavras_tipo(tipo[1], registros)
        if not 1 <= palavras <= 0x0FFFFFFF:
            from .erros import ErroCompilacao
            raise ErroCompilacao('Largura do registro excede o limite de armazenamento do gerador nativo.')
        return 8 * palavras
    raise ValueError('Tipo sem armazenamento dinamico.')


def eh_bytes(tipo):
    """Dados binários arbitrários, sem conversão implícita para texto."""
    return (tipo in (TIPO_BYTES_DINAMICOS, TIPO_BYTES_EMPRESTADOS)
            or isinstance(tipo, tuple) and len(tipo) == 2 and tipo[0] == 'bytes')


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
    if eh_registro_proprietario(tipo, registros):
        classe = 'agregado_proprietario'
    return ContratoValor(classe, pode_copiar, precisa_descartar, palavras)
