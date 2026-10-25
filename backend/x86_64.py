"""Emissão nativa de instruções AMD64, leitura/escrita e saltos."""
from . import consulta_arquivo
import struct
from compilador.erros import ErroCompilacao
from compilador.propriedade import eh_proprietario, eh_emprestimo, eh_texto, eh_bytes, TIPO_TEXTO_DINAMICO, TIPO_TEXTO_EMPRESTADO, TIPO_BYTES_DINAMICOS, TIPO_BYTES_EMPRESTADOS
from compilador.propriedade import eh_registro_proprietario, donos_do_agregado, contrato_valor
from compilador.propriedade import eh_colecao_proprietaria
from compilador.propriedade import passo_armazenamento
from . import colecoes_proprietarias
from . import valores_dinamicos, memoria_dinamica, sequencias_dinamicas, textos_dinamicos, listas_dinamicas, arquivos, arquivos_posicionais, bytes_seguros, arquivos_abertos, publicacao_atomica, politica_caminhos
from compilador.disposicao_tipos import palavras_tipo as _palavras_tipo
from .base import Emissor, alinhar
from .desenrolamento_windows import registrar_quadro_empilhado
from .convencao_funcoes import LIMITE_PILHA_SEGURA, custo_quadro, tamanho_quadro

# Salvamentos anteriores a RBP preservam os deslocamentos dos locais.
SALVAMENTOS_WINDOWS = bytes.fromhex('56 57 41 54 41 55 41 56 41 57')
RESTAURACOES_WINDOWS = bytes.fromhex('41 5F 41 5E 41 5D 41 5C 5F 5E')

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
        estatisticas = {'candidatos': len(candidatos), 'passagens': 0,
                        'avaliacoes': 0, 'consultas_prefixo': 0,
                        'passos_indice': 0}
        self.estatisticas_compactacao = estatisticas
        if not candidatos:
            return 0
        antigos = bytes(self.codigo)
        selecionados = set()
        finais_originais = [pos + tam for pos, tam, _, _ in candidatos]
        reducoes = [0] * (len(candidatos) + 1)

        def reducao_ate(posicao):
            # Soma dinamica de prefixos. As posicoes continuam sendo as
            # originais; selecionar um salto atualiza somente seu fim.
            estatisticas['consultas_prefixo'] += 1
            indice = bisect.bisect_right(finais_originais, posicao)
            total = 0
            while indice:
                estatisticas['passos_indice'] += 1
                total += reducoes[indice]
                indice -= indice & -indice
            return total

        def selecionar(indice, reducao):
            indice += 1
            while indice < len(reducoes):
                estatisticas['passos_indice'] += 1
                reducoes[indice] += reducao
                indice += indice & -indice

        # Cada troca reduz em 3 ou 4 bytes. Reducoes tornam outros saltos
        # pelo menos tao proximos; portanto a relaxacao e monotona.
        while True:
            estatisticas['passagens'] += 1
            alterou = False
            for indice, (inicio, tamanho, alvo, opcode) in enumerate(candidatos):
                if inicio in selecionados:
                    continue
                if alvo not in self.rotulos:
                    raise ValueError(f'Rotulo local de salto curto desconhecido: {alvo}')
                estatisticas['avaliacoes'] += 1
                # A hipotese inclui o candidato atual sem modificar o indice.
                # O seu fim so contribui quando precede a posicao consultada.
                def ajustado(posicao):
                    hipotetica = tamanho - 2 if inicio + tamanho <= posicao else 0
                    return posicao - reducao_ate(posicao) - hipotetica
                deslocamento = ajustado(self.rotulos[alvo]) - (ajustado(inicio) + 2)
                if -128 <= deslocamento <= 127:
                    selecionados.add(inicio)
                    selecionar(indice, tamanho - 2)
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
    return valores_dinamicos.deslocamento_local(variaveis, nome, windows)


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


def _composto(tipo, registros):
    return eh_proprietario(tipo) or (isinstance(tipo, str) and tipo in registros) or (
        isinstance(tipo, tuple) and tipo[0] in ('registro', 'lista', 'texto', 'bytes'))


def _donos_de_registro(g, nome):
    return donos_do_agregado(nome, g.tipos_atual, g.campos_atual)


def _validar_registro_vivo(g, variaveis, nome, windows):
    for folha in _donos_de_registro(g, nome):
        valores_dinamicos.verificar_vivo(g, variaveis, folha, windows)


def _inativar_registro(g, variaveis, nome, windows):
    for folha in _donos_de_registro(g, nome):
        valores_dinamicos.inativar(g, variaveis, folha, windows)


def _empilhar_palavras(g, variaveis, origem, quantidade, windows):
    numero = g.proxima_condicao
    g.proxima_condicao += 1
    rotulo = f'empilhar_valor_{numero}'
    g.bytes(b'\x4C\x8D\x95' + struct.pack('<i', deslocamento_variavel(variaveis, origem, windows)))
    g.bytes(b'\xB9' + struct.pack('<I', quantidade))
    g.marcar(rotulo)
    g.bytes(b'\x49\x8B\x02\x50\x49\x83\xEA\x08\xFF\xC9')
    g.salto(rotulo, 'jnz')


def _transferir_registro_proprietario(g, variaveis, tipos, destino, origem, windows):
    """Move um agregado sem copiar donos ativos nem liberar a origem duas vezes.

    Primeiro valida todas as folhas de origem. Depois descarta as folhas
    antigas do destino, copia a representacao completa e inativa as folhas
    originais. Desse modo, mesmo campos aninhados tem propriedade unica.
    """
    tipo = tipos[origem]
    if (destino == origem or tipos[destino] != tipo or
            not isinstance(tipo, tuple) or tipo[0] != 'registro'):
        raise ErroCompilacao('Movimento de registro exige agregados distintos do mesmo tipo.')
    donos_origem = _donos_de_registro(g, origem)
    donos_destino = _donos_de_registro(g, destino)
    if not donos_origem or len(donos_origem) != len(donos_destino):
        raise ErroCompilacao('Movimento de registro exige proprietarios correspondentes.')
    # Uma origem parcialmente movida e rejeitada antes de afetar o destino.
    for nome in donos_origem:
        valores_dinamicos.verificar_vivo(g, variaveis, nome, windows)
    for nome in reversed(donos_destino):
        valores_dinamicos.liberar(g, variaveis, nome, windows)
    _copiar_palavras(
        g, deslocamento_variavel(variaveis, origem, windows),
        deslocamento_variavel(variaveis, destino, windows),
        _palavras_tipo(tipo, g.registros))
    for nome in donos_origem:
        valores_dinamicos.inativar(g, variaveis, nome, windows)


def _emitir_copia_palavras(g, quantidade, rotulo):
    """Copia palavras de r10 para r11, avançando ambos os ponteiros para baixo."""
    # A ABI de registros guarda campos consecutivos em endereços decrescentes.
    g.bytes(b'\xB9' + struct.pack('<I', quantidade))
    g.marcar(rotulo)
    g.bytes(b'\x49\x8B\x02\x49\x89\x03')
    g.bytes(b'\x49\x83\xEA\x08\x49\x83\xEB\x08')
    g.bytes(b'\xFF\xC9')
    g.salto(rotulo, 'jnz')


def _copiar_palavras(g, origem, destino, quantidade):
    """Copia valores completos entre posições do quadro local."""
    if origem == destino:
        return
    numero = g.proxima_condicao
    g.proxima_condicao += 1
    rotulo = f'copiar_composto_{numero}'
    g.bytes(b'\x4C\x8D\x95' + struct.pack('<i', origem))
    g.bytes(b'\x4C\x8D\x9D' + struct.pack('<i', destino))
    _emitir_copia_palavras(g, quantidade, rotulo)


def _copiar_para_retorno(g, origem, quantidade, windows=False):
    """Copia o agregado para o destino oculto fornecido pelo chamador."""
    numero = g.proxima_condicao
    g.proxima_condicao += 1
    rotulo = f'retornar_composto_{numero}'
    g.bytes(b'\x4C\x8D\x95' + struct.pack('<i', origem))
    g.bytes(b'\x4C\x8B\x5D' + bytes((80 if windows else 24,)))
    _emitir_copia_palavras(g, quantidade, rotulo)


def _carregar_uso_pilha(g, variaveis, windows):
    if '__rs_uso_pilha' in variaveis:
        offset = deslocamento_variavel(variaveis, '__rs_uso_pilha', windows)
        g.bytes(b'\x48\x8B\x85' + struct.pack('<i', offset))
    else:
        carregar_numero(g, g.custo_pilha_principal)


def _somar_uso_pilha(g, custo):
    if custo > 0x7FFFFFFF:
        g.salto('erro_recursao_limite')
    elif custo:
        g.bytes(b'\x48\x05' + struct.pack('<I', custo))
        g.salto('erro_recursao_limite', 'jo')


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
        custo_chamada = 8 * (pilha_extra + palavras + ocultas + ajustar)
        # Validar antes de avaliar argumentos evita tanto copiar um valor
        # grande sem espaço quanto consumir donos numa chamada inviável.
        _carregar_uso_pilha(g, variaveis, windows)
        _somar_uso_pilha(g, custo_chamada + custo_quadro(g.quadros_funcoes[nome]))
        g.bytes(b'\x48\x3D' + struct.pack('<I', LIMITE_PILHA_SEGURA))
        g.salto('erro_recursao_limite', 'ja')
        if ajustar:
            g.bytes(b'\x48\x83\xEC\x08')
        empilhados = 0
        for argumento, (_, tipo_parametro) in zip(argumentos, assinatura):
            quantidade = _palavras_tipo(tipo_parametro, g.registros)
            if eh_proprietario(tipo_parametro):
                if argumento[0] == 'temporario_composto':
                    origem = argumento[1]
                    if g.tipos_atual.get(origem) != tipo_parametro:
                        raise ErroCompilacao('Temporario dinamico possui tipo incompatível com o parametro.')
                    expressao(g, argumento[2], variaveis, windows, registradores,
                             pilha_extra + ajustar + empilhados,
                             destino_composto=origem)
                elif argumento[0] == 'mova_valor_dinamico':
                    origem = argumento[1]
                else:
                    raise ErroCompilacao('Parametro proprietario exige mova(origem) ou chamada com retorno proprietario.')
                if g.tipos_atual.get(origem) != tipo_parametro:
                    raise ErroCompilacao('Transferencia de argumento exige o mesmo tipo dinamico.')
                valores_dinamicos.empilhar_transferencia(g, variaveis, origem, windows)
            elif eh_registro_proprietario(tipo_parametro, g.registros):
                if argumento[0] == 'temporario_composto':
                    origem = argumento[1]
                    expressao(g, argumento[2], variaveis, windows, registradores,
                              pilha_extra + ajustar + empilhados, destino_composto=origem)
                elif argumento[0] == 'mova_registro_proprietario':
                    origem = argumento[1]
                else:
                    raise ErroCompilacao('Parametro de registro proprietario exige mova ou chamada.')
                if g.tipos_atual[origem][1] != tipo_parametro:
                    raise ErroCompilacao('Transferencia de registro exige o mesmo tipo.')
                _validar_registro_vivo(g, variaveis, origem, windows)
                _empilhar_palavras(g, variaveis, origem, quantidade, windows)
                _inativar_registro(g, variaveis, origem, windows)
            elif isinstance(tipo_parametro, tuple) and tipo_parametro[0] == 'registro_emprestado':
                from .emprestimos_registros import empilhar
                empilhar(g, argumento, tipo_parametro, variaveis, windows, expressao,
                         _empilhar_palavras, pilha_extra + ajustar + empilhados)
            elif _composto(tipo_parametro, g.registros):
                if argumento[0] == 'temporario_composto':
                    expressao(g, argumento[2], variaveis, windows, registradores,
                             pilha_extra + ajustar + empilhados,
                             destino_composto=argumento[1])
                    origem = argumento[1]
                elif argumento[0] == 'var':
                    origem = argumento[1]
                else:
                    raise ValueError('Argumento composto exige variável ou chamada válida.')
                # A ordem da pilha acompanha os campos/palavras do valor.
                _empilhar_palavras(g, variaveis, origem, quantidade, windows)
            else:
                expressao(g, argumento, variaveis, windows, registradores,
                         pilha_extra + ajustar + empilhados)
                g.bytes(b'\x50')
            empilhados += quantidade
        if composto_retorno:
            if destino_composto == '__rs_retorno_externo':
                g.bytes(b'\x48\x8B\x45' + bytes((80 if windows else 24,)))
            else:
                destino = deslocamento_variavel(variaveis, destino_composto, windows)
                g.bytes(b'\x48\x8D\x85' + struct.pack('<i', destino))
            g.bytes(b'\x50')
        _carregar_uso_pilha(g, variaveis, windows)
        _somar_uso_pilha(g, custo_chamada)
        g.bytes(b'\x50')  # consumo de pilha acumulado
        g.chamada(f'funcao_{nome}')
        limpar = 8 * (palavras + ocultas + ajustar)
        if limpar:
            if limpar < 128:
                g.bytes(b'\x48\x83\xC4' + struct.pack('<B', limpar))
            else:
                g.bytes(b'\x48\x81\xC4' + struct.pack('<I', limpar))
    elif tipo == 'retire_registro_lista':
        if destino_composto is None:
            raise ErroCompilacao('retire exige destino proprietario para o registro retirado.')
        expressao(g, expr[2], variaveis, windows, registradores, pilha_extra)
        g.bytes(b'\x48\x89\xC6')  # RSI=índice já avaliado uma única vez
        valores_dinamicos.endereco_descritor(g, variaveis, expr[1], windows)
        if destino_composto == '__rs_retorno_externo':
            g.bytes(b'\x48\x8B\x55' + bytes((80 if windows else 24,)))
        else:
            g.bytes(b'\x48\x8D\x95' + struct.pack('<i', deslocamento_variavel(variaveis, destino_composto, windows)))
        if pilha_extra % 2:
            g.bytes(b'\x48\x83\xEC\x08')
        g.chamada(colecoes_proprietarias.rotulo(g.tipos_atual[expr[1]], 'retirar'))
        if pilha_extra % 2:
            g.bytes(b'\x48\x83\xC4\x08')
    elif tipo in ('mova_valor_dinamico', 'mova_registro_proprietario'):
        raise ErroCompilacao('Transferencia dinamica exige parametro, retorno ou declaracao proprietaria.')
    elif tipo == 'empreste_texto_lista':
        nome, indice, reserva = expr[1:]
        listas_dinamicas.copiar_composto(g, variaveis, reserva, nome, indice, windows,
            lambda gerador, no, locais, alvo: expressao(
                gerador, no, locais, alvo, registradores, pilha_extra),
            3, emprestada=g.tipos_atual[nome][0] == 'lista_emprestada')
        base = deslocamento_variavel(variaveis, reserva, windows)
        g.bytes(b'\x48\x83\xBD' + struct.pack('<i', base - 8) + b'\x00')
        g.salto('erro_valor_inativo', 'jl')
        g.bytes(b'\x48\x8D\x85' + struct.pack('<i', base))
    elif tipo in ('empreste_texto_dinamico', 'empreste_bytes_dinamicos'):
        valores_dinamicos.verificar_vivo(g, variaveis, expr[1], windows)
        g.bytes(b'\x48\x8D\x85' + struct.pack('<i', deslocamento_variavel(variaveis, expr[1], windows)))
    elif tipo in ('tamanho_texto_dinamico', 'capacidade_texto_dinamico', 'caracteres_texto'):
        textos_dinamicos.consulta(g, tipo, expr[1], variaveis, g.tipos_atual, windows, pilha_extra)
    elif tipo in ('tamanho_bytes_dinamicos', 'capacidade_bytes_dinamicos'):
        sequencias_dinamicas.vista(g, variaveis, g.tipos_atual, expr[1], windows)
        g.bytes(bytes.fromhex('48 89 D0' if tipo == 'tamanho_bytes_dinamicos' else '49 8B 40 F0'))
    elif tipo == 'byte_texto':
        expressao(g, expr[2], variaveis, windows, registradores, pilha_extra)
        g.bytes(b'\x50')
        textos_dinamicos.vista(g, variaveis, g.tipos_atual, expr[1], windows)
        g.bytes(b'\x59\x48\x85\xC9')
        g.salto('erro_indice_texto', 'js')
        g.bytes(b'\x48\x39\xD1')
        g.salto('erro_indice_texto', 'jae')
        g.bytes(b'\x0F\xB6\x04\x0E')
    elif tipo == 'empreste_lista_dinamica':
        listas_dinamicas.emprestar(g, variaveis, expr[1], windows)
    elif tipo == 'quantidade_lista_emprestada':
        listas_dinamicas.quantidade_emprestada(g, variaveis, expr[1], windows)
    elif tipo == 'capacidade_lista_emprestada':
        listas_dinamicas.quantidade_emprestada(g, variaveis, expr[1], windows, capacidade=True)
    elif tipo == 'indice_lista_emprestada':
        listas_dinamicas.ler_indice(g, variaveis, expr[1], expr[2], windows,
            lambda gerador, indice, locais, alvo: expressao(
                gerador, indice, locais, alvo, registradores, pilha_extra), emprestada=True)
    elif tipo == 'quantidade_lista_dinamica':
        listas_dinamicas.quantidade(g, variaveis, expr[1], windows)
    elif tipo == 'capacidade_lista_dinamica':
        listas_dinamicas.quantidade(g, variaveis, expr[1], windows, capacidade=True)
    elif tipo == 'indice_lista_dinamica':
        listas_dinamicas.ler_indice(g, variaveis, expr[1], expr[2], windows,
            lambda gerador, indice, locais, alvo: expressao(
                gerador, indice, locais, alvo, registradores, pilha_extra))
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
        if eh_proprietario(getattr(g, 'tipos_atual', {}).get(expr[1])):
            raise ErroCompilacao('Valor dinamico proprietario nao admite copia implicita.')
        if registradores and expr[1] in registradores:
            from .ssa_x86_64 import _emite_mov
            _emite_mov(g, 'rax', registradores[expr[1]])
        else:
            offset = deslocamento_variavel(variaveis, expr[1], windows)
            g.bytes(b'\x48\x8B\x85' + struct.pack('<i', offset))
    elif tipo == 'nao':
        expressao(g, expr[1], variaveis, windows, registradores, pilha_extra)
        g.bytes(b'\x48\x85\xC0\x0F\x94\xC0\x0F\xB6\xC0')
    elif tipo == 'logica':
        _, operador, esquerda, direita = expr
        if operador not in ('e', 'ou'):
            raise ValueError(f'Operador logico desconhecido: {operador}.')
        numero = g.proxima_condicao
        g.proxima_condicao += 1
        curta = f'logica_curta_{numero}'
        fim = f'logica_fim_{numero}'
        # Os dois caminhos mantem a mesma profundidade de pilha. A direita
        # so e avaliada se a esquerda ainda nao determinar o resultado.
        expressao(g, esquerda, variaveis, windows, registradores, pilha_extra)
        g.bytes(b'\x48\x85\xC0')
        g.salto(curta, 'jz' if operador == 'e' else 'jnz')
        expressao(g, direita, variaveis, windows, registradores, pilha_extra)
        g.bytes(b'\x48\x85\xC0\x0F\x95\xC0\x0F\xB6\xC0')
        g.salto(fim)
        g.marcar(curta)
        carregar_numero(g, 0 if operador == 'e' else 1)
        g.marcar(fim)
    elif tipo == 'neg':
        if expr[1] == ('numero', 1 << 63):
            # Menor inteiro: o valor positivo 2^63 não cabe, mas sua negação sim.
            carregar_numero(g, -(1 << 63))
        else:
            expressao(g, expr[1], variaveis, windows, registradores, pilha_extra)
            g.bytes(b'\x48\xF7\xD8')  # neg rax
            g.salto('erro_overflow_aritmetico', 'jo')
    elif tipo == 'comparacao_texto':
        textos_dinamicos.comparar(g, expr[2][1], expr[3][1], expr[1] == '!=',
                                  variaveis, g.tipos_atual, windows, pilha_extra)
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
        g.bytes(b'\x48\xC7\x44\x24\x20\x00\x00\x00\x00')
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
        g.bytes(b'\x48\xC7\x44\x24\x20\x00\x00\x00\x00')
        g.relativo(b'\xFF\x15', 'WriteFile')
        g.bytes(b'\x48\x81\xC4' + struct.pack('<I', 0x80) + b'\x5F\xC3')
        registrar_quadro_empilhado(g, 'imprimir_inteiro', ['rdi'], 128)
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
    # Deslocamentos relativos ao RBP principal, nunca ao quadro auxiliar.
    # No Windows a palavra RBP-8 fica reservada por compatibilidade dos locais.
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
    g.bytes(b'\x56')  # preserva o ponteiro do buffer do chamador
    if windows:
        g.bytes(b'\x48\x83\xEC\x30')
    g.bytes(b'\x48\x8B\x85' + struct.pack('<i', cursor))
    g.bytes(b'\x48\x3B\x85' + struct.pack('<i', quantidade))
    g.salto('entrada_tem_byte', 'jb')
    if windows:
        # Entering helper: rsp%16=8; push rsi -> aligned, 0x30 keeps it.
        # shadow space [rsp+0..0x1f], overlapped NULL at +0x20,
        # bytes-read DWORD at +0x28.
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
        g.salto('entrada_falha')
        g.marcar('entrada_windows_eof')
        g.salto('entrada_eof')
        g.marcar('entrada_windows_ok')
        g.bytes(b'\x8B\x44\x24\x28') # eax=nread
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
    if windows:
        g.bytes(b'\x48\x83\xC4\x30')
    g.bytes(b'\x5E\xC3')  # pop rsi; ret
    if windows:
        registrar_quadro_empilhado(g, 'entrada_proximo_byte', ['rsi'], 48)

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
    if windows:
        registrar_quadro_empilhado(g, 'ler_inteiro', ['r13', 'r14', 'r15'], 64)


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
        g.bytes(b'\x48\xC7\x44\x24\x20\x00\x00\x00\x00')
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
    elif tipos[origem[1]] in (TIPO_TEXTO_DINAMICO, TIPO_TEXTO_EMPRESTADO):
        textos_dinamicos.vista(g, variaveis, tipos, origem[1], windows)
        g.bytes(b'\x48\x89\xD1')
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
    elif tipos[origem[1]] not in (TIPO_TEXTO_DINAMICO, TIPO_TEXTO_EMPRESTADO):
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
    if windows:
        registrar_quadro_empilhado(g, 'ler_buffer_texto',
                                  ['r13', 'r14', 'r15', 'rsi'], 72)


def reservar_pilha(g, bytes_reservados, windows=False):
    """Reserva quadro com sondagem de páginas, sem saltar a página de guarda.

    A sondagem é necessária para crescimento seguro da pilha Windows x64.
    Usamos também no Linux para evitar pular regiões não mapeadas.
    """
    if bytes_reservados <= 0:
        return
    if bytes_reservados < 4096:
        g.bytes(b'\x48\x81\xEC' + struct.pack('<I', bytes_reservados))
        return
    if windows:
        if bytes_reservados > 0xFFFFFFFF:
            raise ErroCompilacao('Quadro Windows nao representavel em 32 bits.')
        g.exige_sondagem_pilha = True
        g.bytes(b'\x48\xB8' + struct.pack('<Q', bytes_reservados))  # movabs rax, quadro
        g.chamada('rs_sondar_pilha')  # consulta páginas em passos de 4096 bytes
        g.bytes(b'\x48\x29\xC4')  # sub rsp,rax (unwind conhece tamanho)
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


def emitir_sondagem_pilha_windows(g):
    """Rotina folha nativa: preserva RAX/RSP, modifica só R10/R11 (voláteis)."""
    g.marcar('rs_sondar_pilha')
    g.bytes(b'\x4C\x8D\x54\x24\x08')  # lea r10,[rsp+8] = rsp do chamador
    g.bytes(b'\x49\x89\xC3')  # mov r11,rax
    g.marcar('rs_sondar_pilha_pagina')
    g.bytes(b'\x49\x81\xFB\x00\x10\x00\x00')  # cmp r11,4096
    g.salto('rs_sondar_pilha_restante', 'jb')
    g.bytes(b'\x49\x81\xEA\x00\x10\x00\x00')  # sub r10,4096
    g.bytes(b'\x41\xF6\x02\x00')  # test byte ptr [r10],0
    g.bytes(b'\x49\x81\xEB\x00\x10\x00\x00')  # sub r11,4096
    g.salto('rs_sondar_pilha_pagina')
    g.marcar('rs_sondar_pilha_restante')
    g.bytes(b'\x4D\x29\xDA')  # sub r10,r11
    g.bytes(b'\x41\xF6\x02\x00')  # test byte ptr [r10],0
    g.bytes(b'\xC3')  # ret


def preparar_saida_fatal_windows(g):
    """Prepara pilha e espaço de sombra antes de imprimir erro e encerrar.

    As saídas podem ser atingidas com operandos temporários empilhados
    ou de dentro de rotinas auxiliares com quadros diferentes.
    Alinhar RSP e reservar 48 bytes oferece 32 bytes de sombra,
    argumento extra em [RSP+32] e margem independente do chamador.
    Esta saída NÃO retorna ao programa.
    """
    g.bytes(b'\x48\x83\xE4\xF0')  # and rsp,-16
    g.bytes(b'\x48\x83\xEC\x30')  # sub rsp,48



def _emitir_erro_fatal(g, mensagens, rotulo, mensagem, windows):
    """Registra um erro e emite a sua saída nativa, sem retornar ao programa."""
    indice = len(mensagens)
    mensagens[indice] = mensagem
    g.marcar(rotulo)
    if windows:
        # Chamadas Win64 exigem pilha alinhada mesmo quando o erro ocorre
        # durante a avaliação de uma expressão com valores empilhados.
        preparar_saida_fatal_windows(g)
    escreve_literal(g, indice, mensagem, windows, 'saida' if windows else 'erro')
    if windows:
        g.bytes(b'\xB9\x01\x00\x00\x00')
        g.relativo(b'\xFF\x15', 'ExitProcess')
    else:
        g.bytes(b'\xB8\x3C\x00\x00\x00\xBF\x01\x00\x00\x00\x0F\x05')


def montar_codigo(programa, windows, emissor_alternativo=None, emissores_funcoes=None):
    g = Gerador()
    g.desenrolamentos = []  # contratos reais para .pdata/.xdata
    g.exige_sondagem_pilha = False
    g.funcoes = getattr(programa, 'funcoes', {})
    tem_conversao_utf8 = any(op[0] in ('codifique_utf8', 'decodifique_utf8')
        for corpo in [programa, *(f.programa for f in g.funcoes.values())]
        for op in percorrer_instrucoes(corpo.instrucoes))
    tem_consulta_arquivo = any(op[0] == 'consulte_arquivo'
        for corpo in [programa, *(f.programa for f in g.funcoes.values())]
        for op in percorrer_instrucoes(corpo.instrucoes))
    g.quadros_funcoes = {nome: tamanho_quadro(_total_slots(funcao.programa) + 1, windows)
                        for nome, funcao in g.funcoes.items()}
    g.registros = getattr(programa, 'registros', {})
    g.campos_atual = getattr(programa, 'campos_registro', {})
    funcao_atual = None
    variaveis = programa.variaveis
    mensagens = {}
    tem_leitura = any(op[0] in ('leia_int', 'leia_indice', 'leia_indice_dinamico', 'leia_texto', 'leia_texto_dinamico') for op in percorrer_instrucoes(programa.instrucoes))
    tem_arquivos = (any(op[0] in ('grave_arquivo', 'carregue_arquivo', 'carregue_texto_dinamico', 'carregue_bytes_dinamicos')
                        for op in percorrer_instrucoes(programa.instrucoes))
                    or any(op[0] in ('grave_arquivo', 'carregue_arquivo', 'carregue_texto_dinamico', 'carregue_bytes_dinamicos')
                        for f in g.funcoes.values() for op in percorrer_instrucoes(f.programa.instrucoes)))
    tem_arquivos_posicionais = (any(op[0] in ('grave_trecho', 'carregue_trecho')
                        for op in percorrer_instrucoes(programa.instrucoes))
                    or any(op[0] in ('grave_trecho', 'carregue_trecho')
                        for f in g.funcoes.values() for op in percorrer_instrucoes(f.programa.instrucoes)))
    tipos = getattr(programa, 'tipos', {})
    tipos_do_programa = tuple(tipos.values()) + tuple(
        t for f in g.funcoes.values() for t in f.programa.tipos.values())
    colecoes_proprietarias.preparar(g, tipos_do_programa)
    pendentes = [programa.instrucoes] + [f.programa.instrucoes for f in g.funcoes.values()]
    consultas_utf8 = False
    while pendentes:
        no = pendentes.pop()
        if not isinstance(no, (tuple, list)):
            continue
        if no and no[0] in ('caracteres_texto', 'byte_texto', 'comparacao_texto'):
            consultas_utf8 = True
        pendentes.extend(f for f in no if isinstance(f, (tuple, list)))
    tem_texto_novo = consultas_utf8 or any(t in (TIPO_TEXTO_DINAMICO, TIPO_TEXTO_EMPRESTADO) for t in tipos_do_programa)
    tem_sequencias_dinamicas = tem_texto_novo or any(t in (TIPO_BYTES_DINAMICOS, TIPO_BYTES_EMPRESTADOS) for t in tipos_do_programa)
    tem_dinamicas = tem_sequencias_dinamicas or any(eh_proprietario(t) or eh_emprestimo(t) for t in tipos_do_programa)
    tem_listas_dinamicas = any(listas_dinamicas.eh_lista_dinamica(t) for t in tipos_do_programa)
    tem_listas = tem_listas_dinamicas or any(
        isinstance(t, tuple) and t[0] in ('lista', 'lista_emprestada') for t in tipos_do_programa)
    tem_textos = any(eh_texto(t) for t in tipos_do_programa)
    tem_bytes = any(eh_bytes(t) for t in tipos_do_programa)
    tem_publicacao = any(op[0] == 'publique_arquivo'
                        for op in percorrer_instrucoes(programa.instrucoes)) or any(
        op[0] == 'publique_arquivo'
        for f in g.funcoes.values() for op in percorrer_instrucoes(f.programa.instrucoes))
    tem_recursos = (any(t == 'arquivo' for t in tipos.values()) or
                    any(t == 'arquivo' for f in g.funcoes.values()
                        for t in f.programa.tipos.values()))
    tem_encerre = any(op[0] == 'encerre' for op in percorrer_instrucoes(programa.instrucoes)) or any(
        op[0] == 'encerre' for f in g.funcoes.values()
        for op in percorrer_instrucoes(f.programa.instrucoes))
    g.tipos_atual = tipos
    tem_leitura_texto = any(op[0] in ('leia_texto', 'leia_texto_dinamico') for op in percorrer_instrucoes(programa.instrucoes))
    tem_leitura_dinamica = any(op[0] == 'leia_texto_dinamico' for op in percorrer_instrucoes(programa.instrucoes))
    slots = _total_slots(programa)
    memoria_cache = ((256 if windows else TAMANHO_CACHE_ENTRADA) + 16) if tem_leitura else 0
    frame = tamanho_quadro(slots, windows, memoria_cache)
    g.custo_pilha_principal = custo_quadro(frame)
    if g.custo_pilha_principal > LIMITE_PILHA_SEGURA:
        raise ErroCompilacao('Quadro principal excede o limite seguro de pilha de 768 KiB.')
    if windows:
        g.marcar('rs_inicio_principal')
        g.bytes(SALVAMENTOS_WINDOWS)
        g.bytes(b'\x53\x55\x48\x89\xE5')  # push rbx; push rbp; mov rbp,rsp
        reservar_pilha(g, frame, windows)
        g.marcar('rs_fim_prologo_principal')
        g.desenrolamentos.append({
            'inicio': 'rs_inicio_principal',
            'fim': 'rs_fim_principal',
            'fim_prologo': 'rs_fim_prologo_principal',
            'quadro': frame,
            'prologo': 'usuario_preservado',
        })
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
        g.bytes(b'\x55\x48\x89\xE5')
        if frame:
            reservar_pilha(g, frame, windows)

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
            elif op[0] == 'modifique_texto_dinamico':
                textos_dinamicos.modificar(g, op[1], op[2], op[3], variaveis, tipos, windows, mensagens)
            elif op[0] == 'modifique_bytes':
                bytes_seguros.modificar(g, op[1], op[2], op[3][1], variaveis, tipos, windows, deslocamento_variavel)
            elif op[0] in ('limpe_texto_dinamico', 'limpe_bytes_dinamicos'):
                textos_dinamicos.limpar(g, op[1], variaveis, windows)
            elif op[0] == 'libere_valor_dinamico':
                valores_dinamicos.liberar(g, variaveis, op[1], windows, explicito=True)
            elif op[0] in ('limpe_texto', 'limpe_bytes'):
                comprimento = deslocamento_variavel(variaveis, op[1], windows)
                g.bytes(b'\x31\xC0\x48\x89\x85' + struct.pack('<i', comprimento))
            elif op[0] in ('adicione_byte', 'adicione_byte_dinamico'):
                bytes_seguros.acrescentar(g, op[1], op[2], variaveis, tipos,
                    windows, expressao, deslocamento_variavel)
            elif op[0] in ('atribua_byte', 'atribua_byte_dinamico'):
                bytes_seguros.substituir(g, op[1], op[2], op[3], variaveis, tipos,
                    windows, expressao, deslocamento_variavel)
            elif op[0] == 'imprima_texto':
                if tipos[op[1]] in (TIPO_TEXTO_DINAMICO, TIPO_TEXTO_EMPRESTADO):
                    textos_dinamicos.imprimir(g, op[1], variaveis, tipos, windows)
                else:
                    _imprimir_buffer(g, op[1], variaveis, tipos, windows)
                msg_indice = len(mensagens)
                mensagens[msg_indice] = '\n'
                escreve_literal(g, msg_indice, '\n', windows)
            elif op[0] in ('grave_arquivo', 'carregue_arquivo', 'carregue_texto_dinamico', 'carregue_bytes_dinamicos'):
                arquivos.emitir_comando(g, op, variaveis, tipos, windows, mensagens,
                                        _endereco_buffer, deslocamento_variavel)
            elif op[0] in ('grave_trecho', 'carregue_trecho'):
                arquivos_posicionais.emitir_comando(g, op, variaveis, tipos, windows,
                    mensagens, _endereco_buffer, deslocamento_variavel, expressao)
            elif op[0] == 'crie_recurso':
                offset = deslocamento_variavel(variaveis, op[1], windows)
                g.bytes(b'\x48\xC7\x85' + struct.pack('<i',offset) + b'\xFF\xFF\xFF\xFF')
            elif op[0] in ('abra_recurso','feche_recurso','sincronize_recurso','bloqueie_recurso','grave_em','carregue_de'):
                arquivos_abertos.emitir_comando(g, op, variaveis, tipos, windows,
                    mensagens, _endereco_buffer, expressao)
            elif op[0] == 'consulte_arquivo':
                consulta_arquivo.emitir_comando(g, op, variaveis, windows, mensagens, deslocamento_variavel)
            elif op[0] == 'publique_arquivo':
                publicacao_atomica.emitir_comando(
                    g, op, variaveis, windows, mensagens, deslocamento_variavel)
            elif op[0] in ('codifique_utf8', 'decodifique_utf8'):
                textos_dinamicos.converter_utf8(g, op, variaveis, tipos, windows)
            elif op[0] == 'leia_texto':
                nome = op[1]
                dados, comprimento, capacidade = _endereco_buffer(variaveis, nome, tipos, windows)
                g.bytes(b'\x48\x8D\xB5' + struct.pack('<i', dados)) # RSI=buffer
                carregar_numero(g, capacidade)
                g.bytes(b'\x48\x89\xC2') # RDX=cap
                g.chamada('ler_buffer_texto')
                g.bytes(b'\x48\x89\x85' + struct.pack('<i', comprimento))
            elif op[0] == 'leia_texto_dinamico':
                valores_dinamicos.endereco_descritor(g, variaveis, op[1], windows)
                g.chamada('rs_texto_ler_linha')
            elif op[0] == 'reserve_capacidade_dinamica':
                # O valor e avaliado uma unica vez antes de obter o endereco
                # do descritor; a propria rotina verifica vida, limites e OOM.
                nome, minimo = op[1:]
                expressao(g, minimo, variaveis, windows)
                g.bytes(b'\x48\x89\xC6')  # RSI = capacidade minima
                valores_dinamicos.endereco_descritor(g, variaveis, nome, windows)
                g.bytes(b'\xBA' + struct.pack('<I',
                    passo_armazenamento(tipos[nome], g.registros)))  # EDX = bytes por unidade
                g.chamada('rs_valor_reservar')
            elif op[0] in ('crie_lista_dinamica', 'crie_valor_dinamico'):
                valores_dinamicos.criar_vazio(g, variaveis, op[1], windows)
            elif op[0] == 'receba_valor_dinamico':
                destino, origem = op[1:]
                if not eh_proprietario(tipos.get(destino)):
                    raise ErroCompilacao('Recebimento dinamico exige destino proprietario.')
                if origem[0] == 'mova_valor_dinamico':
                    if tipos.get(origem[1]) != tipos[destino] or origem[1] == destino:
                        raise ErroCompilacao('Transferencia dinamica exige donos distintos do mesmo tipo.')
                    valores_dinamicos.mover(g, variaveis, destino, origem[1], windows)
                elif origem[0] == 'chamada':
                    if g.funcoes[origem[1]].retorno != tipos[destino]:
                        raise ErroCompilacao('Retorno dinamico possui tipo incompatível com o destino.')
                    expressao(g, origem, variaveis, windows, destino_composto=destino)
                elif origem[0] == 'retire_registro_lista':
                    expressao(g, origem, variaveis, windows, destino_composto=destino)
                else:
                    raise ErroCompilacao('Recebimento dinamico exige transferencia ou chamada proprietaria.')
            elif op[0] == 'receba_registro_proprietario':
                destino, origem = op[1:]
                if origem[0] == 'mova_registro_proprietario':
                    _transferir_registro_proprietario(g, variaveis, tipos, destino, origem[1], windows)
                elif origem[0] == 'retire_registro_lista':
                    expressao(g, origem, variaveis, windows, destino_composto=destino)
                elif origem[0] == 'chamada':
                    if g.funcoes[origem[1]].retorno != tipos[destino][1]:
                        raise ErroCompilacao('Retorno de registro exige o mesmo tipo.')
                    expressao(g, origem, variaveis, windows, destino_composto=destino)
                else:
                    raise ErroCompilacao('Recebimento de registro proprietario exige mova ou chamada.')
            elif op[0] == 'mova_registro_proprietario':
                _transferir_registro_proprietario(
                    g, variaveis, tipos, op[1], op[2], windows)
            elif op[0] == 'mova_lista_dinamica':
                listas_dinamicas.mover(g, variaveis, op[1], op[2], windows,
                                       listas_dinamicas.largura_elemento(g, tipos[op[1]]))
            elif op[0] == 'mova_valor_dinamico_comando':
                valores_dinamicos.mover(g, variaveis, op[1], op[2], windows)
            elif op[0] == 'libere_escopo_listas':
                for nome in op[1]:
                    if tipos[nome] == 'arquivo':
                        arquivos_abertos.emitir_auto_fechar(g, variaveis, nome, windows)
                    else:
                        valores_dinamicos.liberar(g, variaveis, nome, windows)
            elif op[0] == 'adicione_lista_dinamica':
                listas_dinamicas.acrescentar(g, variaveis, op[1], op[2], windows, expressao,
                                            listas_dinamicas.largura_elemento(g, tipos[op[1]]))
            elif op[0] in ('adicione_colecao_proprietaria', 'substitua_colecao_proprietaria'):
                nome, valor = op[1], op[-1]
                substituicao = op[0] == 'substitua_colecao_proprietaria'
                if substituicao:
                    listas_dinamicas.indice(g, variaveis, nome, op[2], windows, expressao)
                    g.bytes(b'\x50')
                if valor[0] == 'temporario_composto':
                    origem = valor[1]
                    expressao(g, valor[2], variaveis, windows, pilha_extra=int(substituicao), destino_composto=origem)
                elif valor[0] in ('mova_registro_proprietario', 'mova_valor_dinamico'):
                    origem = valor[1]
                else:
                    raise ErroCompilacao('Colecao proprietaria exige registro transferido ou novo.')
                if eh_proprietario(tipos[origem]):
                    valores_dinamicos.verificar_vivo(g, variaveis, origem, windows)
                else:
                    _validar_registro_vivo(g, variaveis, origem, windows)
                if substituicao:
                    g.bytes(b'\x5E')  # recupera índice, sem guardar ponteiro do heap entre chamadas
                    valores_dinamicos.endereco_descritor(g, variaveis, nome, windows)
                    g.bytes(b'\x48\x8D\x95' + struct.pack('<i', deslocamento_variavel(variaveis, origem, windows)))
                    g.chamada(colecoes_proprietarias.rotulo(tipos[nome], 'substituir'))
                else:
                    listas_dinamicas.acrescentar(g, variaveis, nome, ('var', origem), windows, expressao,
                                                listas_dinamicas.largura_elemento(g, tipos[nome]))
                if eh_proprietario(tipos[origem]):
                    valores_dinamicos.inativar(g, variaveis, origem, windows)
                else:
                    _inativar_registro(g, variaveis, origem, windows)
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
                if not contrato_valor(tipos[destino], g.registros).pode_copiar:
                    raise ErroCompilacao('Copia composta nao pode duplicar um proprietario dinamico.')
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
                tipo_retorno = g.funcoes[funcao_atual].retorno
                if eh_proprietario(tipo_retorno):
                    if op[1][0] == 'mova_valor_dinamico':
                        if tipos.get(op[1][1]) != tipo_retorno:
                            raise ErroCompilacao('Retorno proprietario exige transferencia do mesmo tipo.')
                        valores_dinamicos.transferir_para_retorno(
                            g, variaveis, op[1][1], windows)
                    elif op[1][0] == 'retire_registro_lista':
                        expressao(g, op[1], variaveis, windows, destino_composto='__rs_retorno_externo')
                    elif op[1][0] == 'chamada':
                        if g.funcoes[op[1][1]].retorno != tipo_retorno:
                            raise ErroCompilacao('Retorno proprietario exige chamada do mesmo tipo.')
                        expressao(g, op[1], variaveis, windows,
                                 destino_composto='__rs_retorno_externo')
                    else:
                        raise ErroCompilacao('Retorno proprietario exige mova(origem) ou chamada proprietaria.')
                elif eh_registro_proprietario(tipo_retorno, g.registros):
                    if op[1][0] == 'mova_registro_proprietario':
                        origem = op[1][1]
                        if tipos[origem][1] != tipo_retorno:
                            raise ErroCompilacao('Retorno de registro exige o mesmo tipo.')
                        _validar_registro_vivo(g, variaveis, origem, windows)
                        _copiar_para_retorno(g, deslocamento_variavel(variaveis, origem, windows),
                                           _palavras_tipo(tipo_retorno, g.registros), windows)
                        _inativar_registro(g, variaveis, origem, windows)
                    elif op[1][0] == 'retire_registro_lista':
                        expressao(g, op[1], variaveis, windows, destino_composto='__rs_retorno_externo')
                    elif op[1][0] == 'chamada':
                        if g.funcoes[op[1][1]].retorno != tipo_retorno:
                            raise ErroCompilacao('Retorno de registro exige chamada do mesmo tipo.')
                        expressao(g, op[1], variaveis, windows, destino_composto='__rs_retorno_externo')
                    else:
                        raise ErroCompilacao('Retorno de registro proprietario exige mova ou chamada.')
                elif _composto(tipo_retorno, g.registros):
                    if op[1][0] == 'chamada':
                        expressao(g, op[1], variaveis, windows,
                                 destino_composto='__rs_retorno_externo')
                    elif op[1][0] == 'var':
                        _copiar_para_retorno(g,
                            deslocamento_variavel(variaveis, op[1][1], windows),
                            _palavras_tipo(g.funcoes[funcao_atual].retorno, g.registros), windows)
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
        valores_dinamicos.liberar_todos(g, variaveis, tipos, windows)
    if tem_recursos:
        for nome, tipo in reversed(tuple(tipos.items())):
            if tipo == 'arquivo':
                arquivos_abertos.emitir_auto_fechar(g, variaveis, nome, windows)

    if windows:
        g.bytes(b'\x31\xC9')
        g.relativo(b'\xFF\x15', 'ExitProcess')
        g.marcar('rs_fim_principal')
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
        n_frame = g.quadros_funcoes[nome]
        if windows:
            g.bytes(SALVAMENTOS_WINDOWS)
            g.bytes(b'\x53\x55\x48\x89\xE5')
        else:
            g.bytes(b'\x55\x48\x89\xE5')
        # A profundidade é limitada por bytes acumulados de quadros; o
        # controle ocorre ANTES de reservar a pilha da chamada atual.
        g.bytes(b'\x48\x8B\x45' + bytes((72 if windows else 16,)))
        custo = custo_quadro(n_frame)
        if custo > 0x7FFFFFFF:
            g.salto('erro_recursao_limite')
        else:
            g.bytes(b'\x48\x05' + struct.pack('<I', custo))
            g.salto('erro_recursao_limite', 'jo')
            g.bytes(b'\x48\x3D' + struct.pack('<I', LIMITE_PILHA_SEGURA))
            g.salto('erro_recursao_limite', 'ja')
        reservar_pilha(g, n_frame, windows)
        if windows:
            rotulo_prologo = f'rs_fim_prologo_funcao_{nome}'
            g.marcar(rotulo_prologo)
            g.desenrolamentos.append({
                'inicio': f'funcao_{nome}',
                'fim': f'rs_fim_funcao_{nome}',
                'fim_prologo': rotulo_prologo,
                'quadro': n_frame,
                'prologo': 'usuario_preservado',
            })
        # A sondagem Windows carrega o tamanho da reserva em RAX. Recuperar
        # o orçamento após ela impede que quadros grandes reiniciem a conta.
        # Os inicializadores de donos também alteram RAX: salvar antes deles.
        if windows and n_frame >= 4096 and custo <= 0x7FFFFFFF:
            g.bytes(b'\x48\x8B\x45\x48\x48\x05' + struct.pack('<I', custo))
        g.bytes(b'\x48\x89\x85' + struct.pack('<i', deslocamento_variavel(variaveis, '__rs_uso_pilha', windows)))
        if tem_dinamicas:
            listas_dinamicas.inicializar_inativas(g, variaveis, tipos, windows)
        if tem_recursos:
            for recurso_nome, tipo in tipos.items():
                if tipo == 'arquivo':
                    offset = deslocamento_variavel(variaveis, recurso_nome, windows)
                    g.bytes(b'\x48\xC7\x85' + struct.pack('<i',offset) + b'\xFF\xFF\xFF\xFF')
        total_palavras = sum(_palavras_tipo(t, g.registros) for _, t in funcao.parametros)
        base_argumentos = 32 if _composto(funcao.retorno, g.registros) else 24
        if windows:
            base_argumentos += 56
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
        if emissores_funcoes is not None and nome in emissores_funcoes:
            emissores_funcoes[nome](g, mensagens, windows, variaveis)
        else:
            emitir_bloco(funcao.programa.instrucoes)
        g.marcar(f'funcao_fim_{nome}')
        if tem_dinamicas:
            valores_dinamicos.liberar_todos(g, variaveis, tipos, windows,
                                           preservar_retorno=True)
        if tem_recursos and any(t == 'arquivo' for t in tipos.values()):
            retorno_guardado = deslocamento_variavel(variaveis, '__rs_uso_pilha', windows)
            g.bytes(b'\x48\x89\x85' + struct.pack('<i',retorno_guardado))
            for recurso_nome, tipo in reversed(tuple(tipos.items())):
                if tipo == 'arquivo':
                    arquivos_abertos.emitir_auto_fechar(g, variaveis, recurso_nome, windows)
            g.bytes(b'\x48\x8B\x85' + struct.pack('<i',retorno_guardado))
        if windows:
            g.bytes(b'\x48\x8D\x65\x00\x5D\x5B' + RESTAURACOES_WINDOWS + b'\xC3')
            g.marcar(f'rs_fim_funcao_{nome}')
        else:
            g.bytes(b'\x48\x89\xEC\x5D\xC3')
    funcao_atual = None
    variaveis = programa.variaveis
    g.campos_atual = getattr(programa, 'campos_registro', {})
    tipos = getattr(programa, 'tipos', {})
    g.tipos_atual = tipos
    if windows and g.exige_sondagem_pilha:
        emitir_sondagem_pilha_windows(g)
    if tem_dinamicas:
        if tem_listas_dinamicas:
            listas_dinamicas.emitir_rotinas(g, windows)
        else:
            memoria_dinamica.emitir_rotinas(g, windows)
        colecoes_proprietarias.emitir_rotinas(g, windows)
    if tem_sequencias_dinamicas:
        sequencias_dinamicas.emitir_rotinas(g, windows)
    if tem_texto_novo:
        textos_dinamicos.emitir_rotinas(g, windows, tem_leitura_dinamica)
    if tem_consulta_arquivo:
        consulta_arquivo.emitir_rotina(g, windows)
    if tem_conversao_utf8:
        textos_dinamicos.emitir_conversao_utf8(g, windows)
    if windows and (tem_arquivos or tem_recursos or tem_arquivos_posicionais):
        politica_caminhos.emitir_verificacao_windows(g)
    if tem_arquivos:
        arquivos.emitir_rotinas(g, windows, tem_sequencias_dinamicas, tem_texto_novo)
    if tem_recursos:
        arquivos_abertos.emitir_rotinas(g, windows)
    if tem_publicacao:
        publicacao_atomica.emitir_rotina(g, windows, mensagens)
    if tem_arquivos_posicionais:
        arquivos_posicionais.emitir_rotinas(g, windows)
    imprime_inteiro(g, windows)
    if tem_leitura:
        emitir_cache_entrada(g, windows, slots)
    if tem_leitura and any(op[0] in ('leia_int', 'leia_indice', 'leia_indice_dinamico') for op in percorrer_instrucoes(programa.instrucoes)):
        ler_inteiro(g, windows)
    if any(op[0] == 'leia_texto' for op in percorrer_instrucoes(programa.instrucoes)):
        ler_buffer_texto(g, windows)

    # A ordem dos rótulos é parte do contrato de emissão: preserva
    # os índices de mensagens e a disposição do código nativo.
    for rotulo, mensagem in (
        ('erro_divisao_zero', 'Erro: divisão por zero.\n'),
        ('erro_estouro', 'Erro: divisão inteira fora do limite.\n'),
        ('erro_overflow_aritmetico', 'Erro: estouro aritmético em inteiro de 64 bits.\n'),
    ):
        _emitir_erro_fatal(g, mensagens, rotulo, mensagem, windows)

    if getattr(programa, 'funcoes', {}):
        _emitir_erro_fatal(
            g, mensagens, 'erro_recursao_limite',
            'Erro: limite seguro de pilha em chamada de função.\n', windows)

    if tem_listas:
        _emitir_erro_fatal(
            g, mensagens, 'erro_indice_lista',
            'Erro: índice fora dos limites da lista.\n', windows)

    if tem_leitura and any(
        op[0] in ('leia_int', 'leia_indice', 'leia_indice_dinamico')
        for op in percorrer_instrucoes(programa.instrucoes)
    ):
        for rotulo, mensagem in (
            ('erro_entrada_invalida', 'Erro: entrada invalida; digite um numero inteiro.\n'),
            ('erro_entrada_limite', 'Erro: numero fora do limite de 64 bits.\n'),
        ):
            _emitir_erro_fatal(g, mensagens, rotulo, mensagem, windows)

    if tem_textos:
        for rotulo, mensagem in (
            ('erro_texto_capacidade', 'Erro: texto excede a capacidade do buffer.\n'),
            ('erro_texto_utf8', 'Erro: sequencia UTF-8 invalida.\n'),
            ('erro_texto_entrada', 'Erro: falha ao ler texto.\n'),
            ('erro_texto_saida', 'Erro: falha ao escrever texto.\n'),
            ('erro_indice_texto', 'Erro: indice de byte fora dos limites do texto.\n'),
        ):
            _emitir_erro_fatal(g, mensagens, rotulo, mensagem, windows)

    if tem_dinamicas:
        for rotulo, mensagem in (
            ('erro_lista_liberada', 'Erro: lista dinamica usada depois da liberacao.\n'),
            ('erro_lista_memoria', 'Erro: nao foi possivel reservar ou liberar memoria.\n'),
            ('erro_valor_inativo', 'Erro: valor dinamico usado depois da movimentacao ou liberacao.\n'),
        ):
            _emitir_erro_fatal(g, mensagens, rotulo, mensagem, windows)

    if tem_bytes:
        for rotulo, mensagem in (
            ('erro_indice_bytes', 'Erro: indice fora dos bytes validos.\n'),
            ('erro_valor_byte', 'Erro: byte deve estar entre 0 e 255.\n'),
            ('erro_bytes_capacidade', 'Erro: capacidade do buffer binario excedida.\n'),
        ):
            _emitir_erro_fatal(g, mensagens, rotulo, mensagem, windows)

    if tem_encerre:
        _emitir_erro_fatal(
            g, mensagens, 'erro_codigo_saida',
            'Erro: codigo de saida deve estar entre 0 e 255.\n', windows)

    if tem_recursos:
        _emitir_erro_fatal(
            g, mensagens, 'erro_fechamento_implicito',
            'Erro: nao foi possivel fechar automaticamente um arquivo.\n', windows)

    if tem_arquivos:
        for rotulo, mensagem in (
            ('erro_arquivo_abrir', 'Erro: nao foi possivel abrir o arquivo.\n'),
            ('erro_arquivo_leitura', 'Erro: falha na leitura do arquivo.\n'),
            ('erro_arquivo_gravacao', 'Erro: falha na gravacao do arquivo.\n'),
            ('erro_arquivo_capacidade', 'Erro: arquivo excede a capacidade do texto.\n'),
            ('erro_arquivo_fechar', 'Erro: nao foi possivel fechar o arquivo.\n'),
        ):
            _emitir_erro_fatal(g, mensagens, rotulo, mensagem, windows)
    return g, mensagens
