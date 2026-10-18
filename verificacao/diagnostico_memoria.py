"""Diagnóstico estático RS-MEM: operações de memória no programa tipado.

Não executa o programa nem afirma medir heap, RSS, fragmentação ou escape.
Apenas classifica instruções que o parser realmente produziu, inclusive
corpos de funções e blocos de controle.
"""
import argparse
from collections import Counter
import json
from pathlib import Path
import sys

RAIZ = Path(__file__).resolve().parents[1]
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

from compilador.modulos import carregar_fontes
from compilador.parser import analisar_programa
from compilador.propriedade import eh_valor_proprietario

CATEGORIAS = {
    'crie_lista_dinamica': 'declaracao_dinamica',
    'crie_valor_dinamico': 'declaracao_dinamica',
    'adicione_lista_dinamica': 'crescimento_potencial',
    'adicione_colecao_proprietaria': 'crescimento_potencial',
    'adicione_byte_dinamico': 'crescimento_potencial',
    'modifique_texto_dinamico': 'crescimento_potencial',
    'modifique_bytes': 'crescimento_potencial',
    'reserve_capacidade_dinamica': 'reserva_antecipada',
    'mova_lista_dinamica': 'transferencia',
    'mova_valor_dinamico_comando': 'transferencia',
    'mova_registro_proprietario': 'transferencia',
    'receba_valor_dinamico': 'transferencia',
    'receba_registro_proprietario': 'transferencia',
    'libere_lista_dinamica': 'liberacao_explicita',
    'libere_valor_dinamico': 'liberacao_explicita',
    'libere_escopo_listas': 'liberacao_de_escopo',
}
BLOCOS = {'se': (2, 3), 'enquanto': (2,), 'para': (5,)}
CRESCIMENTO = {nome for nome, tipo in CATEGORIAS.items()
               if tipo == 'crescimento_potencial'}


def percorrer(instrucoes):
    """Gera (nó, caminho, repeticao_condicional) sem executar o código."""
    pilha = [(itens, prefixo, em_laco)
             for itens, prefixo, em_laco in [(instrucoes, 'principal', False)]]
    while pilha:
        itens, prefixo, em_laco = pilha.pop()
        for indice, no in enumerate(itens):
            caminho = prefixo + '/' + str(indice)
            yield no, caminho, em_laco
            filhos = BLOCOS.get(no[0], ())
            for n in reversed(filhos):
                pilha.append((no[n], caminho + '/' + str(n),
                             em_laco or no[0] in ('para', 'enquanto')))


def diagnosticar(programa):
    contagens = Counter()
    detalhes = []
    avisos = []
    escopos = [('inicio', programa)]
    escopos.extend((nome, fn.programa)
                   for nome, fn in getattr(programa, 'funcoes', {}).items())
    for nome, p in escopos:
        locais = Counter()
        proprietarios = []
        for identificador, tipo in getattr(p, 'tipos', {}).items():
            if eh_valor_proprietario(tipo, getattr(p, 'registros', {})):
                proprietarios.append(identificador)
        for no, caminho, no_laco in percorrer(p.instrucoes):
            tag = no[0]
            categoria = CATEGORIAS.get(tag)
            if categoria:
                contagens[categoria] += 1
                locais[categoria] += 1
                if categoria == 'crescimento_potencial' and no_laco:
                    avisos.append({
                        'escopo': nome,
                        'caminho': caminho,
                        'operacao': tag,
                        'observacao': 'Possível crescimento repetido em laço; '
                                      'avaliar capacidade antecipada após medir.',
                    })
        detalhes.append({
            'escopo': nome,
            'donos_tipados': sorted(proprietarios),
            'ocorrencias_sintaticas': dict(sorted(locais.items())),
        })
    return {
        'versao': 'RS-MEM 0.1',
        'escopo': 'diagnostico estatico, sem medicao de alocacoes reais',
        'contagens_sintaticas': dict(sorted(contagens.items())),
        'rotinas': detalhes,
        'pontos_de_atencao': avisos,
        'limites': [
            'Contagens são ocorrências no código-fonte, não frequências de execução.',
            'Não demonstra ausência de vazamentos, segurança ou custos numéricos.',
            'Não estima RAM física, CPU, fragmentação ou equivalência entre plataformas.',
            'Sugestões em laços exigem análise e benchmarks antes de alterar o programa.',
        ],
    }


def formatar(relatorio):
    linhas = ['RS-MEM — diagnóstico estático de memória']
    for categoria, quantidade in relatorio['contagens_sintaticas'].items():
        linhas.append(f'{categoria}: {quantidade}')
    linhas.append(f"Pontos de atenção em laços: {len(relatorio['pontos_de_atencao'])}")
    for item in relatorio['pontos_de_atencao']:
        linhas.append(f"  {item['escopo']} {item['caminho']}: {item['operacao']}")
    linhas.append('Atenção: nenhuma contagem representa alocações reais ou bytes de RAM.')
    return '\n'.join(linhas)


def main(argv=None):
    p = argparse.ArgumentParser(description='Diagnóstico estático RS-MEM')
    p.add_argument('fonte', type=Path, help='Arquivo .rts')
    p.add_argument('--json', type=Path, dest='saida')
    args = p.parse_args(argv)
    programa = analisar_programa(carregar_fontes(args.fonte).texto)
    relatorio = diagnosticar(programa)
    print(formatar(relatorio))
    if args.saida:
        args.saida.parent.mkdir(parents=True, exist_ok=True)
        args.saida.write_text(json.dumps(relatorio, ensure_ascii=False, indent=2) + '\n',
                              encoding='utf-8')


if __name__ == '__main__':
    main()
