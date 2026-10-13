"""Descrições verificadas de quadros e epílogos Windows x64.

Cada contrato corresponde aos bytes emitidos. As rotinas internas preservam
os registradores não voláteis que usam; prólogos parciais e epílogos podem ser
percorridos pelo desenrolador do sistema operacional.
"""
import struct

from compilador.erros import ErroCompilacao
from .convencao_funcoes import LIMITE_PILHA_SEGURA, custo_quadro


_REGISTRADORES = {
    'rbx': 3, 'rbp': 5, 'rsi': 6, 'rdi': 7,
    'r12': 12, 'r13': 13, 'r14': 14, 'r15': 15,
}


def _empilhar(registrador, retirar=False):
    numero = _REGISTRADORES[registrador]
    return ((b'\x41' if numero >= 8 else b'')
            + bytes(((0x58 if retirar else 0x50) + numero % 8,)))


def _ajustar_pilha(tamanho, devolver=False):
    if not isinstance(tamanho, int) or not 0 < tamanho <= 0x7FFFFFFF:
        raise ErroCompilacao('Reserva Windows fora do limite representavel.')
    opcode = b'\xC4' if devolver else b'\xEC'
    if tamanho <= 127:
        return b'\x48\x83' + opcode + bytes((tamanho,))
    return b'\x48\x81' + opcode + struct.pack('<I', tamanho)


def emitir_prologo_auxiliar(gerador, windows, quadro):
    """Preserva RSI/RDI no Windows sem deslocar os locais relativos a RBP."""
    if windows:
        gerador.bytes(b'\x57\x56')
    gerador.bytes(b'\x55\x48\x89\xE5' + _ajustar_pilha(quadro))


def emitir_epilogo_auxiliar(gerador, windows):
    if windows:
        # MOV RSP,RBP não pertence aos epílogos reconhecidos pelo Windows.
        gerador.bytes(b'\x48\x8D\x65\x00\x5D\x5E\x5F\xC3')
    else:
        gerador.bytes(b'\x48\x89\xEC\x5D\xC3')


def _registrar(gerador, nome, quadro, prologo, comprimento, **campos):
    inicio = gerador.rotulos[nome]
    rotulo_prologo = f'{nome}_fim_prologo_abi'
    rotulo_fim = f'{nome}_fim_abi'
    if rotulo_prologo in gerador.rotulos or rotulo_fim in gerador.rotulos:
        raise ErroCompilacao('Rotina auxiliar Windows registrada duas vezes.')
    descricao = {
        'inicio': nome, 'fim': rotulo_fim, 'fim_prologo': rotulo_prologo,
        'quadro': quadro, 'prologo': prologo, **campos,
    }
    # A validação antecede a publicação, sem deixar rótulos parciais.
    _validar_auxiliar(gerador.codigo, inicio, len(gerador.codigo),
                      comprimento, descricao)
    gerador.rotulos[rotulo_prologo] = inicio + comprimento
    gerador.marcar(rotulo_fim)
    gerador.desenrolamentos.append(descricao)


def registrar_quadro_auxiliar(gerador, nome):
    """Registra PUSH RDI/RSI/RBP, MOV RBP,RSP e reserva fixa verificada."""
    inicio = gerador.rotulos[nome]
    codigo = gerador.codigo
    prefixo = b'\x57\x56\x55\x48\x89\xE5'
    if bytes(codigo[inicio:inicio + len(prefixo)]) != prefixo:
        raise ErroCompilacao(f'Quadro auxiliar {nome}: prologo nao representavel.')
    pos = inicio + len(prefixo)
    if bytes(codigo[pos:pos + 3]) == b'\x48\x83\xEC' and pos + 4 <= len(codigo):
        quadro, comprimento = codigo[pos + 3], len(prefixo) + 4
        if quadro >= 128:
            raise ErroCompilacao('Quadro auxiliar Windows usa imediato negativo.')
    elif bytes(codigo[pos:pos + 3]) == b'\x48\x81\xEC' and pos + 7 <= len(codigo):
        quadro = struct.unpack_from('<I', codigo, pos + 3)[0]
        comprimento = len(prefixo) + 7
    else:
        raise ErroCompilacao(f'Quadro auxiliar {nome}: reserva nao representavel.')
    _registrar(gerador, nome, quadro, 'auxiliar_preservado', comprimento)


def registrar_quadro_empilhado(gerador, nome, registradores, quadro):
    """Valida PUSHs + SUB fixo e ADD + POPs inversos + RET, sem frame register.

    Recebe somente registradores não voláteis. Os 40 bytes de uma chamada
    direta incluem o espaço de sombra e o alinhamento exigidos pelo Windows.
    """
    registradores = tuple(registradores)
    if len(set(registradores)) != len(registradores) or any(
            r not in _REGISTRADORES for r in registradores):
        raise ErroCompilacao('Registradores do quadro Windows invalidos.')
    prefixo = b''.join(_empilhar(r) for r in registradores)
    if quadro:
        prefixo += _ajustar_pilha(quadro)
    _registrar(gerador, nome, quadro, 'auxiliar_empilhado', len(prefixo),
               registradores=registradores)


def registrar_rotina_folha(gerador, nome):
    """Descreve apenas a folha Windows auditada XOR EAX,EAX; RET."""
    _registrar(gerador, nome, 0, 'auxiliar_folha', 0)


def _validar_auxiliar(codigo, inicio, fim, comprimento, descricao):
    if not 0 <= inicio < fim <= len(codigo):
        raise ErroCompilacao('Intervalo de desenrolamento Windows invalido.')
    quadro = descricao['quadro']
    formato = descricao['prologo']
    if formato == 'auxiliar_folha':
        if quadro or comprimento or bytes(codigo[inicio:fim]) != b'\x31\xC0\xC3':
            raise ErroCompilacao('Rotina folha Windows diverge do contrato.')
        return b'', [], 0
    if formato == 'auxiliar_preservado':
        if quadro < 16 or quadro % 16:
            raise ErroCompilacao('Quadro auxiliar Windows viola alinhamento.')
        prefixo = b'\x57\x56\x55\x48\x89\xE5' + _ajustar_pilha(quadro)
        epilogo = b'\x48\x8D\x65\x00\x5D\x5E\x5F\xC3'
        operacoes = [(6, 3, 0), (3, 0, 5), (2, 0, 6), (1, 0, 7)]
        frame = 5
    elif formato == 'auxiliar_empilhado':
        registradores = tuple(descricao.get('registradores', ()))
        if len(set(registradores)) != len(registradores) or any(
                r not in _REGISTRADORES for r in registradores):
            raise ErroCompilacao('Registradores do quadro Windows invalidos.')
        if (not isinstance(quadro, int) or quadro < 0 or quadro % 8
                or (8 - len(registradores) * 8 - quadro) % 16):
            raise ErroCompilacao('Quadro empilhado Windows viola alinhamento.')
        prefixo = b''
        operacoes = []
        for r in registradores:
            prefixo += _empilhar(r)
            operacoes.append((len(prefixo), 0, _REGISTRADORES[r]))
        if quadro:
            prefixo += _ajustar_pilha(quadro)
        epilogo = ((_ajustar_pilha(quadro, True) if quadro else b'')
                   + b''.join(_empilhar(r, True) for r in reversed(registradores))
                   + b'\xC3')
        operacoes.reverse()
        frame = 0
    else:
        raise ErroCompilacao('Formato de quadro auxiliar Windows desconhecido.')
    if (comprimento != len(prefixo) or comprimento > 255
            or bytes(codigo[inicio:inicio + comprimento]) != prefixo):
        raise ErroCompilacao('Quadro auxiliar Windows diverge do prologo declarado.')
    if (inicio + comprimento > fim - len(epilogo)
            or bytes(codigo[fim - len(epilogo):fim]) != epilogo):
        raise ErroCompilacao('Epilogo auxiliar Windows diverge do contrato.')
    return epilogo, operacoes, frame


def _registrar_codigo(operacao, informacao, deslocamento):
    return bytes((deslocamento, (informacao << 4) | operacao))


def _alocacao(quadro, comprimento, pequeno=True):
    if quadro == 0:
        return b'', 0
    if pequeno and quadro <= 128:
        return _registrar_codigo(2, quadro // 8 - 1, comprimento), 1
    if quadro <= 0xFFFF * 8:
        return (_registrar_codigo(1, 0, comprimento)
                + struct.pack('<H', quadro // 8)), 2
    return (_registrar_codigo(1, 1, comprimento)
            + struct.pack('<I', quadro)), 3


def _validar_usuario(gerador, descricao, inicio, fim, fim_prologo):
    quadro = descricao['quadro']
    if descricao.get('prologo') != 'usuario_preservado':
        raise ErroCompilacao('Formato de quadro de usuario Windows desconhecido.')
    prefixo = (b'\x56\x57\x41\x54\x41\x55\x41\x56\x41\x57'
               b'\x53\x55\x48\x89\xE5')
    comprimento = fim_prologo - inicio
    if bytes(gerador.codigo[inicio:inicio + len(prefixo)]) != prefixo:
        raise ErroCompilacao('Prologo Windows mudou: regenerar regras de desenrolamento.')
    if not len(prefixo) + 7 <= comprimento <= 255:
        raise ErroCompilacao('Prologo Windows fora do limite de 255 bytes.')
    if not (0 < quadro <= 0xFFFFFFFF and quadro % 16 == 8):
        raise ErroCompilacao('Quadro Windows nao respeita o alinhamento deste prologo.')
    tamanho_reserva = 7 if quadro < 4096 else 18
    meio = bytes(gerador.codigo[inicio + len(prefixo):fim_prologo - tamanho_reserva])
    if descricao['inicio'] == 'rs_inicio_principal':
        meio_valido = not meio
    else:
        # O controle de profundidade só pode ler/alterar RAX e comparar.
        # Validar também esse trecho impede um PUSH não descrito no meio.
        custo = custo_quadro(quadro)
        if custo > 0x7FFFFFFF:
            meio_valido = (len(meio) == 9 and meio[:4] == b'\x48\x8B\x45\x48'
                           and meio[4] == 0xE9)
        else:
            meio_valido = (len(meio) == 28
                           and meio[:6] == b'\x48\x8B\x45\x48\x48\x05'
                           and struct.unpack_from('<I', meio, 6)[0] == custo
                           and meio[10:12] == b'\x0F\x80')
            if meio_valido:
                meio_valido = (meio[16:18] == b'\x48\x3D'
                               and struct.unpack_from('<I', meio, 18)[0] == LIMITE_PILHA_SEGURA
                               and meio[22:24] == b'\x0F\x87')
    if not meio_valido:
        raise ErroCompilacao('Controle de profundidade mudou dentro do prologo Windows.')
    if quadro < 4096:
        final = bytes(gerador.codigo[fim_prologo - 7:fim_prologo])
        valido = (final[:3] == b'\x48\x81\xEC'
                  and struct.unpack_from('<I', final, 3)[0] == quadro)
    else:
        trecho = bytes(gerador.codigo[fim_prologo - 18:fim_prologo])
        valido = (trecho[:2] == b'\x48\xB8'
                  and struct.unpack_from('<Q', trecho, 2)[0] == quadro
                  and trecho[10] == 0xE8 and trecho[15:18] == b'\x48\x29\xC4'
                  and getattr(gerador, 'exige_sondagem_pilha', False)
                  and (fim_prologo - 7, 'rs_sondar_pilha')
                  in getattr(gerador, 'pendencias', ()))
    if not valido:
        raise ErroCompilacao('Reserva ou sondagem nao corresponde ao prologo Windows.')
    # Todos os PUSHs precedem SET_FPREG: temporários no corpo não podem
    # deslocar o endereço a partir do qual o Windows recupera registradores.
    operacoes = [(15, 3, 0), (12, 0, 5), (11, 0, 3),
                 (10, 0, 15), (8, 0, 14), (6, 0, 13),
                 (4, 0, 12), (2, 0, 7), (1, 0, 6)]
    epilogo = b'\x48\x8D\x65\x00\x5D\x5B\x41\x5F\x41\x5E\x41\x5D\x41\x5C\x5F\x5E\xC3'
    if descricao['inicio'] != 'rs_inicio_principal' and bytes(
            gerador.codigo[fim - len(epilogo):fim]) != epilogo:
        raise ErroCompilacao('Epilogo de usuario Windows diverge do contrato.')
    return operacoes, comprimento


def gerar_desenrolamentos(gerador, base_codigo, base_xdados):
    """Produz .pdata/.xdata e confere novamente os contratos nos bytes finais."""
    entradas, dados = [], bytearray()
    for descricao in getattr(gerador, 'desenrolamentos', ()):
        inicio = gerador.rotulos[descricao['inicio']]
        fim = gerador.rotulos[descricao['fim']]
        fim_prologo = gerador.rotulos[descricao['fim_prologo']]
        if not 0 <= inicio < fim <= len(gerador.codigo):
            raise ErroCompilacao('Intervalo de desenrolamento Windows invalido.')
        comprimento = fim_prologo - inicio
        quadro = descricao['quadro']
        auxiliar = descricao.get('prologo', '').startswith('auxiliar_')
        if auxiliar:
            _, operacoes, frame = _validar_auxiliar(
                gerador.codigo, inicio, fim, comprimento, descricao)
        else:
            operacoes, comprimento = _validar_usuario(
                gerador, descricao, inicio, fim, fim_prologo)
            frame = 5
        alocacao, quantidade = _alocacao(quadro, comprimento, pequeno=auxiliar)
        codigos = alocacao + b''.join(
            _registrar_codigo(op, info, deslocamento)
            for deslocamento, op, info in operacoes)
        quantidade += len(operacoes)
        if quantidade > 255:
            raise ErroCompilacao('Quantidade de codigos Windows fora do limite.')
        informacao = struct.pack('<BBBB', 1, comprimento, quantidade, frame) + codigos
        if quantidade % 2:
            informacao += b'\0\0'
        if len(dados) % 4:
            dados += bytes(4 - len(dados) % 4)
        endereco = base_xdados + len(dados)
        dados += informacao
        entradas.append((base_codigo + inicio, base_codigo + fim, endereco))
    entradas.sort()
    for anterior, atual in zip(entradas, entradas[1:]):
        if anterior[1] > atual[0]:
            raise ErroCompilacao('Intervalos de desenrolamento Windows sobrepostos.')
    return b''.join(struct.pack('<III', *e) for e in entradas), bytes(dados)
