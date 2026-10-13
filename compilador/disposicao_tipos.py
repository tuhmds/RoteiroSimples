"""Contrato de disposicao nativa dos tipos da RS em palavras de 64 bits.

Quadros na pilha e elementos dinamicos no heap compartilham a MESMA
representacao de tamanho, inclusive campos compostos e bytes[N].
"""
from .propriedade import PALAVRAS_DESCRITOR, eh_proprietario, eh_emprestimo


def palavras_tipo(tipo, registros):
    """Devolve a quantidade de palavras de oito bytes de um valor completo."""
    if isinstance(tipo, str):
        if tipo in registros:
            return sum(palavras_tipo(campo, registros)
                       for _, campo in registros[tipo])
        if tipo in ('inteiro', 'logico', 'arquivo'):
            return 1
        raise ValueError(f'Tipo desconhecido para disposicao de memoria: {tipo!r}.')

    if not isinstance(tipo, tuple) or not tipo:
        raise ValueError(f'Tipo de memoria invalido: {tipo!r}.')

    categoria = tipo[0]
    if categoria == 'registro' and len(tipo) == 3:
        return sum(palavras_tipo(campo, registros) for _, campo in tipo[2])
    if eh_proprietario(tipo):
        return PALAVRAS_DESCRITOR
    if eh_emprestimo(tipo):
        return 1  # endereco do descritor de origem
    if categoria == 'lista' and len(tipo) == 3:
        return tipo[2]  # lista fixa de inteiros
    if categoria in ('texto', 'bytes') and len(tipo) == 2:
        return 1 + (tipo[1] + 7) // 8  # comprimento e conteudo arredondado
    raise ValueError(f'Categoria de memoria desconhecida: {tipo!r}.')
