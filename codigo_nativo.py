"""Emissão direta de código de máquina AMD64 para Windows PE e Linux ELF."""
import struct
def alinhar(valor, multiplo):
    return (valor + multiplo - 1) // multiplo * multiplo


class Emissor:
    def __init__(self):
        self.codigo = bytearray()
        self.pendencias = []

    def bytes(self, dados):
        self.codigo += dados

    def relativo(self, prefixo, identificador):
        self.bytes(prefixo)
        posicao = len(self.codigo)
        self.bytes(b"\x00" * 4)
        self.pendencias.append((posicao, identificador))

    def resolver(self, base_codigo_rva, enderecos_rva):
        for posicao, identificador in self.pendencias:
            if identificador not in enderecos_rva:
                raise ValueError(f"Referência interna desconhecida: {identificador}")
            delta = enderecos_rva[identificador] - (base_codigo_rva + posicao + 4)
            struct.pack_into('<i', self.codigo, posicao, delta)


def construir_importacoes(base_rva, nomes):
    conteudo = bytearray(40)
    tabela = (len(nomes) + 1) * 8
    inicio_ilt = len(conteudo)
    conteudo += bytes(tabela)
    inicio_iat = len(conteudo)
    conteudo += bytes(tabela)
    nomes_pos = []
    for nome in nomes:
        if len(conteudo) % 2:
            conteudo.append(0)
        nomes_pos.append(len(conteudo))
        conteudo += b'\x00\x00' + nome.encode('ascii') + b'\x00'
    inicio_dll = len(conteudo)
    conteudo += b'KERNEL32.dll\x00'
    while len(conteudo) % 4:
        conteudo.append(0)
    inicio_contador = len(conteudo)
    conteudo += bytes(4)
    for i, p in enumerate(nomes_pos):
        struct.pack_into('<Q', conteudo, inicio_ilt + i * 8, base_rva + p)
        struct.pack_into('<Q', conteudo, inicio_iat + i * 8, base_rva + p)
    struct.pack_into('<IIIII', conteudo, 0, base_rva + inicio_ilt, 0, 0,
                     base_rva + inicio_dll, base_rva + inicio_iat)
    enderecos = {nome: base_rva + inicio_iat + i * 8 for i, nome in enumerate(nomes)}
    enderecos['contador'] = base_rva + inicio_contador
    return conteudo, enderecos, inicio_iat, tabela

from sintaxe import ErroCompilacao


class Gerador(Emissor):
    def __init__(self):
        super().__init__()
        self.rotulos = {}
        self.proxima_condicao = 0

    def marcar(self, nome):
        if nome in self.rotulos:
            raise ValueError(f'Rótulo repetido: {nome}')
        self.rotulos[nome] = len(self.codigo)

    def salto(self, nome, tipo='jmp'):
        prefixo = {'jmp': b'\xE9', 'jz': b'\x0F\x84', 'jnz': b'\x0F\x85', 'jns': b'\x0F\x89'}[tipo]
        self.relativo(prefixo, nome)

    def chamada(self, nome):
        self.relativo(b'\xE8', nome)

    def finalizar(self, base, externos):
        self.resolver(base, {**externos, **{n: base + p for n, p in self.rotulos.items()}})


def carregar_numero(g, numero):
    g.bytes(b'\x48\xB8' + struct.pack('<Q', numero & 0xFFFFFFFFFFFFFFFF))


def expressao(g, expr, variaveis, windows):
    tipo = expr[0]
    if tipo == 'numero':
        carregar_numero(g, expr[1])
    elif tipo == 'var':
        i = variaveis[expr[1]]
        offset = -(16 + i * 8) if windows else -(8 + i * 8)
        g.bytes(b'\x48\x8B\x85' + struct.pack('<i', offset))
    elif tipo == 'neg':
        expressao(g, expr[1], variaveis, windows)
        g.bytes(b'\x48\xF7\xD8')  # neg rax
    elif tipo == 'comparacao':
        _, op, esquerda, direita = expr
        expressao(g, esquerda, variaveis, windows)
        g.bytes(b'\x50')  # salva o operando esquerdo
        expressao(g, direita, variaveis, windows)
        g.bytes(b'\x59')  # rcx = operando esquerdo
        g.bytes(b'\x48\x39\xC1')  # cmp rcx, rax (inteiros com sinal)
        codigo = {'==': 0x94, '!=': 0x95, '<': 0x9C, '<=': 0x9E, '>': 0x9F, '>=': 0x9D}[op]
        g.bytes(bytes((0x0F, codigo, 0xC0)) + b'\x0F\xB6\xC0')  # setcc al; movzx eax,al
    elif tipo == 'bin':
        _, op, esquerda, direita = expr
        expressao(g, esquerda, variaveis, windows)
        g.bytes(b'\x50')  # push rax
        expressao(g, direita, variaveis, windows)
        g.bytes(b'\x59')  # pop rcx: esquerda
        if op == '+':
            g.bytes(b'\x48\x01\xC8')  # add rax, rcx
        elif op == '-':
            g.bytes(b'\x48\x29\xC1\x48\x89\xC8')  # sub rcx,rax; mov rax,rcx
        elif op == '*':
            g.bytes(b'\x48\x0F\xAF\xC1')  # imul rax,rcx
        elif op in ('/', '%'):
            g.bytes(b'\x49\x89\xC2')  # mov r10,rax (divisor)
            g.bytes(b'\x4D\x85\xD2')  # test r10,r10
            g.salto('erro_divisao_zero', 'jz')
            # INT64_MIN / -1 é a única divisão inteira que transborda.
            g.bytes(b'\x49\x83\xFA\xFF')  # cmp r10,-1
            g.salto(f'div_normal_{len(g.codigo)}', 'jnz')
            nome_normal = g.pendencias[-1][1]
            g.bytes(b'\x48\xB8' + struct.pack('<Q', 1 << 63))
            g.bytes(b'\x48\x39\xC1')  # cmp rcx,rax
            g.salto('erro_estouro', 'jz')
            g.marcar(nome_normal)
            g.bytes(b'\x48\x89\xC8\x48\x99\x49\xF7\xFA')  # mov rax,rcx; cqo; idiv r10
            if op == '%':
                g.bytes(b'\x48\x89\xD0')  # mov rax,rdx
    else:
        raise ValueError(f'Expressão interna desconhecida: {expr!r}')


def escreve_literal(g, indice, mensagem, windows, manipulador='saida'):
    dados = (mensagem).encode('utf-8')
    if windows:
        g.bytes(b'\x48\x89\xD9' if manipulador == 'saida' else b'\x4C\x89\xE1')  # mov rcx,rbx ou r12
        g.relativo(b'\x48\x8D\x15', f'mensagem_{indice}')  # rdx = string
        g.bytes(b'\x41\xB8' + struct.pack('<I', len(dados)))
        g.relativo(b'\x4C\x8D\x0D', 'contador')
        g.bytes(b'\xC7\x44\x24\x20\x00\x00\x00\x00')
        g.relativo(b'\xFF\x15', 'WriteFile')
    else:
        g.bytes(b'\xB8\x01\x00\x00\x00')  # eax=sys_write
        g.bytes(b'\xBF' + struct.pack('<I', 1 if manipulador == 'saida' else 2))
        g.relativo(b'\x48\x8D\x35', f'mensagem_{indice}')
        g.bytes(b'\xBA' + struct.pack('<I', len(dados)))
        g.bytes(b'\x0F\x05')


def imprime_inteiro(g, windows):
    """Rotina nativa de decimalização: entrada RAX, com sinal e quebra de linha."""
    g.marcar('imprimir_inteiro')
    if windows:
        g.bytes(b'\x57\x48\x81\xEC' + struct.pack('<I', 0x80))  # salva RDI, reserva buffer+shadow
        g.bytes(b'\x48\x8D\x7C\x24\x70')  # lea rdi,[rsp+0x70]
    else:
        g.bytes(b'\x48\x83\xEC\x40\x48\x8D\x7C\x24\x40')
    g.bytes(b'\xC6\x47\xFF\x0A\x48\xFF\xCF')  # buffer[-1] = \n; --rdi
    g.bytes(b'\x45\x31\xC9')  # xor r9d,r9d
    g.bytes(b'\x48\x85\xC0')  # test rax,rax
    g.salto('numero_positivo', 'jns')
    g.bytes(b'\x48\xF7\xD8\x41\xB9\x01\x00\x00\x00')  # neg rax; mov r9d,1
    g.marcar('numero_positivo')
    g.bytes(b'\x41\xBB\x0A\x00\x00\x00')  # mov r11d,10
    g.marcar('digito')
    g.bytes(b'\x31\xD2\x49\xF7\xF3')  # xor edx,edx; div r11
    g.bytes(b'\x80\xC2\x30\x48\xFF\xCF\x88\x17')  # add dl,'0'; --rdi; mov [rdi],dl
    g.bytes(b'\x48\x85\xC0')
    g.salto('digito', 'jnz')
    g.bytes(b'\x45\x85\xC9')
    g.salto('numero_pronto', 'jz')
    g.bytes(b'\x48\xFF\xCF\xC6\x07\x2D')  # insere '-'
    g.marcar('numero_pronto')
    if windows:
        g.bytes(b'\x4C\x8D\x44\x24\x70')  # lea r8,[rsp+0x70]
        g.bytes(b'\x49\x29\xF8')  # sub r8,rdi => tamanho
        g.bytes(b'\x48\x89\xFA\x48\x89\xD9')  # mov rdx,rdi; mov rcx,rbx
        g.relativo(b'\x4C\x8D\x0D', 'contador')
        g.bytes(b'\xC7\x44\x24\x20\x00\x00\x00\x00')
        g.relativo(b'\xFF\x15', 'WriteFile')
        g.bytes(b'\x48\x81\xC4' + struct.pack('<I', 0x80) + b'\x5F\xC3')
    else:
        g.bytes(b'\x48\x8D\x54\x24\x40')  # lea rdx,[rsp+64]
        g.bytes(b'\x48\x29\xFA')  # sub rdx,rdi
        g.bytes(b'\x48\x89\xFE\xBF\x01\x00\x00\x00\xB8\x01\x00\x00\x00\x0F\x05')
        g.bytes(b'\x48\x83\xC4\x40\xC3')


def montar_codigo(programa, windows):
    g = Gerador()
    variaveis = programa.variaveis
    mensagens = {}
    if windows:
        n = len(variaveis)
        frame = ((8 * n + 0x38 + 15) // 16) * 16 + 8
        g.bytes(b'\x55\x48\x89\xE5\x53')  # push rbp; mov rbp,rsp; push rbx
        g.bytes(b'\x48\x81\xEC' + struct.pack('<I', frame))
        g.bytes(b'\xB9' + struct.pack('<I', 65001))
        g.relativo(b'\xFF\x15', 'SetConsoleOutputCP')
        g.bytes(b'\xB9\xF5\xFF\xFF\xFF')
        g.relativo(b'\xFF\x15', 'GetStdHandle')
        g.bytes(b'\x48\x89\xC3')  # RBX = stdout handle
    else:
        frame = alinhar(len(variaveis) * 8, 16)
        g.bytes(b'\x55\x48\x89\xE5')
        if frame:
            g.bytes(b'\x48\x81\xEC' + struct.pack('<I', frame))

    def emitir_bloco(instrucoes):
        for op in instrucoes:
            if op[0] == 'texto':
                n = len(mensagens)
                mensagens[n] = op[1]
                escreve_literal(g, n, op[1], windows)
            elif op[0] == 'atribua':
                expressao(g, op[2], variaveis, windows)
                i = variaveis[op[1]]
                offset = -(16 + i * 8) if windows else -(8 + i * 8)
                g.bytes(b'\x48\x89\x85' + struct.pack('<i', offset))
            elif op[0] == 'imprima_num':
                expressao(g, op[1], variaveis, windows)
                g.chamada('imprimir_inteiro')
            elif op[0] == 'se':
                numero = g.proxima_condicao
                g.proxima_condicao += 1
                rotulo_falso = f'se_falso_{numero}'
                rotulo_fim = f'se_fim_{numero}'
                expressao(g, op[1], variaveis, windows)
                g.bytes(b'\x48\x85\xC0')  # test rax,rax
                g.salto(rotulo_falso, 'jz')
                emitir_bloco(op[2])
                if op[3]:
                    g.salto(rotulo_fim)
                g.marcar(rotulo_falso)
                if op[3]:
                    emitir_bloco(op[3])
                    g.marcar(rotulo_fim)

    emitir_bloco(programa.instrucoes)

    if windows:
        g.bytes(b'\x31\xC9')
        g.relativo(b'\xFF\x15', 'ExitProcess')
    else:
        g.bytes(b'\xB8\x3C\x00\x00\x00\x31\xFF\x0F\x05')
    imprime_inteiro(g, windows)

    primeiro_erro = len(mensagens)
    for indice, msg in [(primeiro_erro, 'Erro: divisão por zero.\n'),
                        (primeiro_erro + 1, 'Erro: divisão inteira fora do limite.\n')]:
        rotulo = 'erro_divisao_zero' if indice == primeiro_erro else 'erro_estouro'
        g.marcar(rotulo)
        mensagens[indice] = msg
        if windows:
            # Erros comunicados por saída padrão nesta fase, com código 1.
            escreve_literal(g, indice, msg, True)
            g.bytes(b'\xB9\x01\x00\x00\x00')
            g.relativo(b'\xFF\x15', 'ExitProcess')
        else:
            escreve_literal(g, indice, msg, False, 'erro')
            g.bytes(b'\xB8\x3C\x00\x00\x00\xBF\x01\x00\x00\x00\x0F\x05')
    return g, mensagens


def montar_elf(g, mensagens):
    inicio_codigo = 0x100
    inicio_dados = inicio_codigo + len(g.codigo)
    dados = bytearray()
    externos = {}
    for i, msg in mensagens.items():
        externos[f'mensagem_{i}'] = inicio_dados + len(dados)
        dados += msg.encode('utf-8')
    g.finalizar(inicio_codigo, externos)
    imagem = bytearray(inicio_codigo)
    imagem += g.codigo + dados
    imagem[:64] = struct.pack('<16sHHIQQQIHHHHHH', b'\x7fELF' + bytes([2, 1, 1, 0]) + bytes(8),
                              2, 62, 1, 0x400000 + inicio_codigo, 64, 0, 0, 64, 56, 1, 0, 0, 0)
    imagem[64:120] = struct.pack('<IIQQQQQQ', 1, 5, 0, 0x400000, 0x400000,
                                 len(imagem), len(imagem), 0x1000)
    return bytes(imagem)


def montar_pe(g, mensagens):
    base_codigo, base_importacoes, base_dados = 0x1000, 0x2000, 0x3000
    nomes = ['GetStdHandle', 'SetConsoleOutputCP', 'WriteFile', 'ExitProcess']
    importacoes, enderecos, inicio_iat, tamanho_iat = construir_importacoes(base_importacoes, nomes)
    dados = bytearray()
    for i, msg in mensagens.items():
        enderecos[f'mensagem_{i}'] = base_dados + len(dados)
        dados += msg.encode('utf-8')
    if max(len(g.codigo), len(importacoes), len(dados)) > 0x1000:
        raise ErroCompilacao('Programa grande demais para as seções fixas da versão 0.3 (4 KiB).')
    g.finalizar(base_codigo, enderecos)
    secoes = [(b'.text', bytes(g.codigo), base_codigo, 0x60000020),
              (b'.idata', bytes(importacoes), base_importacoes, 0xC0000040),
              (b'.rdata', bytes(dados), base_dados, 0x40000040)]
    descritores = []
    off = 0x200
    for nome, conteudo, virtual, flags in secoes:
        tamanho = alinhar(len(conteudo), 0x200)
        descritores.append((nome, conteudo, virtual, flags, off, tamanho))
        off += tamanho
    cabecalho = bytearray(0x200)
    cabecalho[:2] = b'MZ'
    struct.pack_into('<I', cabecalho, 0x3C, 0x80)
    cabecalho[0x80:0x84] = b'PE\x00\x00'
    struct.pack_into('<HHIIIHH', cabecalho, 0x84, 0x8664, 3, 0, 0, 0, 0xF0, 0x0022)
    opt = bytearray(0xF0)
    struct.pack_into('<H', opt, 0, 0x20B)
    struct.pack_into('<I', opt, 4, descritores[0][5])
    struct.pack_into('<I', opt, 8, descritores[1][5] + descritores[2][5])
    struct.pack_into('<I', opt, 16, base_codigo)
    struct.pack_into('<I', opt, 20, base_codigo)
    struct.pack_into('<Q', opt, 24, 0x140000000)
    struct.pack_into('<I', opt, 32, 0x1000)
    struct.pack_into('<I', opt, 36, 0x200)
    struct.pack_into('<HHHH', opt, 40, 6, 0, 0, 0)
    struct.pack_into('<HH', opt, 48, 6, 0)
    struct.pack_into('<I', opt, 56, 0x4000)
    struct.pack_into('<I', opt, 60, 0x200)
    struct.pack_into('<HH', opt, 68, 3, 0x100)
    struct.pack_into('<QQQQ', opt, 72, 0x100000, 0x1000, 0x100000, 0x1000)
    struct.pack_into('<II', opt, 104, 0, 16)
    struct.pack_into('<II', opt, 112 + 8, base_importacoes, 40)
    struct.pack_into('<II', opt, 112 + 8 * 12, base_importacoes + inicio_iat, tamanho_iat)
    cabecalho[0x98:0x98 + 0xF0] = opt
    pos = 0x98 + 0xF0
    for nome, conteudo, virtual, flags, offset, tamanho in descritores:
        struct.pack_into('<8sIIIIIIHHI', cabecalho, pos, nome.ljust(8, b'\0'),
                         len(conteudo), virtual, tamanho, offset, 0, 0, 0, 0, flags)
        pos += 40
    resultado = cabecalho
    for nome, conteudo, virtual, flags, offset, tamanho in descritores:
        resultado += conteudo + bytes(tamanho - len(conteudo))
    return bytes(resultado)


def compilar(programa, alvo):
    windows = alvo == 'windows'
    g, mensagens = montar_codigo(programa, windows)
    return montar_pe(g, mensagens) if windows else montar_elf(g, mensagens)
