"""Construção de SSA *real* sobre o CFG tipado da RS 0.12.

Implementação de análise: renomeação de definições/leituras, colocação pruned
phi com fronteiras de dominância e verificação das arestas. NÃO altera o backend.
"""
from collections import defaultdict
from dataclasses import dataclass, field
import json

from .cfg import GrafoCFG
from .fluxo_dados import analisar_fluxo
from .nos_ir import ExpressaoIR


def _ordenar_bloco(nome):
    return int(nome[1:])


def _fontes(expressao):
    """Versões SSA lidas recursivamente na expressão."""
    if not isinstance(expressao, ExpressaoIR):
        return ()
    if expressao.operacao == 'var':
        return (expressao.valor,)
    return tuple(v for filho in expressao.filhos for v in _fontes(filho))


def _usos(argumentos):
    return tuple(v for item in argumentos for v in
                 (_fontes(item) if isinstance(item, ExpressaoIR) else
                  (item,) if isinstance(item, str) and '@' in item else ()))


@dataclass
class PhiSSA:
    variavel: str
    destino: str
    tipo: str
    entradas: dict = field(default_factory=dict)  # predecessor -> versão


@dataclass(frozen=True)
class InstrucaoSSA:
    operacao: str
    destino: str | None
    argumentos: tuple
    usos: tuple
    origem: object = None


@dataclass
class BlocoSSA:
    id: str
    papel: str
    phis: dict = field(default_factory=dict)  # nome original -> PhiSSA
    instrucoes: list = field(default_factory=list)
    alcancavel: bool = True


@dataclass
class ProgramaSSA:
    cfg: GrafoCFG
    blocos: dict
    tipos: dict
    dominadores: dict
    idom: dict
    fronteiras: dict
    predecessores: dict

    def validar(self):
        """Confere unicidade, preenchimento dos phis e dominância das leituras."""
        defs = {}
        posicoes = {}
        for bid, bloco in self.blocos.items():
            if not bloco.alcancavel:
                continue
            for phi in bloco.phis.values():
                if phi.destino in defs:
                    raise ValueError(f'Definição SSA duplicada: {phi.destino}')
                defs[phi.destino] = bid
                posicoes[phi.destino] = -1
                if set(phi.entradas) != self.predecessores[bid]:
                    raise ValueError(f'Phi incompleto no bloco {bid}: {phi.destino}')
            for indice, instr in enumerate(bloco.instrucoes):
                if instr.destino:
                    if instr.destino in defs:
                        raise ValueError(f'Definição SSA duplicada: {instr.destino}')
                    defs[instr.destino] = bid
                    posicoes[instr.destino] = indice
        for bid, bloco in self.blocos.items():
            if not bloco.alcancavel:
                continue
            for phi in bloco.phis.values():
                for predecessor, versao in phi.entradas.items():
                    if versao not in defs or defs[versao] not in self.dominadores[predecessor]:
                        raise ValueError(f'Phi {phi.destino} usa {versao} inválido na aresta {predecessor}->{bid}')
                    if versao.split('@')[0] != phi.variavel:
                        raise ValueError(f'Phi {phi.destino} recebeu variável de outro nome: {versao}')
            for indice, instr in enumerate(bloco.instrucoes):
                if instr.usos != _usos(instr.argumentos):
                    raise ValueError(f'Usos SSA incompatíveis com os argumentos em {bid}.')
                for versao in instr.usos:
                    if versao not in defs or defs[versao] not in self.dominadores[bid]:
                        raise ValueError(f'Leitura SSA não dominada: {versao} em {bid}')
                    if defs[versao] == bid and posicoes[versao] >= indice:
                        raise ValueError(f'Leitura SSA antes da definição: {versao} em {bid}')
        return True

    def formatar(self):
        def renderizar(x):
            if isinstance(x, ExpressaoIR):
                if x.operacao in ('numero', 'logico', 'var'):
                    return str(x.valor)
                if x.operacao == 'neg':
                    return '-' + renderizar(x.filhos[0])
                if x.operacao == 'nao':
                    return 'nao(' + renderizar(x.filhos[0]) + ')'
                if x.operacao == 'chamada':
                    return str(x.valor) + '(' + ', '.join(renderizar(f) for f in x.filhos) + ')'
                return '(' + renderizar(x.filhos[0]) + ' ' + str(x.valor) + ' ' + renderizar(x.filhos[1]) + ')'
            return str(x)
        linhas = ['RS 0.12 - SSA tipada (analise, ainda sem baixar para codigo nativo)']
        if self.cfg.nome_funcao is not None or self.cfg.chamadas:
            linhas = ['RS 0.42O - SSA tipada (análise e emissão nativa em O4–O8)']
        if self.cfg.tem_curto_circuito():
            linhas.append('Expressões e/ou: filhos com avaliação por curto-circuito; '
                          'o CFG conserva dependências potenciais dos dois lados.')
        for bid, b in self.blocos.items():
            if not b.alcancavel:
                linhas.append(f'{bid} [{b.papel}] inacessivel')
                continue
            linhas.append(f'{bid} [{b.papel}] idom={self.idom.get(bid) or "-"}')
            for phi in b.phis.values():
                fontes = ', '.join(f'{pred}: {phi.entradas[pred]}' for pred in sorted(phi.entradas, key=_ordenar_bloco))
                linhas.append(f'  {phi.destino}:{phi.tipo} = phi({fontes})')
            for i in b.instrucoes:
                args = ', '.join(renderizar(x) for x in i.argumentos)
                linhas.append(f'  {i.destino + " = " if i.destino else ""}{i.operacao}({args})')
        return '\n'.join(linhas)

    def para_json(self):
        def valor(x):
            if isinstance(x, ExpressaoIR):
                return {'tipo': x.tipo, 'operacao': x.operacao,
                        'valor': x.valor, 'filhos': [valor(f) for f in x.filhos]}
            if isinstance(x, (tuple, list)):
                return [valor(a) for a in x]
            return x
        return json.dumps({
            'versao': 'RS 0.12',
            'modo': 'SSA de analise; o backend ainda utiliza a IR anterior',
            'entrada': self.cfg.entrada, 'saida': self.cfg.saida,
            'tipos': self.tipos,
            'blocos': [
                {'id': bid, 'papel': b.papel, 'alcancavel': b.alcancavel,
                 'idom': self.idom.get(bid),
                 'fronteira_dominancia': sorted(self.fronteiras.get(bid, ()), key=_ordenar_bloco),
                 'phis': [{'variavel': p.variavel, 'tipo': p.tipo, 'destino': p.destino,
                           'entradas': {k: p.entradas[k] for k in sorted(p.entradas, key=_ordenar_bloco)}}
                          for _, p in sorted(b.phis.items())],
                 'instrucoes': [{'operacao': i.operacao, 'destino': i.destino,
                                 'argumentos': valor(i.argumentos), 'usos': list(i.usos)}
                                for i in b.instrucoes]}
                for bid, b in self.blocos.items()
            ]
        }, ensure_ascii=False, indent=2) + '\n'


def construir_ssa(cfg: GrafoCFG) -> ProgramaSSA:
    """Phi pruned via dominance frontiers; renomeação via árvore de dominadores."""
    cfg.validar_para_ssa()
    fluxo = analisar_fluxo(cfg)
    alcancaveis = cfg.alcancaveis()
    preds = {b: set() for b in alcancaveis}
    for bid in alcancaveis:
        for a in cfg.blocos[bid].saidas:
            if a.destino in alcancaveis:
                preds[a.destino].add(bid)
    idom = {cfg.entrada: None}
    for b in sorted(alcancaveis, key=_ordenar_bloco):
        if b == cfg.entrada:
            continue
        candidatos = fluxo.dominadores[b] - {b}
        if not candidatos:
            raise ValueError(f'Sem dominador imediato para {b}')
        idom[b] = max(candidatos, key=lambda x: len(fluxo.dominadores[x]))
    filhos = {b: [] for b in alcancaveis}
    for b, pai in idom.items():
        if pai is not None:
            filhos[pai].append(b)
    for lista in filhos.values():
        lista.sort(key=_ordenar_bloco)

    fronteiras = {b: set() for b in alcancaveis}
    for bloco in alcancaveis:
        if len(preds[bloco]) < 2:
            continue
        for p in preds[bloco]:
            atual = p
            while atual != idom[bloco]:
                fronteiras[atual].add(bloco)
                atual = idom[atual]
                if atual is None:
                    raise ValueError('CFG inconsistente ao calcular fronteiras de dominância.')

    blocos = {bid: BlocoSSA(bid, cfg.blocos[bid].papel, alcancavel=bid in alcancaveis)
              for bid in cfg.blocos}
    tipos = {nome: cfg_tipo(fluxo, nome)
             for nome in sorted(set().union(*(fluxo.definicoes[b] for b in alcancaveis)))}
    incrementos = {bid: f'__rs_incremento_{bid}' for bid in alcancaveis
                   if cfg.blocos[bid].papel == 'para:incremento'
                   and any(a.motivo == 'estouro_incremento' for a in cfg.blocos[bid].saidas)}
    tipos.update({nome: 'inteiro' for nome in incrementos.values()})
    gravacoes = {next(a.destino for a in cfg.blocos[bid].saidas if a.motivo == 'proximo'): nome
                for bid, nome in incrementos.items()}
    definicoes_por_nome = defaultdict(set)
    for bid in alcancaveis:
        for nome in fluxo.definicoes[bid]:
            definicoes_por_nome[nome].add(bid)

    # Posicionamento de phi iterado nas fronteiras de dominância, filtrado por vivacidade.
    for nome in sorted(definicoes_por_nome):
        pendentes = set(definicoes_por_nome[nome])
        usados = set()
        while pendentes:
            x = min(pendentes, key=_ordenar_bloco)
            pendentes.remove(x)
            for y in sorted(fronteiras[x], key=_ordenar_bloco):
                if y in usados or nome not in fluxo.vivos_entrada[y]:
                    continue
                usados.add(y)
                blocos[y].phis[nome] = PhiSSA(nome, '', tipos[nome])
                if y not in definicoes_por_nome[nome]:
                    pendentes.add(y)

    pilhas = defaultdict(list)
    contador = defaultdict(int)

    def nova(nome):
        versao = f'{nome}@{contador[nome]}'
        contador[nome] += 1
        pilhas[nome].append(versao)
        return versao

    def ler(nome):
        if not pilhas[nome]:
            raise ValueError(f'Uso de {nome} antes de definição dominadora na SSA.')
        return pilhas[nome][-1]

    def renomear_expressao(x):
        if not isinstance(x, ExpressaoIR):
            return x
        if x.operacao == 'var':
            return ExpressaoIR(x.tipo, 'var', ler(x.valor), (), x.origem)
        return ExpressaoIR(x.tipo, x.operacao, x.valor,
                           tuple(renomear_expressao(f) for f in x.filhos), x.origem)

    def visitar(bid):
        bb = blocos[bid]
        original = cfg.blocos[bid]
        criadas = []
        for nome in sorted(bb.phis):
            bb.phis[nome].destino = nova(nome)
            criadas.append(nome)
        if original.instrucoes and original.papel == 'entrada':
            for parametro in original.instrucoes:
                if parametro.operacao != 'parametro':
                    raise ValueError('Entrada SSA contém instrução que não define parâmetro.')
                nome, tipo = parametro.argumentos
                destino = nova(nome)
                criadas.append(nome)
                bb.instrucoes.append(InstrucaoSSA('parametro', destino, (nome, tipo), (), parametro.origem))
        if original.instrucoes and original.papel != 'entrada':
            ir = original.instrucoes[0]
            op, a = ir.operacao, ir.argumentos
            funcao = original.papel
            destino, operandos = None, ()
            if funcao == 'para:inicio':
                inicial = renomear_expressao(a[1])
                destino = nova(a[0]); criadas.append(a[0])
                operandos = (inicial,)
            elif funcao == 'para:condicao':
                operandos = (ler(a[0]), renomear_expressao(a[2]), a[3])
            elif funcao == 'para:incremento':
                corrente = ler(a[0])
                nome = incrementos.get(bid, a[0])
                destino = nova(nome); criadas.append(nome)
                operandos = (corrente, a[3])
            elif funcao == 'para:gravar_incremento':
                resultado = ExpressaoIR('inteiro', 'var', ler(gravacoes[bid]), origem=ir.origem)
                destino = nova(a[0]); criadas.append(a[0])
                operandos = (resultado,)
            elif op == 'atribua':
                expr = renomear_expressao(a[1])
                destino = nova(a[0]); criadas.append(a[0])
                operandos = (expr,)
            elif op == 'leia_int':
                destino = nova(a[0])
                criadas.append(a[0])
            elif op in ('imprima_num', 'retorne'):
                operandos = (renomear_expressao(a[0]),)
            elif funcao in ('se:condicao', 'enquanto:condicao'):
                operandos = (renomear_expressao(a[0]),)
            elif op == 'texto':
                operandos = (a[0],)
            elif op not in ('pare', 'continue'):
                raise ValueError(f'Papel não reconhecido na SSA: {funcao}')
            fontes = _usos(operandos)
            bb.instrucoes.append(InstrucaoSSA(funcao, destino, operandos, fontes, ir.origem))
        # Cada aresta recebe exatamente a versão vigente ao sair do bloco.
        for a in original.saidas:
            if a.destino not in alcancaveis:
                continue
            destino_bb = blocos[a.destino]
            for nome, phi in destino_bb.phis.items():
                phi.entradas[bid] = ler(nome)
        return criadas

    # A árvore de dominância pode ser profunda mesmo sem laços aninhados.
    # Percurso iterativo evita esgotar a pilha do compilador Python.
    pendentes = [(cfg.entrada, False, ())]
    while pendentes:
        bid, saindo, criadas = pendentes.pop()
        if saindo:
            for nome in reversed(criadas):
                pilhas[nome].pop()
            continue
        criadas = visitar(bid)
        pendentes.append((bid, True, criadas))
        for filho in reversed(filhos[bid]):
            pendentes.append((filho, False, ()))
    ssa = ProgramaSSA(cfg, blocos, tipos,
                      fluxo.dominadores, idom, fronteiras, preds)
    # Tipo de cada phi é mantido no próprio nó; os tipos vêm da IR.
    ssa.validar()
    return ssa


def cfg_tipo(fluxo, nome):
    """Determina o tipo do identificador com base nas instruções da IR."""
    for bloco in fluxo.cfg.blocos.values():
        for instr in bloco.instrucoes:
            op, a = instr.operacao, instr.argumentos
            if op == 'atribua' and a[0] == nome:
                return a[1].tipo
            if op == 'parametro' and a[0] == nome:
                return a[1]
            if bloco.papel.startswith('para:') and a[0] == nome:
                return 'inteiro'
            if op == 'leia_int' and a[0] == nome:
                return 'inteiro'
    raise ValueError(f'Tipo da variável {nome} não encontrado.')
