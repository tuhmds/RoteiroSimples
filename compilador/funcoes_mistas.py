"""Contrato escalar fechado para funções em programas com recursos não IR."""
from collections import deque

from .cobertura_intermediaria import (
    analisar_cobertura, motivos_de_cobertura, EXPRESSOES_DA_INSTRUCAO,
    BLOCOS_DA_INSTRUCAO,
)
from .erros import ErroCompilacao
from .medicao_compilacao import etapa
from .nos_ir import FuncaoIR, GrupoFuncoesIR


def chamadas_do_corpo(corpo):
    """Consulta todas as chamadas, inclusive em argumentos e trechos inacessíveis."""
    chamadas = set()

    def expressao(no):
        if no[0] == 'chamada':
            chamadas.add(no[1])
            for filho in no[2]:
                expressao(filho)
        elif no[0] in ('neg', 'nao'):
            expressao(no[1])
        elif no[0] in ('bin', 'comparacao', 'logica'):
            expressao(no[2])
            expressao(no[3])
        elif no[0] == 'indice':
            expressao(no[2])

    def bloco(instrucoes):
        for no in instrucoes:
            for indice in EXPRESSOES_DA_INSTRUCAO.get(no[0], ()):
                expressao(no[indice])
            for indice in BLOCOS_DA_INSTRUCAO.get(no[0], ()):
                bloco(no[indice])
    bloco(corpo.instrucoes)
    return tuple(sorted(chamadas))


def _analisar_funcao(funcao):
    """Reúne restrições locais e chamadas antes de examinar as dependências."""
    restricoes = []
    escalares = ('inteiro', 'logico')
    if funcao.programa.funcoes:
        restricoes.append('funções aninhadas fora do contrato escalar')
    if funcao.retorno not in escalares:
        restricoes.append('retorno fora do contrato inteiro/logico')
    if any(tipo not in escalares for _, tipo in funcao.parametros):
        restricoes.append('parâmetros fora do contrato inteiro/logico')
    if any(tipo not in escalares for tipo in funcao.programa.tipos.values()):
        restricoes.append('variáveis locais fora do contrato inteiro/logico')
    cobertura = analisar_cobertura(funcao.programa)
    restricoes.extend(motivos_de_cobertura(cobertura))
    chamadas = chamadas_do_corpo(funcao.programa) if cobertura.completa else ()
    return restricoes, chamadas


def _propagar_recusas(motivos, dependentes):
    """Recusa os chamadores transitivos, preservando ciclos sem restrições."""
    recusadas = {nome for nome, restricoes in motivos.items() if restricoes}
    pendentes = deque(nome for nome in motivos if nome in recusadas)
    while pendentes:
        for dependente in dependentes[pendentes.popleft()]:
            if dependente not in recusadas:
                recusadas.add(dependente)
                pendentes.append(dependente)
    return recusadas


def classificar_funcoes(programa):
    """Elimina dependências de corpos não escalares sem excluir ciclos elegíveis."""
    funcoes = programa.funcoes
    motivos = {}
    chamadas = {}
    dependentes = {nome: [] for nome in funcoes}
    for nome, funcao in funcoes.items():
        restricoes, chamadas_da_funcao = _analisar_funcao(funcao)
        chamadas[nome] = chamadas_da_funcao
        for chamada in chamadas_da_funcao:
            if chamada in dependentes:
                dependentes[chamada].append(nome)
            else:
                restricoes.append(f'chamada sem assinatura conhecida: {chamada}')
        motivos[nome] = tuple(restricoes)

    recusadas = _propagar_recusas(motivos, dependentes)
    classificacao = {}
    for nome in funcoes:
        dependencias_recusadas = tuple(
            f'chamada fora do grupo escalar elegível: {chamada}'
            for chamada in chamadas[nome]
            if chamada in recusadas
        )
        classificacao[nome] = motivos[nome] + dependencias_recusadas
    return classificacao


def construir_ir_funcoes(programa, nomes, otimizar=True, nivel=3, medidor=None):
    """IR parcial explícita: não inventa um corpo para o início conservador."""
    from .ir import converter_corpo_ir
    if not 0 <= nivel <= 3:
        raise ValueError('A IR de funções escalares aceita níveis de 0 a 3.')
    nomes = tuple(nomes)
    classificacao = classificar_funcoes(programa)
    if not nomes or len(set(nomes)) != len(nomes):
        raise ErroCompilacao('Grupo de funções IR contém função ausente ou não elegível.')
    for nome in nomes:
        if nome not in classificacao or classificacao[nome]:
            raise ErroCompilacao('Grupo de funções IR contém função ausente ou não elegível.')

    selecionadas = set(nomes)
    for nome in nomes:
        chamadas = chamadas_do_corpo(programa.funcoes[nome].programa)
        if set(chamadas) - selecionadas:
            raise ErroCompilacao('Grupo de funções IR não contém todas as funções chamadas.')

    assinaturas = {}
    for nome in nomes:
        funcao = programa.funcoes[nome]
        assinaturas[nome] = (funcao.parametros, funcao.retorno)
    with etapa(medidor, 'ir_conversao_funcoes_mistas'):
        funcoes_ir = {}
        for nome in nomes:
            funcao = programa.funcoes[nome]
            corpo_ir = converter_corpo_ir(
                funcao.programa, assinaturas, otimizar, nivel, True, medidor
            )
            funcoes_ir[nome] = FuncaoIR(
                nome, funcao.parametros, funcao.retorno, corpo_ir, funcao.recursiva
            )
        grupo = GrupoFuncoesIR(funcoes_ir)
    if otimizar and nivel >= 3:
        from .otimizacao_funcoes_ssa import otimizar_grupo_funcoes
        with etapa(medidor, 'ir_otimizacao_funcoes_mistas'):
            grupo = otimizar_grupo_funcoes(grupo, medidor)
    return grupo
