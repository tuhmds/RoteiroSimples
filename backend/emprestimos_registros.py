"""Emissão de vistas de leitura por chamada, sem alocação de conteúdo."""
import struct
from compilador.disposicao_tipos import palavras_tipo
from compilador.emprestimos_registros import plano_vista, eh_registro_emprestado
from . import listas_dinamicas, valores_dinamicos


def _empilhar_bloco(g, base, palavras):
    numero = g.proxima_condicao
    g.proxima_condicao += 1
    rotulo = f'empilhar_campo_emprestado_{numero}'
    g.bytes(b'\x4C\x8D\x95' + struct.pack('<i', base))
    g.bytes(b'\xB9' + struct.pack('<I', palavras))
    g.marcar(rotulo)
    g.bytes(b'\x49\x8B\x02\x50\x49\x83\xEA\x08\xFF\xC9')
    g.salto(rotulo, 'jnz')


def empilhar(g, argumento, tipo, variaveis, windows, emitir_expressao,
             empilhar_palavras, pilha_extra):
    """A ABI da vista contém valores fixos e ponteiros para descritores.

    Elementos do heap recebem uma adaptação temporária na pilha do chamador,
    com a orientação decrescente histórica. O temporário não possui donos
    e só é alcançável durante a chamada. Registros locais dispensam adaptação.
    """
    if argumento[0] == 'var' or (argumento[0] == 'empreste_registro' and
            eh_registro_emprestado(g.tipos_atual[argumento[1]])):
        empilhar_palavras(g, variaveis, argumento[1], palavras_tipo(tipo, g.registros), windows)
        return
    if argumento[0] == 'empreste_registro_lista':
        nome, indice, reserva = argumento[1:]
        largura = palavras_tipo(tipo[1], g.registros)
        listas_dinamicas.copiar_composto(g, variaveis, reserva, nome, indice, windows,
            lambda gerador, expr, locais, alvo: emitir_expressao(
                gerador, expr, locais, alvo, pilha_extra=pilha_extra),
            largura, emprestada=g.tipos_atual[nome][0] == 'lista_emprestada')
        origem = reserva
    else:
        origem = argumento[1]
    base = valores_dinamicos.deslocamento_local(variaveis, origem, windows)
    plano = plano_vista(tipo[1], g.registros)
    # Conferir todas as folhas antes de transmitir a vista, inclusive um
    # registro parcialmente inativo obtido de armazenamento nativo.
    for offset, _, descritor in plano:
        if descritor:
            g.bytes(b'\x48\x83\xBD' + struct.pack('<i', base - 8 * (offset + 1)) + b'\x00')
            g.salto('erro_valor_inativo', 'jl')
    for offset, palavras, descritor in plano:
        campo = base - 8 * offset
        if descritor:
            g.bytes(b'\x48\x8D\x85' + struct.pack('<i', campo) + b'\x50')
        else:
            _empilhar_bloco(g, campo, palavras)
