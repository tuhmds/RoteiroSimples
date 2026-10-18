"""Memória nativa compartilhada: reserva, crescimento, liberação e movimento.

Descritores armazenam ponteiro, comprimento e capacidade. O passo em bytes
separa unidades de listas e de texto, sem criar outro gerenciador de memória.
Os nomes antigos dos alocadores são preservados no código e nos ensaios.
"""
from .desenrolamento_windows import (
    emitir_prologo_auxiliar, emitir_epilogo_auxiliar,
    registrar_quadro_auxiliar, registrar_quadro_empilhado,
)


def emitir_alocadores(g, windows):
    g.marcar('rs_lista_alocar')
    if windows:
        # Entrada: RDI=tamanho em bytes; saída: RAX=ponteiro.
        g.bytes(b'\x48\x83\xEC\x28')  # reserva fixa desde o prologo
        g.bytes(b'\x48\x89\xFA')     # mov rdx,rdi
        g.bytes(b'\x31\xC9')         # xor ecx,ecx
        g.bytes(b'\x41\xB8\x00\x30\x00\x00')  # r8d=MEM_COMMIT|MEM_RESERVE
        g.bytes(b'\x41\xB9\x04\x00\x00\x00')  # r9d=PAGE_READWRITE
        g.relativo(b'\xFF\x15', 'VirtualAlloc')
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
    if windows:
        g.bytes(b'\x48\x83\xC4\x28')
    g.bytes(b'\xC3')
    if windows:
        registrar_quadro_empilhado(g, 'rs_lista_alocar', (), 40)

    g.marcar('rs_lista_desalocar')
    if windows:
        # Entrada: RDI=ponteiro; RSI=bytes (Windows ignora tamanho).
        g.bytes(b'\x48\x83\xEC\x28')
        g.bytes(b'\x48\x89\xF9')   # mov rcx,rdi
        g.bytes(b'\x31\xD2')       # xor edx,edx
        g.bytes(b'\x41\xB8\x00\x80\x00\x00')  # r8d=MEM_RELEASE
        g.relativo(b'\xFF\x15', 'VirtualFree')
        g.bytes(b'\x85\xC0')
        g.salto('erro_lista_memoria', 'jz')
    else:
        g.bytes(b'\xB8\x0B\x00\x00\x00\x0F\x05')  # munmap
        g.bytes(b'\x48\x85\xC0')
        g.salto('erro_lista_memoria', 'jnz')
    if windows:
        g.bytes(b'\x48\x83\xC4\x28')
    g.bytes(b'\xC3')
    if windows:
        registrar_quadro_empilhado(g, 'rs_lista_desalocar', (), 40)


def _emitir(g, codigo):
    g.bytes(bytes.fromhex(codigo))


def _terminar(g, windows, nome):
    emitir_epilogo_auxiliar(g, windows)
    if windows:
        registrar_quadro_auxiliar(g, nome)


def emitir_rotinas(g, windows):
    emitir_alocadores(g, windows)
    nome = 'rs_valor_liberar_descritor'
    g.marcar(nome)
    emitir_prologo_auxiliar(g, windows, 32)
    _emitir(g, '48 89 7D F8 48 89 75 F0')
    _emitir(g, '48 83 7F F8 00')  # comprimento negativo: já inativo
    g.salto(nome + '_fim', 'jl')
    _emitir(g, '48 8B 3F 48 85 FF')
    g.salto(nome + '_marcar', 'jz')
    _emitir(g, '48 8B 75 F8 48 8B 76 F0 48 0F AF 75 F0')
    g.salto('erro_lista_memoria', 'jo')
    g.chamada('rs_lista_desalocar')
    g.marcar(nome + '_marcar')
    _emitir(g, '48 8B 7D F8 31 C0 48 89 07 48 89 47 F0')
    _emitir(g, '48 C7 47 F8 FF FF FF FF')
    g.marcar(nome + '_fim')
    _terminar(g, windows, nome)

    nome = 'rs_valor_mover_descritor'
    g.marcar(nome)
    emitir_prologo_auxiliar(g, windows, 32)
    _emitir(g, '48 89 7D F8 48 89 75 F0 48 89 55 E8')
    _emitir(g, '48 83 7E F8 00')
    g.salto('erro_valor_inativo', 'jl')
    _emitir(g, '48 89 D6')  # bytes por unidade para liberar destino
    g.chamada('rs_valor_liberar_descritor')
    _emitir(g, '48 8B 7D F8 48 8B 75 F0')
    _emitir(g, '48 8B 06 48 89 07 48 8B 46 F8 48 89 47 F8')
    _emitir(g, '48 8B 46 F0 48 89 47 F0 31 C0 48 89 06 48 89 46 F0')
    _emitir(g, '48 C7 46 F8 FF FF FF FF')
    _terminar(g, windows, nome)

    nome = 'rs_valor_reservar'
    g.marcar(nome)
    emitir_prologo_auxiliar(g, windows, 64)
    # RDI=descritor, RSI=mínimo em unidades, RDX=bytes por unidade.
    _emitir(g, '48 89 7D F8 48 89 75 F0 48 89 55 E8')
    _emitir(g, '48 85 F6')
    g.salto('erro_lista_memoria', 'js')
    _emitir(g, '48 85 D2')
    g.salto('erro_lista_memoria', 'jle')
    _emitir(g, '48 83 7F F8 00')
    g.salto('erro_valor_inativo', 'jl')
    _emitir(g, '48 8B 47 F0 48 39 F0')
    g.salto(nome + '_fim', 'jge')
    _emitir(g, '48 85 C0')
    g.salto(nome + '_dobrar', 'jnz')
    _emitir(g, 'B8 04 00 00 00')
    g.marcar(nome + '_dobrar')
    _emitir(g, '48 3B 45 F0')
    g.salto(nome + '_alocar', 'jge')
    _emitir(g, '48 D1 E0')
    g.salto(nome + '_minimo', 'jo')
    g.salto(nome + '_dobrar')
    g.marcar(nome + '_minimo')
    _emitir(g, '48 8B 45 F0')
    g.marcar(nome + '_alocar')
    _emitir(g, '48 89 45 E0 48 0F AF 45 E8')
    g.salto('erro_lista_memoria', 'jo')
    if not windows:
        # Linux x86-64: mremap(antigo, bytes_antigos, bytes_novos,
        # MREMAP_MAYMOVE). A chamada pode realocar sem copiar os dados.
        # Se o kernel recusar o redimensionamento, o caminho histórico
        # aloca, copia o comprimento usado e libera o mapeamento antigo.
        # Preservamos o contrato público do descritor (três palavras).
        _emitir(g, '48 89 45 D0')  # [rbp-48] = novo tamanho em bytes
        _emitir(g, '4C 8B 55 F8 49 8B 3A 48 85 FF')  # ponteiro antigo
        g.salto(nome + '_copia', 'jz')
        _emitir(g, '49 8B 72 F0 48 0F AF 75 E8')  # capacidade * passo
        g.salto('erro_lista_memoria', 'jo')
        _emitir(g, '48 8B 55 D0')  # rdx = bytes novos
        _emitir(g, '41 BA 01 00 00 00')  # r10d = MREMAP_MAYMOVE
        _emitir(g, 'B8 19 00 00 00 0F 05')  # syscall mremap (25)
        _emitir(g, '48 3D 01 F0 FF FF')  # -4095: erro Linux
        g.salto(nome + '_copia', 'jae')
        _emitir(g, '48 89 45 D8')  # ponteiro retornado (inclusive movido)
        g.salto(nome + '_atualizar')
        g.marcar(nome + '_copia')
        _emitir(g, '48 8B 7D D0')  # tamanho novo para mmap
    else:
        # Manter o caminho Windows byte a byte (VirtualAlloc/VirtualFree).
        _emitir(g, '48 89 C7')
    g.chamada('rs_lista_alocar')
    _emitir(g, '48 89 45 D8 4C 8B 55 F8 49 8B 32 48 85 F6')
    g.salto(nome + '_atualizar', 'jz')
    _emitir(g, '48 8B 7D D8 49 8B 4A F8 48 0F AF 4D E8')
    g.salto('erro_lista_memoria', 'jo')
    _emitir(g, 'FC F3 A4 4C 8B 55 F8 49 8B 3A 49 8B 72 F0')
    _emitir(g, '48 0F AF 75 E8')
    g.salto('erro_lista_memoria', 'jo')
    g.chamada('rs_lista_desalocar')
    g.marcar(nome + '_atualizar')
    _emitir(g, '4C 8B 55 F8 48 8B 45 D8 49 89 02 48 8B 45 E0 49 89 42 F0')
    g.marcar(nome + '_fim')
    _terminar(g, windows, nome)
