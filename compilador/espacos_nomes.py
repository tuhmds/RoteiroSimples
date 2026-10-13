"""Resolução de espaços de nomes e visibilidade da RS 0.28."""
from dataclasses import dataclass
import json
from pathlib import Path
import re

from .erros import ErroCompilacao
from .lexico import tokens
from .modulos import FontesReunidas, OrigemLinha
from .importacoes_padrao import resolver_importacao

IDENTIFICADOR = re.compile(r'[A-Za-z_][A-Za-z_0-9]*\Z')
PREFIXO_INTERNO = 'SimboloInternoRS_'
RESERVADOS = frozenset({'inicio', 'funcao', 'tipo', 'importe', 'publico', 'privado',
                        'como', 'seja', 'retorne', 'inteiro', 'logico', 'lista',
                        'texto', 'bytes', 'adicione_byte', 'encerre', 'arquivo', 'abra_arquivo',
                        'feche_arquivo', 'sincronize_arquivo', 'bloqueie_arquivo',
                        'grave_em', 'carregue_de', 'publique_arquivo', 'escreva', 'leia', 'para', 'se', 'senao', 'enquanto'})


@dataclass(frozen=True)
class Importacao:
    destino: Path
    apelido: str | None
    origem: OrigemLinha


@dataclass(frozen=True)
class Definicao:
    categoria: str
    nome: str
    visibilidade: str
    bloco: tuple[OrigemLinha, ...]


@dataclass
class Modulo:
    caminho: Path
    importacoes: list[Importacao]
    definicoes: list[Definicao]
    bloco_principal: tuple[OrigemLinha, ...] | None
    matematica: OrigemLinha | None
    nomes: dict


def _partes(origem):
    itens = tokens(origem.texto, origem.numero)
    if itens and itens[-1] == ';':
        itens = itens[:-1]
    return [str(token) for token in itens]


def carregar_com_espacos(principal):
    """Reúne os módulos e substitui qualificadores por símbolos nativos exclusivos."""
    principal = Path(principal).resolve()
    raiz = principal.parent
    visitando = []
    encontrados = {}
    ordem = []

    def erro(origem, mensagem):
        raise ErroCompilacao(f'{origem.caminho}:{origem.numero}: {mensagem}')

    def ler_modulo(caminho):
        if caminho in visitando:
            ciclo = ' -> '.join(p.name for p in visitando + [caminho])
            raise ErroCompilacao(f'Importação circular detectada: {ciclo}.')
        if caminho in encontrados:
            return encontrados[caminho]
        visitando.append(caminho)
        try:
            try:
                fonte = caminho.read_text(encoding='utf-8-sig')
            except (OSError, UnicodeError) as excecao:
                raise ErroCompilacao(f'Não foi possível ler módulo {caminho}: {excecao}.') from excecao
            linhas = [OrigemLinha(caminho, n, linha)
                      for n, linha in enumerate(fonte.splitlines(), 1)]
            importacoes = []
            definicoes = []
            principal_atual = None
            matematica = None
            indice = 0
            while indice < len(linhas):
                origem = linhas[indice]
                partes = _partes(origem)
                if not partes:
                    indice += 1
                    continue
                primeiro = partes[0]
                if primeiro == 'importe':
                    if (len(partes) not in (2, 4) or not partes[1].startswith('"') or
                            (len(partes) == 4 and partes[2] != 'como')):
                        erro(origem, 'use importe "pasta/arquivo.rts" [como apelido].')
                    apelido = partes[3] if len(partes) == 4 else None
                    if apelido and (not IDENTIFICADOR.fullmatch(apelido) or
                                    apelido in RESERVADOS or apelido.startswith(PREFIXO_INTERNO)):
                        erro(origem, f'apelido de módulo inválido ou reservado: {apelido!r}.')
                    try:
                        nome = json.loads(partes[1])
                    except (ValueError, UnicodeError) as excecao:
                        erro(origem, f'caminho de módulo inválido: {excecao}.')
                    if (not isinstance(nome, str) or not nome or '\\' in nome or
                            Path(nome).is_absolute() or Path(nome).suffix.lower() != '.rts'):
                        erro(origem, 'importação exige caminho relativo terminado em .rts.')
                    try:
                        destino = resolver_importacao(nome, caminho, raiz)
                    except ErroCompilacao as excecao:
                        erro(origem, str(excecao))
                    importacoes.append(Importacao(destino, apelido, origem))
                    indice += 1
                    continue
                if primeiro == 'inclua':
                    if partes != ['inclua', 'matematica']:
                        erro(origem, 'biblioteca desconhecida; use inclua matematica.')
                    matematica = origem
                    indice += 1
                    continue
                visibilidade = 'publico'
                if primeiro in ('publico', 'privado'):
                    visibilidade = primeiro
                    partes = partes[1:]
                if not partes or partes[0] not in ('tipo', 'funcao', 'inicio'):
                    erro(origem, f'instrução {primeiro!r} fora de tipo, funcao ou inicio.')
                categoria = partes[0]
                if categoria == 'inicio' and primeiro in ('publico', 'privado'):
                    erro(origem, 'bloco inicio não pode receber visibilidade.')
                if len(partes) < 2 or '{' not in partes:
                    erro(origem, f'definição {categoria} exige abertura {{.')
                quantidade = 0
                bloco = []
                while indice < len(linhas):
                    atual = linhas[indice]
                    itens = _partes(atual)
                    bloco.append(atual)
                    quantidade += itens.count('{') - itens.count('}')
                    indice += 1
                    if quantidade == 0:
                        break
                    if quantidade < 0:
                        erro(atual, 'fechamento de bloco inesperado.')
                if quantidade:
                    erro(origem, 'bloco sem fechamento.')
                if categoria == 'inicio':
                    if caminho != principal:
                        erro(origem, 'módulos não podem conter inicio; somente o programa principal.')
                    if principal_atual is not None:
                        erro(origem, 'programa contém mais de um bloco inicio.')
                    principal_atual = tuple(bloco)
                else:
                    nome_simbolo = partes[1]
                    if (not IDENTIFICADOR.fullmatch(nome_simbolo) or
                            nome_simbolo.startswith(PREFIXO_INTERNO)):
                        erro(origem, f'nome de símbolo inválido ou reservado: {nome_simbolo!r}.')
                    if any(d.nome == nome_simbolo for d in definicoes):
                        erro(origem, f'{nome_simbolo!r} já foi declarado neste módulo.')
                    definicoes.append(Definicao(categoria, nome_simbolo,
                                                 visibilidade, tuple(bloco)))
            if caminho == principal and principal_atual is None:
                raise ErroCompilacao(f'Arquivo principal {caminho} não tem bloco inicio.')
            if caminho != principal and not (definicoes or importacoes):
                raise ErroCompilacao(f'Módulo {caminho} precisa definir ou importar funções ou tipos.')
            modulo = Modulo(caminho, importacoes, definicoes,
                            principal_atual, matematica, {})
            encontrados[caminho] = modulo
            for importacao in importacoes:
                ler_modulo(importacao.destino)
            ordem.append(modulo)
            return modulo
        finally:
            visitando.pop()

    ler_modulo(principal)
    for numero, modulo in enumerate(ordem, 1):
        modulo.nomes = {d.nome: (d.nome if modulo.caminho == principal else
                          f'{PREFIXO_INTERNO}{numero}_{d.nome}')
                        for d in modulo.definicoes}

    def visiveis(importacao):
        destino = encontrados[importacao.destino]
        return {d.nome: destino.nomes[d.nome]
                for d in destino.definicoes if d.visibilidade == 'publico'}

    memo_globais = {}
    def acessiveis_globais(modulo):
        if modulo.caminho in memo_globais:
            return memo_globais[modulo.caminho]
        resultado = {d.nome: modulo.nomes[d.nome]
                     for d in modulo.definicoes if d.visibilidade == 'publico'}
        for importacao in modulo.importacoes:
            if importacao.apelido:
                continue
            for nome, interno in acessiveis_globais(encontrados[importacao.destino]).items():
                if nome in resultado and resultado[nome] != interno:
                    erro(importacao.origem, f'nome {nome!r} já foi declarado em outro módulo.')
                resultado[nome] = interno
        memo_globais[modulo.caminho] = resultado
        return resultado

    def resolver_escopo(modulo):
        referencias = dict(modulo.nomes)
        apelidos = {}
        for importacao in modulo.importacoes:
            if importacao.apelido:
                apelido = importacao.apelido
                anterior = apelidos.get(apelido)
                if anterior is not None and anterior != importacao.destino:
                    erro(importacao.origem, f'apelido {apelido!r} já representa outro módulo.')
                if apelido in referencias:
                    erro(importacao.origem, f'apelido {apelido!r} conflita com símbolo local.')
                apelidos[apelido] = importacao.destino
                continue
            for nome, interno in visiveis(importacao).items():
                if nome in referencias and referencias[nome] != interno:
                    erro(importacao.origem,
                         f'nome {nome!r} já foi declarado; use importe ... como apelido.')
                referencias[nome] = interno
        for importacao in modulo.importacoes:
            if importacao.apelido:
                continue
            filho = encontrados[importacao.destino]
            for nome, interno in acessiveis_globais(filho).items():
                if nome in referencias and referencias[nome] != interno:
                    erro(importacao.origem, f'nome {nome!r} já foi declarado; use apelidos.')
                referencias[nome] = interno
        return referencias, apelidos

    def reescrever(origem, modulo, referencias, apelidos):
        partes = _partes(origem)
        if not partes:
            return OrigemLinha(origem.caminho, origem.numero, origem.texto)
        if partes[0] in ('publico', 'privado'):
            partes = partes[1:]
        if apelidos and len(partes) > 1:
            if partes[0] in ('seja', 'para') and partes[1] in apelidos:
                erro(origem, f'nome {partes[1]!r} reservado como apelido de módulo.')
            if partes[0] == 'funcao' and '(' in partes and ')' in partes:
                argumentos = partes[partes.index('(')+1:partes.index(')')]
                if any(argumentos[i] in apelidos and argumentos[i+1] == ':'
                       for i in range(len(argumentos)-1)):
                    erro(origem, 'um parâmetro não pode ter nome igual a apelido de módulo.')
        saida = []
        indice = 0
        while indice < len(partes):
            nome = partes[indice]
            if indice + 2 < len(partes) and partes[indice+1] == '.' and nome in apelidos:
                alvo = encontrados[apelidos[nome]]
                proximo = partes[indice+2]
                definicao = next((d for d in alvo.definicoes if d.nome == proximo), None)
                tipo_contexto = indice > 0 and partes[indice-1] in (':', '>')
                chamada = indice + 3 < len(partes) and partes[indice+3] == '('
                if definicao is not None or tipo_contexto or chamada:
                    if definicao is None:
                        erro(origem, f'símbolo {nome}.{proximo} não existe no módulo.')
                    if definicao.visibilidade == 'privado':
                        erro(origem, f'símbolo {nome}.{proximo} é privado.')
                    saida.append(alvo.nomes[proximo])
                    indice += 3
                    continue
            # Tipos importados devem ser resolvidos tambem dentro de lista[Tipo].
            deve_renomear = bool(
                (indice >= 1 and partes[indice-1] in ('tipo', 'funcao', ':', '>')) or
                (indice >= 2 and partes[indice-1] == '[' and partes[indice-2] in ('lista', 'resultado', 'sucesso', 'falha')) or
                (indice + 1 < len(partes) and partes[indice+1] == '('))
            if deve_renomear and nome in referencias:
                saida.append(referencias[nome])
            else:
                saida.append(nome)
            indice += 1
        return OrigemLinha(origem.caminho, origem.numero, ' '.join(saida))

    tipos = []
    funcoes = []
    matematica = None
    principal_bloco = []
    for modulo in ordem:
        referencias, apelidos = resolver_escopo(modulo)
        if modulo.matematica and matematica is None:
            matematica = modulo.matematica
        for definicao in modulo.definicoes:
            bloco = [reescrever(origem, modulo, referencias, apelidos)
                     for origem in definicao.bloco]
            destino = tipos if definicao.categoria == 'tipo' else funcoes
            destino.extend(zip(definicao.bloco, bloco))
        if modulo.bloco_principal is not None:
            principal_bloco.extend((origem, reescrever(origem, modulo, referencias, apelidos))
                                   for origem in modulo.bloco_principal)

    todos = ([] if matematica is None else [(matematica, matematica)]) + tipos + funcoes + principal_bloco
    texto = '\n'.join(modificado.texto for _, modificado in todos) + '\n'
    return FontesReunidas(texto, tuple(original for original, _ in todos),
                         tuple(modulo.caminho for modulo in ordem))
