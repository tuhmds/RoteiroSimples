"""RS 0.42L: emissão SSA por quadro, preservando a convenção interna RS."""
from dataclasses import dataclass, replace

from compilador.alocacao import Local, alocar_registradores
from compilador.ir import programa_para_backend
from compilador.ssa_funcoes import construir_ssa_programa
from .ssa_x86_64 import emissor_ssa
from .x86_64 import montar_codigo
from compilador.cfg import construir_cfg_programa
from compilador.medicao_compilacao import etapa


@dataclass
class BackendFuncoesSSA:
    programa: object
    alocacoes: dict

    def relatorio(self):
        linhas = ['RS 0.42S - alocação por função (r13/r14/r15 preservados nas chamadas)']
        for nome, aloc in self.alocacoes.items():
            linhas.extend((f'{nome}:', aloc.relatorio()))
        return '\n'.join(linhas)


def construir_backend_funcoes_ssa(ir, coalescer=False, medidor=None):
    with etapa(medidor, 'cfg_funcoes'):
        grafos = construir_cfg_programa(ir)
    with etapa(medidor, 'ssa_funcoes'):
        programa = construir_ssa_programa(ir, grafos, medidor=medidor)
    # O montador destes quadros aplica sondagem e o limite global de 768 KiB.
    # O limite antigo de 256 vagas continua no caminho SSA sem funções.
    with etapa(medidor, 'alocacao_registradores'):
        alocacoes = {'inicio': alocar_registradores(programa.principal, coalescer=coalescer, limite_vagas=None)}
        alocacoes.update({nome: alocar_registradores(ssa, coalescer=coalescer, limite_vagas=None)
                         for nome, ssa in programa.funcoes.items()})
    if medidor is not None:
        medidor.contar('blocos_cfg', len(grafos.principal.blocos) + sum(len(g.blocos) for g in grafos.funcoes.values()))
        medidor.contar('vagas_pilha', sum(a.vagas_pilha for a in alocacoes.values()))
    return BackendFuncoesSSA(programa, alocacoes)


def montar_funcoes_ssa(ir, windows, nivel=4, medidor=None):
    plano = construir_backend_funcoes_ssa(ir, coalescer=nivel >= 6, medidor=medidor)
    with etapa(medidor, 'preparacao_emissor_funcoes'):
        legado, principal, emissores = _preparar_emissores(ir, plano, windows, nivel)
    with etapa(medidor, 'emissao_nativa'):
        return montar_codigo(legado, windows, principal, emissores)


def _preparar_emissores(ir, plano, windows, nivel):
    legado = programa_para_backend(ir)
    principal = plano.alocacoes['inicio']
    legado.variaveis = {f'__rs_ssa_vaga_{n}': n for n in range(principal.vagas_pilha + 1)}
    emissores = {}
    for nome, ssa in plano.programa.funcoes.items():
        funcao = legado.funcoes[nome]
        aloc = plano.alocacoes[nome]
        emissores[nome] = preparar_emissor_funcao(funcao, ir.funcoes[nome], ssa, aloc, windows, nivel)
    return legado, emissor_ssa(ir, plano.programa.principal, principal,
        otimizar_layout=nivel >= 5, otimizar_copias=nivel >= 6, saltos_curtos=nivel >= 6,
        prefixo='ssa_inicio_'), emissores


def preparar_emissor_funcao(funcao, funcao_ir, ssa, aloc, windows, nivel):
    """Quadro e salvamentos comuns à emissão completa e à emissão mista."""
    nome = funcao.nome
    casas = {parametro: n for n, (parametro, _) in enumerate(funcao.parametros)}
    deslocamento = len(casas)
    locais = {v: Local('pilha', loc.indice + deslocamento) if loc.classe == 'pilha' else loc
              for v, loc in aloc.locais.items()}
    fim = deslocamento + aloc.vagas_pilha + 1  # reserva temporário de cópias
    salvamentos = {reg: fim + n for n, reg in enumerate(sorted(
        {loc.indice for loc in locais.values() if loc.classe == 'reg'}))} if not windows else {}
    total = fim + len(salvamentos)
    funcao.programa.variaveis = {**casas, **{f'__rs_ssa_vaga_{n}': n for n in range(deslocamento, total)}}
    aloc = replace(aloc, locais=locais, vagas_pilha=deslocamento + aloc.vagas_pilha)
    return emissor_ssa(funcao_ir.programa, ssa, aloc,
        otimizar_layout=nivel >= 5, otimizar_copias=nivel >= 6, saltos_curtos=nivel >= 6,
        prefixo=f'ssa_funcao_{nome}_', salvamentos_linux=salvamentos)
