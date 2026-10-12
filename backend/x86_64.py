"""Emissão nativa de instruções AMD64, leitura/escrita e saltos."""
import struct
from compilador.erros import ErroCompilacao
from .base import Emissor, alinhar

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
        prefixo = {'jmp': b'\xE9', 'jz': b'\x0F\x84', 'jnz': b'\x0F\x85', 'jns': b'\x0F\x89', 'jg': b'\x0F\x8F', 'jl': b'\x0F\x8C', 'jo': b'\x0F\x80', 'je': b'\x0F\x84', 'jne': b'\x0F\x85', 'jb': b'\x0F\x82', 'ja': b'\x0F\x87', 'js': b'\x0F\x88'}[tipo]
        self.relativo(prefixo, nome)

    def chamada(self, nome):
        self.relativo(b'\xE8', nome)

    def finalizar(self, base, externos):
        self.resolver(base, {**externos, **{n: base + p for n, p in self.rotulos.items()}})


def carregar_numero(g, numero):
    """Menor MOV imediato equivalente, sem modificar flags do processador.

    mov eax,imm32 zera os 32 bits altos de RAX; mov rax,imm32 estende sinal.
    Os demais inteiros continuam com movabs rax,imm64.
    """
    if 0 <= numero <= 0xFFFFFFFF:
        g.bytes(b'\xB8' + struct.pack('<I', numero))
    elif -(1 << 31) <= numero < 0:
        g.bytes(b'\x48\xC7\xC0' + struct.pack('<i', numero))
    else:
        g.bytes(b'\x48\xB8' + struct.pack('<Q', numero & 0xFFFFFFFFFFFFFFFF))


def deslocamento_variavel(variaveis, nome, windows):
    """Posicao da variavel local na pilha do programa (em bytes)."""
    indice = variaveis[nome]
    return -(16 + indice*8) if windows else -(8 + indice*8)


def expressao(g, expr, variaveis, windows, registradores=None):
    tipo = expr[0]
    if tipo in ('numero', 'logico'):
        carregar_numero(g, expr[1])
    elif tipo == 'var':
        if registradores and expr[1] in registradores:
            from .ssa_x86_64 import _emite_mov
            _emite_mov(g, 'rax', registradores[expr[1]])
        else:
            offset = deslocamento_variavel(variaveis, expr[1], windows)
            g.bytes(b'\x48\x8B\x85' + struct.pack('<i', offset))
    elif tipo == 'neg':
        if expr[1] == ('numero', 1 << 63):
            # Menor inteiro: o valor positivo 2^63 não cabe, mas sua negação sim.
            carregar_numero(g, -(1 << 63))
        else:
            expressao(g, expr[1], variaveis, windows, registradores)
            g.bytes(b'\x48\xF7\xD8')  # neg rax
            g.salto('erro_overflow_aritmetico', 'jo')
    elif tipo == 'comparacao':
        _, op, esquerda, direita = expr
        expressao(g, esquerda, variaveis, windows, registradores)
        g.bytes(b'\x50')  # salva o operando esquerdo
        expressao(g, direita, variaveis, windows, registradores)
        g.bytes(b'\x59')  # rcx = operando esquerdo
        g.bytes(b'\x48\x39\xC1')  # cmp rcx, rax (inteiros com sinal)
        codigo = {'==': 0x94, '!=': 0x95, '<': 0x9C, '<=': 0x9E, '>': 0x9F, '>=': 0x9D}[op]
        g.bytes(bytes((0x0F, codigo, 0xC0)) + b'\x0F\xB6\xC0')  # setcc al; movzx eax,al
    elif tipo == 'bin':
        _, op, esquerda, direita = expr
        expressao(g, esquerda, variaveis, windows, registradores)
        g.bytes(b'\x50')  # push rax
        expressao(g, direita, variaveis, windows, registradores)
        g.bytes(b'\x59')  # pop rcx: esquerda
        if op == '+':
            g.bytes(b'\x48\x01\xC8')  # add rax, rcx
            g.salto('erro_overflow_aritmetico', 'jo')
        elif op == '-':
            g.bytes(b'\x48\x29\xC1')  # sub rcx,rax (mantém OF para o teste)
            g.salto('erro_overflow_aritmetico', 'jo')
            g.bytes(b'\x48\x89\xC8')  # mov rax, rcx
        elif op == '*':
            g.bytes(b'\x48\x0F\xAF\xC1')  # imul rax,rcx
            g.salto('erro_overflow_aritmetico', 'jo')
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



def percorrer_instrucoes(instrucoes):
    """Itera sobre o AST, inclusive instrucoes aninhadas."""
    for op in instrucoes:
        yield op
        if op[0] == 'se':
            yield from percorrer_instrucoes(op[2])
            yield from percorrer_instrucoes(op[3])
        elif op[0] == 'enquanto':
            yield from percorrer_instrucoes(op[2])
        elif op[0] == 'para':
            yield from percorrer_instrucoes(op[5])


def ler_inteiro(g, windows):
    """Leitura de um inteiro ASCII com sinal em stdin, sem alocacao dinamica.

    Aceita espacos antes/depois, sinal opcional, CRLF ou LF e EOF depois
    de digitos. Falhas de IO, entrada vazia, letra e overflow terminam em 1.
    A rotina le um byte por vez: correta, mas ainda nao otimizada.
    """
    g.marcar('ler_inteiro')
    # Windows: registradores r13-r15 sao callee-saved; Linux tambem.
    g.bytes(b'\x41\x55\x41\x56\x41\x57')  # push r13 r14 r15
    g.bytes(b'\x48\x83\xEC\x40' if windows else b'\x48\x83\xEC\x10')
    g.bytes(b'\x45\x31\xED\x45\x31\xF6\x45\x31\xFF')  # xor r13d, r14d, r15d
    # r13 = magnitude, r14d = estado (0 inicio,1 sinal,2 digitos,3 sufixo), r15d = negativo
    g.marcar('leia_proximo_byte')
    if windows:
        g.bytes(b'\x4C\x89\xE1')  # mov rcx,r12 (stdin)
        g.bytes(b'\x48\x8D\x54\x24\x30')  # lea rdx,[rsp+0x30] buffer
        g.bytes(b'\x41\xB8\x01\x00\x00\x00')  # mov r8d,1
        g.bytes(b'\x4C\x8D\x4C\x24\x38')  # lea r9,[rsp+0x38] qtd
        g.bytes(b'\xC7\x44\x24\x20\x00\x00\x00\x00')  # overlapped NULL
        g.relativo(b'\xFF\x15', 'ReadFile')
        g.bytes(b'\x85\xC0')
        g.salto('leia_lida', 'jnz')
        # Pipes fechados retornam FALSE + ERROR_BROKEN_PIPE (109), que e EOF.
        g.relativo(b'\xFF\x15', 'GetLastError')
        g.bytes(b'\x83\xF8\x6D')  # cmp eax,109
        g.salto('leia_fim_entrada', 'jz')
        g.bytes(b'\x83\xF8\x26')  # cmp eax,38 (ERROR_HANDLE_EOF)
        g.salto('leia_fim_entrada', 'jz')
        g.salto('erro_entrada_invalida')
        g.marcar('leia_lida')
        g.bytes(b'\x8B\x44\x24\x38\x85\xC0')  # bytes lidos
        g.salto('leia_fim_entrada', 'jz')
        g.bytes(b'\x44\x8A\x54\x24\x30')  # r10b = byte
    else:
        g.bytes(b'\x31\xC0\x31\xFF')  # sys_read=0, fd=0
        g.bytes(b'\x48\x89\xE6')  # rsi = rsp (1-byte buffer)
        g.bytes(b'\xBA\x01\x00\x00\x00\x0F\x05')  # edx=1; syscall
        g.bytes(b'\x48\x85\xC0')
        g.salto('erro_entrada_invalida', 'js')
        g.salto('leia_fim_entrada', 'jz')
        g.bytes(b'\x44\x8A\x14\x24')  # r10b=[rsp]

    g.bytes(b'\x41\x80\xFA\x0A')  # LF = fim de linha
    g.salto('leia_fim_entrada', 'jz')
    for byte in (0x20, 0x09, 0x0D):  # SPACE, TAB, CR
        g.bytes(b'\x41\x80\xFA' + bytes((byte,)))
        g.salto('leia_espaco', 'jz')

    g.bytes(b'\x41\x83\xFE\x00')  # estado 0?
    g.salto('leia_sinais', 'jz')
    # Estado 1 ou 2 continua para checagem de digito; estado 3 rejeita.
    g.bytes(b'\x41\x83\xFE\x03')
    g.salto('erro_entrada_invalida', 'jz')
    g.salto('leia_digito')

    g.marcar('leia_sinais')
    g.bytes(b'\x41\x80\xFA\x2D')  # '-'
    g.salto('leia_negativo', 'jz')
    g.bytes(b'\x41\x80\xFA\x2B')  # '+'
    g.salto('leia_positivo', 'jz')
    g.salto('leia_digito')
    g.marcar('leia_negativo')
    g.bytes(b'\x41\xBF\x01\x00\x00\x00')  # mov r15d,1
    g.marcar('leia_positivo')
    g.bytes(b'\x41\xBE\x01\x00\x00\x00')  # estado=1
    g.salto('leia_proximo_byte')

    g.marcar('leia_espaco')
    g.bytes(b'\x41\x83\xFE\x01')  # espaco depois do sinal nao aceito
    g.salto('erro_entrada_invalida', 'jz')
    g.bytes(b'\x41\x83\xFE\x02')  # depois dos digitos marca sufixo
    g.salto('leia_marcar_sufixo', 'jz')
    g.salto('leia_proximo_byte')
    g.marcar('leia_marcar_sufixo')
    g.bytes(b'\x41\xBE\x03\x00\x00\x00')
    g.salto('leia_proximo_byte')

    g.marcar('leia_digito')
    g.bytes(b'\x41\x80\xFA\x30')  # menor que '0'
    g.salto('erro_entrada_invalida', 'jb')
    g.bytes(b'\x41\x80\xFA\x39')  # maior que '9'
    g.salto('erro_entrada_invalida', 'ja')
    g.bytes(b'\x41\xBE\x02\x00\x00\x00')  # estado=digitos
    g.bytes(b'\x45\x0F\xB6\xD2')  # movzx r10d,r10b
    g.bytes(b'\x49\x83\xEA\x30')  # sub r10,48
    # magnitude <= 922337203685477580 antes de multiplicar por 10.
    carregar_numero(g, 922337203685477580)
    g.bytes(b'\x49\x39\xC5')  # cmp r13,rax
    g.salto('erro_entrada_limite', 'ja')
    g.salto('leia_multiplicar', 'jne')
    # Ultimo algarismo so pode ser 0..7 (positivo) ou 0..8 (negativo).
    g.bytes(b'\x41\x83\xFF\x00')  # cmp r15d,0
    g.salto('leia_ultimo_negativo', 'jne')
    g.bytes(b'\x41\x83\xFA\x07')  # cmp r10d,7
    g.salto('erro_entrada_limite', 'ja')
    g.salto('leia_multiplicar')
    g.marcar('leia_ultimo_negativo')
    g.bytes(b'\x41\x83\xFA\x08')
    g.salto('erro_entrada_limite', 'ja')
    g.marcar('leia_multiplicar')
    g.bytes(b'\x4D\x6B\xED\x0A')  # imul r13,r13,10
    g.bytes(b'\x4D\x01\xD5')  # add r13,r10
    g.salto('leia_proximo_byte')

    g.marcar('leia_fim_entrada')
    g.bytes(b'\x41\x83\xFE\x02')  # estado >= 2 (digitos ou espaco apos)
    g.salto('erro_entrada_invalida', 'jb')
    g.bytes(b'\x4C\x89\xE8')  # mov rax,r13
    g.bytes(b'\x45\x85\xFF')  # test r15d,r15d
    g.salto('leia_retornar', 'jz')
    g.bytes(b'\x48\xF7\xD8')  # neg rax (INT64_MIN mantem o mesmo padrao de bits)
    g.marcar('leia_retornar')
    g.bytes(b'\x48\x83\xC4\x40' if windows else b'\x48\x83\xC4\x10')
    g.bytes(b'\x41\x5F\x41\x5E\x41\x5D\xC3')  # pop r15 r14 r13; ret


def montar_codigo(programa, windows, emissor_alternativo=None):
    g = Gerador()
    variaveis = programa.variaveis
    mensagens = {}
    tem_leitura = any(op[0] == 'leia_int' for op in percorrer_instrucoes(programa.instrucoes))
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
        if tem_leitura:
            g.bytes(b'\xB9\xF6\xFF\xFF\xFF')  # STD_INPUT_HANDLE (-10)
            g.relativo(b'\xFF\x15', 'GetStdHandle')
            g.bytes(b'\x49\x89\xC4')  # R12 = stdin handle
    else:
        frame = alinhar(len(variaveis) * 8, 16)
        g.bytes(b'\x55\x48\x89\xE5')
        if frame:
            g.bytes(b'\x48\x81\xEC' + struct.pack('<I', frame))

    def emitir_bloco(instrucoes, laco=None):
        for op in instrucoes:
            if op[0] == 'texto':
                n = len(mensagens)
                mensagens[n] = op[1]
                escreve_literal(g, n, op[1], windows)
            elif op[0] == 'atribua':
                expressao(g, op[2], variaveis, windows)
                offset = deslocamento_variavel(variaveis, op[1], windows)
                g.bytes(b'\x48\x89\x85' + struct.pack('<i', offset))
            elif op[0] == 'leia_int':
                g.chamada('ler_inteiro')
                posicao = deslocamento_variavel(variaveis, op[1], windows)
                g.bytes(b'\x48\x89\x85' + struct.pack('<i', posicao))
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
                emitir_bloco(op[2], laco)
                if op[3]:
                    g.salto(rotulo_fim)
                g.marcar(rotulo_falso)
                if op[3]:
                    emitir_bloco(op[3], laco)
                    g.marcar(rotulo_fim)
            elif op[0] == 'enquanto':
                numero = g.proxima_condicao
                g.proxima_condicao += 1
                inicio = f'enquanto_inicio_{numero}'
                fim = f'enquanto_fim_{numero}'
                g.marcar(inicio)
                expressao(g, op[1], variaveis, windows)
                g.bytes(b'\x48\x85\xC0')  # test rax, rax
                g.salto(fim, 'jz')
                emitir_bloco(op[2], (inicio, fim))
                g.salto(inicio)
                g.marcar(fim)
            elif op[0] == 'para':
                _, nome, inicial, final, passo, corpo = op
                numero = g.proxima_condicao
                g.proxima_condicao += 1
                inicio = f'para_inicio_{numero}'
                incremento = f'para_incremento_{numero}'
                fim = f'para_fim_{numero}'
                deslocamento = deslocamento_variavel(variaveis, nome, windows)
                # Avalia o inicio uma vez e guarda o contador na pilha.
                expressao(g, inicial, variaveis, windows)
                g.bytes(b'\x48\x89\x85' + struct.pack('<i', deslocamento))
                g.marcar(inicio)
                # O limite e avaliado a cada iteracao; fim inclusivo.
                expressao(g, final, variaveis, windows)
                g.bytes(b'\x50')  # push limite
                g.bytes(b'\x48\x8B\x85' + struct.pack('<i', deslocamento))  # contador em RAX
                g.bytes(b'\x59\x48\x39\xC8')  # pop RCX; cmp RAX, RCX
                g.salto(fim, 'jg' if passo > 0 else 'jl')
                emitir_bloco(corpo, (incremento, fim))
                g.marcar(incremento)
                carregar_numero(g, passo)  # passo em RAX
                g.bytes(b'\x48\x8B\x8D' + struct.pack('<i', deslocamento))
                g.bytes(b'\x48\x01\xC8')  # add RAX,RCX
                g.salto(fim, 'jo')  # ao ultrapassar 64 bits, encerra sem dar a volta
                g.bytes(b'\x48\x89\x85' + struct.pack('<i', deslocamento))
                g.salto(inicio)
                g.marcar(fim)
            elif op[0] == 'pare':
                if laco is None:
                    raise ValueError('Uso de pare fora de um laço (erro interno).')
                g.salto(laco[1])
            elif op[0] == 'continue':
                if laco is None:
                    raise ValueError('Uso de continue fora de um laço (erro interno).')
                g.salto(laco[0])
            else:
                raise ValueError(f'Instrução interna desconhecida: {op!r}')

    if emissor_alternativo is None:
        emitir_bloco(programa.instrucoes)
    else:
        emissor_alternativo(g, mensagens, windows)

    if windows:
        g.bytes(b'\x31\xC9')
        g.relativo(b'\xFF\x15', 'ExitProcess')
    else:
        g.bytes(b'\xB8\x3C\x00\x00\x00\x31\xFF\x0F\x05')
    imprime_inteiro(g, windows)
    if tem_leitura:
        ler_inteiro(g, windows)

    primeiro_erro = len(mensagens)
    for indice, msg in [(primeiro_erro, 'Erro: divisão por zero.\n'),
                        (primeiro_erro + 1, 'Erro: divisão inteira fora do limite.\n'),
                        (primeiro_erro + 2, 'Erro: estouro aritmético em inteiro de 64 bits.\n')]:
        rotulo = {primeiro_erro: 'erro_divisao_zero', primeiro_erro + 1: 'erro_estouro',
                  primeiro_erro + 2: 'erro_overflow_aritmetico'}[indice]
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
    if tem_leitura:
        for indice, msg, rotulo in [
            (len(mensagens), 'Erro: entrada invalida; digite um numero inteiro.\n', 'erro_entrada_invalida'),
            (len(mensagens)+1, 'Erro: numero fora do limite de 64 bits.\n', 'erro_entrada_limite'),
        ]:
            mensagens[indice] = msg
            g.marcar(rotulo)
            escreve_literal(g, indice, msg, windows, 'saida' if windows else 'erro')
            if windows:
                g.bytes(b'\xB9\x01\x00\x00\x00')
                g.relativo(b'\xFF\x15', 'ExitProcess')
            else:
                g.bytes(b'\xB8\x3C\x00\x00\x00\xBF\x01\x00\x00\x00\x0F\x05')
    return g, mensagens
