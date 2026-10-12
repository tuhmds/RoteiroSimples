"""Análise de blocos, declarações e instruções da linguagem."""
import json
import re
from .ast import Programa, Funcao, NoInstrucao, PosicaoFonte
from .erros import ErroCompilacao
from .lexico import tokens
from .semantica import ContextoSemantico

def analisar_programa(fonte, _linhas=None, _contexto=None, _assinaturas=None, _retorno=None):
    linhas = (_linhas if _linhas is not None else
             [(n, tokens(l, n)) for n, l in enumerate(fonte.splitlines(), 1)])
    linhas = [(n, t) for n, t in linhas if t]
    importa = _contexto.importa_matematica if _contexto else False
    if _linhas is None and linhas and linhas[0][1] == ['inclua', 'matematica']:
        importa = True
        linhas.pop(0)
    # Aceita tanto '} senao {' quanto '}' seguido de 'senao {' na linha seguinte.
    normalizadas = []
    for n, t in linhas:
        if t == ['}', 'senao', '{']:
            normalizadas.extend([(n, ['}']), (n, ['senao', '{'])])
        else:
            normalizadas.append((n, t))
    linhas = normalizadas
    definicoes = []
    assinaturas = _assinaturas if _assinaturas is not None else {}
    if _linhas is None:
        while linhas and linhas[0][1] and linhas[0][1][0] == 'funcao':
            n, cabecalho = linhas[0]
            if len(cabecalho) < 8 or cabecalho[2] != '(' or ')' not in cabecalho:
                raise ErroCompilacao(f'Linha {n}: cabeçalho de função inválido.')
            nome = str(cabecalho[1])
            if not re.fullmatch(r'[A-Za-z_][A-Za-z_0-9]*', nome) or nome in ('inicio', 'seja', 'funcao', 'retorne'):
                raise ErroCompilacao(f'Linha {n}: nome de função inválido.')
            fim_par = cabecalho.index(')', 3)
            if cabecalho[fim_par+1:] != ['-', '>', 'inteiro', '{'] and cabecalho[fim_par+1:] != ['-', '>', 'logico', '{']:
                raise ErroCompilacao(f'Linha {n}: use funcao nome(parametro: tipo) -> inteiro ou logico {{.')
            retorno = str(cabecalho[fim_par+3])
            partes = cabecalho[3:fim_par]
            parametros = []
            if partes:
                grupos = []
                ultimo = 0
                for i, token in enumerate(partes):
                    if token == ',':
                        grupos.append(partes[ultimo:i]); ultimo = i+1
                grupos.append(partes[ultimo:])
                for grupo in grupos:
                    if len(grupo) != 3 or grupo[1] != ':' or grupo[2] not in ('inteiro', 'logico') or not re.fullmatch(r'[A-Za-z_][A-Za-z_0-9]*', grupo[0]):
                        raise ErroCompilacao(f'Linha {n}: use parametro: inteiro ou parametro: logico.')
                    if grupo[0] in (x[0] for x in parametros):
                        raise ErroCompilacao(f'Linha {n}: parâmetro duplicado: {grupo[0]}.')
                    parametros.append((str(grupo[0]), str(grupo[2])))
            if nome in assinaturas:
                raise ErroCompilacao(f'Linha {n}: função {nome!r} já foi declarada.')
            assinaturas[nome] = (tuple(tipo for _, tipo in parametros), retorno)
            nivel = 1
            fim = 1
            while fim < len(linhas) and nivel:
                t = linhas[fim][1]
                nivel += t.count('{') - t.count('}')
                fim += 1
            if nivel:
                raise ErroCompilacao(f'Linha {n}: função {nome!r} sem fechamento.')
            definicoes.append((nome, parametros, retorno, n, linhas[1:fim]))
            linhas = linhas[fim:]
    if not linhas or linhas[0][1] != ['inicio', '{']:
        raise ErroCompilacao("O programa deve começar com 'inicio {' (após as definições de função).")
    normalizadas = linhas[1:]
    contexto = _contexto or ContextoSemantico(importa, assinaturas)
    variaveis, tipos = contexto.variaveis, contexto.tipos
    expressao_tipada, registrar = contexto.expressao_tipada, contexto.registrar
    reservadas = {'inicio', 'seja', 'escreva', 'leia', 'inclua', 'se', 'senao', 'enquanto', 'para', 'de', 'ate', 'passo', 'pare', 'continue', 'inteiro', 'logico', 'verdadeiro', 'falso', 'lista', 'tamanho', 'texto', 'capacidade', 'copie', 'junte', 'limpe', 'funcao', 'retorne'}

    def indice_lista(partes, linha):
        if len(partes) < 4 or partes[1] != '[' or partes[-1] != ']':
            raise ErroCompilacao(f'Linha {linha}: use lista[indice].')
        nome = contexto.resolver(str(partes[0]))
        tipo = tipos.get(nome)
        if not isinstance(tipo, tuple) or tipo[0] != 'lista':
            raise ErroCompilacao(f'Linha {linha}: {nome!r} não é uma lista declarada.')
        indice, _ = expressao_tipada(partes[2:-1], linha, 'inteiro')
        return nome, indice, tipo[2]

    def texto_destino(partes, linha):
        if len(partes) != 1:
            raise ErroCompilacao(f'Linha {linha}: informe um único nome de buffer.')
        nome = contexto.resolver(str(partes[0]))
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
        if profundidade:
            contexto.entrar_escopo()
        instrucoes = []

        def adicionar(instruicao, linha, partes):
            instrucao = NoInstrucao(instruicao, PosicaoFonte(linha, partes[0].origem.coluna))
            instrucoes.append(instrucao)
        while i < len(normalizadas):
            n, t = normalizadas[i]
            if t == ['}']:
                if profundidade:
                    contexto.sair_escopo()
                return instrucoes, i + 1
            if t[-1] == ';':
                t = t[:-1]
            if not t:
                i += 1
                continue
            if t[0] == 'retorne':
                if _retorno is None:
                    raise ErroCompilacao(f'Linha {n}: retorne só pode aparecer dentro de função.')
                if len(t) == 1:
                    raise ErroCompilacao(f'Linha {n}: retorne exige um valor.')
                valor, _ = expressao_tipada(t[1:], n, _retorno)
                adicionar(('retorne', valor), n, t)
                i += 1
                continue
            if _retorno is not None and t[0] in ('leia', 'copie', 'junte', 'limpe'):
                raise ErroCompilacao(f'Linha {n}: entrada e buffers dentro de funções serão habilitados após os quadros de memória por chamada.')
            if len(t) >= 3 and t[0] == 'se'  and t[-1] == '{':
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
                interno = contexto.resolver(str(nome))
                if interno not in variaveis:
                    interno = registrar(str(nome), 'inteiro', n)
                elif tipos[interno] != 'inteiro':
                    raise ErroCompilacao(f'Linha {n}: contador do para precisa ser inteiro.')
                corpo, i = bloco(i+1, profundidade+1, True)
                adicionar(('para', interno, inicial, final, passo, corpo), n, t)
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
                elif len(destino) == 1 and isinstance(tipos.get(contexto.resolver(str(destino[0]))), tuple) and tipos[contexto.resolver(str(destino[0]))][0] == 'texto':
                    adicionar(('leia_texto', contexto.resolver(str(destino[0]))), n, t)
                elif len(destino) == 1 and re.fullmatch(r'[A-Za-z_][A-Za-z_0-9]*', destino[0]):
                    nome = contexto.resolver(str(destino[0]))
                    if nome not in variaveis:
                        raise ErroCompilacao(f"Linha {n}: declare a variável '{nome}' com seja antes de leia.")
                    if tipos[nome] != 'inteiro':
                        raise ErroCompilacao(f'Linha {n}: leia aceita somente variável do tipo inteiro nesta versão.')
                    adicionar(('leia_int', nome), n, t)
                else:
                    raise ErroCompilacao(f'Linha {n}: use leia(inteiro), leia(lista[indice]) ou leia(buffer).')
            elif t[:2] == ['escreva', '('] and t[-1] == ')':
                expr = t[2:-1]
                if len(expr) == 1 and isinstance(tipos.get(contexto.resolver(str(expr[0]))), tuple) and tipos[contexto.resolver(str(expr[0]))][0] == 'texto':
                    adicionar(('imprima_texto', contexto.resolver(str(expr[0]))), n, t)
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
                nome = t[1] if len(t) > 1 else ''
                if not re.fullmatch(r'[A-Za-z_][A-Za-z_0-9]*', nome):
                    raise ErroCompilacao(f'Linha {n}: nome de variável inválido.')
                if contexto.declarado_neste_escopo(str(nome)) or nome in reservadas:
                    raise ErroCompilacao(f"Linha {n}: variável '{nome}' duplicada ou reservada.")
                if len(t) == 7 and t[2:4] == [':', 'texto'] and t[4] == '[' and t[6] == ']':
                    literal = t[5]
                    if not literal.isascii() or not literal.isdecimal():
                        raise ErroCompilacao(f'Linha {n}: capacidade do texto precisa ser um inteiro constante.')
                    capacidade = int(literal)
                    if _retorno is not None:
                        raise ErroCompilacao(f'Linha {n}: buffers locais em funções ainda não estão disponíveis.')
                    if not 1 <= capacidade < 0x7FFF0000:
                        raise ErroCompilacao(f'Linha {n}: capacidade de texto fora do intervalo do gerador nativo.')
                    interno = registrar(str(nome), ('texto', capacidade), n)
                    adicionar(('crie_texto', interno, capacidade), n, t)
                    i += 1
                    continue
                if len(t) == 7 and t[2:4] == [':', 'lista'] and t[4] == '[' and t[6] == ']':
                    tamanho_literal = t[5]
                    if not tamanho_literal.isascii() or not tamanho_literal.isdecimal():
                        raise ErroCompilacao(f'Linha {n}: tamanho da lista deve ser um inteiro constante.')
                    tamanho = int(tamanho_literal)
                    if _retorno is not None:
                        raise ErroCompilacao(f'Linha {n}: listas locais em funções ainda não estão disponíveis.')
                    if not 1 <= tamanho < 0x0FFF0000:
                        raise ErroCompilacao(f'Linha {n}: tamanho de lista fora do intervalo do gerador nativo.')
                    interno = registrar(str(nome), ('lista', 'inteiro', tamanho), n)
                    adicionar(('crie_lista', interno, tamanho), n, t)
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
                interno = registrar(str(nome), inferido, n)
                adicionar(('atribua', interno, arvore), n, t)
            elif len(t) >= 5 and '[' in t and ']' in t and '=' in t and t.index('[') < t.index(']') < t.index('='):
                igual = t.index('=')
                nome, indice, tamanho = indice_lista(t[:igual], n)
                valor, _ = expressao_tipada(t[igual+1:], n, 'inteiro')
                adicionar(('atribua_indice', nome, indice, valor, tamanho), n, t)
            elif len(t) >= 3 and t[1] == '=':
                nome = contexto.resolver(str(t[0]))
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
    programa = Programa(instrucoes, variaveis, importa, tipos,
                        escopos_locais=contexto.usou_locais)
    if _retorno is not None:
        def retorna_em_todos_caminhos(bloco):
            for instrucao in bloco:
                if instrucao[0] == 'retorne':
                    return True
                if instrucao[0] == 'se' and instrucao[3] and (retorna_em_todos_caminhos(instrucao[2])
                                                             and retorna_em_todos_caminhos(instrucao[3])):
                    return True
            return False
        if not retorna_em_todos_caminhos(instrucoes):
            raise ErroCompilacao(f'Linha {normalizadas[0][0]}: função deve retornar um valor em todos os caminhos.')
        return programa
    for nome, parametros, retorno, n, corpo in definicoes:
        ctx = ContextoSemantico(importa, assinaturas)
        internos = []
        for variavel, tipo in parametros:
            if variavel in reservadas:
                raise ErroCompilacao(f'Linha {n}: parâmetro usa palavra reservada: {variavel}.')
            internos.append((ctx.registrar(variavel, tipo, n), tipo))
        corpo_funcao = analisar_programa('', _linhas=[(n, ['inicio', '{'])] + corpo,
                                         _contexto=ctx, _assinaturas=assinaturas,
                                         _retorno=retorno)
        programa.funcoes[nome] = Funcao(nome, tuple(internos), retorno, corpo_funcao)
    # Chamadas recursivas serão introduzidas com controle explícito de
    # profundidade e sondagem dos quadros em cada chamada. Nesta etapa,
    # rejeitamos ciclos, inclusive indiretos, em vez de arriscar esgotar pilha.
    def chamadas_expressao(expr):
        if not isinstance(expr, tuple):
            return set()
        tag = expr[0]
        if tag == 'chamada':
            nomes = {expr[1]}
            for argumento in expr[2]:
                nomes |= chamadas_expressao(argumento)
            return nomes
        if tag == 'neg':
            return chamadas_expressao(expr[1])
        if tag in ('bin', 'comparacao'):
            return chamadas_expressao(expr[2]) | chamadas_expressao(expr[3])
        if tag == 'indice':
            return chamadas_expressao(expr[2])
        return set()

    def chamadas_bloco(bloco):
        nomes = set()
        for instrucao in bloco:
            tag = instrucao[0]
            if tag in ('atribua', 'atribua_indice', 'imprima_num', 'retorne'):
                expressoes = ((instrucao[2],) if tag == 'atribua' else
                             (instrucao[2], instrucao[3]) if tag == 'atribua_indice' else
                             (instrucao[1],))
                for expressao in expressoes:
                    nomes |= chamadas_expressao(expressao)
            if tag in ('se', 'enquanto', 'para'):
                expressoes = ((instrucao[1],) if tag != 'para' else (instrucao[2], instrucao[3]))
                for expressao in expressoes:
                    nomes |= chamadas_expressao(expressao)
                if tag == 'se':
                    nomes |= chamadas_bloco(instrucao[2]) | chamadas_bloco(instrucao[3])
                else:
                    nomes |= chamadas_bloco(instrucao[2] if tag == 'enquanto' else instrucao[5])
        return nomes

    dependencias = {nome: chamadas_bloco(funcao.programa.instrucoes)
                    for nome, funcao in programa.funcoes.items()}
    visitados, ativos = set(), set()
    def verificar_ciclos(nome):
        if nome in ativos:
            raise ErroCompilacao(f'Função {nome!r}: recursão ainda indisponível nesta versão.')
        if nome in visitados:
            return
        ativos.add(nome)
        for destino in dependencias[nome]:
            verificar_ciclos(destino)
        ativos.remove(nome)
        visitados.add(nome)
    for nome in dependencias:
        verificar_ciclos(nome)
    return programa
