"""Carregador de módulos da RS: reúne arquivos e preserva a origem dos erros."""
from dataclasses import dataclass
from pathlib import Path
import json
import re

from .erros import ErroCompilacao
from .lexico import tokens
from .importacoes_padrao import resolver_importacao


@dataclass(frozen=True)
class OrigemLinha:
    caminho: Path
    numero: int
    texto: str


@dataclass(frozen=True)
class FontesReunidas:
    texto: str
    origens: tuple
    arquivos: tuple


def carregar_fontes(principal):
    """Resolve importações relativas e gera uma unidade nativa de compilação."""
    principal = Path(principal).resolve()
    raiz = principal.parent
    ativos, visitados, arquivos = [], set(), []
    tipos, funcoes, bloco_principal, matematicas = [], [], [], []
    possui_importacoes = False

    def erro(origem, mensagem):
        raise ErroCompilacao(f'{origem.caminho}:{origem.numero}: {mensagem}')

    def visitar(caminho, principal_atual=False):
        nonlocal possui_importacoes
        if caminho in ativos:
            trilha = ' -> '.join(p.name for p in ativos + [caminho])
            raise ErroCompilacao(f'Importação circular detectada: {trilha}.')
        if caminho in visitados:
            return
        ativos.append(caminho)
        try:
            try:
                texto = caminho.read_text(encoding='utf-8-sig')
            except (OSError, UnicodeError) as exc:
                raise ErroCompilacao(f'Não foi possível ler o módulo {caminho}: {exc}.') from exc
            linhas = [OrigemLinha(caminho, n, linha)
                      for n, linha in enumerate(texto.splitlines(), 1)]
            dependencias, tipos_locais, funcoes_locais = [], [], []
            inicio_local = None
            i = 0
            while i < len(linhas):
                origem = linhas[i]
                try:
                    partes = tokens(origem.texto, origem.numero)
                except ErroCompilacao as exc:
                    erro(origem, str(exc))
                if not partes:
                    i += 1
                    continue
                if partes[-1] == ';':
                    partes = partes[:-1]
                comando = str(partes[0])
                if comando == 'importe':
                    if len(partes) != 2 or not partes[1].startswith('"'):
                        erro(origem, 'use importe "pasta/arquivo.rts".')
                    try:
                        nome = json.loads(str(partes[1]))
                    except (UnicodeError, ValueError) as exc:
                        erro(origem, f'caminho inválido: {exc}.')
                    if not isinstance(nome, str) or not nome or '\\' in nome:
                        erro(origem, 'use caminho relativo com barras / e extensão .rts.')
                    relativo = Path(nome)
                    if relativo.is_absolute() or relativo.suffix.lower() != '.rts':
                        erro(origem, 'importação exige caminho relativo terminado em .rts.')
                    try:
                        destino = resolver_importacao(nome, caminho, raiz)
                    except ErroCompilacao as excecao:
                        erro(origem, str(excecao))
                    dependencias.append(destino)
                    possui_importacoes = True
                    i += 1
                    continue
                if comando == 'inclua':
                    if partes != ['inclua', 'matematica']:
                        erro(origem, 'biblioteca desconhecida; use inclua matematica.')
                    matematicas.append(origem)
                    i += 1
                    continue
                if comando not in ('tipo', 'funcao', 'inicio'):
                    erro(origem, f'instrução {comando!r} fora de tipo, funcao ou inicio.')
                if '{' not in partes:
                    erro(origem, f'definição {comando} exige abertura de bloco.')
                bloco, profundidade = [], 0
                while i < len(linhas):
                    atual = linhas[i]
                    try:
                        t = tokens(atual.texto, atual.numero)
                    except ErroCompilacao as exc:
                        erro(atual, str(exc))
                    bloco.append(atual)
                    profundidade += t.count('{') - t.count('}')
                    i += 1
                    if profundidade == 0:
                        break
                    if profundidade < 0:
                        erro(atual, 'fechamento de bloco inesperado.')
                if profundidade:
                    erro(origem, 'bloco sem fechamento.')
                if comando == 'tipo':
                    tipos_locais.extend(bloco)
                elif comando == 'funcao':
                    funcoes_locais.extend(bloco)
                else:
                    if not principal_atual:
                        erro(origem, 'módulos não podem conter inicio.')
                    if inicio_local is not None:
                        erro(origem, 'mais de um bloco inicio.')
                    inicio_local = bloco
            if principal_atual and inicio_local is None:
                raise ErroCompilacao(f'Arquivo principal {caminho} não tem bloco inicio.')
            if not principal_atual and not (tipos_locais or funcoes_locais or dependencias):
                raise ErroCompilacao(f'Módulo {caminho} precisa definir ou importar funções ou tipos.')
            for dependencia in dependencias:
                visitar(dependencia)
            tipos.extend(tipos_locais)
            funcoes.extend(funcoes_locais)
            if principal_atual:
                bloco_principal.extend(inicio_local)
            visitados.add(caminho)
            arquivos.append(caminho)
        finally:
            ativos.pop()

    visitar(principal, True)
    if not possui_importacoes:
        # Fonte legada passa inalterada ao analisador, inclusive linhas vazias.
        texto = principal.read_text(encoding='utf-8-sig')
        origens = tuple(OrigemLinha(principal, i, linha)
                        for i, linha in enumerate(texto.splitlines(), 1))
        return FontesReunidas(texto, origens, (principal,))
    origens = tuple(([matematicas[0]] if matematicas else []) + tipos + funcoes + bloco_principal)
    return FontesReunidas('\n'.join(l.texto for l in origens) + '\n',
                         origens, tuple(arquivos))


def apresentar_erro(erro, origens):
    """Traduz uma linha gerada para arquivo e linha originais."""
    mensagem = str(erro)
    achado = re.search(r'Linha (\d+)(?:, coluna (\d+))?:', mensagem)
    if achado is None or not 1 <= int(achado.group(1)) <= len(origens):
        return mensagem, None, None
    origem = origens[int(achado.group(1)) - 1]
    coluna = int(achado.group(2)) if achado.group(2) else None
    referencia = f'{origem.caminho}:{origem.numero}'
    if coluna is not None:
        referencia += f', coluna {coluna}'
    return (mensagem[:achado.start()] + referencia + ':' + mensagem[achado.end():],
            origem, coluna)


# RS 0.28: mantém a expansão antiga intacta para projetos sem visibilidade
# explícita e sem apelidos. Os novos recursos usam um resolvedor separado.
_carregar_fontes_legado = carregar_fontes


def _requer_espacos_nomes(principal):
    raiz = Path(principal).resolve().parent
    pendentes = [Path(principal).resolve()]
    visitados = set()
    while pendentes:
        caminho = pendentes.pop()
        if caminho in visitados:
            continue
        visitados.add(caminho)
        try:
            fonte = caminho.read_text(encoding='utf-8-sig')
        except (OSError, UnicodeError):
            continue
        for numero, linha in enumerate(fonte.splitlines(), 1):
            partes = tokens(linha, numero)
            if not partes:
                continue
            if (partes[0] in ('publico', 'privado') and len(partes) > 1 and
                    partes[1] in ('funcao', 'tipo')):
                return True
            if partes[0] == 'importe':
                if 'como' in partes:
                    return True
                if len(partes) >= 2 and partes[1].startswith('"'):
                    try:
                        nome = json.loads(partes[1])
                    except (ValueError, UnicodeError):
                        continue
                    if isinstance(nome, str):
                        try:
                            proximo = resolver_importacao(nome, caminho, raiz)
                        except ErroCompilacao:
                            continue
                        pendentes.append(proximo)
    return False


def carregar_fontes(principal):
    if _requer_espacos_nomes(principal):
        from .espacos_nomes import carregar_com_espacos
        return carregar_com_espacos(principal)
    return _carregar_fontes_legado(principal)
