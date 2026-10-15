"""RS 0.42L: SSA independente de cada função escalar e do início."""
from dataclasses import dataclass
import json

from .cfg import construir_cfg_programa, construir_cfg_funcao
from .nos_ir import ExpressaoIR, GrupoFuncoesIR
from .ssa import construir_ssa
from .ssa_baixamento import formatar_copias_phi
from .medicao_compilacao import etapa


@dataclass
class SSAPrograma:
    principal: object
    funcoes: dict
    assinaturas: dict

    def validar(self):
        for ssa in (*((self.principal,) if self.principal is not None else ()), *self.funcoes.values()):
            ssa.validar()
            for bloco in ssa.blocos.values():
                if not bloco.alcancavel:
                    continue
                for instr in bloco.instrucoes:
                    pendentes = list(instr.argumentos)
                    while pendentes:
                        expr = pendentes.pop()
                        if not isinstance(expr, ExpressaoIR):
                            continue
                        if expr.operacao == 'chamada':
                            assinatura = self.assinaturas.get(expr.valor)
                            if assinatura is None:
                                raise ValueError(f'Chamada SSA sem assinatura: {expr.valor}.')
                            if (expr.tipo != assinatura.retorno or
                                    tuple(f.tipo for f in expr.filhos) != tuple(t for _, t in assinatura.parametros)):
                                raise ValueError(f'Chamada SSA incompatível com a assinatura: {expr.valor}.')
                        pendentes.extend(expr.filhos)
        return True

    def formatar(self):
        linhas = ['RS 0.42U - SSA por função escalar']
        linhas.extend(('inicio:', self.principal.formatar()) if self.principal is not None else
                      ('Análise parcial: início conservador não representado.',))
        for nome, ssa in self.funcoes.items():
            f = self.assinaturas[nome]
            linhas.extend((f'funcao {nome}: {f.parametros} -> {f.retorno}; recursiva={f.recursiva}', ssa.formatar()))
        return '\n'.join(linhas)

    def para_json(self):
        return json.dumps({'versao': 'RS 0.42U',
                           'modo': ('SSA parcial; somente funções escalares elegíveis' if self.principal is None else
                                    'SSA por função; emissão nativa com alocação em O4–O8'),
                           'principal': json.loads(self.principal.para_json()) if self.principal is not None else None,
                           'funcoes': {nome: {**json.loads(ssa.para_json()),
                                              'parametros': f.parametros, 'retorno': f.retorno,
                                              'recursiva': f.recursiva}
                                       for nome, ssa in self.funcoes.items()
                                       for f in (self.assinaturas[nome],)}}, ensure_ascii=False, indent=2) + '\n'

    def formatar_copias(self):
        linhas = (['inicio:', formatar_copias_phi(self.principal)] if self.principal is not None else
                  ['Análise parcial: início conservador não representado.'])
        for nome, ssa in self.funcoes.items():
            linhas.extend((f'funcao {nome}:', formatar_copias_phi(ssa)))
        return '\n'.join(linhas)


def construir_ssa_programa(ir, grafos=None, medidor=None):
    grafos = grafos or construir_cfg_programa(ir)
    programa = SSAPrograma(construir_ssa(grafos.principal, medidor=medidor),
                           {nome: construir_ssa(cfg, medidor=medidor) for nome, cfg in grafos.funcoes.items()}, ir.funcoes)
    with etapa(medidor, 'ssa_validacao_programa'):
        programa.validar()
    return programa


def construir_ssa_funcoes(grupo, medidor=None):
    """SSA parcial, com validação de assinaturas do grupo fechado."""
    if not isinstance(grupo, GrupoFuncoesIR):
        raise TypeError('SSA parcial recebe GrupoFuncoesIR tipado.')
    if any(nome != f.nome for nome, f in grupo.funcoes.items()):
        raise ValueError('Nome de função incompatível com a chave do grupo IR.')
    with etapa(medidor, 'cfg_funcoes_mistas'):
        grafos = {nome: construir_cfg_funcao(f) for nome, f in grupo.funcoes.items()}
    with etapa(medidor, 'ssa_funcoes_mistas'):
        programa = SSAPrograma(None, {nome: construir_ssa(cfg, medidor=medidor)
                                     for nome, cfg in grafos.items()}, grupo.funcoes)
    with etapa(medidor, 'ssa_validacao_programa'):
        programa.validar()
    return programa
