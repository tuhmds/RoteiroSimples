"""Emissão nativa de instruções AMD64, leitura/escrita e saltos."""
import struct
from compilador.erros import ErroCompilacao
from . import listas_dinamicas, arquivos, arquivos_posicionais, bytes_seguros, arquivos_abertos
from .base import Emissor, alinhar

class Gerador(Emissor):
    def __init__(self):
        super().__init__()
        self.rotulos = {}
        self.proxima_condicao = 0
        self._saltos_curtos_ssa = False
        self._candidatos_curto = []
        self.saltos_compactados = 0

    def ativar_saltos_curtos_ssa(self):
        """Ativa coleta de branches locais SSA; nao altera os demais niveis."""
        self._saltos_curtos_ssa = True

    def marcar(self, nome):
        if nome in self.rotulos:
            raise ValueError(f'Rótulo repetido: {nome}')
        self.rotulos[nome] = len(self.codigo)

    def salto(self, nome, tipo='jmp'):
        prefixo = {'jmp': b'\xE9', 'jz': b'\x0F\x84', 'jnz': b'\x0F\x85', 'jns': b'\x0F\x89', 'jg': b'\x0F\x8F', 'jl': b'\x0F\x8C', 'jo': b'\x0F\x80', 'je': b'\x0F\x84', 'jne': b'\x0F\x85', 'jb': b'\x0F\x82', 'ja': b'\x0F\x87', 'jae': b'\x0F\x83', 'js': b'\x0F\x88', 'jle': b'\x0F\x8E', 'jge': b'\x0F\x8D', 'jbe': b'\x0F\x86'}[tipo]
        inicio = len(self.codigo)
        self.relativo(prefixo, nome)
        if self._saltos_curtos_ssa and nome.startswith('ssa_'):
            curtos = {'jmp': 0xEB, 'jz': 0x74, 'je': 0x74, 'jnz': 0x75,
                      'jne': 0x75, 'jns': 0x79, 'jg': 0x7F, 'jl': 0x7C,
                      'jo': 0x70, 'jb': 0x72, 'ja': 0x77, 'js': 0x78,
                      'jle': 0x7E, 'jge': 0x7D}
            self._candidatos_curto.append((inicio, len(prefixo) + 4, nome, curtos[tipo]))

    def compactar_saltos_ssa(self):
        """Relaxa rel32->rel8 em ponto fixo, corrigindo TODOS os offsets.

        Nao encurta chamadas, referencias RIP a dados, nem saltos das
        rotinas auxiliares. Essas referencias tambem sao remapeadas.
        """
        import bisect
        candidatos = sorted(self._candidatos_curto)
        if not candidatos:
            return 0
        antigos = bytes(self.codigo)
        selecionados = set()
        # Cada troca reduz em 3 ou 4 bytes. Reducoes tornam outros saltos
        # pelo menos tao proximos; portanto a relaxacao e monotona.
        while True:
            alterou = False
            for inicio, tamanho, alvo, opcode in candidatos:
                if inicio in selecionados:
                    continue
                if alvo not in self.rotulos:
                    raise ValueError(f'Rotulo local de salto curto desconhecido: {alvo}')
                hipotese = selecionados | {inicio}
                # Recalcular explicitamente com a hipotese; usa posições
                # ORIGINAIS e desconta apenas saltos que terminam antes.
                def ajustado(posicao):
                    return posicao - sum(tam - 2 for pos, tam, _, _ in candidatos
                                         if pos in hipotese and pos + tam <= posicao)
                deslocamento = ajustado(self.rotulos[alvo]) - (ajustado(inicio) + 2)
                if -128 <= deslocamento <= 127:
                    selecionados.add(inicio)
                    alterou = True
            if not alterou:
                break
        if not selecionados:
            return 0
        candidatos_ativos = [(pos, tam, alvo, opcode) for pos, tam, alvo, opcode in candidatos if pos in selecionados]
        finais = [pos + tam for pos, tam, _, _ in candidatos_ativos]
        acumulado = [0]
        for _, tam, _, _ in candidatos_ativos:
            acumulado.append(acumulado[-1] + tam - 2)
        def mapear(posicao):
            return posicao - acumulado[bisect.bisect_right(finais, posicao)]
        saida = bytearray()
        cursor = 0
        pendentes_removidas = set()
        for pos, tam, alvo, opcode in candidatos_ativos:
            saida += antigos[cursor:pos]
            distancia = mapear(self.rotulos[alvo]) - (mapear(pos) + 2)
            if not -128 <= distancia <= 127:
                raise ValueError('Salto curto fora da faixa apos compactacao.')
            saida += bytes((opcode,)) + struct.pack('<b', distancia)
            pendentes_removidas.add(pos + tam - 4)
            cursor = pos + tam
        saida += antigos[cursor:]
        self.codigo = saida
        self.rotulos = {nome: mapear(pos) for nome, pos in self.rotulos.items()}
        self.pendencias = [(mapear(pos), nome) for pos, nome in self.pendencias
                           if pos not in pendentes_removidas]
        self.saltos_compactados = len(selecionados)
        self._candidatos_curto.clear()
        return self.saltos_compactados

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


def _checar_indice(g, expr_indice, tamanho, variaveis, windows, pilha_extra=0):
    # Sempre valida o índice ANTES do deslocamento, inclusive para negativos.
    expressao(g, expr_indice, variaveis, windows, pilha_extra=pilha_extra)
    g.bytes(b'\x48\x85\xC0')  # test rax,rax
    g.salto('erro_indice_lista', 'js')
    g.bytes(b'\x48\x3D' + struct.pack('<I', tamanho))  # cmp rax, tamanho
    g.salto('erro_indice_lista', 'jge')
    g.bytes(b'\x48\xF7\xD8')  # neg rax, para endereços abaixo de RBP


def _total_slots(programa):
    """Calcula o fim real de cada valor, inclusive registros e temporários internos."""
    registros = getattr(programa, 'registros', {})
    tipos = getattr(programa, 'tipos', {})
    return max((indice + _palavras_tipo(tipos.get(nome, 'inteiro'), registros)
                for nome, indice in programa.variaveis.items()), default=0)


def _palavras_tipo(tipo, registros):
    """Quantidade de palavras de oito bytes em um valor completo."""
    if listas_dinamicas.eh_lista_dinamica(tipo):
        return 3
    if isinstance(tipo, str) and tipo in registros:
        return sum(_palavras_tipo(t, registros) for _, t in registros[tipo])
    if isinstance(tipo, tuple) and tipo[0] == 'registro':
        return sum(_palavras_tipo(t, registros) for _, t in tipo[2])
    if isinstance(tipo, tuple) and tipo[0] == 'lista':
        return tipo[2]
    if isinstance(tipo, tuple) and tipo[0] in ('texto', 'bytes'):
        return 1 + (tipo[1] + 7) // 8
    return 1


def _composto(tipo, registros):
    return (isinstance(tipo, str) and tipo in registros) or (
        isinstance(tipo, tuple) and tipo[0] in ('registro', 'lista', 'texto', 'bytes'))


def _copiar_palavras(g, origem, destino, quantidade):
    """Copia valores completos sem extrapolar os quadros de pilha locais."""
    if origem == destino:
        return
    numero = g.proxima_condicao
    g.proxima_condicao += 1
    rotulo = f'copiar_composto_{numero}'
    g.bytes(b'\x4C\x8D\x95' + struct.pack('<i', origem))  # lea r10,[rbp+origem]
    g.bytes(b'\x4C\x8D\x9D' + struct.pack('<i', destino)) # lea r11,[rbp+destino]
    g.bytes(b'\xB9' + struct.pack('<I', quantidade))           # mov ecx, quantidade
    g.marcar(rotulo)
    g.bytes(b'\x49\x8B\x02\x49\x89\x03')      # mov rax,[r10]; mov [r11],rax
    g.bytes(b'\x49\x83\xEA\x08\x49\x83\xEB\x08')  # sub ponteiros,8
    g.bytes(b'\xFF\xC9')
    g.salto(rotulo, 'jnz')


def _copiar_para_retorno(g, origem, quantidade):
    """O chamador fornece endereço de destino na palavra oculta de retorno."""
    numero = g.proxima_condicao
    g.proxima_condicao += 1
    rotulo = f'retornar_composto_{numero}'
    g.bytes(b'\x4C\x8D\x95' + struct.pack('<i', origem))
    g.bytes(b'\x4C\x8B\x5D\x18')   # mov r11,[rbp+24]
    g.bytes(b'\xB9' + struct.pack('<I', quantidade)) # mov ecx,count
    g.marcar(rotulo)
    g.bytes(b'\x49\x8B\x02\x49\x89\x03')
    g.bytes(b'\x49\x83\xEA\x08\x49\x83\xEB\x08')
    g.bytes(b'\xFF\xC9')
    g.salto(rotulo, 'jnz')


def expressao(g, expr, variaveis, windows, registradores=None, pilha_extra=0, destino_composto=None):
    tipo = expr[0]
    if tipo in ('numero', 'logico'):
        carregar_numero(g, expr[1])
    elif tipo == 'chamada':
        nome, argumentos = expr[1], expr[2]
        if nome not in getattr(g, 'funcoes', {}):
            raise ValueError(f'Função sem rótulo nativo: {nome}.')
        # Convenção interna RS: argumentos completos empilhados por valor.
        # Para retornos compostos, o chamador oferece um endereço privado.
        assinatura = g.funcoes[nome].parametros
        retorno = g.funcoes[nome].retorno
        composto_retorno = _composto(retorno, g.registros)
        if composto_retorno and destino_composto is None:
            raise ValueError(f'Retorno composto de {nome} precisa de destino explícito.')
        palavras = sum(_palavras_tipo(t, g.registros) for _, t in assinatura)
        ocultas = 1 + int(composto_retorno)  # orçamento de pilha e destino opcional
        ajustar = (pilha_extra + palavras + ocultas) % 2
        if ajustar:
            g.bytes(b'\x48\x83\xEC\x08')
        empilhados = 0
        for argumento, (_, tipo_parametro) in zip(argumentos, assinatura):
            quantidade = _palavras_tipo(tipo_parametro, g.registros)
            if _composto(tipo_parametro, g.registros):
                if argumento[0] == 'temporario_composto':
                    expressao(g, argumento[2], variaveis, windows, registradores,
                             pilha_extra + ajustar + empilhados,
                             destino_composto=argumento[1])
                    origem = argumento[1]
                elif argumento[0] == 'var':
                    origem = argumento[1]
                else:
                    raise ValueError('Argumento composto exige variável ou chamada válida.')
                offset = deslocamento_variavel(variaveis, origem, windows)
                # A ordem da pilha acompanha os campos/palavras do valor.
                numero = g.proxima_condicao
                g.proxima_condicao += 1
                rotulo = f'empilhar_valor_{numero}'
                g.bytes(b'\x4C\x8D\x95' + struct.pack('<i', offset))
                g.bytes(b'\xB9' + struct.pack('<I', quantidade))
                g.marcar(rotulo)
                g.bytes(b'\x49\x8B\x02\x50') # mov rax,[r10]; push rax
                g.bytes(b'\x49\x83\xEA\x08\xFF\xC9')
                g.salto(rotulo, 'jnz')
            else:
                expressao(g, argumento, variaveis, windows, registradores,
                         pilha_extra + ajustar + empilhados)
                g.bytes(b'\x50')
            empilhados += quantidade
        if composto_retorno:
            if destino_composto == '__rs_retorno_externo':
                g.bytes(b'\x48\x8B\x45\x18') # carrega ponteiro do chamador anterior
            else:
                destino = deslocamento_variavel(variaveis, destino_composto, windows)
                g.bytes(b'\x48\x8D\x85' + struct.pack('<i', destino))
            g.bytes(b'\x50')
        if '__rs_uso_pilha' in variaveis:
            offset = deslocamento_variavel(variaveis, '__rs_uso_pilha', windows)
            g.bytes(b'\x48\x8B\x85' + struct.pack('<i', offset))
        else:
            carregar_numero(g, 0)
        g.bytes(b'\x50')  # consumo de pilha acumulado
        g.chamada(f'funcao_{nome}')
        limpar = 8 * (palavras + ocultas + ajustar)
        if limpar:
            if limpar < 128:
                g.bytes(b'\x48\x83\xC4' + struct.pack('<B', limpar))
            else:
                g.bytes(b'\x48\x81\xC4' + struct.pack('<I', limpar))
    elif tipo == 'empreste_lista_dinamica':
        listas_dinamicas.emprestar(g, variaveis, expr[1], windows)
    elif tipo == 'quantidade_lista_emprestada':
        listas_dinamicas.quantidade_emprestada(g, variaveis, expr[1], windows)
    elif tipo == 'capacidade_lista_emprestada':
        listas_dinamicas.quantidade_emprestada(g, variaveis, expr[1], windows, capacidade=True)
    elif tipo == 'indice_lista_emprestada':
        listas_dinamicas.ler_indice(g, variaveis, expr[1], expr[2], windows, expressao, emprestada=True)
    elif tipo == 'quantidade_lista_dinamica':
        listas_dinamicas.quantidade(g, variaveis, expr[1], windows)
    elif tipo == 'capacidade_lista_dinamica':
        listas_dinamicas.quantidade(g, variaveis, expr[1], windows, capacidade=True)
    elif tipo == 'indice_lista_dinamica':
        listas_dinamicas.ler_indice(g, variaveis, expr[1], expr[2], windows, expressao)
    elif tipo in ('tamanho_texto', 'tamanho_bytes'):
        offset = deslocamento_variavel(variaveis, expr[1], windows)
        g.bytes(b'\x48\x8B\x85' + struct.pack('<i', offset))
    elif tipo == 'indice_bytes':
        bytes_seguros.ler(g, expr[1], expr[2], variaveis, g.tipos_atual,
                          windows, expressao, deslocamento_variavel,
                          pilha_extra=pilha_extra)
    elif tipo == 'indice':
        nome, indice, tamanho = expr[1:]
        _checar_indice(g, indice, tamanho, variaveis, windows, pilha_extra)
        offset = deslocamento_variavel(variaveis, nome, windows)
        g.bytes(b'\x48\x8B\x84\xC5' + struct.pack('<i', offset))  # mov rax,[rbp+rax*8+disp]
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
            expressao(g, expr[1], variaveis, windows, registradores, pilha_extra)
            g.bytes(b'\x48\xF7\xD8')  # neg rax
            g.salto('erro_overflow_aritmetico', 'jo')
    elif tipo == 'comparacao':
        _, op, esquerda, direita = expr
        expressao(g, esquerda, variaveis, windows, registradores, pilha_extra)
        g.bytes(b'\x50')  # salva o operando esquerdo
        expressao(g, direita, variaveis, windows, registradores, pilha_extra + 1)
        g.bytes(b'\x59')  # rcx = operando esquerdo
        g.bytes(b'\x48\x39\xC1')  # cmp rcx, rax (inteiros com sinal)
        codigo = {'==': 0x94, '!=': 0x95, '<': 0x9C, '<=': 0x9E, '>': 0x9F, '>=': 0x9D}[op]
        g.bytes(bytes((0x0F, codigo, 0xC0)) + b'\x0F\xB6\xC0')  # setcc al; movzx eax,al
    elif tipo == 'bin':
        _, op, esquerda, direita = expr
        expressao(g, esquerda, variaveis, windows, registradores, pilha_extra)
        g.bytes(b'\x50')  # push rax
        expressao(g, direita, variaveis, windows, registradores, pilha_extra + 1)
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



TAMANHO_CACHE_ENTRADA = 1024


def _offsets_cache_entrada(slots, windows):
    # All offsets are relative to the main frame pointer (RBP); never to a
    # short-lived helper frame. In Windows [rbp-8] stores the saved RBX.
    base = -(16 + slots * 8) if windows else -(8 + slots * 8)
    capacidade = 256 if windows else TAMANHO_CACHE_ENTRADA
    return base, base - 8, base - 8 - capacidade


def emitir_cache_entrada(g, windows, slots):
    """Yield one buffered byte in R10b; RAX=1 byte, 0 EOF, -1 I/O error.

    Persistent state belongs to the program's stack frame. Reads are shared
    between leia(inteiro), leia(lista[indice]) and leia(texto), so bytes fetched
    after a newline are retained for later calls. The helper preserves RSI.
    """
    cursor, quantidade, buffer = _offsets_cache_entrada(slots, windows)
    bloco = 256 if windows else TAMANHO_CACHE_ENTRADA
    g.marcar('entrada_proximo_byte')
    g.bytes(b'\x56')  # push rsi: preserve pointer to caller's UTF-8 buffer
    g.bytes(b'\x48\x8B\x85' + struct.pack('<i', cursor))
    g.bytes(b'\x48\x3B\x85' + struct.pack('<i', quantidade))
    g.salto('entrada_tem_byte', 'jb')
    if windows:
        # Entering helper: rsp%16=8; push rsi -> aligned, 0x30 keeps it.
        # shadow space [rsp+0..0x1f], overlapped NULL at +0x20,
        # bytes-read DWORD at +0x28.
        g.bytes(b'\x48\x83\xEC\x30')
        g.bytes(b'\x4C\x89\xE1')  # rcx = R12 = handle stdin
        g.bytes(b'\x48\x8D\x95' + struct.pack('<i', buffer))  # rdx = buffer
        g.bytes(b'\x41\xB8' + struct.pack('<I', bloco))
        g.bytes(b'\x4C\x8D\x4C\x24\x28')  # r9= &nread
        g.bytes(b'\x48\xC7\x44\x24\x20\x00\x00\x00\x00')
        g.relativo(b'\xFF\x15', 'ReadFile')
        g.bytes(b'\x85\xC0')
        g.salto('entrada_windows_ok', 'jnz')
        g.relativo(b'\xFF\x15', 'GetLastError')
        g.bytes(b'\x83\xF8\x6D')  # ERROR_BROKEN_PIPE (109)
        g.salto('entrada_windows_eof', 'je')
        g.bytes(b'\x83\xF8\x26')  # ERROR_HANDLE_EOF (38)
        g.salto('entrada_windows_eof', 'je')
        g.bytes(b'\x48\x83\xC4\x30')
        g.salto('entrada_falha')
        g.marcar('entrada_windows_eof')
        g.bytes(b'\x48\x83\xC4\x30')
        g.salto('entrada_eof')
        g.marcar('entrada_windows_ok')
        g.bytes(b'\x8B\x44\x24\x28') # eax=nread
        g.bytes(b'\x48\x83\xC4\x30')
    else:
        g.bytes(b'\x31\xC0\x31\xFF')  # read fd0
        g.bytes(b'\x48\x8D\xB5' + struct.pack('<i', buffer))
        g.bytes(b'\xBA' + struct.pack('<I', TAMANHO_CACHE_ENTRADA))
        g.bytes(b'\x0F\x05')
        g.bytes(b'\x48\x85\xC0')
        g.salto('entrada_falha', 'js')
    g.bytes(b'\x48\x85\xC0')
    g.salto('entrada_eof', 'jz')
    g.bytes(b'\x48\x89\x85' + struct.pack('<i', quantidade))
    g.bytes(b'\x48\xC7\x85' + struct.pack('<i', cursor) + b'\x00\x00\x00\x00')
    g.marcar('entrada_tem_byte')
    g.bytes(b'\x48\x8B\x85' + struct.pack('<i', cursor))
    g.bytes(b'\x44\x0F\xB6\x94\x05' + struct.pack('<i', buffer))  # movzx r10d,[rbp+rax+buffer]
    g.bytes(b'\x48\xFF\xC0')  # inc rax
    g.bytes(b'\x48\x89\x85' + struct.pack('<i', cursor))
    g.bytes(b'\xB8\x01\x00\x00\x00')
    g.salto('entrada_retorno')
    g.marcar('entrada_eof')
    g.bytes(b'\x31\xC0')
    g.salto('entrada_retorno')
    g.marcar('entrada_falha')
    g.bytes(b'\x48\xC7\xC0\xFF\xFF\xFF\xFF')
    g.marcar('entrada_retorno')
    g.bytes(b'\x5E\xC3')  # pop rsi; ret

def ler_inteiro(g, windows):
    """Leitura de um inteiro ASCII com sinal em stdin, sem alocacao dinamica.

    Aceita espacos antes/depois, sinal opcional, CRLF ou LF e EOF depois
    de digitos. Falhas de IO, entrada vazia, letra e overflow terminam em 1.
    Usa cache compartilhado de stdin em blocos de 1024 bytes.
    """
    g.marcar('ler_inteiro')
    # Windows: registradores r13-r15 sao callee-saved; Linux tambem.
    g.bytes(b'\x41\x55\x41\x56\x41\x57')  # push r13 r14 r15
    g.bytes(b'\x48\x83\xEC\x40' if windows else b'\x48\x83\xEC\x10')
    g.bytes(b'\x45\x31\xED\x45\x31\xF6\x45\x31\xFF')  # xor r13d, r14d, r15d
    # r13 = magnitude, r14d = estado (0 inicio,1 sinal,2 digitos,3 sufixo), r15d = negativo
    g.marcar('leia_proximo_byte')
    g.chamada('entrada_proximo_byte')
    g.bytes(b'\x85\xC0')  # test eax,eax: 1 byte, 0 EOF, -1 I/O error
    g.salto('erro_entrada_invalida', 'js')
    g.salto('leia_fim_entrada', 'jz')

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


def _endereco_buffer(variaveis, nome, tipos, windows):
    capacidade = tipos[nome][1]
    dados = deslocamento_variavel(variaveis, nome, windows) - 8 * ((capacidade+7)//8)
    comprimento = deslocamento_variavel(variaveis, nome, windows)
    return dados, comprimento, capacidade


def _imprimir_buffer(g, nome, variaveis, tipos, windows):
    dados, comprimento, _ = _endereco_buffer(variaveis, nome, tipos, windows)
    if windows:
        g.bytes(b'\x48\x89\xD9')  # RCX = stdout
        g.bytes(b'\x48\x8D\x95' + struct.pack('<i', dados))  # RDX=bytes
        g.bytes(b'\x44\x8B\x85' + struct.pack('<i', comprimento))  # R8D=tamanho
        g.relativo(b'\x4C\x8D\x0D', 'contador')
        g.bytes(b'\xC7\x44\x24\x20\x00\x00\x00\x00')
        g.relativo(b'\xFF\x15', 'WriteFile')
    else:
        g.bytes(b'\xB8\x01\x00\x00\x00\xBF\x01\x00\x00\x00')
        g.bytes(b'\x48\x8D\xB5' + struct.pack('<i', dados))
        g.bytes(b'\x48\x8B\x95' + struct.pack('<i', comprimento))
        g.bytes(b'\x0F\x05')


def _copiar_para_buffer(g, nome, origem, anexar, variaveis, tipos, windows, mensagens):
    dados, comprimento, capacidade = _endereco_buffer(variaveis, nome, tipos, windows)
    if origem[0] == 'literal':
        literal = origem[1]
        tamanho = len(literal.encode('utf-8'))
        indice = len(mensagens)
        mensagens[indice] = literal
        carregar_numero(g, tamanho)
        g.bytes(b'\x48\x89\xC1')  # RCX=tamanho
    else:
        dados_origem, comprimento_origem, _ = _endereco_buffer(variaveis, origem[1], tipos, windows)
        g.bytes(b'\x48\x8B\x8D' + struct.pack('<i', comprimento_origem))
    if anexar:
        g.bytes(b'\x48\x8B\x85' + struct.pack('<i', comprimento))
    else:
        g.bytes(b'\x31\xC0')  # RAX=0
    g.bytes(b'\x48\x01\xC8')  # soma novo comprimento + bytes adicionados
    g.bytes(b'\x48\x3D' + struct.pack('<I', capacidade))
    g.salto('erro_texto_capacidade', 'ja')
    g.bytes(b'\x48\x8D\xBD' + struct.pack('<i', dados))
    if anexar:
        g.bytes(b'\x4C\x8B\x85' + struct.pack('<i', comprimento))  # R8=velho tamanho
        g.bytes(b'\x4C\x01\xC7')  # add rdi,r8
    if origem[0] == 'literal':
        g.relativo(b'\x48\x8D\x35', f'mensagem_{indice}')
    else:
        g.bytes(b'\x48\x8D\xB5' + struct.pack('<i', dados_origem))
    g.bytes(b'\xFC\xF3\xA4')  # cld; rep movsb
    g.bytes(b'\x48\x89\x85' + struct.pack('<i', comprimento))


def ler_buffer_texto(g, windows):
    """Leitura linha-a-linha em bytes UTF-8, sem ultrapassar capacidade."""
    g.marcar('ler_buffer_texto')
    # RSI aponta para os dados, EDX informa a capacidade.
    g.bytes(b'\x41\x55\x41\x56\x41\x57\x56')  # preserva r13/r14/r15/rsi
    g.bytes(b'\x48\x83\xEC\x48' if windows else b'\x48\x83\xEC\x18')
    capoff = 0x40 if windows else 0x10
    g.bytes(b'\x48\x89\x54\x24' + bytes([capoff]))  # cap = rdx
    if not windows:
        g.bytes(b'\x48\x89\x74\x24\x08') # salva ptr do buffer (rsi)
    g.bytes(b'\x45\x31\xED\x45\x31\xF6\x45\x31\xFF')
    # r13=count, r14=continuation bytes remaining, r15=first continuation constraint
    g.marcar('texto_ler_byte')
    g.chamada('entrada_proximo_byte')
    g.bytes(b'\x85\xC0')
    g.salto('erro_texto_entrada', 'js')
    g.salto('texto_concluir', 'jz')

    g.bytes(b'\x41\x80\xFA\x0A') # byte == LF
    g.salto('texto_concluir', 'jz')
    g.bytes(b'\x45\x85\xF6') # r14>0?
    g.salto('texto_validar_cont', 'jnz')
    # Novo codepoint: ASCII; ou inicio multibyte UTF-8 legal.
    g.bytes(b'\x41\x80\xFA\x80')
    g.salto('texto_armazena', 'jb')
    g.bytes(b'\x41\x80\xFA\xC2')
    g.salto('erro_texto_utf8', 'jb')
    g.bytes(b'\x41\x80\xFA\xDF')
    g.salto('texto_dois', 'jbe')
    g.bytes(b'\x41\x80\xFA\xEF')
    g.salto('texto_tres', 'jbe')
    g.bytes(b'\x41\x80\xFA\xF4')
    g.salto('texto_quatro', 'jbe')
    g.salto('erro_texto_utf8')
    g.marcar('texto_dois')
    g.bytes(b'\x41\xBE\x01\x00\x00\x00')
    g.salto('texto_armazena')
    g.marcar('texto_tres')
    g.bytes(b'\x41\xBE\x02\x00\x00\x00')
    g.bytes(b'\x41\x80\xFA\xE0')
    g.salto('texto_tipo_e0', 'je')
    g.bytes(b'\x41\x80\xFA\xED')
    g.salto('texto_tipo_ed', 'je')
    g.salto('texto_armazena')
    g.marcar('texto_tipo_e0')
    g.bytes(b'\x41\xBF\x01\x00\x00\x00')
    g.salto('texto_armazena')
    g.marcar('texto_tipo_ed')
    g.bytes(b'\x41\xBF\x02\x00\x00\x00')
    g.salto('texto_armazena')
    g.marcar('texto_quatro')
    g.bytes(b'\x41\xBE\x03\x00\x00\x00')
    g.bytes(b'\x41\x80\xFA\xF0')
    g.salto('texto_tipo_f0', 'je')
    g.bytes(b'\x41\x80\xFA\xF4')
    g.salto('texto_tipo_f4', 'je')
    g.salto('texto_armazena')
    g.marcar('texto_tipo_f0')
    g.bytes(b'\x41\xBF\x03\x00\x00\x00')
    g.salto('texto_armazena')
    g.marcar('texto_tipo_f4')
    g.bytes(b'\x41\xBF\x04\x00\x00\x00')
    g.salto('texto_armazena')
    g.marcar('texto_validar_cont')
    g.bytes(b'\x41\x80\xFA\x80')
    g.salto('erro_texto_utf8', 'jb')
    g.bytes(b'\x41\x80\xFA\xBF')
    g.salto('erro_texto_utf8', 'ja')
    for flag, bound, salto in [(1,0xA0,'jb'),(2,0x9F,'ja'),(3,0x90,'jb'),(4,0x8F,'ja')]:
        rotulo=f'texto_flag_{flag}_fim'
        g.bytes(b'\x41\x83\xFF' + bytes([flag]))
        g.salto(rotulo, 'jne')
        g.bytes(b'\x41\x80\xFA' + bytes([bound]))
        g.salto('erro_texto_utf8', salto)
        g.marcar(rotulo)
    g.bytes(b'\x41\xFF\xCE\x45\x31\xFF') # --r14; r15=0
    g.marcar('texto_armazena')
    g.bytes(b'\x4C\x3B\x6C\x24' + bytes([capoff])) # cmp count,cap
    g.salto('erro_texto_capacidade', 'jge')
    g.bytes(b'\x46\x88\x14\x2E') # [rsi+r13]=r10b
    g.bytes(b'\x49\xFF\xC5') # ++count
    g.salto('texto_ler_byte')
    g.marcar('texto_concluir')
    g.bytes(b'\x45\x85\xF6')
    g.salto('erro_texto_utf8', 'jnz')
    # Trata CRLF sem incluir CR no texto retornado.
    g.bytes(b'\x4D\x85\xED')
    g.salto('texto_retorno', 'jz')
    g.bytes(b'\x42\x0F\xB6\x44\x2E\xFF') # last byte
    g.bytes(b'\x83\xF8\x0D')
    g.salto('texto_retorno', 'jne')
    g.bytes(b'\x49\xFF\xCD')
    g.marcar('texto_retorno')
    g.bytes(b'\x4C\x89\xE8') # RAX=count
    g.bytes(b'\x48\x83\xC4\x48' if windows else b'\x48\x83\xC4\x18')
    g.bytes(b'\x5E\x41\x5F\x41\x5E\x41\x5D\xC3')


def reservar_pilha(g, bytes_reservados):
    """Reserva quadro com sondagem de páginas, sem saltar a página de guarda.

    A sondagem é necessária para crescimento seguro da pilha Windows x64.
    Usamos também no Linux para evitar pular regiões não mapeadas.
    """
    if bytes_reservados <= 0:
        return
    if bytes_reservados < 4096:
        g.bytes(b'\x48\x81\xEC' + struct.pack('<I', bytes_reservados))
        return
    repeticoes, restante = divmod(bytes_reservados, 4096)
    identificador = g.proxima_condicao
    g.proxima_condicao += 1
    rotulo = f'sondagem_pilha_{identificador}'
    g.bytes(b'\xB9' + struct.pack('<I', repeticoes))
    g.marcar(rotulo)
    g.bytes(b'\x48\x81\xEC' + struct.pack('<I', 4096))
    g.bytes(b'\xC6\x04\x24\x00')  # escreve na página atual
    g.bytes(b'\xFF\xC9')                # dec ecx
    g.salto(rotulo, 'jnz')
    if restante:
        g.bytes(b'\x48\x81\xEC' + struct.pack('<I', restante))
        g.bytes(b'\xC6\x04\x24\x00')


def montar_codigo(programa, windows, emissor_alternativo=None):
    g = Gerador()
    g.funcoes = getattr(programa, 'funcoes', {})
    g.registros = getattr(programa, 'registros', {})
    g.campos_atual = getattr(programa, 'campos_registro', {})
    funcao_atual = None
    variaveis = programa.variaveis
    mensagens = {}
    tem_leitura = any(op[0] in ('leia_int', 'leia_indice', 'leia_indice_dinamico', 'leia_texto') for op in percorrer_instrucoes(programa.instrucoes))
    tem_arquivos = (any(op[0] in ('grave_arquivo', 'carregue_arquivo')
                        for op in percorrer_instrucoes(programa.instrucoes))
                    or any(op[0] in ('grave_arquivo', 'carregue_arquivo')
                        for f in g.funcoes.values() for op in percorrer_instrucoes(f.programa.instrucoes)))
    tem_arquivos_posicionais = (any(op[0] in ('grave_trecho', 'carregue_trecho')
                        for op in percorrer_instrucoes(programa.instrucoes))
                    or any(op[0] in ('grave_trecho', 'carregue_trecho')
                        for f in g.funcoes.values() for op in percorrer_instrucoes(f.programa.instrucoes)))
    tipos = getattr(programa, 'tipos', {})
    tem_dinamicas = any(listas_dinamicas.eh_lista_dinamica(t)
                        for t in tipos.values()) or any(
        listas_dinamicas.eh_lista_dinamica(t)
        for f in g.funcoes.values() for t in f.programa.tipos.values())
    tem_listas = tem_dinamicas or any(isinstance(t, tuple) and t[0] == 'lista' for t in tipos.values())
    tem_textos = any(isinstance(t, tuple) and t[0] == 'texto' for t in tipos.values())
    tem_bytes = any(isinstance(t, tuple) and t[0] == 'bytes'
                    for t in tipos.values()) or any(
        isinstance(t, tuple) and t[0] == 'bytes'
        for f in g.funcoes.values() for t in f.programa.tipos.values())
    tem_recursos = (any(t == 'arquivo' for t in tipos.values()) or
                    any(t == 'arquivo' for f in g.funcoes.values()
                        for t in f.programa.tipos.values()))
    tem_encerre = any(op[0] == 'encerre' for op in percorrer_instrucoes(programa.instrucoes)) or any(
        op[0] == 'encerre' for f in g.funcoes.values()
        for op in percorrer_instrucoes(f.programa.instrucoes))
    g.tipos_atual = tipos
    tem_leitura_texto = any(op[0] == 'leia_texto' for op in percorrer_instrucoes(programa.instrucoes))
    slots = _total_slots(programa)
    memoria_cache = ((256 if windows else TAMANHO_CACHE_ENTRADA) + 16) if tem_leitura else 0
    if windows:
        n = slots
        frame = ((8 * n + memoria_cache + 0x38 + 15) // 16) * 16 + 8
        g.bytes(b'\x55\x48\x89\xE5\x53')  # push rbp; mov rbp,rsp; push rbx
        reservar_pilha(g, frame)
        g.bytes(b'\xB9' + struct.pack('<I', 65001))
        g.relativo(b'\xFF\x15', 'SetConsoleOutputCP')
        if tem_leitura_texto:
            g.bytes(b'\xB9' + struct.pack('<I',65001))
            g.relativo(b'\xFF\x15', 'SetConsoleCP')
        g.bytes(b'\xB9\xF5\xFF\xFF\xFF')
        g.relativo(b'\xFF\x15', 'GetStdHandle')
        g.bytes(b'\x48\x89\xC3')  # RBX = stdout handle
        if tem_leitura:
            g.bytes(b'\xB9\xF6\xFF\xFF\xFF')  # STD_INPUT_HANDLE (-10)
            g.relativo(b'\xFF\x15', 'GetStdHandle')
            g.bytes(b'\x49\x89\xC4')  # R12 = stdin handle
    else:
        frame = alinhar(slots * 8 + memoria_cache, 16)
        g.bytes(b'\x55\x48\x89\xE5')
        if frame:
            reservar_pilha(g, frame)

    if tem_dinamicas:
        listas_dinamicas.inicializar_inativas(g, variaveis, tipos, windows)
    if tem_recursos:
        for nome, tipo in tipos.items():
            if tipo == 'arquivo':
                offset = deslocamento_variavel(variaveis, nome, windows)
                g.bytes(b'\x48\xC7\x85' + struct.pack('<i',offset) + b'\xFF\xFF\xFF\xFF')

    if tem_leitura:
        offset_cursor, offset_quantidade, _ = _offsets_cache_entrada(slots, windows)
        g.bytes(b'\x31\xC0')
        for offset in (offset_cursor, offset_quantidade):
            g.bytes(b'\x48\x89\x85' + struct.pack('<i', offset))

    def emitir_bloco(instrucoes, laco=None):
        for op in instrucoes:
            if op[0] == 'texto':
                n = len(mensagens)
                mensagens[n] = op[1]
                escreve_literal(g, n, op[1], windows)
            elif op[0] in ('crie_texto', 'crie_bytes'):
                nome, capacidade = op[1:]
                dados, comprimento, _ = _endereco_buffer(variaveis, nome, tipos, windows)
                g.bytes(b'\x31\xC0')
                total = 1 + (capacidade+7)//8
                if total < 64:
                    for k in range(total):
                        g.bytes(b'\x48\x89\x85' + struct.pack('<i', comprimento - 8*k))
                else:
                    identificador = g.proxima_condicao
                    g.proxima_condicao += 1
                    rotulo = f'zerar_texto_{identificador}'
                    g.bytes(b'\x48\x8D\xBD' + struct.pack('<i', comprimento))  # lea rdi, [rbp+disp]
                    g.bytes(b'\xB9' + struct.pack('<I', total))
                    g.marcar(rotulo)
                    g.bytes(b'\x48\x89\x07\x48\x83\xEF\x08\xFF\xC9')
                    g.salto(rotulo, 'jnz')
            elif op[0] == 'modifique_texto':
                _, modo, nome, origem = op
                _copiar_para_buffer(g, nome, origem, modo=='junte', variaveis, tipos, windows, mensagens)
            elif op[0] in ('limpe_texto', 'limpe_bytes'):
                comprimento = deslocamento_variavel(variaveis, op[1], windows)
                g.bytes(b'\x31\xC0\x48\x89\x85' + struct.pack('<i', comprimento))
            elif op[0] == 'adicione_byte':
                bytes_seguros.acrescentar(g, op[1], op[2], variaveis, tipos,
                    windows, expressao, deslocamento_variavel)
            elif op[0] == 'atribua_byte':
                bytes_seguros.substituir(g, op[1], op[2], op[3], variaveis, tipos,
                    windows, expressao, deslocamento_variavel)
            elif op[0] == 'imprima_texto':
                _imprimir_buffer(g, op[1], variaveis, tipos, windows)
                msg_indice = len(mensagens)
                mensagens[msg_indice] = '\n'
                escreve_literal(g, msg_indice, '\n', windows)
            elif op[0] in ('grave_arquivo', 'carregue_arquivo'):
                arquivos.emitir_comando(g, op, variaveis, tipos, windows, mensagens,
                                        _endereco_buffer, deslocamento_variavel)
            elif op[0] in ('grave_trecho', 'carregue_trecho'):
                arquivos_posicionais.emitir_comando(g, op, variaveis, tipos, windows,
                    mensagens, _endereco_buffer, deslocamento_variavel, expressao)
            elif op[0] == 'crie_recurso':
                offset = deslocamento_variavel(variaveis, op[1], windows)
                g.bytes(b'\x48\xC7\x85' + struct.pack('<i',offset) + b'\xFF\xFF\xFF\xFF')
            elif op[0] in ('abra_recurso','feche_recurso','sincronize_recurso','grave_em','carregue_de'):
                arquivos_abertos.emitir_comando(g, op, variaveis, tipos, windows,
                    mensagens, _endereco_buffer, expressao)
            elif op[0] == 'leia_texto':
                nome = op[1]
                dados, comprimento, capacidade = _endereco_buffer(variaveis, nome, tipos, windows)
                g.bytes(b'\x48\x8D\xB5' + struct.pack('<i', dados)) # RSI=buffer
                carregar_numero(g, capacidade)
                g.bytes(b'\x48\x89\xC2') # RDX=cap
                g.chamada('ler_buffer_texto')
                g.bytes(b'\x48\x89\x85' + struct.pack('<i', comprimento))
            elif op[0] == 'crie_lista_dinamica':
                listas_dinamicas.criar(g, variaveis, op[1], windows)
            elif op[0] == 'mova_lista_dinamica':
                listas_dinamicas.mover(g, variaveis, op[1], op[2], windows,
                                       listas_dinamicas.largura_elemento(g, tipos[op[1]]))
            elif op[0] == 'libere_escopo_listas':
                for nome in op[1]:
                    if tipos[nome] == 'arquivo':
                        arquivos_abertos.emitir_auto_fechar(g, variaveis, nome, windows)
                    else:
                        listas_dinamicas.liberar(g, variaveis, nome, windows,
                                              largura=listas_dinamicas.largura_elemento(g, tipos[nome]))
            elif op[0] == 'adicione_lista_dinamica':
                listas_dinamicas.acrescentar(g, variaveis, op[1], op[2], windows, expressao,
                                            listas_dinamicas.largura_elemento(g, tipos[op[1]]))
            elif op[0] == 'limpe_lista_dinamica':
                listas_dinamicas.limpar(g, variaveis, op[1], windows)
            elif op[0] == 'remova_ultimo_lista_dinamica':
                listas_dinamicas.retirar(g, variaveis, op[1], windows)
            elif op[0] == 'libere_lista_dinamica':
                listas_dinamicas.liberar(g, variaveis, op[1], windows, explicito=True,
                                        largura=listas_dinamicas.largura_elemento(g, tipos[op[1]]))
            elif op[0] == 'atribua_indice_dinamico':
                largura = listas_dinamicas.largura_elemento(g, tipos[op[1]])
                if tipos[op[1]][1] in g.registros:
                    listas_dinamicas.escrever_composto(g, variaveis, op[1], op[2], op[3],
                                                       windows, expressao, largura)
                else:
                    listas_dinamicas.escrever_indice(g, variaveis, op[1], op[2], op[3],
                                                    windows, expressao)
            elif op[0] == 'leia_indice_dinamico':
                listas_dinamicas.indice(g, variaveis, op[1], op[2], windows, expressao)
                g.bytes(b'\x50\x48\x83\xEC\x08')
                g.chamada('ler_inteiro')
                g.bytes(b'\x48\x83\xC4\x08\x59')
                base = deslocamento_variavel(variaveis, op[1], windows)
                g.bytes(b'\x48\x8B\x95' + struct.pack('<i', base))
                g.bytes(b'\x48\x89\x04\xCA')
            elif op[0] == 'crie_lista':
                nome, tamanho = op[1:]
                inicio = deslocamento_variavel(variaveis, nome, windows)
                g.bytes(b'\x31\xC0')  # xor eax,eax
                if tamanho < 64:
                    for k in range(tamanho):
                        g.bytes(b'\x48\x89\x85' + struct.pack('<i', inicio-8*k))
                else:
                    identificador = g.proxima_condicao
                    g.proxima_condicao += 1
                    rotulo = f'zerar_lista_{identificador}'
                    g.bytes(b'\x48\x8D\xBD' + struct.pack('<i', inicio))
                    g.bytes(b'\xB9' + struct.pack('<I', tamanho))
                    g.marcar(rotulo)
                    g.bytes(b'\x48\x89\x07\x48\x83\xEF\x08\xFF\xC9')
                    g.salto(rotulo, 'jnz')
            elif op[0] == 'atribua_indice':
                _, nome, indice, valor, tamanho = op
                # Avalia e verifica índice antes de avaliar valor. Preserva erro de índice.
                _checar_indice(g, indice, tamanho, variaveis, windows)
                g.bytes(b'\x50')  # push indice negativo
                expressao(g, valor, variaveis, windows, pilha_extra=1)
                g.bytes(b'\x59')  # pop rcx = indice negativo
                offset = deslocamento_variavel(variaveis, nome, windows)
                g.bytes(b'\x48\x89\x84\xCD' + struct.pack('<i', offset))
            elif op[0] == 'leia_indice':
                _, nome, indice, tamanho = op
                # Rejeita índices inválidos ANTES de solicitar entrada.
                _checar_indice(g, indice, tamanho, variaveis, windows)
                g.bytes(b'\x50\x48\x83\xEC\x08')  # push índice; mantém stack alinhada
                g.chamada('ler_inteiro')
                g.bytes(b'\x48\x83\xC4\x08\x59')  # restaura índice negativo em RCX
                offset = deslocamento_variavel(variaveis, nome, windows)
                g.bytes(b'\x48\x89\x84\xCD' + struct.pack('<i', offset))  # store RAX
            elif op[0] == 'crie_registro':
                # Registros históricos de campos simples preservam sua emissão.
                tipo_registro = tipos[op[1]]
                tem_campos_compostos = any(_composto(t, g.registros) for _, t in tipo_registro[2])
                if not tem_campos_compostos:
                    for campo in op[2]:
                        carregar_numero(g, 0)
                        offset = deslocamento_variavel(variaveis, campo, windows)
                        g.bytes(b'\x48\x89\x85' + struct.pack('<i', offset))
                else:
                    quantidade = _palavras_tipo(tipo_registro, g.registros)
                    inicio = deslocamento_variavel(variaveis, op[1], windows)
                    g.bytes(b'\x31\xC0')
                    if quantidade < 64:
                        for posicao in range(quantidade):
                            g.bytes(b'\x48\x89\x85' + struct.pack('<i', inicio - 8 * posicao))
                    else:
                        numero = g.proxima_condicao
                        g.proxima_condicao += 1
                        rotulo = f'zerar_registro_{numero}'
                        g.bytes(b'\x48\x8D\xBD' + struct.pack('<i', inicio))
                        g.bytes(b'\xB9' + struct.pack('<I', quantidade))
                        g.marcar(rotulo)
                        g.bytes(b'\x48\x89\x07\x48\x83\xEF\x08\xFF\xC9')
                        g.salto(rotulo, 'jnz')
            elif op[0] == 'copie_composto':
                destino, origem = op[1], op[2]
                if origem[0] == 'chamada':
                    expressao(g, origem, variaveis, windows, destino_composto=destino)
                elif origem[0] in ('indice_lista_dinamica', 'indice_lista_emprestada'):
                    nome = origem[1]
                    largura = listas_dinamicas.largura_elemento(g, tipos[nome])
                    listas_dinamicas.copiar_composto(g, variaveis, destino, nome, origem[2],
                        windows, expressao, largura,
                        emprestada=(origem[0] == 'indice_lista_emprestada'))
                else:
                    if origem[0] != 'var':
                        raise ValueError('Cópia de composto exige valor de variável.')
                    quantidade = _palavras_tipo(tipos[destino], g.registros)
                    _copiar_palavras(
                        g, deslocamento_variavel(variaveis, origem[1], windows),
                        deslocamento_variavel(variaveis, destino, windows), quantidade)
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
            elif op[0] == 'retorne':
                if funcao_atual is None:
                    raise ValueError('Retorno fora de função (erro interno).')
                if _composto(g.funcoes[funcao_atual].retorno, g.registros):
                    if op[1][0] == 'chamada':
                        expressao(g, op[1], variaveis, windows,
                                 destino_composto='__rs_retorno_externo')
                    elif op[1][0] == 'var':
                        _copiar_para_retorno(g,
                            deslocamento_variavel(variaveis, op[1][1], windows),
                            _palavras_tipo(g.funcoes[funcao_atual].retorno, g.registros))
                    else:
                        raise ValueError('Retorno composto exige variável ou chamada.')
                else:
                    expressao(g, op[1], variaveis, windows)
                g.salto(f'funcao_fim_{funcao_atual}')
            elif op[0] == 'encerre':
                expressao(g, op[1], variaveis, windows)
                g.bytes(b'\x48\x85\xC0')
                g.salto('erro_codigo_saida', 'js')
                g.bytes(b'\x48\x3D\xFF\x00\x00\x00')
                g.salto('erro_codigo_saida', 'ja')
                if windows:
                    g.bytes(b'\x48\x89\xC1\x48\x83\xE4\xF0')
                    g.relativo(b'\xFF\x15', 'ExitProcess')
                else:
                    g.bytes(b'\x48\x89\xC7\xB8\x3C\x00\x00\x00\x0F\x05')
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
    if tem_dinamicas:
        listas_dinamicas.liberar_todas(g, variaveis, tipos, windows)
    if tem_recursos:
        for nome, tipo in reversed(tuple(tipos.items())):
            if tipo == 'arquivo':
                arquivos_abertos.emitir_auto_fechar(g, variaveis, nome, windows)

    if windows:
        g.bytes(b'\x31\xC9')
        g.relativo(b'\xFF\x15', 'ExitProcess')
    else:
        g.bytes(b'\xB8\x3C\x00\x00\x00\x31\xFF\x0F\x05')
    # As definições usam quadros locais independentes e instruções CALL/RET
    # genuínas, sem expansão textual das funções (inclusive chamadas aninhadas).
    for nome, funcao in g.funcoes.items():
        funcao_atual = nome
        variaveis = dict(funcao.programa.variaveis)
        tipos = funcao.programa.tipos
        g.campos_atual = funcao.programa.campos_registro
        g.tipos_atual = tipos
        n_slots = _total_slots(funcao.programa)
        variaveis['__rs_uso_pilha'] = n_slots
        g.marcar(f'funcao_{nome}')
        if windows:
            n_frame = (((n_slots+1)*8 + 0x38 + 15)//16)*16+8
            g.bytes(b'\x55\x48\x89\xE5\x53')
        else:
            n_frame = alinhar((n_slots+1)*8, 16)
            g.bytes(b'\x55\x48\x89\xE5')
        # A profundidade é limitada por bytes acumulados de quadros; o
        # controle ocorre ANTES de reservar a pilha da chamada atual.
        g.bytes(b'\x48\x8B\x45\x10')  # mov rax,[rbp+16]
        custo = n_frame + 128  # margem conservadora para CALL, argumentos e temporários
        if custo > 0x7FFFFFFF:
            g.salto('erro_recursao_limite')
        else:
            g.bytes(b'\x48\x05' + struct.pack('<I', custo))
            g.salto('erro_recursao_limite', 'jo')
            if funcao.recursiva:
                g.bytes(b'\x48\x3D' + struct.pack('<I', 1024 * 1024))
                g.salto('erro_recursao_limite', 'ja')
        reservar_pilha(g, n_frame)
        if tem_dinamicas:
            listas_dinamicas.inicializar_inativas(g, variaveis, tipos, windows)
        if tem_recursos:
            for recurso_nome, tipo in tipos.items():
                if tipo == 'arquivo':
                    offset = deslocamento_variavel(variaveis, recurso_nome, windows)
                    g.bytes(b'\x48\xC7\x85' + struct.pack('<i',offset) + b'\xFF\xFF\xFF\xFF')
        g.bytes(b'\x48\x89\x85' + struct.pack('<i', deslocamento_variavel(variaveis, '__rs_uso_pilha', windows)))
        total_palavras = sum(_palavras_tipo(t, g.registros) for _, t in funcao.parametros)
        base_argumentos = 32 if _composto(funcao.retorno, g.registros) else 24
        indice_palavra = 0
        for interno, tipo in funcao.parametros:
            quantidade = _palavras_tipo(tipo, g.registros)
            origem = base_argumentos + 8*(total_palavras - indice_palavra - 1)
            destino = deslocamento_variavel(variaveis, interno, windows)
            numero = g.proxima_condicao
            g.proxima_condicao += 1
            rotulo = f'receber_parametro_{numero}'
            g.bytes(b'\x4C\x8D\x95' + struct.pack('<i', origem))
            g.bytes(b'\x4C\x8D\x9D' + struct.pack('<i', destino))
            g.bytes(b'\xB9' + struct.pack('<I', quantidade))
            g.marcar(rotulo)
            g.bytes(b'\x49\x8B\x02\x49\x89\x03')
            g.bytes(b'\x49\x83\xEA\x08\x49\x83\xEB\x08')
            g.bytes(b'\xFF\xC9')
            g.salto(rotulo, 'jnz')
            indice_palavra += quantidade
        emitir_bloco(funcao.programa.instrucoes)
        g.marcar(f'funcao_fim_{nome}')
        if tem_dinamicas:
            listas_dinamicas.liberar_todas(g, variaveis, tipos, windows,
                                           preservar_retorno=True)
        if tem_recursos and any(t == 'arquivo' for t in tipos.values()):
            retorno_guardado = deslocamento_variavel(variaveis, '__rs_uso_pilha', windows)
            g.bytes(b'\x48\x89\x85' + struct.pack('<i',retorno_guardado))
            for recurso_nome, tipo in reversed(tuple(tipos.items())):
                if tipo == 'arquivo':
                    arquivos_abertos.emitir_auto_fechar(g, variaveis, recurso_nome, windows)
            g.bytes(b'\x48\x8B\x85' + struct.pack('<i',retorno_guardado))
        if windows:
            g.bytes(b'\x48\x8D\x65\xF8\x5B\x5D\xC3')  # restaura RBX e retorna
        else:
            g.bytes(b'\x48\x89\xEC\x5D\xC3')
    funcao_atual = None
    variaveis = programa.variaveis
    g.campos_atual = getattr(programa, 'campos_registro', {})
    tipos = getattr(programa, 'tipos', {})
    g.tipos_atual = tipos
    if tem_dinamicas:
        listas_dinamicas.emitir_rotinas(g, windows)
    if tem_arquivos:
        arquivos.emitir_rotinas(g, windows)
    if tem_recursos:
        arquivos_abertos.emitir_rotinas(g, windows)
    if tem_arquivos_posicionais:
        arquivos_posicionais.emitir_rotinas(g, windows)
    imprime_inteiro(g, windows)
    if tem_leitura:
        emitir_cache_entrada(g, windows, slots)
    if tem_leitura and any(op[0] in ('leia_int', 'leia_indice', 'leia_indice_dinamico') for op in percorrer_instrucoes(programa.instrucoes)):
        ler_inteiro(g, windows)
    if tem_leitura_texto:
        ler_buffer_texto(g, windows)

    primeiro_erro = len(mensagens)
    for indice, msg in [(primeiro_erro, 'Erro: divisão por zero.\n'),
                        (primeiro_erro + 1, 'Erro: divisão inteira fora do limite.\n'),
                        (primeiro_erro + 2, 'Erro: estouro aritmético em inteiro de 64 bits.\n')]:
        rotulo = {primeiro_erro: 'erro_divisao_zero', primeiro_erro + 1: 'erro_estouro',
                  primeiro_erro + 2: 'erro_overflow_aritmetico'}[indice]
        g.marcar(rotulo)
        mensagens[indice] = msg
        if windows:
            # Uma expressao pode ter deixado operandos no stack ao falhar.
            # Antes de chamar WriteFile/ExitProcess restauramos o alinhamento
            # obrigatorio de 16 bytes da ABI Windows x64.
            if tem_listas:
                g.bytes(b'\x48\x83\xE4\xF0')  # and rsp, -16
            escreve_literal(g, indice, msg, True)
            g.bytes(b'\xB9\x01\x00\x00\x00')
            g.relativo(b'\xFF\x15', 'ExitProcess')
        else:
            escreve_literal(g, indice, msg, False, 'erro')
            g.bytes(b'\xB8\x3C\x00\x00\x00\xBF\x01\x00\x00\x00\x0F\x05')
    if getattr(programa, 'funcoes', {}):
        indice = len(mensagens)
        msg = 'Erro: limite seguro de pilha em chamada recursiva.\n'
        mensagens[indice] = msg
        g.marcar('erro_recursao_limite')
        if windows:
            g.bytes(b'\x48\x83\xE4\xF0')
        escreve_literal(g, indice, msg, windows, 'saida' if windows else 'erro')
        if windows:
            g.bytes(b'\xB9\x01\x00\x00\x00')
            g.relativo(b'\xFF\x15', 'ExitProcess')
        else:
            g.bytes(b'\xB8\x3C\x00\x00\x00\xBF\x01\x00\x00\x00\x0F\x05')
    if tem_listas:
        indice = len(mensagens)
        msg = 'Erro: índice fora dos limites da lista.\n'
        mensagens[indice] = msg
        g.marcar('erro_indice_lista')
        if windows and tem_listas:
            g.bytes(b'\x48\x83\xE4\xF0')  # and rsp, -16
        escreve_literal(g, indice, msg, windows, 'saida' if windows else 'erro')
        if windows:
            g.bytes(b'\xB9\x01\x00\x00\x00')
            g.relativo(b'\xFF\x15', 'ExitProcess')
        else:
            g.bytes(b'\xB8\x3C\x00\x00\x00\xBF\x01\x00\x00\x00\x0F\x05')
    if tem_leitura and any(op[0] in ('leia_int', 'leia_indice', 'leia_indice_dinamico') for op in percorrer_instrucoes(programa.instrucoes)):
        for indice, msg, rotulo in [
            (len(mensagens), 'Erro: entrada invalida; digite um numero inteiro.\n', 'erro_entrada_invalida'),
            (len(mensagens)+1, 'Erro: numero fora do limite de 64 bits.\n', 'erro_entrada_limite'),
        ]:
            mensagens[indice] = msg
            g.marcar(rotulo)
            if windows and tem_listas:
                g.bytes(b'\x48\x83\xE4\xF0')  # and rsp, -16
            escreve_literal(g, indice, msg, windows, 'saida' if windows else 'erro')
            if windows:
                g.bytes(b'\xB9\x01\x00\x00\x00')
                g.relativo(b'\xFF\x15', 'ExitProcess')
            else:
                g.bytes(b'\xB8\x3C\x00\x00\x00\xBF\x01\x00\x00\x00\x0F\x05')
    if tem_textos:
        for msg, rotulo in [
            ('Erro: texto excede a capacidade do buffer.\n', 'erro_texto_capacidade'),
            ('Erro: sequencia UTF-8 invalida.\n', 'erro_texto_utf8'),
            ('Erro: falha ao ler texto.\n', 'erro_texto_entrada'),
        ]:
            indice = len(mensagens)
            mensagens[indice] = msg
            g.marcar(rotulo)
            if windows and tem_listas:
                g.bytes(b'\x48\x83\xE4\xF0')  # and rsp, -16
            escreve_literal(g, indice, msg, windows, 'saida' if windows else 'erro')
            if windows:
                g.bytes(b'\xB9\x01\x00\x00\x00')
                g.relativo(b'\xFF\x15', 'ExitProcess')
            else:
                g.bytes(b'\xB8\x3C\x00\x00\x00\xBF\x01\x00\x00\x00\x0F\x05')
    if tem_dinamicas:
        for rotulo, msg in [
            ('erro_lista_liberada', 'Erro: lista dinamica usada depois da liberacao.\n'),
            ('erro_lista_memoria', 'Erro: nao foi possivel reservar ou liberar memoria.\n'),
        ]:
            indice = len(mensagens)
            mensagens[indice] = msg
            g.marcar(rotulo)
            if windows:
                g.bytes(b'\x48\x83\xE4\xF0')
            escreve_literal(g, indice, msg, windows, 'saida' if windows else 'erro')
            if windows:
                g.bytes(b'\xB9\x01\x00\x00\x00')
                g.relativo(b'\xFF\x15', 'ExitProcess')
            else:
                g.bytes(b'\xB8\x3C\x00\x00\x00\xBF\x01\x00\x00\x00\x0F\x05')
    if tem_bytes:
        for nome, mensagem in (
            ('erro_indice_bytes', 'Erro: indice fora dos bytes validos.\n'),
            ('erro_valor_byte', 'Erro: byte deve estar entre 0 e 255.\n'),
            ('erro_bytes_capacidade', 'Erro: capacidade do buffer binario excedida.\n')):
            indice = len(mensagens)
            mensagens[indice] = mensagem
            g.marcar(nome)
            if windows:
                g.bytes(b'\x48\x83\xE4\xF0')
            escreve_literal(g, indice, mensagem, windows, 'saida' if windows else 'erro')
            if windows:
                g.bytes(b'\xB9\x01\x00\x00\x00')
                g.relativo(b'\xFF\x15', 'ExitProcess')
            else:
                g.bytes(b'\xB8\x3C\x00\x00\x00\xBF\x01\x00\x00\x00\x0F\x05')
    if tem_encerre:
        indice = len(mensagens)
        mensagem = 'Erro: codigo de saida deve estar entre 0 e 255.\n'
        mensagens[indice] = mensagem
        g.marcar('erro_codigo_saida')
        if windows:
            g.bytes(b'\x48\x83\xE4\xF0')
        escreve_literal(g, indice, mensagem, windows, 'saida' if windows else 'erro')
        if windows:
            g.bytes(b'\xB9\x01\x00\x00\x00')
            g.relativo(b'\xFF\x15', 'ExitProcess')
        else:
            g.bytes(b'\xB8\x3C\x00\x00\x00\xBF\x01\x00\x00\x00\x0F\x05')
    if tem_recursos:
        indice = len(mensagens)
        mensagem = 'Erro: nao foi possivel fechar automaticamente um arquivo.\n'
        mensagens[indice] = mensagem
        g.marcar('erro_fechamento_implicito')
        if windows:
            g.bytes(b'\x48\x83\xE4\xF0')
        escreve_literal(g, indice, mensagem, windows, 'saida' if windows else 'erro')
        if windows:
            g.bytes(b'\xB9\x01\x00\x00\x00')
            g.relativo(b'\xFF\x15', 'ExitProcess')
        else:
            g.bytes(b'\xB8\x3C\x00\x00\x00\xBF\x01\x00\x00\x00\x0F\x05')
    if tem_arquivos:
        for nome, mensagem in (
                ('erro_arquivo_abrir', 'Erro: nao foi possivel abrir o arquivo.\n'),
                ('erro_arquivo_leitura', 'Erro: falha na leitura do arquivo.\n'),
                ('erro_arquivo_gravacao', 'Erro: falha na gravacao do arquivo.\n'),
                ('erro_arquivo_capacidade', 'Erro: arquivo excede a capacidade do texto.\n'),
                ('erro_arquivo_fechar', 'Erro: nao foi possivel fechar o arquivo.\n')):
            indice = len(mensagens)
            mensagens[indice] = mensagem
            g.marcar(nome)
            if windows:
                g.bytes(b'\x48\x83\xE4\xF0')
            escreve_literal(g, indice, mensagem, windows, 'saida' if windows else 'erro')
            if windows:
                g.bytes(b'\xB9\x01\x00\x00\x00')
                g.relativo(b'\xFF\x15', 'ExitProcess')
            else:
                g.bytes(b'\xB8\x3C\x00\x00\x00\xBF\x01\x00\x00\x00\x0F\x05')
    return g, mensagens
