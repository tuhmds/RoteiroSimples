"""Listas dinâmicas nativas da RS com propriedade única e empréstimos de leitura.

Descritor por proprietário no quadro de execução:
[rbp+base] ponteiro, [rbp+base-8] quantidade, [rbp+base-16] capacidade.
A largura de cada elemento segue a disposição de seu tipo. A lista nasce vazia.
A memória cresce geometricamente e é devolvida ao sistema operacional.
"""
import struct
from compilador.propriedade import passo_armazenamento
from . import valores_dinamicos
from .desenrolamento_windows import (
    registrar_quadro_auxiliar, registrar_quadro_empilhado,
    emitir_prologo_auxiliar, emitir_epilogo_auxiliar,
)

TIPO_LISTA_DINAMICA = ('lista_dinamica', 'inteiro')


def eh_lista_dinamica(tipo):
    return isinstance(tipo, tuple) and len(tipo) == 2 and tipo[0] == 'lista_dinamica'


def largura_elemento(g, tipo):
    """Usa o mesmo contrato de disposicao da pilha e dos registros."""
    return passo_armazenamento(tipo, g.registros) // 8


def deslocamento(variaveis, nome, windows):
    return valores_dinamicos.deslocamento_local(variaveis, nome, windows)


def criar(g, variaveis, nome, windows):
    valores_dinamicos.criar_vazio(g, variaveis, nome, windows)


def inicializar_inativas(g, variaveis, tipos, windows):
    """Marca descritores não alcançados como inativos na entrada."""
    valores_dinamicos.inicializar_inativos(g, variaveis, tipos, windows)


def mover(g, variaveis, destino, origem, windows, largura=1):
    endereco(g, variaveis, destino, windows)
    g.bytes(b'\x48\x83\xEC\x10\x48\x89\x3C\x24')  # reserva 16, salva destino
    endereco(g, variaveis, origem, windows)
    g.bytes(b'\x48\x89\xFE\x48\x8B\x3C\x24')  # RSI=origem; RDI=destino
    g.bytes(b'\xBA' + struct.pack('<I', largura))
    g.chamada('rs_lista_mover_descritor')
    g.bytes(b'\x48\x83\xC4\x10')


def endereco(g, variaveis, nome, windows):
    valores_dinamicos.endereco_descritor(g, variaveis, nome, windows)


def verificar_viva(g, variaveis, nome, windows):
    valores_dinamicos.verificar_vivo(g, variaveis, nome, windows)


def emprestar(g, variaveis, nome, windows):
    """Em RAX, endereço temporário do descritor do proprietário vivo."""
    verificar_viva(g, variaveis, nome, windows)
    base = deslocamento(variaveis, nome, windows)
    g.bytes(b'\x48\x8D\x85' + struct.pack('<i', base))


def quantidade_emprestada(g, variaveis, nome, windows, capacidade=False):
    base = deslocamento(variaveis, nome, windows)
    g.bytes(b'\x48\x8B\x95' + struct.pack('<i', base))   # descritor em RDX
    g.bytes(b'\x48\x8B\x42\xF8')                           # quantidade em RAX
    g.bytes(b'\x48\x85\xC0')
    g.salto('erro_lista_liberada', 'js')
    if capacidade:
        g.bytes(b'\x48\x8B\x42\xF0')                       # capacidade em RAX


def quantidade(g, variaveis, nome, windows, capacidade=False):
    verificar_viva(g, variaveis, nome, windows)
    if capacidade:
        base = deslocamento(variaveis, nome, windows)
        g.bytes(b'\x48\x8B\x85' + struct.pack('<i', base-16))


def indice(g, variaveis, nome, expressao_indice, windows, emitir_expressao, emprestada=False):
    """Retorna índice validado em RAX, sem ler ponteiros potencialmente nulos."""
    emitir_expressao(g, expressao_indice, variaveis, windows)
    g.bytes(b'\x48\x85\xC0')
    g.salto('erro_indice_lista', 'js')
    base = deslocamento(variaveis, nome, windows)
    if emprestada:
        g.bytes(b'\x48\x8B\x95' + struct.pack('<i', base))  # rdx=descritor emprestado
    else:
        g.bytes(b'\x48\x8D\x95' + struct.pack('<i', base))  # rdx=descritor proprietario
    g.bytes(b'\x48\x8B\x4A\xF8') # rcx=quantidade
    g.bytes(b'\x48\x85\xC9')
    g.salto('erro_lista_liberada', 'js')
    g.bytes(b'\x48\x39\xC8')  # cmp rax,rcx
    g.salto('erro_indice_lista', 'jge')


def ler_indice(g, variaveis, nome, expressao_indice, windows, emitir_expressao, emprestada=False):
    indice(g, variaveis, nome, expressao_indice, windows, emitir_expressao, emprestada)
    g.bytes(b'\x48\x8B\x12')   # rdx=[rdx]=ponteiro para os elementos
    g.bytes(b'\x48\x8B\x04\xC2')  # mov rax,[rdx+rax*8]


def escrever_indice(g, variaveis, nome, expressao_indice, valor, windows, emitir_expressao):
    indice(g, variaveis, nome, expressao_indice, windows, emitir_expressao)
    g.bytes(b'\x50')  # índice em pilha
    emitir_expressao(g, valor, variaveis, windows, pilha_extra=1)
    g.bytes(b'\x59')  # rcx=índice
    # O valor pode consumir a própria lista em uma chamada. O índice já
    # foi avaliado; conferir novamente a vida do dono sem repetir efeitos
    # impede escrita através do ponteiro invalidado durante o valor.
    g.bytes(b'\x50')  # conserva o valor enquanto a validação usa RAX
    verificar_viva(g, variaveis, nome, windows)
    g.bytes(b'\x58')
    base = deslocamento(variaveis, nome, windows)
    g.bytes(b'\x48\x8B\x95' + struct.pack('<i', base))
    g.bytes(b'\x48\x89\x04\xCA')  # mov [rdx+rcx*8],rax


def acrescentar(g, variaveis, nome, valor, windows, emitir_expressao, largura=1):
    if largura == 1:
        emitir_expressao(g, valor, variaveis, windows)
        g.bytes(b'\x48\x83\xEC\x10\x48\x89\x04\x24')  # temporário alinhado
        g.bytes(b'\x48\x89\xE6')                        # RSI=&valor
    else:
        if valor[0] != 'var':
            raise ValueError('Elemento composto requer origem com endereço.')
        g.bytes(b'\x48\x8D\xB5' + struct.pack('<i', deslocamento(variaveis, valor[1], windows)))
    endereco(g, variaveis, nome, windows)
    g.bytes(b'\xBA' + struct.pack('<I', largura))
    g.chamada('rs_lista_acrescentar')
    if largura == 1:
        g.bytes(b'\x48\x83\xC4\x10')


def endereco_elemento(g, variaveis, nome, indice_expressao, windows, emitir_expressao,
                      largura, emprestada=False):
    """RAX aponta ao primeiro campo do elemento, com índice validado."""
    indice(g, variaveis, nome, indice_expressao, windows, emitir_expressao, emprestada)
    g.bytes(b'\x48\x69\xC0' + struct.pack('<i', largura * 8))
    g.bytes(b'\x48\x8B\x12\x48\x01\xD0')  # heap + indice * bytes


def copiar_composto(g, variaveis, destino, nome, indice_expressao,
                    windows, emitir_expressao, largura, emprestada=False):
    """Copia heap crescente -> quadro local decrescente."""
    endereco_elemento(g, variaveis, nome, indice_expressao, windows, emitir_expressao,
                      largura, emprestada)
    g.bytes(b'\x48\x89\xC6')  # RSI=primeira palavra no heap
    g.bytes(b'\x48\x8D\xBD' + struct.pack('<i', deslocamento(variaveis, destino, windows)))
    g.bytes(b'\xB9' + struct.pack('<I', largura))
    numero = g.proxima_condicao
    g.proxima_condicao += 1
    rotulo = f'copiar_lista_para_registro_{numero}'
    g.marcar(rotulo)
    g.bytes(b'\x48\x8B\x06\x48\x89\x07')  # mov rax,[rsi];mov [rdi],rax
    g.bytes(b'\x48\x83\xC6\x08\x48\x83\xEF\x08') # +8, -8
    g.bytes(b'\xFF\xC9')
    g.salto(rotulo, 'jnz')


def escrever_composto(g, variaveis, nome, indice_expressao, valor,
                     windows, emitir_expressao, largura):
    """Copia quadro local decrescente -> heap crescente."""
    endereco_elemento(g, variaveis, nome, indice_expressao, windows, emitir_expressao, largura)
    g.bytes(b'\x48\x89\xC7')  # RDI=primeira palavra no heap
    g.bytes(b'\x48\x8D\xB5' + struct.pack('<i', deslocamento(variaveis, valor[1], windows)))
    g.bytes(b'\xB9' + struct.pack('<I', largura))
    numero = g.proxima_condicao
    g.proxima_condicao += 1
    rotulo = f'copiar_registro_para_lista_{numero}'
    g.marcar(rotulo)
    g.bytes(b'\x48\x8B\x06\x48\x89\x07')
    g.bytes(b'\x48\x83\xEE\x08\x48\x83\xC7\x08') # -8,+8
    g.bytes(b'\xFF\xC9')
    g.salto(rotulo, 'jnz')


def limpar(g, variaveis, nome, windows):
    verificar_viva(g, variaveis, nome, windows)
    base = deslocamento(variaveis, nome, windows)
    g.bytes(b'\x31\xC0')
    g.bytes(b'\x48\x89\x85' + struct.pack('<i', base-8))


def retirar(g, variaveis, nome, windows):
    base = deslocamento(variaveis, nome, windows)
    quantidade(g, variaveis, nome, windows)
    g.bytes(b'\x48\x85\xC0')
    g.salto('erro_indice_lista', 'jz')
    g.bytes(b'\x48\xFF\x8D' + struct.pack('<i', base-8)) # dec qword [rbp+base-8]


def liberar(g, variaveis, nome, windows, explicito=False, largura=1):
    if explicito:
        verificar_viva(g, variaveis, nome, windows)
    endereco(g, variaveis, nome, windows)
    g.bytes(b'\xBE' + struct.pack('<I', largura))
    g.chamada('rs_lista_liberar_descritor')


def liberar_todas(g, variaveis, tipos, windows, preservar_retorno=False):
    proprietarias = [nome for nome, tipo in tipos.items() if eh_lista_dinamica(tipo)]
    if not proprietarias:
        return
    if preservar_retorno:
        g.bytes(b'\x50\x48\x83\xEC\x08')  # salva rax, alinha chamadas
    for nome in proprietarias:
        liberar(g, variaveis, nome, windows, largura=largura_elemento(g, tipos[nome]))
    if preservar_retorno:
        g.bytes(b'\x48\x83\xC4\x08\x58')


def emitir_rotinas(g, windows):
    """Emite as cinco rotinas nativas e valida chamadas das APIs do SO."""
    from . import memoria_dinamica
    memoria_dinamica.emitir_rotinas(g, windows)

    # Adaptadores históricos: a largura de lista continua em palavras.
    # O gerenciador comum recebe bytes por unidade do descritor.
    for nome, registrador, rotina in (
        ('rs_lista_liberar_descritor', b'\x48\x6B\xF6\x08', 'rs_valor_liberar_descritor'),
        ('rs_lista_mover_descritor', b'\x48\x6B\xD2\x08', 'rs_valor_mover_descritor'),
    ):
        g.marcar(nome)
        emitir_prologo_auxiliar(g, windows, 32)
        g.bytes(registrador)
        g.salto('erro_lista_memoria', 'jo')
        g.chamada(rotina)
        emitir_epilogo_auxiliar(g, windows)
        if windows:
            registrar_quadro_auxiliar(g, nome)

    g.marcar('rs_lista_acrescentar')
    # RDI=descritor, RSI=ponteiro fonte, RDX=palavras por elemento.
    emitir_prologo_auxiliar(g, windows, 64)
    g.bytes(b'\x48\x89\x7D\xF8\x48\x89\x75\xF0\x48\x89\x55\xD8')
    g.bytes(b'\x4C\x8B\x55\xF8')
    g.bytes(b'\x49\x8B\x42\xF8') # quantidade
    g.bytes(b'\x48\x85\xC0')
    g.salto('erro_lista_liberada','js')
    # A mesma reserva é usada pelo texto dinâmico, com passo de um byte.
    g.bytes(b'\x48\x89\xC6\x48\xFF\xC6')  # minimo = quantidade+1
    g.salto('erro_lista_memoria', 'jo')
    g.bytes(b'\x48\x8B\x7D\xF8\x48\x8B\x55\xD8')
    g.bytes(b'\x48\x6B\xD2\x08')  # passo = palavras * 8
    g.salto('erro_lista_memoria', 'jo')
    g.chamada('rs_valor_reservar')
    g.marcar('rs_lista_acrescentar_gravar')
    g.bytes(b'\x4C\x8B\x55\xF8')
    g.bytes(b'\x49\x8B\x3A') # destino base heap
    g.bytes(b'\x49\x8B\x42\xF8') # quantidade
    g.bytes(b'\x48\x0F\xAF\x45\xD8') # * largura
    g.salto('erro_lista_memoria','jo')
    g.bytes(b'\x48\x8D\x3C\xC7') # lea rdi,[rdi+rax*8]
    g.bytes(b'\x48\x8B\x75\xF0') # fonte primeiro campo
    g.bytes(b'\x48\x8B\x4D\xD8') # largura palavras
    numero = 'rs_lista_acrescentar_copiar_elemento'
    g.marcar(numero)
    g.bytes(b'\x48\x8B\x06\x48\x89\x07')
    g.bytes(b'\x48\x83\xEE\x08\x48\x83\xC7\x08')
    g.bytes(b'\xFF\xC9')
    g.salto(numero,'jnz')
    g.bytes(b'\x4C\x8B\x55\xF8')
    g.bytes(b'\x49\xFF\x42\xF8')
    emitir_epilogo_auxiliar(g, windows)
    if windows:
        registrar_quadro_auxiliar(g, 'rs_lista_acrescentar')
