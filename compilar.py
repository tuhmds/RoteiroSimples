#!/usr/bin/env python3
"""Primeiro compilador experimental de RoteiroSimples (RS): código-fonte -> x86-64 nativo.
Sem invocar compilador C, assembler ou linker externo.
Alvos: Linux ELF64 e Windows PE32+ (x86-64).
"""

import argparse
import json
import os
import re
import struct
import sys
from pathlib import Path


class ErroCompilacao(Exception):
    pass


def alinhar(valor: int, multiplo: int) -> int:
    return (valor + multiplo - 1) // multiplo * multiplo


def ler_programa(caminho: Path) -> list[str]:
    try:
        fonte = caminho.read_text(encoding="utf-8-sig")
    except (OSError, UnicodeError) as erro:
        raise ErroCompilacao(f"Não foi possível ler o arquivo: {erro}") from erro
    linhas = [(numero, linha.strip()) for numero, linha in enumerate(fonte.splitlines(), 1)
             if linha.strip() and not linha.lstrip().startswith("//")]
    if not linhas or linhas[0][1] != "início {":
        raise ErroCompilacao("Linha 1: o programa deve começar com 'início {'.")
    if len(linhas) < 2 or linhas[-1][1] != "}":
        raise ErroCompilacao("O programa deve terminar com '}' em uma linha separada.")
    padrao = re.compile(r'^escreva\s*\(\s*("(?:\\.|[^"\\])*")\s*\)\s*;?$')
    mensagens = []
    for numero, linha in linhas[1:-1]:
        achado = padrao.fullmatch(linha)
        if not achado:
            raise ErroCompilacao(
                f"Linha {numero}: instrução desconhecida. Nesta versão, use escreva(\"mensagem\")."
            )
        try:
            mensagem = json.loads(achado.group(1))
        except json.JSONDecodeError as erro:
            raise ErroCompilacao(f"Linha {numero}: texto inválido: {erro.msg}.") from erro
        mensagens.append(mensagem + "\n")
    if not mensagens:
        raise ErroCompilacao("Escreva pelo menos uma instrução escreva(\"mensagem\").")
    return mensagens


class Emissor:
    """Monta bytes x86-64 e corrige endereços RIP-relativos na etapa final."""

    def __init__(self):
        self.codigo = bytearray()
        self.pendencias = []  # (posição_disp32, identificador)

    def bytes(self, dados: bytes):
        self.codigo += dados

    def relativo(self, prefixo: bytes, identificador: str):
        self.bytes(prefixo)
        posicao = len(self.codigo)
        self.bytes(b"\x00" * 4)
        self.pendencias.append((posicao, identificador))

    def resolver(self, base_codigo_rva: int, enderecos_rva: dict[str, int]):
        for posicao, identificador in self.pendencias:
            if identificador not in enderecos_rva:
                raise RuntimeError(f"Símbolo ausente: {identificador}")
            deslocamento = enderecos_rva[identificador] - (base_codigo_rva + posicao + 4)
            struct.pack_into("<i", self.codigo, posicao, deslocamento)


def compilar_linux(mensagens: list[str]) -> bytes:
    emissor = Emissor()
    for indice, mensagem in enumerate(mensagens):
        dados = mensagem.encode("utf-8")
        emissor.bytes(b"\xB8\x01\x00\x00\x00")            # mov eax, 1 (sys_write)
        emissor.bytes(b"\xBF\x01\x00\x00\x00")            # mov edi, 1 (stdout)
        emissor.relativo(b"\x48\x8D\x35", f"texto_{indice}") # lea rsi,[rip+texto]
        emissor.bytes(b"\xBA" + struct.pack("<I", len(dados))) # mov edx,tamanho
        emissor.bytes(b"\x0F\x05")                         # syscall
    emissor.bytes(b"\xB8\x3C\x00\x00\x00")  # mov eax, 60 (sys_exit)
    emissor.bytes(b"\x31\xFF\x0F\x05")      # xor edi,edi; syscall

    inicio_codigo = 0x100
    inicio_textos = inicio_codigo + len(emissor.codigo)
    dados = bytearray()
    enderecos = {}
    for indice, mensagem in enumerate(mensagens):
        enderecos[f"texto_{indice}"] = inicio_textos + len(dados)
        dados += mensagem.encode("utf-8")
    emissor.resolver(inicio_codigo, enderecos)

    imagem = bytearray(inicio_codigo)
    imagem += emissor.codigo + dados
    # Cabeçalho ELF64: um segmento de carregamento contendo cabeçalhos, código e dados.
    imagem[:64] = struct.pack(
        "<16sHHIQQQIHHHHHH", b"\x7fELF" + bytes([2, 1, 1, 0]) + bytes(8),
        2, 62, 1, 0x400000 + inicio_codigo, 64, 0, 0, 64, 56, 1, 0, 0, 0,
    )
    imagem[64:120] = struct.pack(
        "<IIQQQQQQ", 1, 5, 0, 0x400000, 0x400000,
        len(imagem), len(imagem), 0x1000,
    )
    return bytes(imagem)


def construir_importacoes(base_rva: int, nomes: list[str]):
    """Seção .idata PE32+ com descritor, ILT, IAT, nomes e área de escrita."""
    conteudo = bytearray(40)  # um descritor de 20 bytes e terminador vazio
    tamanho_tabela = (len(nomes) + 1) * 8
    inicio_ilt = len(conteudo)
    conteudo.extend(bytes(tamanho_tabela))
    inicio_iat = len(conteudo)
    conteudo.extend(bytes(tamanho_tabela))
    offsets_nomes = []
    for nome in nomes:
        while len(conteudo) % 2:
            conteudo.append(0)
        offsets_nomes.append(len(conteudo))
        conteudo += b"\x00\x00" + nome.encode("ascii") + b"\x00"
    inicio_dll = len(conteudo)
    conteudo += b"KERNEL32.dll\x00"
    while len(conteudo) % 4:
        conteudo.append(0)
    inicio_contador = len(conteudo)
    conteudo += b"\x00" * 4
    for indice, offset_nome in enumerate(offsets_nomes):
        struct.pack_into("<Q", conteudo, inicio_ilt + indice * 8, base_rva + offset_nome)
        struct.pack_into("<Q", conteudo, inicio_iat + indice * 8, base_rva + offset_nome)
    struct.pack_into("<IIIII", conteudo, 0, base_rva + inicio_ilt, 0, 0,
                     base_rva + inicio_dll, base_rva + inicio_iat)
    enderecos = {nome: base_rva + inicio_iat + indice * 8 for indice, nome in enumerate(nomes)}
    enderecos["contador"] = base_rva + inicio_contador
    return conteudo, enderecos, inicio_iat, tamanho_tabela


def compilar_windows(mensagens: list[str]) -> bytes:
    base_texto = 0x1000
    base_importacoes = 0x2000
    base_dados = 0x3000
    nomes = ["GetStdHandle", "SetConsoleOutputCP", "WriteFile", "ExitProcess"]
    importacoes, enderecos, inicio_iat, tamanho_iat = construir_importacoes(base_importacoes, nomes)
    emissor = Emissor()
    emissor.bytes(b"\x53")                    # push rbx (registrador não-volátil)
    emissor.bytes(b"\x48\x83\xEC\x30")    # sub rsp, 48 (alinhamento e espaço de argumentos)
    emissor.bytes(b"\xB9" + struct.pack("<I", 65001))  # mov ecx, 65001 (UTF-8)
    emissor.relativo(b"\xFF\x15", "SetConsoleOutputCP")
    emissor.bytes(b"\xB9\xF5\xFF\xFF\xFF") # mov ecx, -11 (STD_OUTPUT_HANDLE)
    emissor.relativo(b"\xFF\x15", "GetStdHandle")
    emissor.bytes(b"\x48\x89\xC3")           # mov rbx, rax
    strings = bytearray()
    for indice, mensagem in enumerate(mensagens):
        dados = mensagem.encode("utf-8")
        enderecos[f"texto_{indice}"] = base_dados + len(strings)
        strings += dados
        emissor.bytes(b"\x48\x89\xD9")  # mov rcx, rbx (handle)
        emissor.relativo(b"\x48\x8D\x15", f"texto_{indice}")  # lea rdx, texto
        emissor.bytes(b"\x41\xB8" + struct.pack("<I", len(dados))) # mov r8d,len
        emissor.relativo(b"\x4C\x8D\x0D", "contador")  # lea r9, contador
        emissor.bytes(b"\xC7\x44\x24\x20\x00\x00\x00\x00") # 5º argumento NULL
        emissor.relativo(b"\xFF\x15", "WriteFile")
    emissor.bytes(b"\x31\xC9")              # xor ecx,ecx (código saída 0)
    emissor.relativo(b"\xFF\x15", "ExitProcess")
    # A função ExitProcess não retorna.
    if len(emissor.codigo) > 0x1000 or len(importacoes) > 0x1000 or len(strings) > 0x1000:
        raise ErroCompilacao("Programa muito grande para a primeira versão experimental (máximo 4 KiB por seção).")
    emissor.resolver(base_texto, enderecos)

    seccoes = [
        (b".text", bytes(emissor.codigo), base_texto, 0x60000020),   # código RX
        (b".idata", bytes(importacoes), base_importacoes, 0xC0000040), # dados RW
        (b".rdata", bytes(strings), base_dados, 0x40000040),       # dados R
    ]
    alinhamento_arquivo = 0x200
    alinhamento_memoria = 0x1000
    tamanho_cabecalho = 0x200
    endereco_arquivo = tamanho_cabecalho
    descritores = []
    for nome, conteudo, endereco_virtual, caracteristicas in seccoes:
        tamanho_fisico = alinhar(len(conteudo), alinhamento_arquivo)
        descritores.append((nome, conteudo, endereco_virtual, caracteristicas,
                            endereco_arquivo, tamanho_fisico))
        endereco_arquivo += tamanho_fisico

    cabecalho = bytearray(tamanho_cabecalho)
    cabecalho[:2] = b"MZ"
    struct.pack_into("<I", cabecalho, 0x3C, 0x80)
    cabecalho[0x80:0x84] = b"PE\x00\x00"
    struct.pack_into("<HHIIIHH", cabecalho, 0x84,
                     0x8664, 3, 0, 0, 0, 0xF0, 0x0022)  # AMD64, exe + large address
    pos = 0x98
    # IMAGE_OPTIONAL_HEADER64 (112 bytes antes do diretório de dados).
    opcionais = bytearray(0xF0)
    struct.pack_into("<H", opcionais, 0, 0x20B)  # PE32+
    struct.pack_into("<I", opcionais, 4, descritores[0][5])
    struct.pack_into("<I", opcionais, 8, descritores[1][5] + descritores[2][5])
    struct.pack_into("<I", opcionais, 16, base_texto)  # endereço inicial
    struct.pack_into("<I", opcionais, 20, base_texto)  # base de código
    struct.pack_into("<Q", opcionais, 24, 0x140000000) # base imagem
    struct.pack_into("<I", opcionais, 32, alinhamento_memoria)
    struct.pack_into("<I", opcionais, 36, alinhamento_arquivo)
    struct.pack_into("<HHHH", opcionais, 40, 6, 0, 0, 0)
    struct.pack_into("<HH", opcionais, 48, 6, 0)
    struct.pack_into("<I", opcionais, 56, 0x4000)      # tamanho de imagem
    struct.pack_into("<I", opcionais, 60, tamanho_cabecalho)
    struct.pack_into("<HH", opcionais, 68, 3, 0x100)   # console, NX compat
    struct.pack_into("<QQQQ", opcionais, 72, 0x100000, 0x1000, 0x100000, 0x1000)
    struct.pack_into("<II", opcionais, 104, 0, 16)    # 16 diretórios
    struct.pack_into("<II", opcionais, 112 + 8 * 1, base_importacoes, 40) # import
    struct.pack_into("<II", opcionais, 112 + 8 * 12,
                     base_importacoes + inicio_iat, tamanho_iat) # IAT
    cabecalho[pos:pos + 0xF0] = opcionais
    pos += 0xF0
    for nome, conteudo, endereco_virtual, caracteristicas, offset, tamanho_fisico in descritores:
        struct.pack_into("<8sIIIIIIHHI", cabecalho, pos, nome.ljust(8, b"\x00"),
                         len(conteudo), endereco_virtual, tamanho_fisico, offset,
                         0, 0, 0, 0, caracteristicas)
        pos += 40
    resultado = cabecalho
    for _, conteudo, _, _, _, tamanho_fisico in descritores:
        resultado += conteudo + bytes(tamanho_fisico - len(conteudo))
    return bytes(resultado)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Compilador experimental RoteiroSimples (RS) 0.1")
    parser.add_argument("fonte", type=Path, help="arquivo .rts em UTF-8")
    parser.add_argument("--alvo", choices=["windows", "linux"], default="windows",
                        help="sistema de destino (padrão: windows)")
    parser.add_argument("-o", "--saida", type=Path, help="nome do executável")
    opcoes = parser.parse_args(argv)
    saida = opcoes.saida or opcoes.fonte.with_suffix(".exe" if opcoes.alvo == "windows" else "")
    try:
        mensagens = ler_programa(opcoes.fonte)
        binario = compilar_windows(mensagens) if opcoes.alvo == "windows" else compilar_linux(mensagens)
        saida.write_bytes(binario)
        if opcoes.alvo == "linux":
            os.chmod(saida, saida.stat().st_mode | 0o111)
    except (ErroCompilacao, OSError, OverflowError, struct.error) as erro:
        print(f"Erro: {erro}", file=sys.stderr)
        return 1
    print(f"Programa compilado: {saida} ({len(binario)} bytes, alvo {opcoes.alvo}).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
