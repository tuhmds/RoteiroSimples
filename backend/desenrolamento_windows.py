"""Metadados reais de desenrolamento de quadros Windows x64.

O emissor não presume que uma função é folha quando ela salva RBP/RBX
ou reserva pilha. As descrições registradas refletem bytes emitidos.
Por segurança, quadros alocados por sondagem em laço ficam fora do
escopo deste primeiro formato: não são falsamente descritos.
"""
import struct

from compilador.erros import ErroCompilacao


def _registrar_codigo(operacao, informacao, deslocamento):
    return bytes((deslocamento, (informacao << 4) | operacao))


def gerar_desenrolamentos(gerador, base_codigo, base_xdados):
    """Cria pares (.pdata,.xdata) para os quadros elegíveis registrados.

    Versão 1, sem manipulador de exceções:
      UWOP_ALLOC_LARGE 1, UWOP_PUSH_NONVOL 0, UWOP_SET_FPREG 3.
    Quadro: push rbp; mov rbp,rsp; push rbx; sub rsp,valor.
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
        if not (tamanho_quadro > 0 and tamanho_quadro % 8 == 0
                and tamanho_quadro <= 0xFFFF * 8):
            raise ErroCompilacao('Quadro Windows nao representavel na tabela.')
        # Quadros com sondagem por varias paginas requerem registro
        # de cada etapa ou padrao de prologo adicional.
        if tamanho_quadro >= 4096:
            continue
        if gerador.codigo[inicio:inicio + 5] != b'\x55\x48\x89\xE5\x53':
            raise ErroCompilacao('Prologo Windows mudou: regenerar regras de desenrolamento.')
        final_subtracao = gerador.codigo[fim_prologo - 7:fim_prologo]
        if final_subtracao[:3] != b'\x48\x81\xEC' or (
                struct.unpack_from('<I', final_subtracao, 3)[0]
                != tamanho_quadro):
            raise ErroCompilacao('Reserva de pilha nao corresponde ao prologo Windows.')
        if len(dados) % 4:
            dados += bytes(4 - len(dados) % 4)
        endereco_xdados = base_xdados + len(dados)
        # Operações em ordem DESCENDENTE do término de cada instrução.
        # ALLOC_LARGE consome um slot adicional com tamanho / 8.
        codigos = b''.join((
            _registrar_codigo(1, 0, comprimento),
            struct.pack('<H', tamanho_quadro // 8),
            _registrar_codigo(0, 3, 5),   # push RBX, posição 5
            _registrar_codigo(3, 0, 4),   # mov RBP,RSP, posição 4
            _registrar_codigo(0, 5, 1),   # push RBP, posição 1
        ))
        assert len(codigos) == 10
        cabecalho = struct.pack('<BBBB', 1, comprimento, 5, 5)
        informacao = cabecalho + codigos + b'\0\0'
        dados += informacao
        entradas.append((
            base_codigo + inicio,
            base_codigo + fim,
            endereco_xdados,
        ))
    entradas.sort()
    for anterior, atual in zip(entradas, entradas[1:]):
        if anterior[1] > atual[0]:
            raise ErroCompilacao('Intervalos de desenrolamento Windows sobrepostos.')
    tabela = bytearray()
    for entrada in entradas:
        tabela += struct.pack('<III', *entrada)
    return bytes(tabela), bytes(dados)
