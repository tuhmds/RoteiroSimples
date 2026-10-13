"""Disposição de vistas temporárias de registros, sem donos armazenáveis."""
from .propriedade import (eh_proprietario, TIPO_TEXTO_DINAMICO,
                         TIPO_TEXTO_EMPRESTADO, TIPO_BYTES_DINAMICOS,
                         TIPO_BYTES_EMPRESTADOS)


def eh_registro_emprestado(tipo):
    return isinstance(tipo, tuple) and tipo[0] == 'registro_emprestado'


def tipo_campo_emprestado(tipo, registros):
    if tipo == TIPO_TEXTO_DINAMICO:
        return TIPO_TEXTO_EMPRESTADO
    if tipo == TIPO_BYTES_DINAMICOS:
        return TIPO_BYTES_EMPRESTADOS
    if eh_proprietario(tipo):
        return ('lista_emprestada', tipo[1])
    if isinstance(tipo, str) and tipo in registros:
        return ('registro_emprestado', tipo)
    return tipo


def campos_emprestados(nome, registros):
    return tuple((campo, tipo_campo_emprestado(tipo, registros))
                 for campo, tipo in registros[nome])


def plano_vista(nome, registros):
    """Folhas (offset original, palavras, descritor), em ordem de campos.

    A vista transmite escalares e buffers fixos por valor. Cada folha dona
    transmite somente o endereço de um descritor temporário decrescente.
    Conteúdo no heap não é copiado, movido, alocado ou liberado.
    """
    from .disposicao_tipos import palavras_tipo
    folhas = []
    def visitar(atual, inicio):
        deslocamento = inicio
        for _, tipo in registros[atual]:
            palavras = palavras_tipo(tipo, registros)
            if isinstance(tipo, str) and tipo in registros:
                visitar(tipo, deslocamento)
            else:
                folhas.append((deslocamento, palavras, eh_proprietario(tipo)))
            deslocamento += palavras
    visitar(nome, 0)
    return tuple(folhas)
