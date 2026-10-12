"""Metadados reais de desenrolamento de quadros Windows x64.

O emissor descreve RBP, RBX, reservas fixas e sondagem por páginas
com uma rotina folha interna; os bytes do prólogo são verificados
antes da publicação das descrições.
"""
import struct

from compilador.erros import ErroCompilacao



def registrar_quadro_auxiliar(gerador, nome):
    """Registra somente rotina auxiliar com prólogo e retorno reconhecidos.

    Espera:
        push rbp; mov rbp,rsp; sub rsp,imm8|imm32
        ...
        mov rsp,rbp; pop rbp; ret

    Todas as verificações são realizadas nos bytes emitidos. Caso o
    prólogo, o fecho ou o alinhamento mudem, a geração falha de modo
    explícito, sem publicar uma tabela de exceções inconsistente.
    """
    inicio = gerador.rotulos[nome]
    fim = len(gerador.codigo)
    codigo = gerador.codigo
    prefixo = bytes(codigo[inicio:inicio + 7])
    if prefixo == b'\x55\x48\x89\xE5\x48\x83\xEC':
        tamanho_quadro = codigo[inicio + 7]
        tamanho_prologo = 8
    elif prefixo == b'\x55\x48\x89\xE5\x48\x81\xEC':
        tamanho_quadro = struct.unpack_from('<I', codigo, inicio + 7)[0]
        tamanho_prologo = 11
    else:
        raise ErroCompilacao(
            f'Prologo da rotina auxiliar {nome} nao eh representavel.')
    if tamanho_quadro < 16 or tamanho_quadro % 16 != 0:
        raise ErroCompilacao(
            f'Reserva da rotina auxiliar {nome} viola alinhamento Windows.')
    if bytes(codigo[fim - 5:fim]) != b'\x48\x89\xEC\x5D\xC3':
        raise ErroCompilacao(
            f'Epilogo da rotina auxiliar {nome} nao eh representavel.')
    if not inicio + tamanho_prologo < fim:
        raise ErroCompilacao('Rotina auxiliar Windows vazia ou invalida.')
    rotulo_prologo = f'{nome}_fim_prologo_abi'
    rotulo_fim = f'{nome}_fim_abi'
    if rotulo_prologo in gerador.rotulos or rotulo_fim in gerador.rotulos:
        raise ErroCompilacao('Rotina auxiliar Windows registrada duas vezes.')
    gerador.rotulos[rotulo_prologo] = inicio + tamanho_prologo
    gerador.marcar(rotulo_fim)
    gerador.desenrolamentos.append({
        'inicio': nome,
        'fim': rotulo_fim,
        'fim_prologo': rotulo_prologo,
        'quadro': tamanho_quadro,
        'prologo': 'auxiliar_sem_rbx',
    })

def _registrar_codigo(operacao, informacao, deslocamento):
    return bytes((deslocamento, (informacao << 4) | operacao))


def gerar_desenrolamentos(gerador, base_codigo, base_xdados):
    """Cria pares .pdata/.xdata para prólogos fixos e quadros sondados.

    Quadro pequeno: PUSH RBP; MOV RBP,RSP; PUSH RBX; SUB RSP,imm32.
    Quadro grande: PUSH RBP; MOV RBP,RSP; PUSH RBX;
                  MOVABS RAX,tamanho; CALL sondagem; SUB RSP,RAX.

    A sondagem é uma rotina folha que não modifica RSP nem registradores
    não voláteis. O desenrolamento do prólogo descreve a reserva final,
    sem fingir que as páginas já foram reservadas durante a chamada.
    """
    entradas = []
    dados = bytearray()
    for descricao in getattr(gerador, 'desenrolamentos', ()):
        inicio = gerador.rotulos[descricao['inicio']]
        fim = gerador.rotulos[descricao['fim']]
        fim_prologo = gerador.rotulos[descricao['fim_prologo']]
        tamanho_quadro = descricao['quadro']
        if not 0 <= inicio < fim <= len(gerador.codigo):
            raise ErroCompilacao('Intervalo de desenrolamento Windows invalido.')
        comprimento = fim_prologo - inicio
        if not 12 <= comprimento <= 255:
            raise ErroCompilacao('Prologo Windows fora do limite de 255 bytes.')
        if not (tamanho_quadro > 0 and tamanho_quadro % 16 == 8
                and tamanho_quadro <= 0xFFFFFFFF):
            raise ErroCompilacao(
                'Quadro Windows deve manter alinhamento de 16 bytes '
                'e tamanho representavel.')
        if descricao.get('prologo') == 'auxiliar_sem_rbx':
            prefixo = bytes(gerador.codigo[inicio:inicio+7])
            if prefixo == b'\x55\x48\x89\xE5\x48\x83\xEC':
                valido_aux = (comprimento == 8
                              and gerador.codigo[inicio+7] == tamanho_quadro)
            elif prefixo == b'\x55\x48\x89\xE5\x48\x81\xEC':
                valido_aux = (comprimento == 11
                              and struct.unpack_from(
                                  '<I', gerador.codigo, inicio+7)[0]
                              == tamanho_quadro)
            else:
                valido_aux = False
            if not valido_aux or tamanho_quadro % 16:
                raise ErroCompilacao(
                    'Quadro auxiliar Windows diverge do prologo declarado.')
            if gerador.codigo[fim-5:fim] != b'\x48\x89\xEC\x5D\xC3':
                raise ErroCompilacao(
                    'Epilogo auxiliar Windows diverge do contrato.')
            if len(dados) % 4:
                dados += bytes(4 - len(dados) % 4)
            endereco_xdados = base_xdados + len(dados)
            if tamanho_quadro <= 128:
                alocacao = _registrar_codigo(
                    2, tamanho_quadro // 8 - 1, comprimento)
                qtd_aloc = 1
            elif tamanho_quadro <= 0xFFFF * 8:
                alocacao = (_registrar_codigo(1, 0, comprimento)
                            + struct.pack('<H', tamanho_quadro // 8))
                qtd_aloc = 2
            else:
                alocacao = (_registrar_codigo(1, 1, comprimento)
                            + struct.pack('<I', tamanho_quadro))
                qtd_aloc = 3
            # unwind codes in descending instruction end order.
            codigos = (alocacao
                       + _registrar_codigo(3, 0, 4)
                       + _registrar_codigo(0, 5, 1))
            qtd = qtd_aloc + 2
            cabecalho = struct.pack('<BBBB', 1, comprimento, qtd, 5)
            informacao = cabecalho + codigos
            if qtd % 2:
                informacao += b'\0\0'
            dados += informacao
            entradas.append(
                (base_codigo + inicio, base_codigo + fim, endereco_xdados))
            continue

        if gerador.codigo[inicio:inicio+5] != b'\x55\x48\x89\xE5\x53':
            raise ErroCompilacao(
                'Prologo Windows mudou: regenerar regras de desenrolamento.')

        if tamanho_quadro < 4096:
            final = gerador.codigo[fim_prologo-7:fim_prologo]
            valido = (final[:3] == b'\x48\x81\xEC'
                      and struct.unpack_from('<I', final, 3)[0] == tamanho_quadro)
        else:
            trecho = gerador.codigo[fim_prologo-18:fim_prologo]
            valido = (trecho[:2] == b'\x48\xB8'
                      and struct.unpack_from('<Q', trecho, 2)[0] == tamanho_quadro
                      and trecho[10] == 0xE8  # call nativa rs_sondar_pilha
                      and trecho[15:18] == b'\x48\x29\xC4')
            if valido and not getattr(gerador, 'exige_sondagem_pilha', False):
                valido = False
        if not valido:
            raise ErroCompilacao(
                'Reserva ou sondagem nao corresponde ao prologo Windows.')

        if len(dados) % 4:
            dados += bytes(4 - len(dados) % 4)
        endereco_xdados = base_xdados + len(dados)

        if tamanho_quadro <= 0xFFFF * 8:
            # UWOP_ALLOC_LARGE opInfo 0, tamanho em unidades de 8 bytes.
            alocacao = (_registrar_codigo(1, 0, comprimento)
                        + struct.pack('<H', tamanho_quadro // 8))
            quantidade_alocacao = 2
        else:
            # UWOP_ALLOC_LARGE opInfo 1, tamanho exato em 32 bits.
            alocacao = (_registrar_codigo(1, 1, comprimento)
                        + struct.pack('<I', tamanho_quadro))
            quantidade_alocacao = 3

        codigos = (alocacao
                   + _registrar_codigo(0, 3, 5)  # push RBX
                   + _registrar_codigo(3, 0, 4)  # mov RBP,RSP
                   + _registrar_codigo(0, 5, 1))  # push RBP
        quantidade_codigos = quantidade_alocacao + 3
        cabecalho = struct.pack(
            '<BBBB', 1, comprimento, quantidade_codigos, 5,
        )
        informacao = cabecalho + codigos
        # A área de UNWIND_CODE deve ocupar número PAR de slots,
        # incluindo um slot nulo se necessário.
        if quantidade_codigos % 2:
            informacao += b'\0\0'
        dados += informacao
        entradas.append((
            base_codigo + inicio, base_codigo + fim, endereco_xdados,
        ))

    entradas.sort()
    for anterior, atual in zip(entradas, entradas[1:]):
        if anterior[1] > atual[0]:
            raise ErroCompilacao('Intervalos de desenrolamento Windows sobrepostos.')
    tabela = bytearray()
    for entrada in entradas:
        tabela += struct.pack('<III', *entrada)
    return bytes(tabela), bytes(dados)
