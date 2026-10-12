"""Análise de blocos, declarações e instruções da linguagem."""
import json
import re
from .ast import Programa, NoInstrucao, PosicaoFonte
from .erros import ErroCompilacao
from .lexico import tokens
from .semantica import ContextoSemantico

def analisar_programa(fonte):
    linhas = [(n, tokens(l, n)) for n, l in enumerate(fonte.splitlines(), 1)]
    linhas = [(n, t) for n, t in linhas if t]
    importa = False
    if linhas and linhas[0][1] == ['inclua', 'matematica']:
        importa = True
        linhas.pop(0)
    if not linhas or linhas[0][1] != ['inicio', '{']:
        raise ErroCompilacao("O programa deve começar com 'inicio {' (após os 'inclua').")
    # Aceita tanto '} senao {' quanto '}' seguido de 'senao {' na linha seguinte.
    normalizadas = []
    for n, t in linhas[1:]:
        if t == ['}', 'senao', '{']:
            normalizadas.extend([(n, ['}']), (n, ['senao', '{'])])
        else:
            normalizadas.append((n, t))
    contexto = ContextoSemantico(importa)
    variaveis, tipos = contexto.variaveis, contexto.tipos
    expressao_tipada, registrar = contexto.expressao_tipada, contexto.registrar
    reservadas = {'inicio', 'seja', 'escreva', 'leia', 'inclua', 'se', 'senao', 'enquanto', 'para', 'de', 'ate', 'passo', 'pare', 'continue', 'inteiro', 'logico', 'verdadeiro', 'falso', 'lista', 'tamanho', 'texto', 'capacidade', 'copie', 'junte', 'limpe'}

    def indice_lista(partes, linha):
        if len(partes) < 4 or partes[1] != '[' or partes[-1] != ']':
            raise ErroCompilacao(f'Linha {linha}: use lista[indice].')
        nome = partes[0]
        tipo = tipos.get(nome)
        if not isinstance(tipo, tuple) or tipo[0] != 'lista':
            raise ErroCompilacao(f'Linha {linha}: {nome!r} não é uma lista declarada.')
        indice, _ = expressao_tipada(partes[2:-1], linha, 'inteiro')
        return nome, indice, tipo[2]

    def texto_destino(partes, linha):
        if len(partes) != 1:
            raise ErroCompilacao(f'Linha {linha}: informe um único nome de buffer.')
        nome = partes[0]
        tipo = tipos.get(nome)
        if not isinstance(tipo, tuple) or tipo[0] != 'texto':
            raise ErroCompilacao(f'Linha {linha}: {nome!r} precisa ser um buffer de texto declarado.')
        return nome, tipo[1]

    def texto_origem(partes, linha):
        if len(partes) != 1:
            raise ErroCompilacao(f'Linha {linha}: origem deve ser um texto literal ou outro buffer.')
        valor = partes[0]
        if valor.startswith('"'):
            try:
                conteudo = json.loads(valor)
                bruto = conteudo.encode('utf-8')
            except (ValueError, UnicodeError) as exc:
                raise ErroCompilacao(f'Linha {linha}: literal de texto inválido.') from exc
            return ('literal', conteudo, len(bruto))
        nome, cap = texto_destino(partes, linha)
        return ('buffer', nome, cap)

    def bloco(i, profundidade=0, em_laco=False):
        instrucoes = []

        def adicionar(instruicao, linha, partes):
            instrucao = NoInstrucao(instruicao, PosicaoFonte(linha, partes[0].origem.coluna))
            instrucoes.append(instrucao)
        while i < len(normalizadas):
            n, t = normalizadas[i]
            if t == ['}']:
                return instrucoes, i + 1
            if t[-1] == ';':
                t = t[:-1]
            if not t:
                i += 1
                continue
            if len(t) >= 3 and t[0] == 'se' and t[-1] == '{':
                cond, _ = expressao_tipada(t[1:-1], n)
                verdadeiro, i = bloco(i+1, profundidade+1, em_laco)
                falso = []
                if i < len(normalizadas) and normalizadas[i][1] == ['senao', '{']:
                    falso, i = bloco(i+1, profundidade+1, em_laco)
                adicionar(('se', cond, verdadeiro, falso), n, t)
                continue
            if len(t) >= 3 and t[0] == 'enquanto' and t[-1] == '{':
                cond, _ = expressao_tipada(t[1:-1], n)
                corpo, i = bloco(i+1, profundidade+1, True)
                adicionar(('enquanto', cond, corpo), n, t)
                continue
            if len(t) >= 7 and t[0] == 'para' and t[-1] == '{':
                # Sintaxe: para nome de inicio ate fim [passo inteiro] {
                nome = t[1]
                if not re.fullmatch(r'[A-Za-z_][A-Za-z_0-9]*', nome) or nome in reservadas:
                    raise ErroCompilacao(f'Linha {n}: nome de contador invalido no para.')
                if t[2] != 'de' or 'ate' not in t[3:-1]:
                    raise ErroCompilacao(f"Linha {n}: use 'para nome de inicio ate fim [passo numero] {{'.")
                pos_ate = t.index('ate', 3)
                if pos_ate == 3:
                    raise ErroCompilacao(f'Linha {n}: informe o valor inicial do para.')
                pos_passo = t.index('passo', pos_ate+1) if 'passo' in t[pos_ate+1:-1] else len(t)-1
                if pos_passo == pos_ate+1:
                    raise ErroCompilacao(f'Linha {n}: informe o valor final do para.')
                inicial, _ = expressao_tipada(t[3:pos_ate], n, 'inteiro')
                final, _ = expressao_tipada(t[pos_ate+1:pos_passo], n, 'inteiro')
                passo = 1
                if pos_passo < len(t)-1:
                    partes = t[pos_passo+1:-1]
                    if not partes or len(partes) > 2 or (len(partes) == 2 and partes[0] != '-'):
                        raise ErroCompilacao(f'Linha {n}: passo precisa ser um numero inteiro constante.')
                    numero = partes[-1]
                    if not numero.isascii() or not numero.isdecimal():
                        raise ErroCompilacao(f'Linha {n}: passo precisa ser um numero inteiro constante.')
                    passo = int(numero) * (-1 if len(partes) == 2 else 1)
                    if passo == 0 or abs(passo) > (1 << 63)-1:
                        raise ErroCompilacao(f'Linha {n}: passo precisa estar entre -9223372036854775807 e 9223372036854775807, sem zero.')
                if nome not in variaveis:
                    registrar(nome, 'inteiro', n)
                elif tipos[nome] != 'inteiro':
                    raise ErroCompilacao(f'Linha {n}: contador do para precisa ser inteiro.')
                corpo, i = bloco(i+1, profundidade+1, True)
                adicionar(('para', nome, inicial, final, passo, corpo), n, t)
                continue
            if t in (['pare'], ['continue']):
                if not em_laco:
                    raise ErroCompilacao(f"Linha {n}: '{t[0]}' só pode ser usado dentro de um laço.")
                adicionar((t[0],), n, t)
                i += 1
                continue
            if t[:2] == ['leia', '('] and t[-1] == ')':
                destino = t[2:-1]
                if '[' in destino:
                    nome, indice, tamanho = indice_lista(destino, n)
                    adicionar(('leia_indice', nome, indice, tamanho), n, t)
                elif len(destino) == 1 and isinstance(tipos.get(destino[0]), tuple) and tipos[destino[0]][0] == 'texto':
                    adicionar(('leia_texto', destino[0]), n, t)
                elif len(destino) == 1 and re.fullmatch(r'[A-Za-z_][A-Za-z_0-9]*', destino[0]):
                    nome = destino[0]
                    if nome not in variaveis:
                        raise ErroCompilacao(f"Linha {n}: declare a variável '{nome}' com seja antes de leia.")
                    if tipos[nome] != 'inteiro':
                        raise ErroCompilacao(f'Linha {n}: leia aceita somente variável do tipo inteiro nesta versão.')
                    adicionar(('leia_int', nome), n, t)
                else:
                    raise ErroCompilacao(f'Linha {n}: use leia(inteiro), leia(lista[indice]) ou leia(buffer).')
            elif t[:2] == ['escreva', '('] and t[-1] == ')':
                expr = t[2:-1]
                if len(expr) == 1 and isinstance(tipos.get(expr[0]), tuple) and tipos[expr[0]][0] == 'texto':
                    adicionar(('imprima_texto', expr[0]), n, t)
                elif len(expr) == 1 and expr[0].startswith('"'):
                    try:
                        valor = json.loads(expr[0])
                    except (ValueError, UnicodeError) as exc:
                        raise ErroCompilacao(f'Linha {n}: texto inválido.') from exc
                    adicionar(('texto', valor + '\n'), n, t)
                else:
                    arvore, _ = expressao_tipada(expr, n)
                    adicionar(('imprima_num', arvore), n, t)
            elif t[0] in ('copie', 'junte') and len(t) >= 6 and t[1] == '(' and t[-1] == ')':
                if t.count(',') != 1:
                    raise ErroCompilacao(f'Linha {n}: use {t[0]}(destino, origem).')
                virgula = t.index(',')
                nome, capacidade = texto_destino(t[2:virgula], n)
                origem = texto_origem(t[virgula+1:-1], n)
                if t[0] == 'copie' and origem[0] == 'literal' and origem[2] > capacidade:
                    raise ErroCompilacao(f'Linha {n}: texto exige {origem[2]} bytes; capacidade de {nome} é {capacidade}.')
                adicionar(('modifique_texto', t[0], nome, origem), n, t)
            elif t[0] == 'limpe' and len(t) >= 4 and t[:2] == ['limpe', '('] and t[-1] == ')':
                nome, _ = texto_destino(t[2:-1], n)
                adicionar(('limpe_texto', nome), n, t)
            elif t[0] == 'seja':
                if profundidade:
                    raise ErroCompilacao(f'Linha {n}: declare variáveis antes dos blocos de decisão ou repetição nesta versão.')
                nome = t[1] if len(t) > 1 else ''
                if not re.fullmatch(r'[A-Za-z_][A-Za-z_0-9]*', nome):
                    raise ErroCompilacao(f'Linha {n}: nome de variável inválido.')
                if nome in variaveis or nome in reservadas:
                    raise ErroCompilacao(f"Linha {n}: variável '{nome}' duplicada ou reservada.")
                if len(t) == 7 and t[2:4] == [':', 'texto'] and t[4] == '[' and t[6] == ']':
                    literal = t[5]
                    if not literal.isascii() or not literal.isdecimal():
                        raise ErroCompilacao(f'Linha {n}: capacidade do texto precisa ser um inteiro constante.')
                    capacidade = int(literal)
                    if not 1 <= capacidade <= 2040:
                        raise ErroCompilacao(f'Linha {n}: capacidade deve estar entre 1 e 2040 bytes.')
                    registrar(nome, ('texto', capacidade), n)
                    adicionar(('crie_texto', nome, capacidade), n, t)
                    i += 1
                    continue
                if len(t) == 7 and t[2:4] == [':', 'lista'] and t[4] == '[' and t[6] == ']':
                    tamanho_literal = t[5]
                    if not tamanho_literal.isascii() or not tamanho_literal.isdecimal():
                        raise ErroCompilacao(f'Linha {n}: tamanho da lista deve ser um inteiro constante.')
                    tamanho = int(tamanho_literal)
                    if not 1 <= tamanho <= 256:
                        raise ErroCompilacao(f'Linha {n}: tamanho da lista deve estar entre 1 e 256.')
                    registrar(nome, ('lista', 'inteiro', tamanho), n)
                    adicionar(('crie_lista', nome, tamanho), n, t)
                    i += 1
                    continue
                if len(t) >= 6 and t[2] == ':' and t[4] == '=':
                    declarado = t[3]
                    if declarado not in ('inteiro', 'logico'):
                        raise ErroCompilacao(f'Linha {n}: tipo {declarado!r} ainda não disponível; use inteiro ou logico.')
                    arvore, inferido = expressao_tipada(t[5:], n, declarado)
                elif len(t) >= 4 and t[2] == '=':
                    arvore, inferido = expressao_tipada(t[3:], n)
                else:
                    raise ErroCompilacao(f"Linha {n}: use 'seja nome = valor' ou 'seja nome: inteiro = valor'.")
                registrar(nome, inferido, n)
                adicionar(('atribua', nome, arvore), n, t)
            elif len(t) >= 5 and '[' in t and ']' in t and '=' in t and t.index('[') < t.index(']') < t.index('='):
                igual = t.index('=')
                nome, indice, tamanho = indice_lista(t[:igual], n)
                valor, _ = expressao_tipada(t[igual+1:], n, 'inteiro')
                adicionar(('atribua_indice', nome, indice, valor, tamanho), n, t)
            elif len(t) >= 3 and t[1] == '=':
                nome = t[0]
                if nome not in variaveis:
                    raise ErroCompilacao(f"Linha {n}: variável '{nome}' não foi declarada.")
                arvore, _ = expressao_tipada(t[2:], n, tipos[nome])
                adicionar(('atribua', nome, arvore), n, t)
            else:
                raise ErroCompilacao(f'Linha {n}, coluna {t[0].origem.coluna}: instrução desconhecida ou incompleta.')
            i += 1
        raise ErroCompilacao('Bloco sem fechamento: faltou uma linha com } .')

    instrucoes, proxima = bloco(0)
    if proxima != len(normalizadas):
        n, _ = normalizadas[proxima]
        raise ErroCompilacao(f'Linha {n}: conteúdo após o fim do programa.')
    if not instrucoes:
        raise ErroCompilacao('Escreva pelo menos uma instrução dentro de inicio.')
    return Programa(instrucoes, variaveis, importa, tipos)
