"""RS 0.42K: fluxo por função escalar, sem transformar o código emitido."""
from dataclasses import dataclass
import json

from .cfg import GrafosProgramaCFG, construir_cfg_programa
from .contrato_efeitos import Efeitos
from .efeitos import efeito_bloco_cfg, resumir_funcoes
from .fluxo_dados import AnaliseFluxo, analisar_fluxo


@dataclass
class FluxoPrograma:
    grafos: GrafosProgramaCFG
    principal: AnaliseFluxo
    funcoes: dict[str, AnaliseFluxo]
    resumos: dict[str, Efeitos]
    recursivas: dict[str, bool]

    def formatar(self):
        linhas = ['RS 0.42K - Fluxo do programa e das funções', 'inicio:', self.principal.formatar()]
        for nome, fluxo in self.funcoes.items():
            linhas.extend((f'funcao {nome}: parâmetros definidos na entrada; '
                           f'retorno {fluxo.cfg.retorno}; recursiva={self.recursivas[nome]}',
                           fluxo.formatar(), f'  efeitos: {self.resumos[nome].para_dict_completo()}'))
        linhas.append('Chamadas preservam ordem, efeitos e verificação de limite seguro de pilha.')
        return '\n'.join(linhas)

    def para_json(self):
        def dados(fluxo):
            documento = json.loads(fluxo.para_json())
            for bloco in documento['blocos']:
                bloco['efeitos'] = efeito_bloco_cfg(fluxo.cfg.blocos[bloco['id']], self.resumos).para_dict_completo()
            documento['chamadas'] = list(fluxo.cfg.chamadas)
            return documento
        funcoes = {}
        for nome, fluxo in self.funcoes.items():
            funcoes[nome] = {**dados(fluxo), 'parametros': list(fluxo.cfg.parametros),
                            'tipo_retorno': fluxo.cfg.retorno, 'recursiva': self.recursivas[nome],
                            'efeitos': self.resumos[nome].para_dict_completo()}
        return json.dumps({'versao': 'RS 0.42K',
                           'observacao': 'Análise por função; não aplica SSA nem transforma chamadas.',
                           'principal': dados(self.principal), 'funcoes': funcoes},
                          ensure_ascii=False, indent=2) + '\n'


def analisar_fluxo_programa(ir, grafos=None):
    grafos = grafos or construir_cfg_programa(ir)
    return FluxoPrograma(grafos, analisar_fluxo(grafos.principal),
                        {nome: analisar_fluxo(grafo) for nome, grafo in grafos.funcoes.items()},
                        resumir_funcoes(ir, grafos),
                        {nome: funcao.recursiva for nome, funcao in ir.funcoes.items()})
