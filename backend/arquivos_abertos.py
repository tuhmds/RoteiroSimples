"""Recursos de arquivo nativos com propriedade local e erro recuperável.

Handle fechado = -1. Não há cópia/transferência de propriedade no RS 0.38.
Rotinas recebem argumentos em registradores da convenção interna RS:
  abrir(path:RDI, modo:RSI) -> handle ou -1
  fechar(handle:RDI) -> 0 ou -4
  sincronizar(handle:RDI) -> 0 ou -6
  transferir(handle:RDI, dados:RSI, tamanho:RDX, posicao:RCX)
     -> bytes ou -2/-3.
"""
import struct
from . import politica_caminhos


def _emitir(g, hexa):
    g.bytes(bytes.fromhex(hexa))


def _deslocamento(variaveis, nome, windows):
    return -(16 + 8 * variaveis[nome]) if windows else -(8 + 8 * variaveis[nome])


def _ler_recurso(g, variaveis, nome, windows):
    g.bytes(b'\x48\x8B\xBD' + struct.pack('<i', _deslocamento(variaveis,nome,windows)))


def _guardar_estado(g, variaveis, nome, windows):
    g.bytes(b'\x48\x89\x85' + struct.pack('<i', _deslocamento(variaveis,nome,windows)))


def _invalido(g, rotulo):
    _emitir(g, '48 83 FF FF')  # cmp rdi,-1
    g.salto(rotulo, 'je')


def emitir_auto_fechar(g, variaveis, nome, windows):
    """Fecha de forma idempotente e detecta falhas também no caminho implícito."""
    ident = g.proxima_condicao
    g.proxima_condicao += 1
    fim = f'recurso_fim_auto_{ident}'
    _ler_recurso(g, variaveis, nome, windows)
    _invalido(g, fim)
    g.chamada('rs_fechar_recurso')
    _emitir(g, '48 85 C0')
    g.salto('erro_fechamento_implicito', 'jnz')
    _emitir(g, '48 C7 C0 FF FF FF FF')
    _guardar_estado(g, variaveis, nome, windows)
    g.marcar(fim)


def emitir_comando(g, op, variaveis, tipos, windows, mensagens, endereco_buffer, expressao):
    comando = op[0]
    recurso = op[1] if comando != 'abra_recurso' else op[2]
    nome_estado = op[-1]
    ident = g.proxima_condicao
    g.proxima_condicao += 1
    invalido = f'recurso_invalido_{ident}'
    finalizar = f'recurso_final_{ident}'
    carregamento = comando == 'carregue_de'

    if comando == 'abra_recurso':
        _, caminho, _, modo, _ = op
        caminho_variavel = isinstance(caminho, tuple) and caminho[0] == 'caminho_buffer'
        if not caminho_variavel:
            indice = len(mensagens)
            mensagens[indice] = caminho + '\x00'
        _ler_recurso(g, variaveis, recurso, windows)
        _emitir(g, '48 83 FF FF')
        ja_aberto = f'recurso_ja_aberto_{ident}'
        g.salto(ja_aberto, 'jne')
        if caminho_variavel:
            dados, comprimento, _ = endereco_buffer(
                variaveis, caminho[1], tipos, windows)
            g.bytes(b'\x48\x8D\xBD' + struct.pack('<i', dados))
            g.bytes(b'\x48\x8B\xB5' + struct.pack('<i', comprimento))
            _emitir(g, 'BA ' + struct.pack('<I', modo).hex(' '))
            g.chamada('rs_abrir_caminho_verificado')
        else:
            g.relativo(b'\x48\x8D\x3D', f'mensagem_{indice}')
            _emitir(g, 'BE ' + struct.pack('<I', modo).hex(' '))
            g.chamada('rs_abrir_recurso')
        _emitir(g, '48 85 C0')
        falha = f'recurso_falha_abertura_{ident}'
        g.salto(falha, 'js')
        _guardar_estado(g, variaveis, recurso, windows)
        _emitir(g, '31 C0')  # 0 = sucesso
        g.salto(finalizar)
        g.marcar(falha)
        # RAX já contém -1 (OS) ou -3 (caminho inválido).
        g.salto(finalizar)
        g.marcar(ja_aberto)
        _emitir(g, '48 C7 C0 FB FF FF FF')  # -5, ativo
        g.salto(finalizar)
    else:
        _ler_recurso(g, variaveis, recurso, windows)
        _invalido(g, invalido)
        if comando == 'feche_recurso':
            g.chamada('rs_fechar_recurso')
            _emitir(g, '50')  # conserva resultado
            _emitir(g, '48 C7 C0 FF FF FF FF')  # marca fechado, inclusive falha
            _guardar_estado(g, variaveis, recurso, windows)
            _emitir(g, '58')
        elif comando == 'sincronize_recurso':
            g.chamada('rs_sincronizar_recurso')
        elif comando == 'bloqueie_recurso':
            g.chamada('rs_bloquear_recurso')
        else:
            nome_buffer = op[2]
            dados, comprimento, capacidade = endereco_buffer(
                variaveis, nome_buffer, tipos, windows)
            expressao(g, op[3], variaveis, windows)
            _emitir(g, '50')  # salva a posição
            if carregamento:
                expressao(g, op[4], variaveis, windows, pilha_extra=1)
            else:
                g.bytes(b'\x48\x8B\x85' + struct.pack('<i', comprimento))
            _emitir(g, '50 5A 59')  # RDX = tamanho, RCX = posicao
            if carregamento:
                _emitir(g, '48 85 D2')
                g.salto(invalido, 'js')
                g.bytes(b'\x48\x81\xFA' + struct.pack('<I', capacidade))
                g.salto(invalido, 'ja')
            _ler_recurso(g, variaveis, recurso, windows)
            g.bytes(b'\x48\x8D\xB5' + struct.pack('<i', dados))
            g.chamada('rs_recurso_ler' if carregamento else 'rs_recurso_gravar')
        g.salto(finalizar)
        g.marcar(invalido)
        _emitir(g, '48 C7 C0 FD FF FF FF')  # -3, fechado/arg inválido
    g.marcar(finalizar)
    _guardar_estado(g, variaveis, nome_estado, windows)
    if carregamento:
        erro = f'recurso_leitura_erro_{ident}'
        fim = f'recurso_leitura_fim_{ident}'
        _emitir(g, '48 85 C0')
        g.salto(erro, 'js')
        g.bytes(b'\x48\x89\x85' + struct.pack('<i', comprimento))
        g.salto(fim)
        g.marcar(erro)
        _emitir(g, '31 C0')
        g.bytes(b'\x48\x89\x85' + struct.pack('<i', comprimento))
        g.marcar(fim)


def _rejeitar_dispositivos_windows(g, invalido):
    """Impede nomes Win32 reservados independentemente da caixa e extensão.

    Chega aqui depois de validar cada caractere; R8 aponta para os bytes
    e R9 contém o comprimento, sem leitura além dele.
    """
    terminar = 'rs_caminho_dispositivo_ok'
    _emitir(g, '49 83 F9 03')  # len < 3?
    g.salto(terminar, 'jb')
    _emitir(g, '41 0F B6 00 83 E0 DF')   # primeiro, maiúsculo
    _emitir(g, '41 0F B6 50 01 83 E2 DF')  # segundo, maiúsculo
    _emitir(g, '45 0F B6 50 02 41 83 E2 DF')  # terceiro, maiúsculo

    simples = ('CON', 'PRN', 'AUX', 'NUL')
    compostos = ('COM', 'LPT')
    for prefixo in simples + compostos:
        proximo = f'rs_dispositivo_proximo_{prefixo.lower()}'
        _emitir(g, f'3C {ord(prefixo[0]):02X}')
        g.salto(proximo, 'jne')
        _emitir(g, f'80 FA {ord(prefixo[1]):02X}')
        g.salto(proximo, 'jne')
        _emitir(g, f'41 80 FA {ord(prefixo[2]):02X}')
        g.salto(proximo, 'jne')

        if prefixo in simples:
            _emitir(g, '49 83 F9 03')
            g.salto(invalido, 'je')
            # Para prefixo reservado, próximo caractere '.' preserva
            # a semântica especial mesmo em CON.txt ou NUL.rsd.
            _emitir(g, '41 0F B6 48 03 80 F9 2E')
            g.salto(invalido, 'je')
        else:
            _emitir(g, '49 83 F9 04')
            g.salto(proximo, 'jb')
            _emitir(g, '41 0F B6 48 03 80 F9 31')
            g.salto(proximo, 'jb')
            _emitir(g, '80 F9 39')
            g.salto(proximo, 'ja')
            _emitir(g, '49 83 F9 04')
            g.salto(invalido, 'je')
            _emitir(g, '41 0F B6 48 04 80 F9 2E')
            g.salto(invalido, 'je')
        g.marcar(proximo)
    g.marcar(terminar)


def _rotina_caminho_verificado(g, windows):
    """Valida e copia um basename ASCII texto[N] para C NUL terminada.

    RDI = bytes originais; RSI = comprimento; RDX = modo.
    Nunca acessa além de len; não grava no buffer do programa.
    Aceita apenas [A-Za-z0-9_][A-Za-z0-9_.-]*, até 240 bytes.
    """
    g.marcar('rs_abrir_caminho_verificado')
    _emitir(g, '55 48 89 E5 48 81 EC 30 01 00 00')  # 304 bytes
    _emitir(g, '48 89 7D F8 48 89 75 F0 48 89 55 E8')
    invalido='rs_caminho_invalido'
    loop='rs_caminho_loop'
    valido='rs_caminho_caractere_valido'
    pontuacao='rs_caminho_pontuacao'
    finalizar='rs_caminho_validado'
    fim='rs_caminho_fim'
    _emitir(g, '48 85 F6')
    g.salto(invalido, 'jle')
    _emitir(g, '48 81 FE F0 00 00 00')
    g.salto(invalido, 'ja')
    _emitir(g, '4C 8B 45 F8 4C 8B 4D F0 31 C9')
    g.marcar(loop)
    _emitir(g, '4C 39 C9')  # cmp rcx,r9
    g.salto(finalizar, 'je')
    _emitir(g, '41 0F B6 04 08') # movzx eax,byte ptr [r8+rcx]
    _emitir(g, '3C 30')
    g.salto(pontuacao, 'jb')
    _emitir(g, '3C 39')
    g.salto(valido, 'jbe')
    _emitir(g, '3C 41')
    g.salto(pontuacao, 'jb')
    _emitir(g, '3C 5A')
    g.salto(valido, 'jbe')
    _emitir(g, '3C 5F')
    g.salto(valido, 'je')
    _emitir(g, '3C 61')
    g.salto(pontuacao, 'jb')
    _emitir(g, '3C 7A')
    g.salto(valido, 'jbe')
    g.marcar(pontuacao)
    _emitir(g, '48 85 C9') # no primeiro byte: não aceita ponto nem hífen
    g.salto(invalido, 'jz')
    _emitir(g, '3C 2D')
    g.salto(valido, 'je')
    _emitir(g, '3C 2E')
    g.salto(valido, 'je')
    g.salto(invalido)
    g.marcar(valido)
    _emitir(g, '88 84 0D D0 FE FF FF') # [rbp+rcx-304]=al
    _emitir(g, '48 FF C1')
    g.salto(loop)
    g.marcar(finalizar)
    if windows:
        _rejeitar_dispositivos_windows(g, invalido)
    # A checagem Windows pode alterar RCX: reconstituímos índice = tamanho
    _emitir(g, '4C 89 C9')
    _emitir(g, 'C6 84 0D D0 FE FF FF 00')
    _emitir(g, '48 8D BD D0 FE FF FF 48 8B 75 E8')
    g.chamada('rs_abrir_recurso')
    g.salto(fim)
    g.marcar(invalido)
    _emitir(g, '48 C7 C0 FD FF FF FF') # -3
    g.marcar(fim)
    _emitir(g, '48 89 EC 5D C3')


def _rotina_abrir(g, windows):
    g.marcar('rs_abrir_recurso')
    _emitir(g, '55 48 89 E5 48 83 EC 40')
    _emitir(g, '48 89 7D F8 48 89 75 F0')
    if windows:
        ler = 'rs_abrir_modo_leitura'
        novo = 'rs_abrir_modo_novo'
        fazer = 'rs_abrir_executar'
        _emitir(g, '48 83 7D F0 00')
        g.salto(ler, 'je')
        _emitir(g, 'BA 00 00 00 C0')  # GENERIC_READ | GENERIC_WRITE
        _emitir(g, '41 B9 04 00 00 00')  # OPEN_ALWAYS
        _emitir(g, '48 83 7D F0 02')
        g.salto(novo, 'je')
        g.salto(fazer)
        g.marcar(novo)
        _emitir(g, '41 B9 01 00 00 00') # CREATE_NEW
        g.salto(fazer)
        g.marcar(ler)
        _emitir(g, 'BA 00 00 00 80') # GENERIC_READ
        _emitir(g, '41 B9 03 00 00 00') # OPEN_EXISTING
        g.marcar(fazer)
        # CreateFileA(path,access,share=0,security=0,disposition,attributes,template)
        # R9 armazena disposition temporariamente, antes de zerar R9 para security
        _emitir(g, '44 89 4D E8')
        _emitir(g, '48 8B 4D F8 45 31 C0 45 31 C9 48 83 EC 40')
        _emitir(g, '8B 45 E8 89 44 24 20')
        g.bytes(b'\xC7\x44\x24\x28' + politica_caminhos.atributos_windows())
        _emitir(g, '48 C7 44 24 30 00 00 00 00')
        g.relativo(b'\xFF\x15', 'CreateFileA')
        _emitir(g, '48 83 C4 40')
        _emitir(g, '48 83 F8 FF')
        fim = 'rs_abrir_fim'
        g.salto(fim, 'je')
        _emitir(g, '48 89 45 E8')  # identificador temporario
        _emitir(g, '48 89 C7')
        g.chamada('rs_verificar_arquivo_regular')
        _emitir(g, '48 85 C0')
        valido = 'rs_abrir_arquivo_validado'
        g.salto(valido, 'jz')
        _emitir(g, '48 8B 7D E8')
        g.chamada('rs_fechar_recurso')
        _emitir(g, '48 C7 C0 FF FF FF FF')
        g.salto(fim)
        g.marcar(valido)
        _emitir(g, '48 8B 45 E8')
        g.marcar(fim)
    else:
        _emitir(g, 'B8 01 01 00 00 48 C7 C7 9C FF FF FF')
        _emitir(g, '48 8B 75 F8')
        leitura='rs_abrir_linux_leitura'
        novo='rs_abrir_linux_novo'
        chamar='rs_abrir_linux_chamar'
        _emitir(g, '48 83 7D F0 00')
        g.salto(leitura, 'je')
        g.bytes(b'\xBA' + politica_caminhos.sinalizadores_linux('alteracao'))
        _emitir(g, '48 83 7D F0 02')
        g.salto(novo, 'je')
        g.salto(chamar)
        g.marcar(novo)
        g.bytes(b'\xBA' + politica_caminhos.sinalizadores_linux('novo'))
        g.salto(chamar)
        g.marcar(leitura)
        g.bytes(b'\xBA' + politica_caminhos.sinalizadores_linux('leitura'))
        g.marcar(chamar)
        _emitir(g, '41 BA 80 01 00 00 0F 05 48 85 C0')
        ok='rs_abrir_linux_ok'
        g.salto(ok, 'jns')
        _emitir(g, '48 C7 C0 FF FF FF FF')
        g.marcar(ok)
    _emitir(g, '48 89 EC 5D C3')


def _rotina_fechar(g, windows):
    g.marcar('rs_fechar_recurso')
    if windows:
        _emitir(g, '48 89 F9 48 83 EC 28')
        g.relativo(b'\xFF\x15', 'CloseHandle')
        _emitir(g, '48 83 C4 28 85 C0')
        falha='rs_fechar_falha'
        g.salto(falha, 'jz')
        _emitir(g, '31 C0 C3')
        g.marcar(falha)
        _emitir(g, '48 C7 C0 FC FF FF FF C3')
    else:
        _emitir(g, 'B8 03 00 00 00 0F 05 48 85 C0')
        falha='rs_fechar_falha'
        g.salto(falha, 'js')
        _emitir(g, '31 C0 C3')
        g.marcar(falha)
        _emitir(g, '48 C7 C0 FC FF FF FF C3')


def _rotina_sincronizar(g, windows):
    g.marcar('rs_sincronizar_recurso')
    if windows:
        _emitir(g, '48 89 F9 48 83 EC 28')
        g.relativo(b'\xFF\x15', 'FlushFileBuffers')
        _emitir(g, '48 83 C4 28 85 C0')
        falha='rs_sincronizar_falha'
        g.salto(falha, 'jz')
        _emitir(g, '31 C0 C3')
        g.marcar(falha)
        _emitir(g, '48 C7 C0 FA FF FF FF C3')
    else:
        _emitir(g, 'B8 4A 00 00 00 0F 05 48 85 C0')
        falha='rs_sincronizar_falha'
        g.salto(falha, 'js')
        _emitir(g, '31 C0 C3')
        g.marcar(falha)
        _emitir(g, '48 C7 C0 FA FF FF FF C3')


def _rotina_bloquear(g, windows):
    """Bloqueio sem espera: Linux flock; Windows já abre share=0."""
    g.marcar('rs_bloquear_recurso')
    if windows:
        # CreateFileA usa dwShareMode=0 desde a abertura: outro processo
        # não pode abrir simultaneamente. Não fingimos LockFileEx adicional.
        _emitir(g, '31 C0 C3')
    else:
        # flock(fd, LOCK_EX | LOCK_NB) = syscall 73, flags 6.
        _emitir(g, 'B8 49 00 00 00 BE 06 00 00 00 0F 05 48 85 C0')
        falha = 'rs_bloquear_falha'
        g.salto(falha, 'js')
        _emitir(g, '31 C0 C3')
        g.marcar(falha)
        _emitir(g, '48 C7 C0 F9 FF FF FF C3') # -7


def _rotina_transferir(g, windows, gravar):
    nome = 'rs_recurso_gravar' if gravar else 'rs_recurso_ler'
    loop = nome+'_volta'
    termino=nome+'_termino'
    erro=nome+'_erro'
    invalido=nome+'_invalido'
    fim=nome+'_fim'
    g.marcar(nome)
    _emitir(g, '55 48 89 E5 48 83 EC 60')
    _emitir(g, '48 89 7D F8 48 89 75 F0 48 89 55 E8 48 89 4D E0')
    _emitir(g, '48 C7 45 D0 00 00 00 00')
    _emitir(g, '48 83 7D E0 00')
    g.salto(invalido, 'js')
    _emitir(g, '48 83 7D E8 00')
    g.salto(invalido, 'js')
    _emitir(g, '48 8B 45 E0 48 03 45 E8')
    g.salto(invalido, 'jo')
    if windows:
        _emitir(g, '48 8B 4D F8 48 8B 55 E0 45 31 C0 45 31 C9')
        _emitir(g, '48 83 EC 20')
        g.relativo(b'\xFF\x15', 'SetFilePointerEx')
        _emitir(g, '48 83 C4 20 85 C0')
        g.salto(invalido, 'jz')
    g.marcar(loop)
    _emitir(g, '48 8B 45 D0 48 3B 45 E8')
    g.salto(termino, 'je')
    if windows:
        _emitir(g, '48 8B 4D F8 48 8B 55 F0 48 03 55 D0')
        _emitir(g, '4C 8B 45 E8 4C 2B 45 D0 4C 8D 4D C8')
        _emitir(g, '48 83 EC 30')
        _emitir(g, '48 C7 44 24 20 00 00 00 00')
        g.relativo(b'\xFF\x15', 'WriteFile' if gravar else 'ReadFile')
        _emitir(g, '48 83 C4 30 85 C0')
        g.salto(erro, 'jz')
        _emitir(g, '8B 45 C8')
    else:
        _emitir(g, 'B8 12 00 00 00' if gravar else 'B8 11 00 00 00')
        _emitir(g, '48 8B 7D F8 48 8B 75 F0 48 03 75 D0')
        _emitir(g, '48 8B 55 E8 48 2B 55 D0')
        _emitir(g, '4C 8B 55 E0 4C 03 55 D0 0F 05')
        _emitir(g, '48 83 F8 FC') # EINTR
        g.salto(loop, 'je')
        _emitir(g, '48 85 C0')
        g.salto(erro, 'js')
    _emitir(g, '48 85 C0')
    g.salto(erro if gravar else termino, 'jz')
    _emitir(g, '48 01 45 D0')
    g.salto(loop)
    g.marcar(termino)
    _emitir(g, '48 8B 45 D0')
    g.salto(fim)
    g.marcar(erro)
    _emitir(g, '48 C7 C0 FE FF FF FF')
    g.salto(fim)
    g.marcar(invalido)
    _emitir(g, '48 C7 C0 FD FF FF FF')
    g.marcar(fim)
    _emitir(g, '48 89 EC 5D C3')


def emitir_rotinas(g, windows):
    _rotina_caminho_verificado(g, windows)
    _rotina_abrir(g, windows)
    _rotina_fechar(g, windows)
    _rotina_sincronizar(g, windows)
    _rotina_bloquear(g, windows)
    _rotina_transferir(g, windows, gravar=True)
    _rotina_transferir(g, windows, gravar=False)
