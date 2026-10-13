"""Ensaios das APIs nativas de desenrolamento AMD64 sem SDK externo.

Referências primárias:
https://learn.microsoft.com/en-us/cpp/build/exception-handling-x64
https://learn.microsoft.com/en-us/windows/win32/api/winnt/nf-winnt-rtlvirtualunwind
https://learn.microsoft.com/en-us/windows/win32/api/winnt/ns-winnt-context

Os estados artificiais usam uma pilha válida. A interpretação dos bytes
é independente dos UNWIND_CODE que o Windows deve verificar.
"""
import ctypes as ct
import struct

REGISTRADORES = ('Rax', 'Rcx', 'Rdx', 'Rbx', 'Rsp', 'Rbp', 'Rsi', 'Rdi',
                 'R8', 'R9', 'R10', 'R11', 'R12', 'R13', 'R14', 'R15')
NAO_VOLATEIS = ('Rbx', 'Rbp', 'Rsi', 'Rdi', 'R12', 'R13', 'R14', 'R15')
SENTINELAS_VETORIAIS = b''.join(bytes((i * 17 + j) & 255 for j in range(16))
                               for i in range(6, 16))
QUADRO_WRAPPER = 280
SENTINELAS = {nome: 0x1357900000000000 + i * 0x102030405 + 0x5A
              for i, nome in enumerate(NAO_VOLATEIS)}


class Contexto(ct.Structure):
    # Layout de CONTEXT AMD64: campos vetoriais preservados como bytes.
    _fields_ = [(f'P{i}Home', ct.c_uint64) for i in range(1, 7)] + [
        ('ContextFlags', ct.c_uint32), ('MxCsr', ct.c_uint32),
    ] + [(nome, ct.c_uint16) for nome in
         ('SegCs', 'SegDs', 'SegEs', 'SegFs', 'SegGs', 'SegSs')] + [
        ('EFlags', ct.c_uint32),
    ] + [(nome, ct.c_uint64) for nome in
         ('Dr0', 'Dr1', 'Dr2', 'Dr3', 'Dr6', 'Dr7')] + [
        (nome, ct.c_uint64) for nome in REGISTRADORES
    ] + [('Rip', ct.c_uint64), ('FltSave', ct.c_ubyte * 512),
         ('VectorRegister', ct.c_ubyte * (26 * 16)),
         ('VectorControl', ct.c_uint64), ('DebugControl', ct.c_uint64),
         ('LastBranchToRip', ct.c_uint64), ('LastBranchFromRip', ct.c_uint64),
         ('LastExceptionToRip', ct.c_uint64),
         ('LastExceptionFromRip', ct.c_uint64)]


class FuncaoNativa(ct.Structure):
    _fields_ = [('BeginAddress', ct.c_uint32), ('EndAddress', ct.c_uint32),
               ('UnwindData', ct.c_uint32)]


class Windows:
    def __init__(self):
        assert ct.sizeof(Contexto) == 1232
        assert Contexto.Rsp.offset == 152 and Contexto.Rip.offset == 248
        self.nucleo = ct.WinDLL('kernel32', use_last_error=True)
        self.nt = ct.WinDLL('ntdll', use_last_error=True)
        self.nucleo.VirtualAlloc.argtypes = [ct.c_void_p, ct.c_size_t,
                                            ct.c_uint32, ct.c_uint32]
        self.nucleo.VirtualAlloc.restype = ct.c_void_p
        self.nucleo.VirtualFree.argtypes = [ct.c_void_p, ct.c_size_t, ct.c_uint32]
        self.nucleo.VirtualFree.restype = ct.c_int
        self.nucleo.VirtualProtect.argtypes = [ct.c_void_p, ct.c_size_t,
                                              ct.c_uint32,
                                              ct.POINTER(ct.c_uint32)]
        self.nucleo.VirtualProtect.restype = ct.c_int
        self.nucleo.GetCurrentProcess.restype = ct.c_void_p
        self.nucleo.FlushInstructionCache.argtypes = [ct.c_void_p, ct.c_void_p, ct.c_size_t]
        self.nucleo.FlushInstructionCache.restype = ct.c_int
        self.nt.RtlAddFunctionTable.argtypes = [ct.POINTER(FuncaoNativa),
                                               ct.c_uint32, ct.c_uint64]
        self.nt.RtlAddFunctionTable.restype = ct.c_ubyte
        self.nt.RtlDeleteFunctionTable.argtypes = [ct.POINTER(FuncaoNativa)]
        self.nt.RtlDeleteFunctionTable.restype = ct.c_ubyte
        self.nt.RtlLookupFunctionEntry.argtypes = [
            ct.c_uint64, ct.POINTER(ct.c_uint64), ct.c_void_p]
        self.nt.RtlLookupFunctionEntry.restype = ct.POINTER(FuncaoNativa)
        self.nt.RtlVirtualUnwind.argtypes = [
            ct.c_uint32, ct.c_uint64, ct.c_uint64, ct.POINTER(FuncaoNativa),
            ct.POINTER(Contexto), ct.POINTER(ct.c_void_p),
            ct.POINTER(ct.c_uint64), ct.c_void_p]
        self.nt.RtlVirtualUnwind.restype = ct.c_void_p

    def alocar(self, tamanho):
        endereco = self.nucleo.VirtualAlloc(None, tamanho, 0x3000, 4)
        if not endereco:
            raise ct.WinError(ct.get_last_error())
        return endereco

    def executar(self, endereco, tamanho):
        anterior = ct.c_uint32()
        if not self.nucleo.VirtualProtect(endereco, tamanho, 0x20,
                                          ct.byref(anterior)):
            raise ct.WinError(ct.get_last_error())
        if not self.nucleo.FlushInstructionCache(self.nucleo.GetCurrentProcess(),
                                                  endereco, tamanho):
            raise ct.WinError(ct.get_last_error())

    def desenrolar(self, contexto):
        base = ct.c_uint64()
        entrada = self.nt.RtlLookupFunctionEntry(contexto.Rip, ct.byref(base), None)
        if not entrada:
            raise AssertionError(f'Sem entrada nativa para {contexto.Rip:#x}.')
        copia = copiar_contexto(contexto)
        dados = ct.c_void_p()
        quadro = ct.c_uint64()
        self.nt.RtlVirtualUnwind(0, base.value, copia.Rip, entrada,
                                ct.byref(copia), ct.byref(dados),
                                ct.byref(quadro), None)
        return copia, quadro.value, entrada.contents


class ImagemRegistrada:
    """Código emitido e suas duas seções de exceção na mesma base virtual."""
    def __init__(self, windows, codigo, tabela, dados, base_codigo=0x1000,
                 base_dados=0x10000):
        self.windows = windows
        self.base_codigo = base_codigo
        self.base_dados = base_dados
        self.tamanho = (max(base_codigo + len(codigo),
                           base_dados + len(dados)) + 0xFFF) & ~0xFFF
        self.base = windows.alocar(self.tamanho)
        ct.memmove(self.base + base_codigo, bytes(codigo), len(codigo))
        ct.memmove(self.base + base_dados, bytes(dados), len(dados))
        self.entradas = (FuncaoNativa * (len(tabela) // 12)).from_buffer_copy(tabela)
        if not windows.nt.RtlAddFunctionTable(self.entradas, len(self.entradas),
                                              self.base):
            self.fechar()
            raise AssertionError('RtlAddFunctionTable recusou .pdata emitida.')
        self.registrada = True

    def fechar(self):
        if getattr(self, 'registrada', False):
            if not self.windows.nt.RtlDeleteFunctionTable(self.entradas):
                raise AssertionError('RtlDeleteFunctionTable falhou.')
            self.registrada = False
        if self.base:
            if not self.windows.nucleo.VirtualFree(self.base, 0, 0x8000):
                raise ct.WinError(ct.get_last_error())
            self.base = 0

    def __enter__(self):
        return self

    def __exit__(self, *erro):
        self.fechar()


class Pilha:
    def __init__(self, tamanho=0x200000):
        self.buffer = ct.create_string_buffer(tamanho + 32)
        self.inicio = (ct.addressof(self.buffer) + 15) & ~15
        self.entrada = self.inicio + tamanho - 0x108
        self.retorno = 0x123456789ABC
        self.escrever(self.entrada, self.retorno)

    def escrever(self, endereco, valor):
        ct.c_uint64.from_address(endereco).value = valor

    def ler(self, endereco):
        return ct.c_uint64.from_address(endereco).value

    def contexto(self, pc):
        c = Contexto()
        c.ContextFlags = 0x10000B
        c.Rsp = self.entrada
        c.Rip = pc
        for nome, valor in SENTINELAS.items():
            setattr(c, nome, valor)
        c.FltSave[256:416] = SENTINELAS_VETORIAIS
        return c


def copiar_contexto(contexto):
    return Contexto.from_buffer_copy(contexto)


def instrucao_de_pilha(codigo, posicao, contexto, pilha):
    """Executa o subconjunto real dos prólogos/epílogos, sem UNWIND_INFO.

    CALL da sondagem é tratado como retorno da rotina folha, cujo RSP e
    não voláteis são inalterados. A execução real é exercitada à parte.
    """
    b = codigo[posicao:posicao + 16]
    prefixo, ext = (1, 8) if b[0] == 0x41 else (0, 0)
    op = b[prefixo]
    if 0x50 <= op <= 0x57:
        registro = REGISTRADORES[op - 0x50 + ext]
        contexto.Rsp -= 8
        pilha.escrever(contexto.Rsp, getattr(contexto, registro))
        return prefixo + 1
    if 0x58 <= op <= 0x5F:
        registro = REGISTRADORES[op - 0x58 + ext]
        setattr(contexto, registro, pilha.ler(contexto.Rsp))
        contexto.Rsp += 8
        return prefixo + 1
    if b[:3] == b'\x48\x89\xe5':
        contexto.Rbp = contexto.Rsp
        return 3
    if b[:3] in (b'\x48\x89\xec', b'\x48\x8d\x65'):
        contexto.Rsp = contexto.Rbp
        if b[:3] == b'\x48\x8d\x65':
            contexto.Rsp += struct.unpack_from('<b', b, 3)[0]
            return 4
        return 3
    if b[:3] in (b'\x48\x83\xec', b'\x48\x83\xc4'):
        valor = struct.unpack_from('<b', b, 3)[0]
        contexto.Rsp += -valor if b[2] == 0xEC else valor
        return 4
    if b[:3] in (b'\x48\x81\xec', b'\x48\x81\xc4'):
        valor = struct.unpack_from('<i', b, 3)[0]
        contexto.Rsp += -valor if b[2] == 0xEC else valor
        return 7
    if b[:2] == b'\x48\xb8':
        contexto.Rax = struct.unpack_from('<Q', b, 2)[0]
        return 10
    if b[:3] == b'\x48\x29\xc4':
        contexto.Rsp -= contexto.Rax
        return 3
    if b[:3] == b'\x48\x8b\x45':
        contexto.Rax = pilha.ler(contexto.Rbp + struct.unpack_from('<b', b, 3)[0])
        return 4
    if b[:2] in (b'\x48\x05', b'\x48\x3d'):
        if b[1] == 5:
            contexto.Rax = (contexto.Rax + struct.unpack_from('<I', b, 2)[0]) & ((1 << 64) - 1)
        return 6
    if b[:1] == b'\x0f' and 0x80 <= b[1] <= 0x8f:
        return 6
    if b[0] == 0xE8:
        return 5
    if b[0] == 0xC3:
        contexto.Rip = pilha.ler(contexto.Rsp)
        contexto.Rsp += 8
        return 1
    raise AssertionError(f'Instrução de pilha desconhecida em {posicao}: {b.hex()}.')


def estados_prologo(codigo, inicio, fim_prologo, imagem, pilha):
    contexto = pilha.contexto(imagem.base + imagem.base_codigo + inicio)
    posicao = inicio
    yield posicao, copiar_contexto(contexto)
    while posicao < fim_prologo:
        posicao += instrucao_de_pilha(codigo, posicao, contexto, pilha)
        contexto.Rip = imagem.base + imagem.base_codigo + posicao
        yield posicao, copiar_contexto(contexto)
    assert posicao == fim_prologo


def verificar_retorno(contexto, pilha):
    esperado = {'Rip': pilha.retorno, 'Rsp': pilha.entrada + 8, **SENTINELAS}
    erros = {nome: (getattr(contexto, nome), valor)
             for nome, valor in esperado.items()
             if getattr(contexto, nome) != valor}
    if erros:
        raise AssertionError('Contexto do chamador divergente: ' + repr(erros))
    assert bytes(contexto.FltSave)[256:416] == SENTINELAS_VETORIAIS, 'XMM6–XMM15 mudaram.'

def encontrar_epilogo(codigo, inicio, fim):
    # Um epílogo canônico só admite restauração de RSP, POPs e RET.
    # Retornos intermediários também são verificados quando encontrados.
    candidatos = []
    for pos in range(inicio, fim):
        b = codigo[pos:pos + 4]
        if b[:3] in (b'\x48\x8d\x65', b'\x48\x83\xc4', b'\x48\x81\xc4'):
            candidatos.append(pos)
    if not candidatos:
        candidatos = [fim - 1]
        pos = fim - 2
        while pos >= inicio:
            if 0x58 <= codigo[pos] <= 0x5F:
                pos -= 1
                if pos >= inicio and codigo[pos] == 0x41:
                    pos -= 1
            else:
                break
        candidatos = [pos + 1]
    validos = []
    for candidato in candidatos:
        pos = candidato
        while pos < fim:
            b = codigo[pos:pos + 7]
            if b[:3] in (b'\x48\x8d\x65', b'\x48\x83\xc4'):
                pos += 4
            elif b[:3] == b'\x48\x81\xc4':
                pos += 7
            elif b[0] == 0x41 and len(b) >= 2 and 0x58 <= b[1] <= 0x5F:
                pos += 2
            elif 0x58 <= b[0] <= 0x5F:
                pos += 1
            elif b[0] == 0xC3:
                validos.append((candidato, pos + 1))
                break
            else:
                break
    if not validos:
        raise AssertionError('Nenhum epílogo canônico encontrado.')
    return validos


def ensaiar_estados(windows, gerador, tabela, dados):
    total = 0
    nomes = []
    classes = set()
    with ImagemRegistrada(windows, gerador.codigo, tabela, dados) as imagem:
        for descricao in gerador.desenrolamentos:
            nome = descricao['inicio']
            nomes.append(nome)
            inicio = gerador.rotulos[nome]
            fim = gerador.rotulos[descricao['fim']]
            prologo = gerador.rotulos[descricao['fim_prologo']]
            pilha = Pilha()
            salvos = set()
            for pos, contexto in estados_prologo(gerador.codigo, inicio,
                                                 prologo, imagem, pilha):
                recuperado, _, entrada = windows.desenrolar(contexto)
                verificar_retorno(recuperado, pilha)
                assert entrada.BeginAddress == 0x1000 + inicio
                assert entrada.EndAddress == 0x1000 + fim
                total += 1
                if pos < prologo:
                    b = gerador.codigo[pos:pos + 2]
                    prefixo, ext = (1, 8) if b[0] == 0x41 else (0, 0)
                    if 0x50 <= b[prefixo] <= 0x57:
                        salvos.add(REGISTRADORES[b[prefixo] - 0x50 + ext])
            # Um PC de corpo, depois de todas as operações do prólogo.
            corpo = copiar_contexto(contexto)
            corpo.Rip += tamanho_primeira_instrucao(gerador.codigo, prologo)
            # Preservamos o frame pointer vivo; os demais salvos podem
            # estar alterados no corpo e precisam retornar das suas pilhas.
            for registro in salvos - {'Rbp'}:
                setattr(corpo, registro, 0xBAD0000000000000 + REGISTRADORES.index(registro))
            recuperado, _, _ = windows.desenrolar(corpo)
            verificar_retorno(recuperado, pilha)
            total += 1
            if 'Rbp' in salvos:
                for temporarios in (8, 64):
                    variavel = copiar_contexto(corpo)
                    variavel.Rsp -= temporarios  # PUSH de expressão ou shadow de chamada
                    recuperado, _, _ = windows.desenrolar(variavel)
                    verificar_retorno(recuperado, pilha)
                    total += 1
            # A entrada principal encerra o processo e não tem RET.
            if nome != 'rs_inicio_principal':
                for epi, final in encontrar_epilogo(gerador.codigo, prologo, fim):
                    atual = copiar_contexto(contexto)
                    pos = epi
                    while pos < final:
                        atual.Rip = imagem.base + 0x1000 + pos
                        recuperado, _, _ = windows.desenrolar(atual)
                        verificar_retorno(recuperado, pilha)
                        total += 1
                        pos += instrucao_de_pilha(gerador.codigo, pos, atual, pilha)
                    verificar_retorno(atual, pilha)
            # Registra as classes efetivamente publicadas pelo compilador.
            info = bytes(ct.string_at(imagem.base + entrada.UnwindData, 4))
            slots = bytes(ct.string_at(imagem.base + entrada.UnwindData + 4,
                                       info[2] * 2))
            i = 0
            while i < info[2]:
                op, extra = slots[2 * i + 1] & 15, slots[2 * i + 1] >> 4
                if op in (1, 2):
                    classes.add((op, extra if op == 1 else 0))
                i += 2 + extra if op == 1 else 1
    return {'estados': total, 'nomes': nomes, 'alocacoes': sorted(classes)}

def tamanho_primeira_instrucao(codigo, pos):
    """Comprimento independente da primeira instrução no corpo emitido."""
    original = pos
    rex = 0
    if 0x40 <= codigo[pos] <= 0x4F:
        rex = codigo[pos]
        pos += 1
    op = codigo[pos]
    pos += 1
    if 0xB8 <= op <= 0xBF:
        return pos - original + (8 if rex & 8 else 4)
    if op in (0x89, 0x8B, 0x8D, 0x31, 0x85, 0x83, 0x81, 0xC7):
        modrm = codigo[pos]
        pos += 1
        modo, rm = modrm >> 6, modrm & 7
        if modo != 3 and rm == 4:
            sib = codigo[pos]
            pos += 1
            if modo == 0 and sib & 7 == 5:
                pos += 4
        if modo == 0 and rm == 5:
            pos += 4
        elif modo == 1:
            pos += 1
        elif modo == 2:
            pos += 4
        if op == 0x83:
            pos += 1
        elif op in (0x81, 0xC7):
            pos += 4
        return pos - original
    raise AssertionError(f'Primeira instrução desconhecida: {codigo[original:original+12].hex()}.')


def secao_pe(imagem, rva, tamanho):
    pe, = struct.unpack_from('<I', imagem, 0x3C)
    quantidade, = struct.unpack_from('<H', imagem, pe + 6)
    opt, = struct.unpack_from('<H', imagem, pe + 20)
    for i in range(quantidade):
        _, virtual, base, bruto, offset = struct.unpack_from(
            '<8sIIII', imagem, pe + 24 + opt + 40 * i)
        if base <= rva and rva + tamanho <= base + virtual:
            return imagem[offset + rva - base:offset + rva - base + tamanho]
    raise AssertionError(f'RVA fora das seções: {rva:#x}.')


def gerar_imagem(fonte):
    from backend.x86_64 import montar_codigo
    from backend.windows_pe import montar_pe
    from compilador.parser import analisar_programa
    gerador, mensagens = montar_codigo(analisar_programa(fonte), True)
    pe = montar_pe(gerador, mensagens)
    pos, = struct.unpack_from('<I', pe, 0x3C)
    tabela_rva, tabela_tam = struct.unpack_from('<II', pe, pos + 24 + 112 + 8 * 3)
    tabela = secao_pe(pe, tabela_rva, tabela_tam)
    # Rebaseia só os RVAs .xdata para a área fixa do ensaio artificial.
    # Os UNWIND_INFO são copiados sem reinterpretar ou reconstruir códigos.
    entradas = list(struct.iter_unpack('<III', tabela))
    primeira_info = min(item[2] for item in entradas)
    quantidade, = struct.unpack_from('<H', pe, pos + 6)
    opt, = struct.unpack_from('<H', pe, pos + 20)
    dados = None
    for i in range(quantidade):
        nome, tamanho, rva = struct.unpack_from('<8sII', pe, pos + 24 + opt + i * 40)
        if nome.rstrip(b'\0') == b'.xdata':
            assert rva == primeira_info
            dados = secao_pe(pe, rva, tamanho)
    assert dados is not None
    tabela_ensaio = b''.join(struct.pack('<III', ini, fim, 0x10000 + info - primeira_info)
                            for ini, fim, info in entradas)
    return gerador, pe, tabela_ensaio, dados


class PeCarregado:
    """Mapeia o PE emitido e resolve a IAT para ensaios em processo isolado."""
    def __init__(self, windows, pe, pontos=()):
        self.windows = windows
        self.base = 0
        self.registrada = False
        pos, = struct.unpack_from('<I', pe, 0x3C)
        opt = pos + 24
        self.tamanho, cabecalho = struct.unpack_from('<II', pe, opt + 56)
        preferida, = struct.unpack_from('<Q', pe, opt + 24)
        self.base = windows.alocar(self.tamanho)
        ct.memmove(self.base, pe[:cabecalho], cabecalho)
        quantidade, = struct.unpack_from('<H', pe, pos + 6)
        tam_opt, = struct.unpack_from('<H', pe, pos + 20)
        self.secoes = []
        for i in range(quantidade):
            nome, tamanho, rva, bruto, off = struct.unpack_from(
                '<8sIIII', pe, opt + tam_opt + i * 40)
            if bruto:
                ct.memmove(self.base + rva, pe[off:off + bruto], bruto)
            self.secoes.append((nome.rstrip(b'\0'), rva, tamanho))
        nucleo = windows.nucleo
        nucleo.GetModuleHandleA.argtypes = [ct.c_char_p]
        nucleo.GetModuleHandleA.restype = ct.c_void_p
        self.importacoes = {}
        nucleo.GetProcAddress.argtypes = [ct.c_void_p, ct.c_char_p]
        nucleo.GetProcAddress.restype = ct.c_void_p
        imports, _ = struct.unpack_from('<II', pe, opt + 112 + 8)
        descritor = self.base + imports
        while imports:
            original, _, _, dll, iat = struct.unpack('<IIIII', ct.string_at(descritor, 20))
            if not dll:
                break
            biblioteca = nucleo.GetModuleHandleA(ct.string_at(self.base + dll))
            assert biblioteca, 'DLL do sistema não carregada.'
            indice = 0
            while True:
                nome_rva = ct.c_uint64.from_address(self.base + original + indice * 8).value
                if not nome_rva:
                    break
                nome = ct.string_at(self.base + nome_rva + 2)
                endereco = nucleo.GetProcAddress(biblioteca, nome)
                assert endereco, f'Importação não resolvida: {nome!r}.'
                celula = self.base + iat + indice * 8
                self.importacoes[nome.decode('ascii')] = celula
                ct.c_uint64.from_address(celula).value = endereco
                indice += 1
            descritor += 20
        reloc, tam_reloc = struct.unpack_from('<II', pe, opt + 112 + 8 * 5)
        cursor = reloc
        while cursor < reloc + tam_reloc:
            pagina, tamanho = struct.unpack('<II', ct.string_at(self.base + cursor, 8))
            assert tamanho >= 8
            for item, in struct.iter_unpack('<H', ct.string_at(self.base + cursor + 8, tamanho - 8)):
                if item >> 12 == 10:
                    palavra = ct.c_uint64.from_address(self.base + pagina + (item & 0xFFF))
                    palavra.value += self.base - preferida
                else:
                    assert item >> 12 == 0
            cursor += tamanho
        for ponto in pontos:
            ct.c_ubyte.from_address(self.base + 0x1000 + ponto).value = 0xCC
        tabela, tamanho = struct.unpack_from('<II', pe, opt + 112 + 8 * 3)
        self.entradas = ct.cast(self.base + tabela, ct.POINTER(FuncaoNativa))
        if not windows.nt.RtlAddFunctionTable(self.entradas, tamanho // 12, self.base):
            self.fechar()
            raise AssertionError('Registro nativo do PE recusado.')
        self.registrada = True
        for nome, rva, tamanho in self.secoes:
            if nome == b'.text':
                windows.executar(self.base + rva, tamanho)

    fechar = ImagemRegistrada.fechar
    __enter__ = ImagemRegistrada.__enter__
    __exit__ = ImagemRegistrada.__exit__


def _mov_imediato(registro, valor):
    numero = REGISTRADORES.index(registro)
    return bytes((0x49 if numero >= 8 else 0x48, 0xB8 + numero % 8)) + struct.pack('<Q', valor)


def _vetor_pilha(indice, deslocamento, carregar):
    rex = b'\x44' if indice >= 8 else b''
    return (b'\xf3' + rex + b'\x0f' + bytes((0x6F if carregar else 0x7F,
            0x84 | ((indice % 8) << 3), 0x24)) + struct.pack('<i', deslocamento))


def _vetor_memoria(indice, base, deslocamento, carregar):
    rex = (4 if indice >= 8 else 0) | (1 if base >= 8 else 0)
    return (b'\xf3' + (bytes((0x40 | rex,)) if rex else b'') + b'\x0f'
            + bytes((0x6F if carregar else 0x7F,
                     0x80 | ((indice % 8) << 3) | (base % 8)))
            + struct.pack('<i', deslocamento))


def wrapper_chamada(windows, alvo, entradas=None, argumento=7, envenenar=False):
    """Wrapper com metadados próprios, oito GPR e dez XMM sentinelas.

    Originais do chamador ctypes são salvos e restaurados. Os SAVE_XMM128
    descrevem as instruções efetivamente executadas no prólogo do wrapper.
    """
    entradas = entradas or {}
    codigo = bytearray()
    operacoes = []
    for nome in NAO_VOLATEIS:
        numero = REGISTRADORES.index(nome)
        codigo += (b'\x41' if numero >= 8 else b'') + bytes((0x50 + numero % 8,))
        operacoes.append((len(codigo), bytes((len(codigo), numero << 4))))
    codigo += b'\x48\x81\xec' + struct.pack('<I', QUADRO_WRAPPER)
    operacoes.append((len(codigo), bytes((len(codigo), 1))
                      + struct.pack('<H', QUADRO_WRAPPER // 8)))
    for i in range(6, 16):
        deslocamento = 112 + 16 * (i - 6)
        codigo += _vetor_pilha(i, deslocamento, False)
        operacoes.append((len(codigo), bytes((len(codigo), (i << 4) | 8))
                          + struct.pack('<H', deslocamento // 16)))
    comprimento = len(codigo)
    codigo += b'\x48\x89\x4c\x24\x50'  # resultado RCX guardado no quadro
    codigo += b'\x48\xc7\x04\x24\0\0\0\0'  # orçamento RS
    codigo += b'\x48\xc7\x44\x24\x08' + struct.pack('<i', argumento)
    vetores = ct.create_string_buffer(SENTINELAS_VETORIAIS)
    codigo += _mov_imediato('Rax', ct.addressof(vetores))
    for i in range(6, 16):
        codigo += _vetor_memoria(i, 0, 16 * (i - 6), True)
    for nome, valor in SENTINELAS.items():
        codigo += _mov_imediato(nome, entradas.get(nome, valor))
    for nome, valor in entradas.items():
        if nome not in SENTINELAS:
            codigo += _mov_imediato(nome, valor)
    codigo += b'\x4c\x8b\x5c\x24\x50'  # R11 = resultado
    codigo += b'\x49\x89\x63\x50'  # RSP anterior
    if envenenar:
        # Contamina a pilha que será usada pelo próximo quadro. O
        # compilador precisa zerar todos os 64 bits de lpOverlapped.
        codigo += _mov_imediato('R10', 0x2222222200000000)
        for deslocamento in range(-2048, 0, 8):
            codigo += b'\x4c\x89\x94\x24' + struct.pack('<i', deslocamento)
    codigo += _mov_imediato('R10', alvo) + b'\x41\xff\xd2'
    retorno = len(codigo)
    codigo += b'\x4c\x8b\x5c\x24\x50'
    for i, nome in enumerate(NAO_VOLATEIS):
        numero = REGISTRADORES.index(nome)
        rex = 0x49 | (4 if numero >= 8 else 0)
        codigo += bytes((rex, 0x89, 0x43 | ((numero % 8) << 3), i * 8))
    codigo += b'\x49\x89\x43\x40\x49\x89\x63\x48'  # RAX / RSP posterior
    for i in range(6, 16):
        codigo += _vetor_memoria(i, 11, 88 + 16 * (i - 6), False)
    for i in range(6, 16):
        codigo += _vetor_pilha(i, 112 + 16 * (i - 6), True)
    codigo += b'\x48\x81\xc4' + struct.pack('<I', QUADRO_WRAPPER)
    for nome in reversed(NAO_VOLATEIS):
        numero = REGISTRADORES.index(nome)
        codigo += (b'\x41' if numero >= 8 else b'') + bytes((0x58 + numero % 8,))
    codigo += b'\xc3'
    codigos = b''.join(item[1] for item in sorted(operacoes, reverse=True))
    quantidade = len(codigos) // 2
    dados = bytes((1, comprimento, quantidade, 0)) + codigos
    if quantidade % 2:
        dados += b'\0\0'
    tabela = struct.pack('<III', 0x1000, 0x1000 + len(codigo), 0x10000)
    imagem = ImagemRegistrada(windows, codigo, tabela, dados)
    imagem.vetores = vetores  # memória referenciada pelos MOVDQU
    windows.executar(imagem.base + 0x1000, len(codigo))
    return imagem, retorno


def verificar_sentinelas(resultado, entradas=None):
    valores = dict(zip(NAO_VOLATEIS, resultado))
    esperado = {**SENTINELAS, **(entradas or {})}
    for nome in NAO_VOLATEIS:
        assert valores[nome] == esperado[nome], (nome, valores[nome], esperado[nome])
    assert resultado[9] == resultado[10], 'RSP mudou no retorno normal.'
    assert ct.string_at(ct.addressof(resultado) + 88, 160) == SENTINELAS_VETORIAIS


def chamar_com_sentinelas(windows, alvo, entradas=None, argumento=7, envenenar=False):
    resultado = (ct.c_uint64 * 31)()
    imagem, _ = wrapper_chamada(windows, alvo, entradas, argumento, envenenar)
    with imagem:
        ct.WINFUNCTYPE(ct.c_uint64, ct.c_void_p)(imagem.base + 0x1000)(resultado)
    verificar_sentinelas(resultado, entradas)
    return resultado[8]


class RegistroExcecao(ct.Structure):
    _fields_ = [('ExceptionCode', ct.c_uint32), ('ExceptionFlags', ct.c_uint32),
               ('ExceptionRecord', ct.c_void_p), ('ExceptionAddress', ct.c_void_p),
               ('NumberParameters', ct.c_uint32), ('Alinhamento', ct.c_uint32),
               ('ExceptionInformation', ct.c_uint64 * 15)]


class PonteirosExcecao(ct.Structure):
    _fields_ = [('ExceptionRecord', ct.POINTER(RegistroExcecao)),
               ('ContextRecord', ct.POINTER(Contexto))]


def ensaiar_excecoes(windows, gerador, pe):
    """VEH recebe CONTEXT de INT3 real, percorre RS e o wrapper real.

    O VEH retoma o chamador usando o contexto desenrolado; não executa
    manipuladores de linguagem nem anuncia suporte RS a try/catch.
    """
    pontos = {gerador.rotulos[d['fim_prologo']] + tamanho_primeira_instrucao(
                  gerador.codigo, gerador.rotulos[d['fim_prologo']]): d['inicio']
              for d in gerador.desenrolamentos}
    erros = []
    capturados = []
    ativo = {}
    tipo_handler = ct.WINFUNCTYPE(ct.c_long, ct.POINTER(PonteirosExcecao))

    @tipo_handler
    def receber(ponteiros):
        try:
            registro = ponteiros.contents.ExceptionRecord.contents
            contexto = ponteiros.contents.ContextRecord.contents
            pc = registro.ExceptionAddress
            if registro.ExceptionCode != 0x80000003 or pc != ativo.get('pc'):
                return 0
            observado = copiar_contexto(contexto)
            observado.Rip = pc
            chamador, _, _ = windows.desenrolar(observado)
            for nome, valor in ativo['esperado'].items():
                assert getattr(chamador, nome) == valor, f'Exceção perdeu {nome}.'
            assert chamador.Rip == ativo['retorno'], 'RET de exceção divergente.'
            # O segundo quadro também está na pilha real do thread.
            externo, _, _ = windows.desenrolar(chamador)
            assert bytes(chamador.FltSave)[256:416] == SENTINELAS_VETORIAIS
            topo = chamador.Rsp + QUADRO_WRAPPER + 8 * len(NAO_VOLATEIS)
            assert externo.Rip == ct.c_uint64.from_address(topo).value
            assert externo.Rsp == topo + 8
            for i, nome in enumerate(NAO_VOLATEIS):
                salvo = chamador.Rsp + QUADRO_WRAPPER + (len(NAO_VOLATEIS) - i - 1) * 8
                assert getattr(externo, nome) == ct.c_uint64.from_address(salvo).value
            assert bytes(externo.FltSave)[256:416] == ct.string_at(chamador.Rsp + 112, 160)
            capturados.append(ativo['nome'])
            # Apenas CONTEXT de controle/integer é substituído. A área
            # SIMD permanece exatamente como Windows entregou ao VEH.
            for nome in REGISTRADORES + ('Rip',):
                setattr(contexto, nome, getattr(chamador, nome))
            contexto.Rax = 42
            return -1
        except BaseException as erro:
            erros.append(repr(erro))
            return 0

    nucleo = windows.nucleo
    nucleo.AddVectoredExceptionHandler.argtypes = [ct.c_uint32, tipo_handler]
    nucleo.AddVectoredExceptionHandler.restype = ct.c_void_p
    nucleo.RemoveVectoredExceptionHandler.argtypes = [ct.c_void_p]
    nucleo.RemoveVectoredExceptionHandler.restype = ct.c_uint32
    handler = nucleo.AddVectoredExceptionHandler(1, receber)
    assert handler, 'Não foi possível instalar VEH.'
    try:
        with PeCarregado(windows, pe, pontos) as imagem:
            for ponto, nome in pontos.items():
                alvo = imagem.base + 0x1000 + gerador.rotulos[nome]
                # A rotina de cache compartilha o RBP do quadro chamador.
                apoio = ct.create_string_buffer(4096)
                entradas = {'Rbp': ct.addressof(apoio) + 2048} if nome == 'entrada_proximo_byte' else {}
                esperado = {**SENTINELAS, **entradas}
                wrapper, retorno = wrapper_chamada(windows, alvo, entradas)
                with wrapper:
                    ativo.update(pc=imagem.base + 0x1000 + ponto, nome=nome, esperado=esperado,
                                 retorno=wrapper.base + 0x1000 + retorno)
                    resultado = (ct.c_uint64 * 31)()
                    ct.WINFUNCTYPE(ct.c_uint64, ct.c_void_p)(wrapper.base + 0x1000)(resultado)
                    verificar_sentinelas(resultado, entradas)
                    assert resultado[8] == 42
        assert not erros, erros
        assert capturados == list(pontos.values()), capturados
        return {'excecoes': capturados, 'quadros': 2 * len(capturados)}
    finally:
        assert nucleo.RemoveVectoredExceptionHandler(handler)

def ensaiar_negativo(windows, gerador, tabela, dados):
    """Controle negativo: muda só o destino do PUSH_NONVOL de RBP."""
    primeira = gerador.desenrolamentos[0]
    inicio = gerador.rotulos[primeira['inicio']]
    fim_prologo = gerador.rotulos[primeira['fim_prologo']]
    ini, _, info = next(item for item in struct.iter_unpack('<III', tabela)
                       if item[0] == 0x1000 + inicio)
    offset = info - 0x10000
    corrompidos = bytearray(dados)
    quantidade = corrompidos[offset + 2]
    indice = 0
    encontrou = False
    while indice < quantidade:
        p = offset + 4 + indice * 2 + 1
        op, extra = corrompidos[p] & 15, corrompidos[p] >> 4
        if op == 0 and extra == 5:
            corrompidos[p] = 0x60  # metadado diz RSI; bytes reais empilham RBP
            encontrou = True
            break
        indice += 2 + extra if op == 1 else 1
    assert encontrou, 'Controle negativo não localizou PUSH RBP.'
    pilha = Pilha()
    with ImagemRegistrada(windows, gerador.codigo, tabela, dados) as imagem:
        estados = list(estados_prologo(gerador.codigo, inicio, fim_prologo, imagem, pilha))
        correto, _, _ = windows.desenrolar(estados[-1][1])
        verificar_retorno(correto, pilha)
    with ImagemRegistrada(windows, gerador.codigo, tabela, corrompidos) as imagem:
        estados = list(estados_prologo(gerador.codigo, inicio, fim_prologo, imagem, pilha))
        errado, _, _ = windows.desenrolar(estados[-1][1])
        try:
            verificar_retorno(errado, pilha)
        except AssertionError:
            return {'corrupcao_detectada': True}
    raise AssertionError('Metadado corrompido produziu falsa aprovação.')


def ensaiar_retorno(windows, gerador, pe):
    nomes = []
    with PeCarregado(windows, pe) as imagem:
        def chamar(nome, entradas=None, argumento=11):
            nomes.append(nome)
            return chamar_com_sentinelas(windows, imagem.base + 0x1000 +
                                        gerador.rotulos[nome], entradas, argumento)

        for nome in gerador.rotulos:
            if nome.startswith('funcao_') and not nome.startswith('funcao_fim_'):
                assert chamar(nome) == 42
        if 'rs_lista_alocar' in gerador.rotulos:
            memoria = chamar('rs_lista_alocar', {'Rdi': 64})
            assert memoria and memoria % 0x1000 == 0
            chamar('rs_lista_desalocar', {'Rdi': memoria, 'Rsi': 64})
            origem = (ct.c_uint64 * 3)(0, 0, 0)  # capacidade, tamanho, ponteiro
            destino = (ct.c_uint64 * 3)(0, 0, 0)
            valor = ct.c_uint64(42)
            origem_ptr = ct.addressof(origem) + 16
            destino_ptr = ct.addressof(destino) + 16
            chamar('rs_lista_acrescentar', {'Rdi': origem_ptr,
                   'Rsi': ct.addressof(valor), 'Rdx': 1})
            assert origem[0] >= 1 and origem[1] == 1 and origem[2]
            assert ct.c_uint64.from_address(origem[2]).value == 42
            chamar('rs_lista_mover_descritor', {'Rdi': destino_ptr,
                   'Rsi': origem_ptr, 'Rdx': 1})
            assert destino[1] == 1 and destino[2] and origem[2] == 0
            chamar('rs_lista_liberar_descritor', {'Rdi': destino_ptr, 'Rsi': 1})
            assert destino[2] == 0 and destino[1] == (1 << 64) - 1
        if 'rs_bloquear_recurso' in gerador.rotulos:
            assert chamar('rs_bloquear_recurso') == 0
    return {'retornos': nomes}


def executar_ensaio(acao, fonte):
    gerador, pe, tabela, dados = gerar_imagem(fonte)
    windows = Windows()
    if acao == 'estados':
        return ensaiar_estados(windows, gerador, tabela, dados)
    if acao == 'excecoes':
        return ensaiar_excecoes(windows, gerador, pe)
    if acao == 'negativo':
        return ensaiar_negativo(windows, gerador, tabela, dados)
    if acao == 'retorno':
        return ensaiar_retorno(windows, gerador, pe)
    if acao == 'sondagem':
        return ensaiar_sondagem(windows, gerador, pe, tabela, dados)
    if acao == 'impressao':
        return ensaiar_impressao(windows, gerador, pe)
    raise AssertionError(f'Ensaio desconhecido: {acao}.')

def ensaiar_sondagem(windows, gerador, pe, tabela, dados):
    folha = gerador.rotulos['rs_sondar_pilha']
    quadros = 0
    with ImagemRegistrada(windows, gerador.codigo, tabela, dados) as imagem:
        base = ct.c_uint64()
        assert not windows.nt.RtlLookupFunctionEntry(
            imagem.base + 0x1000 + folha, ct.byref(base), None), 'Tabela falsa para folha.'
        for descricao in gerador.desenrolamentos:
            if descricao['quadro'] < 4096:
                continue
            pilha = Pilha()
            inicio = gerador.rotulos[descricao['inicio']]
            fim_prologo = gerador.rotulos[descricao['fim_prologo']]
            encontrou = False
            for pos, contexto in estados_prologo(gerador.codigo, inicio, fim_prologo,
                                                 imagem, pilha):
                if pos >= fim_prologo or gerador.codigo[pos] != 0xE8:
                    continue
                alvo = pos + 5 + struct.unpack_from('<i', gerador.codigo, pos + 1)[0]
                assert alvo == folha
                dentro = copiar_contexto(contexto)
                dentro.Rsp -= 8
                pilha.escrever(dentro.Rsp, contexto.Rip + 5)
                dentro.Rip = imagem.base + 0x1000 + folha + 5
                assert not windows.nt.RtlLookupFunctionEntry(dentro.Rip, ct.byref(base), None)
                # Folha sem alteração de RSP: o Windows/caminhador usa RET
                # simples, depois consulta o quadro RS ainda no prólogo.
                dentro.Rip = pilha.ler(dentro.Rsp)
                dentro.Rsp += 8
                restaurado, _, _ = windows.desenrolar(dentro)
                verificar_retorno(restaurado, pilha)
                quadros += 1
                encontrou = True
            assert encontrou, 'Quadro sondado sem chamada folha ensaiada.'
    assert quadros
    with PeCarregado(windows, pe) as imagem:
        alvo = imagem.base + 0x1000 + folha
        for tamanho in (4096, 600000):
            retorno = chamar_com_sentinelas(windows, alvo, {'Rax': tamanho})
            assert retorno == tamanho, 'Sondagem alterou RAX.'
    return {'quadros_intermediarios': quadros, 'retornos_folha': 2}


def ensaiar_impressao(windows, gerador, pe):
    """Mock WinAPI observa os cinco argumentos após execução emitida real.

    Os ponteiros overlapped são observados integralmente. Mesmo um valor
    inválido não é repassado ao sistema, deixando a regressão determinista.
    """
    registros = []
    erros = []
    tipo_escrita = ct.WINFUNCTYPE(ct.c_int, ct.c_void_p, ct.c_void_p,
                                 ct.c_uint32, ct.POINTER(ct.c_uint32), ct.c_void_p)

    @tipo_escrita
    def escrita(arquivo, memoria, quantidade, transferidos, sobreposta):
        try:
            registros.append((ct.string_at(memoria, quantidade), sobreposta))
            transferidos.contents.value = quantidade
            return 1
        except BaseException as erro:
            erros.append(repr(erro))
            return 0

    with PeCarregado(windows, pe) as imagem:
        ct.c_uint64.from_address(imagem.importacoes['WriteFile']).value = ct.cast(
            escrita, ct.c_void_p).value
        alvo = imagem.base + 0x1000 + gerador.rotulos['imprimir_inteiro']
        for numero in (0, 42, -123456789):
            chamar_com_sentinelas(windows, alvo, {'Rax': numero & ((1 << 64) - 1)},
                                  envenenar=True)
            assert registros[-1][0] == f'{numero}\n'.encode('ascii')
        anteriores = len(registros)
        retorno = chamar_com_sentinelas(windows, imagem.base + 0x1000 +
                    gerador.rotulos['funcao_processamento'], argumento=11, envenenar=True)
        assert retorno == 42
        conteudo = b''.join(item[0] for item in registros[anteriores:])
        assert conteudo == b'literal\nbuffer\n11\n', conteudo
    assert not erros, erros
    assert len(registros) >= 6
    assert all(sobreposta is None for _, sobreposta in registros), registros
    return {'escritas': len(registros), 'sobreposta_nula': True}
