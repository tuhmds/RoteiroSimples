"""RS 0.42L: SSA independente de cada função escalar e do início."""
from dataclasses import dataclass
import json

from .cfg import construir_cfg_programa
from .nos_ir import ExpressaoIR
from .ssa import construir_ssa
from .ssa_baixamento import formatar_copias_phi


@dataclass
class SSAPrograma:
    principal: object
    funcoes: dict
    assinaturas: dict

    def validar(self):
        for ssa in (self.principal, *self.funcoes.values()):
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
        linhas = ['RS 0.42N - SSA por função escalar', 'inicio:', self.principal.formatar()]
        for nome, ssa in self.funcoes.items():
            f = self.assinaturas[nome]
            linhas.extend((f'funcao {nome}: {f.parametros} -> {f.retorno}; recursiva={f.recursiva}', ssa.formatar()))
        return '\n'.join(linhas)

    def para_json(self):
        return json.dumps({'versao': 'RS 0.42N',
                           'modo': 'SSA por função; emissão nativa com alocação em O4–O8',
                           'principal': json.loads(self.principal.para_json()),
                           'funcoes': {nome: {**json.loads(ssa.para_json()),
                                              'parametros': f.parametros, 'retorno': f.retorno,
                                              'recursiva': f.recursiva}
                                       for nome, ssa in self.funcoes.items()
                                       for f in (self.assinaturas[nome],)}}, ensure_ascii=False, indent=2) + '\n'

    def formatar_copias(self):
        linhas = ['inicio:', formatar_copias_phi(self.principal)]
        for nome, ssa in self.funcoes.items():
            linhas.extend((f'funcao {nome}:', formatar_copias_phi(ssa)))
        return '\n'.join(linhas)


def construir_ssa_programa(ir, grafos=None):
    grafos = grafos or construir_cfg_programa(ir)
    programa = SSAPrograma(construir_ssa(grafos.principal),
                           {nome: construir_ssa(cfg) for nome, cfg in grafos.funcoes.items()}, ir.funcoes)
    programa.validar()
    return programa
