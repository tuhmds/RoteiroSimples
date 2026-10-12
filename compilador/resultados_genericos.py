"""Resultados genéricos da RS: especialização estática e propagação explícita.

A linguagem aceita resultado[T], sucesso[T](valor), falha[T](codigo)
e propague nome em funções que retornam resultado[T]. O gerador nativo
recebe somente tipos concretos e instruções já verificadas.
"""
import hashlib
import re
from pathlib import Path

from .erros import ErroCompilacao
from .lexico import tokens
from .modulos import FontesReunidas, OrigemLinha


TIPOS_PRIMITIVOS = frozenset(('inteiro', 'logico'))
IDENTIFICADOR = re.compile(r'[A-Za-z_][A-Za-z_0-9]*\Z')
MARCADORES = frozenset(('resultado', 'sucesso', 'falha'))
PREFIXO = 'RsInternoGenerico_'


def _ler_tipo(itens, linha):
    """Reconhece apenas um tipo concreto, sem genéricos recursivos."""
    if len(itens) == 1 and (itens[0] in TIPOS_PRIMITIVOS or IDENTIFICADOR.fullmatch(itens[0])):
        if itens[0].startswith(PREFIXO):
            raise ErroCompilacao(f'Linha {linha}: prefixo interno reservado.')
        return itens[0], itens[0]
    if (len(itens) == 4 and itens[0] in ('texto', 'lista') and
            itens[1] == '[' and itens[3] == ']' and
            itens[2].isascii() and itens[2].isdecimal()):
        capacidade = int(itens[2])
        if not 1 <= capacidade < 0x0FFF0000:
            raise ErroCompilacao(f'Linha {linha}: tamanho inválido em resultado[T].')
        texto = f'{itens[0]}[{capacidade}]'
        return texto, ' '.join(itens)
    raise ErroCompilacao(f'Linha {linha}: resultado[T] exige um tipo concreto (inteiro, logico, registro, texto[N] ou lista[N]).')


def _nomes(tipo):
    sufixo = hashlib.sha1(tipo.encode('utf-8')).hexdigest()[:16]
    return (f'{PREFIXO}Resultado_{sufixo}',
            f'{PREFIXO}Sucesso_{sufixo}',
            f'{PREFIXO}Falha_{sufixo}')


def _separar_generico(itens, indice, linha):
    """Encontra o colchete final da sintaxe nome[T] respeitando lista[N]."""
    if indice + 1 >= len(itens) or itens[indice+1] != '[':
        return None
    nivel = 0
    conteudo = []
    posicao = indice + 1
    while posicao < len(itens):
        parte = itens[posicao]
        if parte == '[':
            nivel += 1
            if nivel > 1:
                conteudo.append(parte)
        elif parte == ']':
            nivel -= 1
            if nivel == 0:
                return conteudo, posicao + 1
            if nivel < 0:
                break
            conteudo.append(parte)
        else:
            conteudo.append(parte)
        posicao += 1
    raise ErroCompilacao(f'Linha {linha}: colchete não fechado em resultado genérico.')


def _montar_tipos_e_funcoes(especializacoes):
    tipos = []
    funcoes = []
    for chave, tipo in especializacoes.items():
        nome, sucesso, falha = _nomes(chave)
        tipos.extend((
            f'tipo {nome} {{',
            '    valido: logico',
            f'    valor: {tipo}',
            '    codigo_erro: inteiro',
            '}',
        ))
        funcoes.extend((
            f'funcao {sucesso}(valor: {tipo}) -> {nome} {{',
            f'    seja resposta: {nome}',
            '    resposta.valido = verdadeiro',
            '    resposta.valor = valor',
            '    resposta.codigo_erro = 0',
            '    retorne resposta',
            '}',
            f'funcao {falha}(codigo: inteiro) -> {nome} {{',
            f'    seja resposta: {nome}',
            '    resposta.valido = falso',
            '    resposta.codigo_erro = codigo',
            '    se resposta.codigo_erro == 0 {',
            '        resposta.codigo_erro = 2',
            '    }',
            '    retorne resposta',
            '}',
        ))
    return tipos, funcoes


def preparar_resultados_genericos(fontes):
    """Transforma resultados genéricos em registros e funções RS verificáveis.

    Não altera arquivos de origem. Linhas sintéticas têm origem própria e as
    linhas transformadas preservam caminho e número do arquivo original.
    """
    especiais = {}
    origens = list(fontes.origens)
    saida = []
    funcao_retorno = None
    nivel_funcao = 0
    usou_recurso = False

    def substituir(itens, origem):
        nonlocal usou_recurso
        novos = []
        indice = 0
        while indice < len(itens):
            token = itens[indice]
            if token in MARCADORES and indice + 1 < len(itens) and itens[indice + 1] == '[':
                encontrado = _separar_generico(itens, indice, origem.numero)
                bruto, fim = encontrado
                chave, tipo = _ler_tipo(bruto, origem.numero)
                especiais[chave] = tipo
                nomes = _nomes(chave)
                nome = nomes[('resultado', 'sucesso', 'falha').index(token)]
                novos.append(nome)
                indice = fim
                usou_recurso = True
            else:
                novos.append(token)
                indice += 1
        return novos

    for origem in origens:
        itens = [str(x) for x in tokens(origem.texto, origem.numero)]
        if not itens:
            saida.append(origem)
            continue

        # Descobre o tipo a propagar na assinatura antes da substituição.
        inicio_funcao = itens[0] == 'funcao' and itens[-1] == '{'
        if inicio_funcao:
            if funcao_retorno is not None:
                raise ErroCompilacao(f'{origem.caminho}:{origem.numero}: função anterior sem fechamento.')
            if ')' not in itens:
                raise ErroCompilacao(f'{origem.caminho}:{origem.numero}: assinatura inválida.')
            fim_parametros = itens.index(')')
            retorno_bruto = itens[fim_parametros+1:-1]
            if len(retorno_bruto) >= 4 and retorno_bruto[:3] == ['-', '>', 'resultado']:
                achado = _separar_generico(retorno_bruto, 2, origem.numero)
                if achado is not None and achado[1] == len(retorno_bruto):
                    chave, _ = _ler_tipo(achado[0], origem.numero)
                    funcao_retorno = chave
            nivel_funcao = 0

        if itens[0] == 'propague':
            if funcao_retorno is None:
                raise ErroCompilacao(f'{origem.caminho}:{origem.numero}: propague exige função com retorno resultado[T].')
            if len(itens) != 2 or not IDENTIFICADOR.fullmatch(itens[1]):
                raise ErroCompilacao(f'{origem.caminho}:{origem.numero}: use propague nome_do_resultado.')
            nome = itens[1]
            _, _, falha = _nomes(funcao_retorno)
            novos = (
                f'se {nome}.valido == falso {{',
                f'    retorne {falha}({nome}.codigo_erro)',
                '}',
            )
            saida.extend(OrigemLinha(origem.caminho, origem.numero, texto) for texto in novos)
            usou_recurso = True
        else:
            novos = substituir(itens, origem)
            if novos == itens:
                saida.append(origem)
            else:
                saida.append(OrigemLinha(origem.caminho, origem.numero, ' '.join(novos)))

        if inicio_funcao or funcao_retorno is not None:
            nivel_funcao += itens.count('{') - itens.count('}')
            if nivel_funcao == 0 and funcao_retorno is not None:
                funcao_retorno = None

    if not usou_recurso:
        return fontes

    declaracoes, construtores = _montar_tipos_e_funcoes(especiais)
    tipos = [OrigemLinha(Path('<resultados_genericos>'), pos+1, linha)
             for pos, linha in enumerate(declaracoes)]
    funcoes = [OrigemLinha(Path('<resultados_genericos>'), pos+1, linha)
               for pos, linha in enumerate(construtores)]

    # O parser exige todos os tipos antes da primeira função/inicio.
    # Inserimos especializações depois das declarações do usuário.
    corte_tipos = None
    for indice, origem in enumerate(saida):
        linha = [str(x) for x in tokens(origem.texto, origem.numero)]
        if linha and linha[0] in ('funcao', 'inicio'):
            corte_tipos = indice
            break
    if corte_tipos is None:
        raise ErroCompilacao('Programa não contém função nem bloco inicio.')
    saida[corte_tipos:corte_tipos] = tipos + funcoes
    return FontesReunidas('\n'.join(x.texto for x in saida) + '\n',
                          tuple(saida), fontes.arquivos)
