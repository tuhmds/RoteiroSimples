"""Listas dinâmicas nativas da RS — propriedade única, sem empréstimos.

Descritor por proprietário no quadro de execução:
[rbp+base] ponteiro, [rbp+base-8] quantidade, [rbp+base-16] capacidade.
Cada elemento ocupa um inteiro de 64 bits. Ao criar, a lista é vazia.
A memória cresce geometricamente e é devolvida ao sistema operacional.
"""
import struct

TIPO_LISTA_DINAMICA = ('lista_dinamica', 'inteiro')


def deslocamento(variaveis, nome, windows):
    return -(16 + variaveis[nome]*8) if windows else -(8 + variaveis[nome]*8)


def criar(g, variaveis, nome, windows):
    base = deslocamento(variaveis, nome, windows)
    g.bytes(b'\x31\xC0')
    for pos in (base, base-8, base-16):
        g.bytes(b'\x48\x89\x85' + struct.pack('<i', pos))


def inicializar_inativas(g, variaveis, tipos, windows):
    """Marca descritores não alcançados como inativos na entrada."""
    for nome, tipo in tipos.items():
        if tipo != TIPO_LISTA_DINAMICA:
            continue
        base = deslocamento(variaveis, nome, windows)
        g.bytes(b'\x31\xC0')
        g.bytes(b'\x48\x89\x85' + struct.pack('<i', base))
        g.bytes(b'\x48\x89\x85' + struct.pack('<i', base - 16))
        g.bytes(b'\x48\xC7\x85' + struct.pack('<i', base - 8) + b'\xFF\xFF\xFF\xFF')


def mover(g, variaveis, destino, origem, windows):
    endereco(g, variaveis, destino, windows)
    g.bytes(b'\x57')  # destino salvo no topo da pilha
    endereco(g, variaveis, origem, windows)
    g.bytes(b'\x48\x89\xFE\x5F')  # rsi=origem; rdi=destino
    g.chamada('rs_lista_mover_descritor')


def endereco(g, variaveis, nome, windows):
    g.bytes(b'\x48\x8D\xBD' + struct.pack('<i', deslocamento(variaveis, nome, windows)))


def verificar_viva(g, variaveis, nome, windows):
    base = deslocamento(variaveis, nome, windows)
    g.bytes(b'\x48\x8B\x85' + struct.pack('<i', base-8))
    g.bytes(b'\x48\x85\xC0')
    g.salto('erro_lista_liberada', 'js')


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
    base = deslocamento(variaveis, nome, windows)
    g.bytes(b'\x48\x8B\x95' + struct.pack('<i', base))
    g.bytes(b'\x48\x89\x04\xCA')  # mov [rdx+rcx*8],rax


def acrescentar(g, variaveis, nome, valor, windows, emitir_expressao):
    # Avaliar o elemento primeiro. A rotina verifica validade e capacidade.
    emitir_expressao(g, valor, variaveis, windows)
    g.bytes(b'\x48\x89\xC6')  # mov rsi,rax
    endereco(g, variaveis, nome, windows)  # mov rdi,endereço descritor
    g.chamada('rs_lista_acrescentar')


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


def liberar(g, variaveis, nome, windows, explicito=False):
    if explicito:
        verificar_viva(g, variaveis, nome, windows)
    endereco(g, variaveis, nome, windows)
    g.chamada('rs_lista_liberar_descritor')


def liberar_todas(g, variaveis, tipos, windows, preservar_retorno=False):
    proprietarias = [nome for nome, tipo in tipos.items() if tipo == TIPO_LISTA_DINAMICA]
    if not proprietarias:
        return
    if preservar_retorno:
        g.bytes(b'\x50\x48\x83\xEC\x08')  # salva rax, alinha chamadas
    for nome in proprietarias:
        liberar(g, variaveis, nome, windows)
    if preservar_retorno:
        g.bytes(b'\x48\x83\xC4\x08\x58')


def emitir_rotinas(g, windows):
    """Emite as três rotinas nativas e valida chamadas das APIs do SO."""
    g.marcar('rs_lista_alocar')
    if windows:
        # Entrada: RDI=tamanho em bytes; saída: RAX=ponteiro.
        g.bytes(b'\x48\x89\xFA')     # mov rdx,rdi
        g.bytes(b'\x31\xC9')         # xor ecx,ecx
        g.bytes(b'\x41\xB8\x00\x30\x00\x00')  # r8d=MEM_COMMIT|MEM_RESERVE
        g.bytes(b'\x41\xB9\x04\x00\x00\x00')  # r9d=PAGE_READWRITE
        g.bytes(b'\x48\x83\xEC\x28')         # 32 bytes shadow, alinhamento
        g.relativo(b'\xFF\x15', 'VirtualAlloc')
        g.bytes(b'\x48\x83\xC4\x28')
        g.bytes(b'\x48\x85\xC0')
        g.salto('erro_lista_memoria', 'jz')
    else:
        # Linux mmap(0, bytes, PROT_READ|WRITE, MAP_PRIVATE|ANON, -1, 0).
        g.bytes(b'\x48\x89\xFE')  # rsi=rdi tamanho
        g.bytes(b'\x31\xFF')      # rdi=0 endereço
        g.bytes(b'\xBA\x03\x00\x00\x00')  # edx=3
        g.bytes(b'\x41\xBA\x22\x00\x00\x00')  # r10d=0x22
        g.bytes(b'\x41\xB8\xFF\xFF\xFF\xFF')  # r8d=-1
        g.bytes(b'\x45\x31\xC9')  # r9d=0
        g.bytes(b'\xB8\x09\x00\x00\x00\x0F\x05')  # mmap
        g.bytes(b'\x48\x3D\x01\xF0\xFF\xFF') # cmp rax,-4095 (sign extended)
        # Trata retornos negativos da faixa de errno como falha.
        g.salto('erro_lista_memoria', 'jae')
    g.bytes(b'\xC3')

    g.marcar('rs_lista_desalocar')
    if windows:
        # Entrada: RDI=ponteiro; RSI=bytes (Windows ignora tamanho).
        g.bytes(b'\x48\x89\xF9')   # mov rcx,rdi
        g.bytes(b'\x31\xD2')       # xor edx,edx
        g.bytes(b'\x41\xB8\x00\x80\x00\x00')  # r8d=MEM_RELEASE
        g.bytes(b'\x48\x83\xEC\x28')
        g.relativo(b'\xFF\x15', 'VirtualFree')
        g.bytes(b'\x48\x83\xC4\x28')
        g.bytes(b'\x85\xC0')
        g.salto('erro_lista_memoria', 'jz')
    else:
        g.bytes(b'\xB8\x0B\x00\x00\x00\x0F\x05')  # munmap
        g.bytes(b'\x48\x85\xC0')
        g.salto('erro_lista_memoria', 'jnz')
    g.bytes(b'\xC3')

    g.marcar('rs_lista_liberar_descritor')
    # RDI aponta para [ponteiro, quantidade, capacidade] em ordem descendente.
    # Se explicitamente liberada, quantidade=-1; saída normal sempre limpa.
    g.bytes(b'\x55\x48\x89\xE5\x48\x83\xEC\x20')
    g.bytes(b'\x48\x89\x7D\xF8')  # [rbp-8]=descritor
    fim = 'rs_lista_liberar_descritor_fim'
    marcar = 'rs_lista_liberar_descritor_marcar'
    g.bytes(b'\x48\x8B\x47\xF8')  # len=[rdi-8]
    g.bytes(b'\x48\x83\xF8\xFF')  # cmp rax,-1 (já liberada)
    g.salto(fim, 'je')
    g.bytes(b'\x48\x8B\x3F')  # rdi=[rdi] = ponteiro
    g.bytes(b'\x48\x85\xFF')
    g.salto(marcar, 'jz')
    g.bytes(b'\x48\x8B\x75\xF8')  # rsi=[rbp-8] = descritor
    g.bytes(b'\x48\x8B\x76\xF0')  # rsi=capacidade
    g.bytes(b'\x48\xC1\xE6\x03')  # bytes=cap*8
    g.chamada('rs_lista_desalocar')
    g.marcar(marcar)
    g.bytes(b'\x48\x8B\x7D\xF8')  # rdi=descritor
    g.bytes(b'\x31\xC0\x48\x89\x07\x48\x89\x47\xF0')
    g.bytes(b'\x48\xC7\xC0\xFF\xFF\xFF\xFF')
    g.bytes(b'\x48\x89\x47\xF8')
    g.marcar(fim)
    g.bytes(b'\x48\x89\xEC\x5D\xC3')

    g.marcar('rs_lista_mover_descritor')
    # RDI=destino, RSI=origem. Verifica antes de liberar o destino.
    g.bytes(b'\x55\x48\x89\xE5\x48\x83\xEC\x20')
    g.bytes(b'\x48\x89\x7D\xF8\x48\x89\x75\xF0')
    g.bytes(b'\x48\x8B\x46\xF8\x48\x85\xC0')
    g.salto('erro_lista_liberada', 'js')
    g.chamada('rs_lista_liberar_descritor')
    g.bytes(b'\x48\x8B\x7D\xF8\x48\x8B\x75\xF0')
    g.bytes(b'\x48\x8B\x06\x48\x89\x07')
    g.bytes(b'\x48\x8B\x46\xF8\x48\x89\x47\xF8')
    g.bytes(b'\x48\x8B\x46\xF0\x48\x89\x47\xF0')
    g.bytes(b'\x31\xC0\x48\x89\x06\x48\x89\x46\xF0')
    g.bytes(b'\x48\xC7\x46\xF8\xFF\xFF\xFF\xFF')
    g.bytes(b'\x48\x89\xEC\x5D\xC3')

    g.marcar('rs_lista_acrescentar')
    # RDI descritor, RSI valor. Não utiliza registradores persistentes do programa.
    g.bytes(b'\x55\x48\x89\xE5\x48\x83\xEC\x40')
    g.bytes(b'\x48\x89\x7D\xF8\x48\x89\x75\xF0')  # descritor e valor
    g.bytes(b'\x4C\x8B\x55\xF8')                 # r10=descritor
    g.bytes(b'\x49\x8B\x42\xF8')                 # rax=[r10-8]=quantidade
    g.bytes(b'\x48\x85\xC0')
    g.salto('erro_lista_liberada','js')
    g.bytes(b'\x49\x3B\x42\xF0')                 # cmp rax,[r10-16]=capacidade
    g.salto('rs_lista_acrescentar_gravar','jl')
    # Nova capacidade: quatro elementos ou duplicar.
    g.bytes(b'\x49\x8B\x42\xF0')                 # rax=cap
    g.bytes(b'\x48\x85\xC0')
    g.salto('rs_lista_acrescentar_inicio','jz')
    g.bytes(b'\x48\xD1\xE0')                     # shl rax,1
    g.salto('erro_lista_memoria','jo')
    g.salto('rs_lista_acrescentar_capacidade')
    g.marcar('rs_lista_acrescentar_inicio')
    g.bytes(b'\xB8\x04\x00\x00\x00')
    g.marcar('rs_lista_acrescentar_capacidade')
    g.bytes(b'\x48\x89\x45\xE0')                 # salva nova capacidade [rbp-32]
    g.bytes(b'\x48\x6B\xF8\x08')                 # imul rdi,rax,8; verifica transbordamento
    g.salto('erro_lista_memoria','jo')
    g.chamada('rs_lista_alocar')
    g.bytes(b'\x48\x89\x45\xE8')                 # salva novo ponteiro [rbp-24]
    g.bytes(b'\x4C\x8B\x55\xF8')                 # descritor
    g.bytes(b'\x49\x8B\x72\x00')                 # rsi=ponteiro antigo
    g.bytes(b'\x48\x85\xF6')                     # test rsi,rsi
    g.salto('rs_lista_acrescentar_atualizar','jz')
    g.bytes(b'\x48\x8B\x7D\xE8')                 # rdi=ponteiro novo
    g.bytes(b'\x49\x8B\x4A\xF8')                 # rcx=quantidade
    g.bytes(b'\xFC\xF3\x48\xA5')                 # cld; rep movsq
    # Devolve bloco antigo após copiar.
    g.bytes(b'\x4C\x8B\x55\xF8')
    g.bytes(b'\x49\x8B\x3A')                     # rdi=ponteiro antigo
    g.bytes(b'\x49\x8B\x72\xF0')                 # rsi=capacidade antiga
    g.bytes(b'\x48\xC1\xE6\x03')                 # shl rsi,3
    g.chamada('rs_lista_desalocar')
    g.marcar('rs_lista_acrescentar_atualizar')
    g.bytes(b'\x4C\x8B\x55\xF8')
    g.bytes(b'\x48\x8B\x45\xE8')
    g.bytes(b'\x49\x89\x02')                     # mov [r10],rax
    g.bytes(b'\x48\x8B\x45\xE0')
    g.bytes(b'\x49\x89\x42\xF0')                 # mov [r10-16],rax
    g.marcar('rs_lista_acrescentar_gravar')
    g.bytes(b'\x4C\x8B\x55\xF8')
    g.bytes(b'\x49\x8B\x0A')                     # rcx=[r10]=ponteiro
    g.bytes(b'\x49\x8B\x42\xF8')                 # rax=quantidade
    g.bytes(b'\x48\x8B\x55\xF0')                 # rdx=valor
    g.bytes(b'\x48\x89\x14\xC1')                 # [rcx+rax*8]=rdx
    g.bytes(b'\x49\xFF\x42\xF8')                 # inc qword [r10-8]
    g.bytes(b'\x48\x89\xEC\x5D\xC3')
