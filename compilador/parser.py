"""Análise de blocos, declarações e instruções da linguagem."""
import json
import re
from .ast import Programa, Funcao, NoInstrucao, PosicaoFonte
from .erros import ErroCompilacao
from .lexico import tokens
from .semantica import ContextoSemantico

def analisar_programa(fonte, _linhas=None, _contexto=None, _assinaturas=None, _retorno=None, _registros=None):
    # O analisador público também compreende resultados genéricos, e não só
    # a interface de linha de comando. Isso mantém a integração com testes,
    # ferramentas e compiladores que invocam analisar_programa diretamente.
    if (_linhas is None and _contexto is None and _assinaturas is None and
            _retorno is None and re.search(r'\b(?:resultado|sucesso|falha)\s*\[|\bpropague\b', fonte)):
        from pathlib import Path
        from .modulos import FontesReunidas, OrigemLinha
        from .resultados_genericos import preparar_resultados_genericos
        origens = tuple(OrigemLinha(Path('<codigo_rs>'), numero, texto)
                        for numero, texto in enumerate(fonte.splitlines(), 1))
        preparados = preparar_resultados_genericos(FontesReunidas(fonte, origens, ()))
        if preparados.texto != fonte:
            return analisar_programa(preparados.texto)
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
    registros = (_registros if _registros is not None else {})
    if _linhas is None:
        while linhas and linhas[0][1] and linhas[0][1][0] == 'tipo':
            n, cab = linhas.pop(0)
            if len(cab) != 3 or cab[2] != '{' or not re.fullmatch(r'[A-Za-z_][A-Za-z_0-9]*', cab[1]):
                raise ErroCompilacao(f'Linha {n}: use tipo Nome {{.')
            nome_tipo = str(cab[1])
            if nome_tipo in registros or nome_tipo in ('inteiro', 'logico', 'texto', 'bytes', 'lista', 'emprestimo', 'empreste', 'seja', 'se', 'senao', 'inicio', 'funcao', 'retorne', 'para', 'enquanto', 'tipo', 'leia', 'escreva') or nome_tipo.startswith('__rs_'):
                raise ErroCompilacao(f'Linha {n}: nome de tipo duplicado ou reservado.')
            campos = []
            while linhas and linhas[0][1] != ['}']:
                n_campo, t = linhas.pop(0)
                if (len(t) < 3 or t[1] != ':' or
                        not re.fullmatch(r'[A-Za-z_][A-Za-z_0-9]*', t[0])):
                    raise ErroCompilacao(f'Linha {n_campo}: declare campo: tipo.')
                parte_tipo = t[2:]
                if len(parte_tipo) == 1:
                    tipo_campo = str(parte_tipo[0])
                    if tipo_campo not in ('inteiro', 'logico') and tipo_campo not in registros:
                        raise ErroCompilacao(f'Linha {n_campo}: tipo de campo desconhecido: {tipo_campo}.')
                elif (len(parte_tipo) == 4 and parte_tipo[0] in ('lista', 'texto', 'bytes')
                      and parte_tipo[1] == '[' and parte_tipo[-1] == ']'
                      and parte_tipo[2].isascii() and parte_tipo[2].isdecimal()):
                    capacidade = int(parte_tipo[2])
                    if not 1 <= capacidade < 0x0FFF0000:
                        raise ErroCompilacao(f'Linha {n_campo}: tamanho de campo fora do intervalo do gerador.')
                    tipo_campo = (('lista', 'inteiro', capacidade) if parte_tipo[0] == 'lista'
                                  else (parte_tipo[0], capacidade))
                else:
                    raise ErroCompilacao(f'Linha {n_campo}: tipo de campo inválido.')
                if t[0] in (c for c, _ in campos):
                    raise ErroCompilacao(f'Linha {n_campo}: campo {t[0]!r} duplicado.')
                campos.append((str(t[0]), tipo_campo))
            if not linhas:
                raise ErroCompilacao(f'Linha {n}: registro {nome_tipo!r} sem fechamento.')
            linhas.pop(0)
            if not campos:
                raise ErroCompilacao(f'Linha {n}: registro precisa de pelo menos um campo.')
            registros[nome_tipo] = tuple(campos)
    def ler_tipo(partes, linha):
        if len(partes) == 1:
            nome = str(partes[0])
            if nome in ('inteiro', 'logico') or nome in registros:
                return nome
        if len(partes) == 4 and partes == ['emprestimo', '[', 'lista', ']']:
            return ('lista_emprestada', 'inteiro')
        if (len(partes) == 7 and partes[:4] == ['emprestimo', '[', 'lista', '[']
                and partes[-2:] == [']', ']'] and (partes[4] in ('inteiro', 'logico') or partes[4] in registros)):
            return ('lista_emprestada', str(partes[4]))
        if len(partes) == 4 and partes[1] == '[' and partes[3] == ']':
            categoria = str(partes[0])
            valor = str(partes[2])
            if categoria == 'lista' and (valor in ('inteiro', 'logico') or valor in registros):
                return ('lista_dinamica', valor)
            if categoria in ('lista', 'texto', 'bytes') and valor.isascii() and valor.isdecimal():
                tamanho = int(valor)
                if not 1 <= tamanho < 0x0FFF0000:
                    raise ErroCompilacao(f'Linha {linha}: capacidade fora dos limites de endereçamento.')
                return ('lista', 'inteiro', tamanho) if categoria == 'lista' else (categoria, tamanho)
        raise ErroCompilacao(f'Linha {linha}: tipo inválido; use inteiro, logico, registro, lista[N], texto[N] ou bytes[N].')

    def eh_composto(tipo):
        return isinstance(tipo, tuple) or tipo in registros

    definicoes = []
    assinaturas = _assinaturas if _assinaturas is not None else {}
    if _linhas is None:
        while linhas and linhas[0][1] and linhas[0][1][0] == 'funcao':
            n, cabecalho = linhas[0]
            if len(cabecalho) < 8 or cabecalho[2] != '(' or ')' not in cabecalho:
                raise ErroCompilacao(f'Linha {n}: cabeçalho de função inválido.')
            nome = str(cabecalho[1])
            if not re.fullmatch(r'[A-Za-z_][A-Za-z_0-9]*', nome) or nome in ('inicio', 'seja', 'funcao', 'retorne', 'empreste', 'emprestimo'):
                raise ErroCompilacao(f'Linha {n}: nome de função inválido.')
            fim_par = cabecalho.index(')', 3)
            if cabecalho[fim_par+1:fim_par+3] != ['-', '>'] or cabecalho[-1] != '{':
                raise ErroCompilacao(f'Linha {n}: use funcao nome(parametros) -> tipo {{.')
            retorno = ler_tipo(cabecalho[fim_par+3:-1], n)
            if isinstance(retorno, tuple) and retorno[0] == 'lista_emprestada':
                raise ErroCompilacao(f'Linha {n}: emprestimo[lista] so pode aparecer em parametros; nao pode ser retornado.')
            if isinstance(retorno, tuple) and retorno[0] == 'lista_dinamica':
                raise ErroCompilacao(f'Linha {n}: lista dinamica proprietaria nao pode ser retornada por valor.')
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
                    if len(grupo) < 3 or grupo[1] != ':' or not re.fullmatch(r'[A-Za-z_][A-Za-z_0-9]*', grupo[0]):
                        raise ErroCompilacao(f'Linha {n}: use parametro: tipo.')
                    if grupo[0] in (x[0] for x in parametros):
                        raise ErroCompilacao(f'Linha {n}: parâmetro duplicado: {grupo[0]}.')
                    tipo_parametro = ler_tipo(grupo[2:], n)
                    if isinstance(tipo_parametro, tuple) and tipo_parametro[0] == 'lista_dinamica':
                        raise ErroCompilacao(f'Linha {n}: use emprestimo[lista[Tipo]] para receber listas, nao transferencia implicita.')
                    parametros.append((str(grupo[0]), tipo_parametro))
            if nome in assinaturas or nome in registros:
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
    contexto = _contexto or ContextoSemantico(importa, assinaturas, registros)
    variaveis, tipos = contexto.variaveis, contexto.tipos
    expressao_tipada, registrar = contexto.expressao_tipada, contexto.registrar
    reservadas = {'grave_trecho', 'carregue_trecho', 'grave_arquivo', 'carregue_arquivo', 'empreste', 'emprestimo', 'mova', 'adicione', 'remova_ultimo', 'limpe_lista', 'libere', 'importe', 'inicio', 'seja', 'escreva', 'leia', 'inclua', 'se', 'senao', 'enquanto', 'para', 'de', 'ate', 'passo', 'pare', 'continue', 'inteiro', 'logico', 'verdadeiro', 'falso', 'lista', 'tamanho', 'texto', 'bytes', 'capacidade', 'copie', 'junte', 'limpe', 'adicione_byte', 'encerre', 'arquivo', 'abra_arquivo', 'grave_em', 'carregue_de', 'sincronize_arquivo', 'feche_arquivo', 'publique_arquivo', 'bloqueie_arquivo', 'funcao', 'retorne', 'tipo'}

    def indice_lista(partes, linha):
        if '[' not in partes or partes[-1] != ']':
            raise ErroCompilacao(f'Linha {linha}: use lista[indice].')
        posicao = partes.index('[')
        nome = contexto.resolver_caminho(partes[:posicao], linha)
        tipo = tipos.get(nome)
        if isinstance(tipo, tuple) and tipo[0] == 'lista_emprestada':
            raise ErroCompilacao(f'Linha {linha}: emprestimo[lista] permite somente leitura; nao pode ser alterado.')
        if not isinstance(tipo, tuple) or tipo[0] not in ('lista', 'lista_dinamica', 'bytes'):
            raise ErroCompilacao(f'Linha {linha}: caminho não aponta para uma lista.')
        indice, _ = expressao_tipada(partes[posicao+1:-1], linha, 'inteiro')
        return nome, indice, (tipo[2] if tipo[0] == 'lista' else 'bytes' if tipo[0] == 'bytes' else None)

    def texto_destino(partes, linha):
        nome = contexto.resolver_caminho(partes, linha)
        tipo = tipos.get(nome)
        if not isinstance(tipo, tuple) or tipo[0] != 'texto':
            raise ErroCompilacao(f'Linha {linha}: caminho não aponta para um buffer de texto.')
        return nome, tipo[1]

    def texto_origem(partes, linha):
        if len(partes) == 1 and partes[0].startswith('"'):
            try:
                conteudo = json.loads(partes[0])
                bruto = conteudo.encode('utf-8')
            except (ValueError, UnicodeError) as exc:
                raise ErroCompilacao(f'Linha {linha}: literal de texto inválido.') from exc
            return ('literal', conteudo, len(bruto))
        nome, cap = texto_destino(partes, linha)
        return ('buffer', nome, cap)

    def argumentos_externos(tokens_instrucao, linha):
        """Separa parâmetros mantendo chamadas e índices aninhados."""
        grupos = []
        inicio = 2
        nivel_par = nivel_col = 0
        for pos in range(2, len(tokens_instrucao)-1):
            item = tokens_instrucao[pos]
            if item == ',' and nivel_par == 0 and nivel_col == 0:
                grupos.append(tokens_instrucao[inicio:pos])
                inicio = pos+1
            elif item == '(':
                nivel_par += 1
            elif item == ')':
                nivel_par -= 1
            elif item == '[':
                nivel_col += 1
            elif item == ']':
                nivel_col -= 1
            if min(nivel_par,nivel_col) < 0:
                raise ErroCompilacao(f'Linha {linha}: parenteses ou colchetes desequilibrados.')
        grupos.append(tokens_instrucao[inicio:-1])
        if any(not x for x in grupos) or nivel_par or nivel_col:
            raise ErroCompilacao(f'Linha {linha}: argumentos incompletos.')
        return grupos

    def validar_caminho(parte, linha):
        if len(parte) != 1 or not parte[0].startswith('"'):
            raise ErroCompilacao(f'Linha {linha}: nome de arquivo deve ser texto literal.')
        try:
            caminho = json.loads(str(parte[0]))
        except (ValueError, UnicodeError) as exc:
            raise ErroCompilacao(f'Linha {linha}: caminho invalido.') from exc
        if (not isinstance(caminho,str) or not 1 <= len(caminho) <= 240
                or not re.fullmatch(r'[A-Za-z0-9_./-]+',caminho,re.ASCII)
                or caminho.startswith('/') or caminho.endswith('/')
                or any(item in ('','.','..') for item in caminho.split('/'))):
            raise ErroCompilacao(f'Linha {linha}: use caminho relativo ASCII, sem . ou .. como segmento.')
        # Nomes DOS como NUL, CON e COM1 não são arquivos comuns no
        # Windows, mesmo quando terminam com extensões (.rsd etc).
        # Rejeitar também no Linux preserva semântica multiplataforma.
        ultimo = caminho.split('/')[-1].split('.')[0].upper()
        if ultimo in ('CON', 'PRN', 'AUX', 'NUL') or (
                len(ultimo) == 4 and ultimo[:3] in ('COM', 'LPT')
                and ultimo[3] in '123456789'):
            raise ErroCompilacao(f'Linha {linha}: nome de dispositivo reservado: {ultimo}.')
        return caminho

    def recurso_nome(parte, linha):
        if len(parte) != 1:
            raise ErroCompilacao(f'Linha {linha}: recurso deve ser variavel simples do tipo arquivo.')
        nome = contexto.resolver(str(parte[0]))
        if tipos.get(nome) != 'arquivo':
            raise ErroCompilacao(f'Linha {linha}: recurso deve ser variavel do tipo arquivo.')
        return nome

    def estado_nome(parte, linha):
        if len(parte) != 1:
            raise ErroCompilacao(f'Linha {linha}: estado deve ser variavel do tipo inteiro.')
        nome = contexto.resolver(str(parte[0]))
        if tipos.get(nome) != 'inteiro':
            raise ErroCompilacao(f'Linha {linha}: estado deve ser variavel do tipo inteiro.')
        return nome

    def bloco(i, profundidade=0, em_laco=False, pilha_listas=None, limite_laco=None):
        # Cada chamada acompanha os donos de seu bloco léxico.
        pilha_listas = ([] if pilha_listas is None else pilha_listas) + [[]]
        donos_locais = pilha_listas[-1]
        if profundidade:
            contexto.entrar_escopo()
        instrucoes = []

        def adicionar(instruicao, linha, partes):
            instrucao = NoInstrucao(instruicao, PosicaoFonte(linha, partes[0].origem.coluna))
            instrucoes.append(instrucao)
        while i < len(normalizadas):
            n, t = normalizadas[i]
            if t == ['}']:
                if profundidade and donos_locais:
                    adicionar(('libere_escopo_listas', tuple(reversed(donos_locais))), n, t)
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
                if eh_composto(_retorno) and valor[0] not in ('var', 'chamada'):
                    raise ErroCompilacao(f'Linha {n}: retorno composto exige variável ou função do mesmo tipo.')
                adicionar(('retorne', valor), n, t)
                i += 1
                continue
            if _retorno is not None and t[0] == 'leia':
                raise ErroCompilacao(f'Linha {n}: leitura do teclado dentro de funções ainda não está disponível.')
            if len(t) >= 3 and t[0] == 'se'  and t[-1] == '{':
                cond, tipo_condicao = expressao_tipada(t[1:-1], n)
                if tipo_condicao not in ('inteiro', 'logico'):
                    raise ErroCompilacao(f'Linha {n}: condição exige inteiro ou logico.')
                verdadeiro, i = bloco(i+1, profundidade+1, em_laco, pilha_listas, limite_laco)
                falso = []
                if i < len(normalizadas) and normalizadas[i][1] == ['senao', '{']:
                    falso, i = bloco(i+1, profundidade+1, em_laco, pilha_listas, limite_laco)
                adicionar(('se', cond, verdadeiro, falso), n, t)
                continue
            if len(t) >= 3 and t[0] == 'enquanto' and t[-1] == '{':
                cond, tipo_condicao = expressao_tipada(t[1:-1], n)
                if tipo_condicao not in ('inteiro', 'logico'):
                    raise ErroCompilacao(f'Linha {n}: condição exige inteiro ou logico.')
                corpo, i = bloco(i+1, profundidade+1, True, pilha_listas, len(pilha_listas))
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
                corpo, i = bloco(i+1, profundidade+1, True, pilha_listas, len(pilha_listas))
                adicionar(('para', interno, inicial, final, passo, corpo), n, t)
                continue
            if t in (['pare'], ['continue']):
                if not em_laco:
                    raise ErroCompilacao(f"Linha {n}: '{t[0]}' só pode ser usado dentro de um laço.")
                # Libera donos do laço atual e de seus blocos internos.
                donos = [nome for escopo in pilha_listas[limite_laco:] for nome in escopo]
                if donos:
                    adicionar(('libere_escopo_listas', tuple(reversed(donos))), n, t)
                adicionar((t[0],), n, t)
                i += 1
                continue
            if t[:2] == ['leia', '('] and t[-1] == ')':
                destino = t[2:-1]
                if '[' in destino:
                    nome, indice, tamanho = indice_lista(destino, n)
                    if tamanho is None and tipos[nome][1] != 'inteiro':
                        raise ErroCompilacao(f'Linha {n}: leia de lista dinamica so aceita elementos inteiros.')
                    if tamanho is None:
                        adicionar(('leia_indice_dinamico', nome, indice), n, t)
                    else:
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
                if expr and len(expr) % 2 == 1 and all(expr[k] == '.' for k in range(1, len(expr), 2)) and (
                    isinstance(tipos.get(contexto.resolver_caminho(expr, n)), tuple) and
                    tipos[contexto.resolver_caminho(expr, n)][0] == 'texto'):
                    adicionar(('imprima_texto', contexto.resolver_caminho(expr, n)), n, t)
                elif len(expr) == 1 and expr[0].startswith('"'):
                    try:
                        valor = json.loads(expr[0])
                    except (ValueError, UnicodeError) as exc:
                        raise ErroCompilacao(f'Linha {n}: texto inválido.') from exc
                    adicionar(('texto', valor + '\n'), n, t)
                else:
                    arvore, tipo_impresso = expressao_tipada(expr, n)
                    if tipo_impresso not in ('inteiro', 'logico'):
                        raise ErroCompilacao(f'Linha {n}: escreva exige número, lógico ou buffer de texto.')
                    adicionar(('imprima_num', arvore), n, t)
            elif t[0] == 'encerre' and t[1:2] == ['('] and t[-1:] == [')']:
                if len(t) < 4:
                    raise ErroCompilacao(f'Linha {n}: use encerre(codigo_inteiro).')
                codigo, _ = expressao_tipada(t[2:-1], n, 'inteiro')
                adicionar(('encerre', codigo), n, t)
            elif t[0] == 'adicione_byte' and t[1:2] == ['('] and t[-1:] == [')']:
                if t.count(',') != 1:
                    raise ErroCompilacao(f'Linha {n}: use adicione_byte(destino, valor).')
                virgula = t.index(',')
                nome = contexto.resolver_caminho(t[2:virgula], n)
                if not isinstance(tipos.get(nome), tuple) or tipos[nome][0] != 'bytes':
                    raise ErroCompilacao(f'Linha {n}: adicione_byte exige buffer bytes[N].')
                valor, _ = expressao_tipada(t[virgula+1:-1], n, 'inteiro')
                adicionar(('adicione_byte', nome, valor), n, t)
            elif t[0] == 'publique_arquivo' and t[1:2] == ['('] and t[-1:] == [')']:
                grupos = argumentos_externos(t,n)
                if len(grupos) != 3:
                    raise ErroCompilacao(f'Linha {n}: use publique_arquivo("provisorio", "destino", estado).')
                origem = validar_caminho(grupos[0],n)
                destino = validar_caminho(grupos[1],n)
                # Publica no diretorio de execução: restringir a um segmento
                # impede renomeações entre diretorios e volumes diferentes.
                for caminho in (origem,destino):
                    if '/' in caminho or caminho in ('.','..') or not re.fullmatch(
                            r'[A-Za-z0-9_-][A-Za-z0-9_.-]*',caminho,re.ASCII):
                        raise ErroCompilacao(f'Linha {n}: publicacao exige nomes simples no mesmo diretorio.')
                if origem == destino:
                    raise ErroCompilacao(f'Linha {n}: origem e destino devem ser diferentes.')
                estado = estado_nome(grupos[2],n)
                adicionar(('publique_arquivo',origem,destino,estado),n,t)
            elif t[0] in ('abra_arquivo', 'feche_arquivo', 'sincronize_arquivo',
                            'bloqueie_arquivo','grave_em', 'carregue_de') and t[1:2] == ['('] and t[-1:] == [')']:
                grupos = argumentos_externos(t, n)
                comando = str(t[0])
                if comando == 'abra_arquivo':
                    if len(grupos) != 4:
                        raise ErroCompilacao(f'Linha {n}: use abra_arquivo("nome", recurso, "modo", estado).')
                    if len(grupos[0]) == 1 and grupos[0][0].startswith('"'):
                        caminho = validar_caminho(grupos[0], n)
                    else:
                        nome_caminho = contexto.resolver_caminho(grupos[0], n)
                        tipo_caminho = tipos.get(nome_caminho)
                        if not isinstance(tipo_caminho, tuple) or tipo_caminho[0] != 'texto':
                            raise ErroCompilacao(f'Linha {n}: caminho deve ser literal ou variavel texto[N].')
                        caminho = ('caminho_buffer', nome_caminho)
                    recurso = recurso_nome(grupos[1], n)
                    modo_texto = grupos[2]
                    if len(modo_texto) != 1 or not modo_texto[0].startswith('"'):
                        raise ErroCompilacao(f'Linha {n}: modo exige literal "leitura", "alteracao" ou "novo".')
                    try:
                        modo = json.loads(str(modo_texto[0]))
                    except (ValueError, UnicodeError) as exc:
                        raise ErroCompilacao(f'Linha {n}: modo invalido.') from exc
                    if modo not in ('leitura','alteracao','novo'):
                        raise ErroCompilacao(f'Linha {n}: modo deve ser "leitura", "alteracao" ou "novo".')
                    estado = estado_nome(grupos[3], n)
                    adicionar(('abra_recurso', caminho, recurso,
                               {'leitura':0,'alteracao':1,'novo':2}[modo], estado), n,t)
                elif comando in ('feche_arquivo','sincronize_arquivo','bloqueie_arquivo'):
                    if len(grupos) != 2:
                        raise ErroCompilacao(f'Linha {n}: use {comando}(recurso, estado).')
                    recurso = recurso_nome(grupos[0],n)
                    estado = estado_nome(grupos[1],n)
                    adicionar(({'feche_arquivo':'feche_recurso',
                               'sincronize_arquivo':'sincronize_recurso',
                               'bloqueie_arquivo':'bloqueie_recurso'}[comando],recurso,estado),n,t)
                else:
                    gravar = comando == 'grave_em'
                    if len(grupos) != (4 if gravar else 5):
                        raise ErroCompilacao(f'Linha {n}: use {comando}(recurso, bytes, posicao, '
                                             + ('estado).' if gravar else 'quantidade, estado).'))
                    recurso = recurso_nome(grupos[0],n)
                    destino = contexto.resolver_caminho(grupos[1],n)
                    tipo_dado = tipos.get(destino)
                    if not isinstance(tipo_dado,tuple) or tipo_dado[0] != 'bytes':
                        raise ErroCompilacao(f'Linha {n}: {comando} exige bytes[N], não texto.')
                    posicao, _ = expressao_tipada(grupos[2],n,'inteiro')
                    estado = estado_nome(grupos[-1],n)
                    if gravar:
                        adicionar(('grave_em',recurso,destino,posicao,estado),n,t)
                    else:
                        quantidade, _ = expressao_tipada(grupos[3],n,'inteiro')
                        adicionar(('carregue_de',recurso,destino,posicao,quantidade,estado),n,t)
            elif t[0] in ('grave_trecho', 'carregue_trecho') and t[1:2] == ['('] and t[-1:] == [')']:
                # Separa vírgulas exteriores: argumentos numéricos podem
                # conter chamadas com múltiplos parâmetros.
                partes = []
                inicio_parte = 2
                parenteses = 0
                colchetes = 0
                for posicao_token in range(2, len(t) - 1):
                    item = t[posicao_token]
                    if item == ',' and parenteses == 0 and colchetes == 0:
                        partes.append(t[inicio_parte:posicao_token])
                        inicio_parte = posicao_token + 1
                    elif item == '(':
                        parenteses += 1
                    elif item == ')':
                        parenteses -= 1
                    elif item == '[':
                        colchetes += 1
                    elif item == ']':
                        colchetes -= 1
                partes.append(t[inicio_parte:-1])
                gravar = t[0] == 'grave_trecho'
                if (len(partes) != (4 if gravar else 5)
                        or any(not parte for parte in partes)
                        or len(partes[0]) != 1 or not partes[0][0].startswith('"')):
                    raise ErroCompilacao(
                        f'Linha {n}: use {t[0]}("dados.rsd", buffer, posicao, '
                        + ('estado).' if gravar else 'quantidade, estado).'))
                try:
                    caminho = json.loads(str(partes[0][0]))
                except (ValueError, UnicodeError) as exc:
                    raise ErroCompilacao(f'Linha {n}: nome de arquivo invalido.') from exc
                if (not isinstance(caminho, str) or not 1 <= len(caminho) <= 240
                        or not re.fullmatch(r'[A-Za-z0-9_./-]+', caminho, re.ASCII)
                        or caminho.startswith('/') or caminho.endswith('/')
                        or any(parte in ('', '.', '..') for parte in caminho.split('/'))):
                    raise ErroCompilacao(
                        f'Linha {n}: arquivo deve ter caminho relativo ASCII, sem . ou .. como pasta.')
                nome = contexto.resolver_caminho(partes[1], n)
                tipo_buffer = tipos.get(nome)
                if not isinstance(tipo_buffer, tuple) or tipo_buffer[0] not in ('texto', 'bytes'):
                    raise ErroCompilacao(f'Linha {n}: operacao posicional exige texto[N] ou bytes[N].')
                deslocamento, _ = expressao_tipada(partes[2], n, 'inteiro')
                parte_estado = partes[3] if gravar else partes[4]
                if len(parte_estado) != 1:
                    raise ErroCompilacao(f'Linha {n}: estado deve ser variavel inteira.')
                estado = contexto.resolver(str(parte_estado[0]))
                if tipos.get(estado) != 'inteiro':
                    raise ErroCompilacao(f'Linha {n}: estado deve ser variavel inteira declarada.')
                if gravar:
                    adicionar(('grave_trecho', caminho, nome, deslocamento, estado), n, t)
                else:
                    quantidade, _ = expressao_tipada(partes[3], n, 'inteiro')
                    adicionar(('carregue_trecho', caminho, nome, deslocamento, quantidade, estado), n, t)
            elif t[0] in ('grave_arquivo', 'carregue_arquivo') and t[1:2] == ['('] and t[-1:] == [')']:
                if len(t) != 6 or t[3] != ',' or not t[2].startswith('"'):
                    raise ErroCompilacao(f'Linha {n}: use {t[0]}("arquivo.txt", variavel_texto).')
                try:
                    caminho = json.loads(str(t[2]))
                except (ValueError, UnicodeError) as exc:
                    raise ErroCompilacao(f'Linha {n}: nome de arquivo invalido.') from exc
                if (not isinstance(caminho, str) or not 1 <= len(caminho) <= 240
                        or not re.fullmatch(r'[A-Za-z0-9_./-]+', caminho, re.ASCII)
                        or caminho.startswith('/') or caminho.endswith('/')
                        or any(parte in ('', '.', '..') for parte in caminho.split('/'))):
                    raise ErroCompilacao(
                        f'Linha {n}: arquivo deve ter caminho relativo ASCII, sem . ou .. como pasta.')
                nome, _ = texto_destino([t[4]], n)
                adicionar((str(t[0]), caminho, nome), n, t)
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
                nome = contexto.resolver_caminho(t[2:-1], n)
                tipo_buffer = tipos.get(nome)
                if not isinstance(tipo_buffer, tuple) or tipo_buffer[0] not in ('texto', 'bytes'):
                    raise ErroCompilacao(f'Linha {n}: limpe exige texto[N] ou bytes[N].')
                adicionar(('limpe_bytes' if tipo_buffer[0] == 'bytes' else 'limpe_texto', nome), n, t)
            elif t[0] == 'mova' and t[1:2] == ['('] and t[-1:] == [')']:
                partes = t[2:-1]
                if len(partes) != 3 or partes[1] != ',':
                    raise ErroCompilacao(f'Linha {n}: use mova(destino, origem).')
                destino = contexto.resolver(str(partes[0]))
                origem = contexto.resolver(str(partes[2]))
                if destino == origem:
                    raise ErroCompilacao(f'Linha {n}: mova exige origem e destino diferentes.')
                if (not isinstance(tipos.get(destino), tuple) or
                        tipos[destino][0] != 'lista_dinamica' or
                        tipos.get(destino) != tipos.get(origem)):
                    raise ErroCompilacao(f'Linha {n}: mova exige duas listas[] proprietarias.')
                adicionar(('mova_lista_dinamica', destino, origem), n, t)
            elif t[0] in ('adicione', 'remova_ultimo', 'limpe_lista', 'libere') and t[1:2] == ['('] and t[-1:] == [')']:
                operacao = str(t[0])
                conteudo = t[2:-1]
                if operacao == 'adicione':
                    if conteudo.count(',') != 1:
                        raise ErroCompilacao(f'Linha {n}: use adicione(lista, valor).')
                    virgula = conteudo.index(',')
                    nome_parte = conteudo[:virgula]
                    if len(nome_parte) != 1:
                        raise ErroCompilacao(f'Linha {n}: adicione exige nome de lista proprietaria.')
                    nome = contexto.resolver(str(nome_parte[0]))
                    if not isinstance(tipos.get(nome), tuple) or tipos[nome][0] != 'lista_dinamica':
                        raise ErroCompilacao(f'Linha {n}: adicione exige lista dinamica proprietaria.')
                    valor, _ = expressao_tipada(conteudo[virgula+1:], n, tipos[nome][1])
                    if tipos[nome][1] in registros and valor[0] != 'var':
                        raise ErroCompilacao(f'Linha {n}: adicione com registro exige variavel de mesmo tipo.')
                    adicionar(('adicione_lista_dinamica', nome, valor), n, t)
                else:
                    if len(conteudo) != 1:
                        raise ErroCompilacao(f'Linha {n}: {operacao} exige nome de lista proprietaria.')
                    nome = contexto.resolver(str(conteudo[0]))
                    if not isinstance(tipos.get(nome), tuple) or tipos[nome][0] != 'lista_dinamica':
                        raise ErroCompilacao(f'Linha {n}: {operacao} exige lista dinamica proprietaria.')
                    mapa = {'libere': 'libere_lista_dinamica',
                            'limpe_lista': 'limpe_lista_dinamica',
                            'remova_ultimo': 'remova_ultimo_lista_dinamica'}
                    adicionar((mapa[operacao], nome), n, t)
            elif t[0] == 'seja':
                nome = t[1] if len(t) > 1 else ''
                if not re.fullmatch(r'[A-Za-z_][A-Za-z_0-9]*', nome):
                    raise ErroCompilacao(f'Linha {n}: nome de variável inválido.')
                if contexto.declarado_neste_escopo(str(nome)) or nome in reservadas:
                    raise ErroCompilacao(f"Linha {n}: variável '{nome}' duplicada ou reservada.")
                if len(t) >= 4 and t[2:4] == [':', 'emprestimo']:
                    raise ErroCompilacao(f'Linha {n}: emprestimo[lista] so e permitido como parametro de funcao.')
                if (t[2:5] == [':', 'lista', '['] and t[-1:] == [']']
                        and ((len(t) == 6 and t[5] == ']') or
                             (len(t) == 7 and (t[5] in ('inteiro', 'logico') or t[5] in registros)))):
                    elemento = 'inteiro' if len(t) == 6 else str(t[5])
                    interno = registrar(str(nome), ('lista_dinamica', elemento), n)
                    donos_locais.append(interno)
                    adicionar(('crie_lista_dinamica', interno), n, t)
                    i += 1
                    continue
                if t[2:] == [':', 'arquivo']:
                    interno = registrar(str(nome), 'arquivo', n)
                    donos_locais.append(interno)
                    adicionar(('crie_recurso', interno), n, t)
                    i += 1
                    continue
                if len(t) >= 4 and t[2] == ':' and str(t[3]) in registros:
                    tipo_nome = str(t[3])
                    interno = registrar(str(nome), ('registro', tipo_nome, registros[tipo_nome]), n)
                    if len(t) == 4:
                        adicionar(('crie_registro', interno, tuple(contexto.campos_registro[interno].values())), n, t)
                    elif len(t) >= 6 and t[4] == '=':
                        arvore, _ = expressao_tipada(t[5:], n, tipo_nome)
                        if arvore[0] not in ('var', 'chamada', 'indice_lista_dinamica', 'indice_lista_emprestada'):
                            raise ErroCompilacao(f'Linha {n}: registro precisa de origem composta.')
                        adicionar(('copie_composto', interno, arvore), n, t)
                    else:
                        raise ErroCompilacao(f'Linha {n}: declaração de registro inválida.')
                    i += 1
                    continue
                if len(t) >= 7 and t[2:4] == [':', 'bytes'] and t[4] == '[' and t[6] == ']':
                    literal = t[5]
                    if not literal.isascii() or not literal.isdecimal():
                        raise ErroCompilacao(f'Linha {n}: capacidade de bytes deve ser um inteiro constante.')
                    capacidade = int(literal)
                    if not 1 <= capacidade < 0x0FFF0000:
                        raise ErroCompilacao(f'Linha {n}: capacidade de bytes fora do enderecamento nativo.')
                    interno = registrar(str(nome), ('bytes', capacidade), n)
                    if len(t) == 7:
                        adicionar(('crie_bytes', interno, capacidade), n, t)
                    elif len(t) >= 9 and t[7] == '=':
                        arvore, _ = expressao_tipada(t[8:], n, ('bytes', capacidade))
                        if arvore[0] not in ('var', 'chamada'):
                            raise ErroCompilacao(f'Linha {n}: copia de bytes exige variavel ou funcao.')
                        adicionar(('copie_composto', interno, arvore), n, t)
                    else:
                        raise ErroCompilacao(f'Linha {n}: declaracao de bytes invalida.')
                    i += 1
                    continue
                if len(t) >= 7 and t[2:4] == [':', 'texto'] and t[4] == '[' and t[6] == ']':
                    literal = t[5]
                    if not literal.isascii() or not literal.isdecimal():
                        raise ErroCompilacao(f'Linha {n}: capacidade do texto precisa ser um inteiro constante.')
                    capacidade = int(literal)
                    if not 1 <= capacidade < 0x7FFF0000:
                        raise ErroCompilacao(f'Linha {n}: capacidade de texto fora do intervalo do gerador nativo.')
                    interno = registrar(str(nome), ('texto', capacidade), n)
                    if len(t) == 7:
                        adicionar(('crie_texto', interno, capacidade), n, t)
                    elif len(t) >= 9 and t[7] == '=':
                        arvore, _ = expressao_tipada(t[8:], n, ('texto', capacidade))
                        if arvore[0] not in ('var', 'chamada'):
                            raise ErroCompilacao(f'Linha {n}: cópia de texto exige variável ou função.')
                        adicionar(('copie_composto', interno, arvore), n, t)
                    else:
                        raise ErroCompilacao(f'Linha {n}: declaração de texto inválida.')
                    i += 1
                    continue
                if len(t) >= 7 and t[2:4] == [':', 'lista'] and t[4] == '[' and t[6] == ']':
                    tamanho_literal = t[5]
                    if not tamanho_literal.isascii() or not tamanho_literal.isdecimal():
                        raise ErroCompilacao(f'Linha {n}: tamanho da lista deve ser um inteiro constante.')
                    tamanho = int(tamanho_literal)
                    if not 1 <= tamanho < 0x0FFF0000:
                        raise ErroCompilacao(f'Linha {n}: tamanho de lista fora do intervalo do gerador nativo.')
                    interno = registrar(str(nome), ('lista', 'inteiro', tamanho), n)
                    if len(t) == 7:
                        adicionar(('crie_lista', interno, tamanho), n, t)
                    elif len(t) >= 9 and t[7] == '=':
                        arvore, _ = expressao_tipada(t[8:], n, ('lista', 'inteiro', tamanho))
                        if arvore[0] not in ('var', 'chamada'):
                            raise ErroCompilacao(f'Linha {n}: cópia de lista exige variável ou função.')
                        adicionar(('copie_composto', interno, arvore), n, t)
                    else:
                        raise ErroCompilacao(f'Linha {n}: declaração de lista inválida.')
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
                if inferido == 'arquivo':
                    raise ErroCompilacao(f'Linha {n}: recursos arquivo nao podem ser copiados; declare seja nome: arquivo.')
                if isinstance(inferido, tuple) and inferido[0] == 'lista_dinamica':
                    raise ErroCompilacao(f'Linha {n}: lista[] tem dono unico; copiar ou inferir propriedade nao e permitido.')
                if isinstance(inferido, tuple) and inferido[0] == 'lista_emprestada':
                    raise ErroCompilacao(f'Linha {n}: emprestimo[lista] nao pode ser armazenado em variavel local.')
                tipo_armazenado = ('registro', inferido, registros[inferido]) if isinstance(inferido, str) and inferido in registros else inferido
                interno = registrar(str(nome), tipo_armazenado, n)
                if eh_composto(inferido):
                    if arvore[0] not in ('var', 'chamada', 'indice_lista_dinamica', 'indice_lista_emprestada'):
                        raise ErroCompilacao(f'Linha {n}: cópia composta exige variável, função ou índice de lista tipada.')
                    adicionar(('copie_composto', interno, arvore), n, t)
                else:
                    adicionar(('atribua', interno, arvore), n, t)
            elif (len(t) >= 5 and t[1] == '.' and '=' in t and
                  '[' not in t[:t.index('=')]):
                igual = t.index('=')
                campo = contexto.resolver_caminho(t[:igual], n)
                tipo_destino = tipos[campo]
                esperado = (tipo_destino[1] if isinstance(tipo_destino, tuple) and
                            tipo_destino[0] == 'registro' else tipo_destino)
                valor, _ = expressao_tipada(t[igual+1:], n, esperado)
                if eh_composto(tipo_destino):
                    if valor[0] not in ('var', 'chamada'):
                        raise ErroCompilacao(f'Linha {n}: campo composto exige variável ou função.')
                    adicionar(('copie_composto', campo, valor), n, t)
                else:
                    adicionar(('atribua', campo, valor), n, t)
            elif len(t) >= 5 and '[' in t and ']' in t and '=' in t and t.index('[') < t.index(']') < t.index('='):
                igual = t.index('=')
                nome, indice, tamanho = indice_lista(t[:igual], n)
                esperado = tipos[nome][1] if tamanho is None else 'inteiro'
                valor, _ = expressao_tipada(t[igual+1:], n, esperado)
                if tamanho == 'bytes':
                    adicionar(('atribua_byte', nome, indice, valor), n, t)
                elif tamanho is None:
                    if esperado in registros and valor[0] != 'var':
                        raise ErroCompilacao(f'Linha {n}: atribuicao de registro em lista exige variavel.')
                    adicionar(('atribua_indice_dinamico', nome, indice, valor), n, t)
                else:
                    adicionar(('atribua_indice', nome, indice, valor, tamanho), n, t)
            elif len(t) >= 3 and t[1] == '=':
                nome = contexto.resolver(str(t[0]))
                if nome not in variaveis:
                    raise ErroCompilacao(f"Linha {n}: variável '{nome}' não foi declarada.")
                if tipos[nome] == 'arquivo':
                    raise ErroCompilacao(f'Linha {n}: recurso arquivo nao pode ser reatribuido ou copiado.')
                if isinstance(tipos[nome], tuple) and tipos[nome][0] == 'lista_dinamica':
                    raise ErroCompilacao(f'Linha {n}: lista[] possui dono unico e nao admite atribuicao.')
                if isinstance(tipos[nome], tuple) and tipos[nome][0] == 'lista_emprestada':
                    raise ErroCompilacao(f'Linha {n}: parametro emprestimo[lista] nao pode ser reatribuido.')
                esperado = tipos[nome][1] if isinstance(tipos[nome], tuple) and tipos[nome][0] == 'registro' else tipos[nome]
                arvore, _ = expressao_tipada(t[2:], n, esperado)
                if eh_composto(tipos[nome]):
                    if arvore[0] not in ('var', 'chamada', 'indice_lista_dinamica', 'indice_lista_emprestada'):
                        raise ErroCompilacao(f'Linha {n}: atribuição composta exige variável, função ou índice de lista tipada.')
                    adicionar(('copie_composto', nome, arvore), n, t)
                else:
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
                        escopos_locais=contexto.usou_locais, registros=registros,
                        campos_registro=contexto.campos_registro)
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
        ctx = ContextoSemantico(importa, assinaturas, registros)
        internos = []
        for variavel, tipo in parametros:
            if variavel in reservadas:
                raise ErroCompilacao(f'Linha {n}: parâmetro usa palavra reservada: {variavel}.')
            tipo_var = ('registro', tipo, registros[tipo]) if isinstance(tipo, str) and tipo in registros else tipo
            internos.append((ctx.registrar(variavel, tipo_var, n), tipo))
        corpo_funcao = analisar_programa('', _linhas=[(n, ['inicio', '{'])] + corpo,
                                         _contexto=ctx, _assinaturas=assinaturas,
                                         _retorno=retorno, _registros=registros)
        programa.funcoes[nome] = Funcao(nome, tuple(internos), retorno, corpo_funcao)
    # Chamadas recursivas serão introduzidas com controle explícito de
    # profundidade e sondagem dos quadros em cada chamada. Nesta etapa,
    # rejeitamos ciclos, inclusive indiretos, em vez de arriscar esgotar pilha.
    def chamadas_expressao(expr):
        if not isinstance(expr, tuple):
            return set()
        tag = expr[0]
        if tag == 'temporario_composto':
            return chamadas_expressao(expr[2])
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
            if tag in ('atribua', 'copie_composto', 'atribua_indice', 'imprima_num', 'retorne'):
                expressoes = ((instrucao[2],) if tag in ('atribua', 'copie_composto') else
                             (instrucao[2], instrucao[3]) if tag == 'atribua_indice' else
                             (instrucao[1],))
                for expressao in expressoes:
                    nomes |= chamadas_expressao(expressao)
            if tag in ('grave_em', 'carregue_de'):
                expressoes = ((instrucao[3],) if tag == 'grave_em'
                             else (instrucao[3], instrucao[4]))
                for expr in expressoes:
                    nomes |= chamadas_expressao(expr)
            if tag in ('encerre', 'adicione_byte', 'atribua_byte'):
                argumentos = ((instrucao[1],) if tag == 'encerre' else
                              (instrucao[2],) if tag == 'adicione_byte' else
                              (instrucao[2], instrucao[3]))
                for argumento in argumentos:
                    nomes |= chamadas_expressao(argumento)
            if tag in ('grave_trecho', 'carregue_trecho'):
                expressoes = ((instrucao[3],) if tag == 'grave_trecho'
                             else (instrucao[3], instrucao[4]))
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
    # Detecta ciclos diretos e indiretos e habilita proteção de pilha
    # somente nas funções realmente recursivas.
    for nome in dependencias:
        pendentes = list(dependencias[nome])
        visitados = set()
        while pendentes:
            atual = pendentes.pop()
            if atual == nome:
                programa.funcoes[nome].recursiva = True
                break
            if atual not in visitados:
                visitados.add(atual)
                pendentes.extend(dependencias.get(atual, ()))
    return programa
