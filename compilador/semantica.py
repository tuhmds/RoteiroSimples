"""Escopos léxicos e verificação estática dos símbolos do RoteiroSimples."""
from .erros import ErroCompilacao
from .expressoes import Expressao
from .lexico import Token
from .ast import NoExpressao
from .tipos import MAX_VARIAVEIS, tipo_expressao
from .disposicao_tipos import palavras_tipo


class ContextoSemantico:
    def __init__(self, importa_matematica=False, funcoes=None, registros=None):
        self.importa_matematica = importa_matematica
        self.funcoes = funcoes or {}
        self.registros = registros or {}
        self.campos_registro = {}
        self.variaveis = {}  # nomes internos -> deslocamentos de pilha
        self.tipos = {}      # nomes internos -> tipos
        self.escopos = [{}]
        self.total_slots = 0
        self.contador = 0
        self.usou_locais = False

    def entrar_escopo(self):
        self.escopos.append({})

    def sair_escopo(self):
        if len(self.escopos) == 1:
            raise RuntimeError('Não é permitido encerrar o escopo principal.')
        self.escopos.pop()

    def declarado_neste_escopo(self, nome):
        return nome in self.escopos[-1]

    def resolver(self, nome):
        for escopo in reversed(self.escopos):
            if nome in escopo:
                return escopo[nome]
        return nome  # Produz erro normal de variável não declarada.

    def resolver_caminho(self, partes, linha):
        """Resolve um caminho como pedido.entrega.endereco, com escopo léxico."""
        if not partes or len(partes) % 2 == 0:
            raise ErroCompilacao(f'Linha {linha}: caminho de campo inválido.')
        interno = self.resolver(str(partes[0]))
        for indice in range(1, len(partes), 2):
            if partes[indice] != '.':
                raise ErroCompilacao(f'Linha {linha}: esperava ponto antes do campo.')
            campo = str(partes[indice + 1])
            if campo not in self.campos_registro.get(interno, {}):
                raise ErroCompilacao(f'Linha {linha}: campo {campo!r} não pertence ao registro.')
            interno = self.campos_registro[interno][campo]
        return interno

    def _espacos_tipo(self, tipo):
        return palavras_tipo(tipo, self.registros)

    def _criar_campos(self, interno, tipo, inicio):
        """Mapeia recursivamente os campos preservando o bloco contíguo."""
        campos = {}
        deslocamento = 0
        for campo, tipo_campo in tipo[2]:
            nome = f'__rs_campo_{self.contador}_{inicio}_{deslocamento}_{campo}'
            tipo_real = (('registro', tipo_campo, self.registros[tipo_campo])
                         if isinstance(tipo_campo, str) and tipo_campo in self.registros
                         else tipo_campo)
            self.variaveis[nome] = inicio + deslocamento
            self.tipos[nome] = tipo_real
            campos[campo] = nome
            if isinstance(tipo_real, tuple) and tipo_real[0] == 'registro':
                self._criar_campos(nome, tipo_real, inicio + deslocamento)
            deslocamento += self._espacos_tipo(tipo_real)
        self.campos_registro[interno] = campos

    def _renomear_tokens(self, partes):
        saida = []
        i = 0
        while i < len(partes):
            token = partes[i]
            if i + 2 < len(partes) and partes[i+1] == '.':
                fim = i + 3
                while fim + 1 < len(partes) and partes[fim] == '.':
                    fim += 2
                interno = self.resolver_caminho(partes[i:fim], token.origem.linha)
                saida.append(Token(interno, token.origem.linha, token.origem.coluna))
                i = fim
                continue
            interno = self.resolver(str(token))
            saida.append(Token(interno, token.origem.linha, token.origem.coluna)
                         if hasattr(token, 'origem') and str(token) != interno else token)
            i += 1
        return saida

    def _preparar_argumentos_compostos(self, arvore):
        """Reserva destino interno para chamada composta passada diretamente como argumento."""
        tag = arvore[0]
        if tag == 'chamada':
            nome, argumentos = arvore[1], arvore[2]
            parametros, _ = self.funcoes[nome]
            novos = []
            for argumento, tipo_parametro in zip(argumentos, parametros):
                argumento = self._preparar_argumentos_compostos(argumento)
                if (argumento[0] == 'chamada' and
                        ((isinstance(tipo_parametro, str) and tipo_parametro in self.registros) or
                         isinstance(tipo_parametro, tuple))):
                    nome_temp = f'__rs_temporario_composto_{self.contador + 1}'
                    self.contador += 1
                    tamanho = self._espacos_tipo(tipo_parametro)
                    if (self.total_slots + tamanho) * 8 >= 0x7FFF0000:
                        raise ErroCompilacao('Quadro de execução excede endereço de 32 bits.')
                    tipo_real = (('registro', tipo_parametro, self.registros[tipo_parametro])
                                 if isinstance(tipo_parametro, str) and tipo_parametro in self.registros
                                 else tipo_parametro)
                    self.variaveis[nome_temp] = self.total_slots
                    self.tipos[nome_temp] = tipo_real
                    self.total_slots += tamanho
                    novos.append(NoExpressao(('temporario_composto', nome_temp, argumento),
                                              getattr(argumento, 'origem', None)))
                else:
                    novos.append(argumento)
            return NoExpressao(('chamada', nome, tuple(novos)), getattr(arvore, 'origem', None))
        if tag in ('bin', 'comparacao'):
            return NoExpressao((tag, arvore[1],
                                self._preparar_argumentos_compostos(arvore[2]),
                                self._preparar_argumentos_compostos(arvore[3])),
                               getattr(arvore, 'origem', None))
        if tag == 'neg':
            return NoExpressao(('neg', self._preparar_argumentos_compostos(arvore[1])),
                               getattr(arvore, 'origem', None))
        if tag == 'indice_bytes':
            return NoExpressao(('indice_bytes', arvore[1],
                                self._preparar_argumentos_compostos(arvore[2])),
                               getattr(arvore, 'origem', None))
        if tag == 'indice':
            return NoExpressao(('indice', arvore[1],
                                self._preparar_argumentos_compostos(arvore[2]), arvore[3]),
                               getattr(arvore, 'origem', None))
        return arvore

    def expressao_tipada(self, partes, linha, exigir=None):
        coluna = partes[0].origem.coluna if partes and hasattr(partes[0], 'origem') else 1
        try:
            analisador = Expressao(self._renomear_tokens(partes), linha, self.variaveis, self.importa_matematica)
            analisador.tipos = self.tipos
            analisador.funcoes = self.funcoes
            arvore = analisador.analisar()
            tipo = tipo_expressao(arvore, self.tipos, linha, self.funcoes)
            arvore = self._preparar_argumentos_compostos(arvore)
            if exigir is not None and tipo != exigir:
                raise ErroCompilacao(f'Linha {linha}: tipo incompatível: esperava {exigir}, recebeu {tipo}.')
        except ErroCompilacao as erro:
            mensagem = str(erro)
            prefixo = f'Linha {linha}:'
            if mensagem.startswith(prefixo):
                mensagem = f'Linha {linha}, coluna {coluna}:' + mensagem[len(prefixo):]
            raise ErroCompilacao(mensagem) from erro
        return arvore, tipo

    def registrar(self, nome, tipo, linha):
        if self.declarado_neste_escopo(nome):
            raise ErroCompilacao(f'Linha {linha}: variável {nome!r} duplicada no mesmo escopo.')
        if nome.startswith('__rs_'):
            raise ErroCompilacao(f'Linha {linha}: o prefixo __rs_ é reservado ao compilador.')
        tamanho = self._espacos_tipo(tipo)
        if (self.total_slots + tamanho)*8 >= 0x7FFF0000:
            raise ErroCompilacao(f'Linha {linha}: quadro local excede endereçamento de 32 bits do gerador x86-64.')
        self.contador += 1
        interno = nome if len(self.escopos) == 1 else f'__escopo_{self.contador}_{nome}'
        self.escopos[-1][nome] = interno
        self.variaveis[interno] = self.total_slots
        self.tipos[interno] = tipo
        self.total_slots += tamanho
        if isinstance(tipo, tuple) and tipo[0] == 'registro':
            self._criar_campos(interno, tipo, self.variaveis[interno])
        if len(self.escopos) > 1:
            self.usou_locais = True
        return interno
