"""Grafo de fluxo de controle (CFG) da IR tipada da RS 0.10.

CFG somente para análise/depuração: não reordena instruções nem altera o
backend nativo. O levantamento inclui saída de laços via pare/continue.
"""
from collections import deque
from dataclasses import dataclass
from .nos_ir import ExpressaoIR, InstrucaoIR, ProgramaIR, FuncaoIR


@dataclass(frozen=True)
class ArestaCFG:
    destino: str
    motivo: str = 'proximo'


@dataclass
class BlocoBasico:
    id: str
    papel: str
    instrucoes: tuple = ()
    saidas: tuple = ()
    origem: object = None


@dataclass
class GrafoCFG:
    blocos: dict
    entrada: str
    saida: str
    nome_funcao: str | None = None
    parametros: tuple = ()
    retorno: str | None = None
    chamadas: tuple = ()

    def tem_curto_circuito(self):
        """O CFG mantém decisões internas de e/ou dentro de ExpressaoIR."""
        pendentes = [x for bloco in self.blocos.values()
                     for instr in bloco.instrucoes for x in instr.argumentos]
        while pendentes:
            no = pendentes.pop()
            if isinstance(no, ExpressaoIR):
                if no.operacao == 'logica':
                    return True
                pendentes.extend(no.filhos)
        return False

    def validar_para_ssa(self):
        if (self.retorno is not None and self.retorno not in ('inteiro', 'logico') or
                any(tipo not in ('inteiro', 'logico') for _, tipo in self.parametros)):
            raise ValueError('SSA de funções requer parâmetros e retorno escalares.')

    def alcancaveis(self):
        visitados = set()
        fila = deque([self.entrada])
        while fila:
            atual = fila.popleft()
            if atual in visitados:
                continue
            visitados.add(atual)
            for aresta in self.blocos[atual].saidas:
                fila.append(aresta.destino)
        return visitados

    def inalcancaveis(self):
        return set(self.blocos) - self.alcancaveis()

    def validar(self):
        assert self.entrada in self.blocos and self.saida in self.blocos
        for bloco in self.blocos.values():
            for aresta in bloco.saidas:
                assert aresta.destino in self.blocos, (bloco.id, aresta.destino)
        return True

    def formatar(self):
        saida = ['RS CFG v1 (analise de fluxo)']
        if self.tem_curto_circuito():
            saida.append('Expressões e/ou preservam curto-circuito na emissão nativa; '
                         'este grafo não expande seus desvios internos.')
        if self.nome_funcao is not None:
            saida.append(f'funcao {self.nome_funcao}: {self.parametros} -> {self.retorno}')
        for ident, bloco in self.blocos.items():
            pos = (f' [linha {bloco.origem.linha}, coluna {bloco.origem.coluna}]'
                   if bloco.origem else '')
            caminhos = ', '.join(f'{a.motivo}->{a.destino}' for a in bloco.saidas) or '(fim)'
            saida.append(f'{ident}: {bloco.papel}{pos} | {caminhos}')
        return '\n'.join(saida)

    def para_dot(self):
        """Emite DOT puro, abrível no Graphviz (sem depender da ferramenta)."""
        def quote(s):
            return '"' + str(s).replace('\\', '\\\\').replace('"', '\\"').replace('\n','\\n') + '"'
        linhas = ['digraph RoteiroSimples {', '  rankdir=TB;', '  node [shape=box, fontname="Arial"];']
        vivos = self.alcancaveis()
        for ident, b in self.blocos.items():
            texto = f'{ident}: {b.papel}'
            if b.origem:
                texto += f'\nlinha {b.origem.linha}:{b.origem.coluna}'
            extra = ', style="dashed"' if ident not in vivos else ''
            linhas.append(f'  {quote(ident)} [label={quote(texto)}{extra}];')
            for a in b.saidas:
                linhas.append(f'  {quote(ident)} -> {quote(a.destino)} [label={quote(a.motivo)}];')
        linhas.append('}')
        return '\n'.join(linhas) + '\n'


def chamadas_instrucao(instr):
    """Chamadas diretas nas expressões, sem duplicar os corpos aninhados."""
    pendentes = list(instr.argumentos)
    nomes = set()
    while pendentes:
        no = pendentes.pop()
        if isinstance(no, ExpressaoIR):
            if no.operacao == 'chamada':
                nomes.add(no.valor)
            pendentes.extend(no.filhos)
    return nomes


def construir_cfg(ir: ProgramaIR):
    """Grafo único histórico; programas com funções exigem grafos separados."""
    if not isinstance(ir, ProgramaIR):
        raise TypeError('CFG recebe ProgramaIR tipado, não AST legada.')
    if ir.funcoes:
        raise ValueError('CFG/SSA de funções exige grafos separados; use construir_cfg_programa.')
    return _construir_cfg(ir)


def construir_cfg_funcao(funcao: FuncaoIR):
    """Parâmetros definidos na entrada; cada retorno vai à saída da função."""
    if not isinstance(funcao, FuncaoIR):
        raise TypeError('CFG de função recebe FuncaoIR tipada.')
    if funcao.programa.funcoes:
        raise ValueError('Corpo de função não pode declarar funções aninhadas na IR.')
    if (funcao.retorno not in ('inteiro', 'logico') or
            any(tipo not in ('inteiro', 'logico') for _, tipo in funcao.parametros) or
            any(tipo not in ('inteiro', 'logico') for tipo in funcao.programa.tipos.values())):
        raise ValueError('CFG de função requer o contrato escalar da IR.')
    nomes = [nome for nome, _ in funcao.parametros]
    if len(set(nomes)) != len(nomes) or any(funcao.programa.tipos.get(nome) != tipo
                                          for nome, tipo in funcao.parametros):
        raise ValueError('Parâmetros incompatíveis com os tipos do corpo da função.')
    return _construir_cfg(funcao.programa, funcao.nome, funcao.parametros, funcao.retorno,
                         incluir_estouro_para=True)


def _construir_cfg(ir, nome_funcao=None, parametros=(), retorno=None, incluir_estouro_para=False):
    """Expande se, enquanto e para em blocos com arestas explícitas."""

    blocos = {}
    contador = 0

    def novo(papel, instr=(), origem=None):
        nonlocal contador
        nome = f'b{contador}'
        contador += 1
        blocos[nome] = BlocoBasico(nome, papel, tuple(instr), (), origem)
        return nome

    def ligacoes(nome, *pares):
        blocos[nome].saidas = tuple(ArestaCFG(destino, motivo) for motivo, destino in pares)

    saida = novo('saida')

    def sequencia(instrucoes, sucessor, laco=None):
        """Construção reversa: cada comando conhece seu sucessor efetivo."""
        proximo = sucessor
        for instr in reversed(instrucoes):
            tag, args = instr.operacao, instr.argumentos
            origem = instr.origem
            if tag == 'retorne':
                if nome_funcao is None:
                    raise ValueError('Análise de retornos de função exige construir_cfg_funcao.')
                if len(args) != 1 or not isinstance(args[0], ExpressaoIR) or args[0].tipo != retorno:
                    raise ValueError('Retorno incompatível com a assinatura da função na IR.')
                nome = novo('retorne', (instr,), origem)
                ligacoes(nome, ('retorne', saida))
            elif tag == 'se':
                nome = novo('se:condicao', (instr,), origem)
                sim = sequencia(args[1], proximo, laco)
                nao = sequencia(args[2], proximo, laco)
                ligacoes(nome, ('verdadeiro', sim), ('falso', nao))
            elif tag == 'enquanto':
                nome = novo('enquanto:condicao', (instr,), origem)
                corpo = sequencia(args[1], nome, (proximo, nome))
                ligacoes(nome, ('verdadeiro', corpo), ('falso', proximo))
            elif tag == 'para':
                inicio = novo('para:inicio', (instr,), origem)
                cond = novo('para:condicao', (instr,), origem)
                incremento = novo('para:incremento', (instr,), origem)
                corpo = sequencia(args[4], incremento, (proximo, incremento))
                ligacoes(inicio, ('proximo', cond))
                ligacoes(cond, ('verdadeiro', corpo), ('falso', proximo))
                if incluir_estouro_para:
                    # O emissor testa overflow ANTES de gravar o contador.
                    gravacao = novo('para:gravar_incremento', (instr,), origem)
                    ligacoes(incremento, ('proximo', gravacao), ('estouro_incremento', proximo))
                    ligacoes(gravacao, ('proximo', cond))
                else:
                    ligacoes(incremento, ('proximo', cond))
                nome = inicio
            elif tag == 'pare':
                if laco is None:
                    raise ValueError('IR com pare fora de um laco.')
                nome = novo('pare', (instr,), origem)
                ligacoes(nome, ('pare', laco[0]))
            elif tag == 'continue':
                if laco is None:
                    raise ValueError('IR com continue fora de um laco.')
                nome = novo('continue', (instr,), origem)
                ligacoes(nome, ('continue', laco[1]))
            else:
                nome = novo(tag, (instr,), origem)
                ligacoes(nome, ('proximo', proximo))
            proximo = nome
        return proximo

    primeiro = sequencia(ir.instrucoes, saida)
    entrada = novo('entrada', tuple(InstrucaoIR('parametro', (nome, tipo))
                                   for nome, tipo in parametros))
    ligacoes(entrada, ('proximo', primeiro))
    # Percorrer começando pela entrada ajuda a leitura humana do CFG.
    ordem = []
    fila = deque([entrada])
    vistos = set()
    while fila:
        item = fila.popleft()
        if item in vistos:
            continue
        vistos.add(item)
        ordem.append(item)
        fila.extend(a.destino for a in blocos[item].saidas)
    ordem.extend(b for b in blocos if b not in vistos)
    renomear = {antigo:f'b{n}' for n,antigo in enumerate(ordem)}
    ordenados = {}
    for velho in ordem:
        bloco = blocos[velho]
        bloco.id = renomear[velho]
        bloco.saidas = tuple(ArestaCFG(renomear[a.destino],a.motivo) for a in bloco.saidas)
        ordenados[bloco.id] = bloco
    cfg = GrafoCFG(ordenados, renomear[entrada], renomear[saida],
                   nome_funcao, tuple(parametros), retorno)
    cfg.chamadas = tuple(sorted(set().union(*(chamadas_instrucao(instr)
        for bid in cfg.alcancaveis() for instr in cfg.blocos[bid].instrucoes))))
    if nome_funcao is not None:
        for bid in cfg.alcancaveis():
            for aresta in cfg.blocos[bid].saidas:
                if aresta.destino == cfg.saida and aresta.motivo != 'retorne':
                    raise ValueError('Função IR pode chegar à saída sem retornar um valor.')
    cfg.validar()
    return cfg


@dataclass
class GrafosProgramaCFG:
    principal: GrafoCFG
    funcoes: dict

    def formatar(self):
        linhas = ['RS 0.42K - CFG do programa e das funções', 'inicio:', self.principal.formatar()]
        for grafo in self.funcoes.values():
            linhas.append(grafo.formatar())
        return '\n'.join(linhas)

    def para_dot(self):
        # Cada subgrafo possui IDs próprios; prefixos evitam colisão entre b0.
        linhas = ['digraph RoteiroSimples {', '  rankdir=TB;']
        for numero, (nome, grafo) in enumerate([('inicio', self.principal), *self.funcoes.items()]):
            linhas.extend((f'  subgraph cluster_{numero} {{', f'    label="{nome}";'))
            for linha in grafo.para_dot().splitlines()[1:-1]:
                for bid in sorted(grafo.blocos, key=len, reverse=True):
                    linha = linha.replace(f'"{bid}"', f'"g{numero}_{bid}"')
                linhas.append('  ' + linha)
            linhas.append('  }')
        linhas.append('}')
        return '\n'.join(linhas) + '\n'


def construir_cfg_programa(ir: ProgramaIR):
    if not isinstance(ir, ProgramaIR):
        raise TypeError('CFG recebe ProgramaIR tipado, não AST legada.')
    if ir.funcoes and any(tipo not in ('inteiro', 'logico') for tipo in ir.tipos.values()):
        raise ValueError('CFG do programa com funções requer o contrato escalar da IR.')
    if any(nome != funcao.nome for nome, funcao in ir.funcoes.items()):
        raise ValueError('Nome de função incompatível com a chave do programa IR.')
    return GrafosProgramaCFG(_construir_cfg(ir, incluir_estouro_para=True),
        {nome: construir_cfg_funcao(funcao) for nome, funcao in ir.funcoes.items()})
