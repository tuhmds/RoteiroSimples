"""Programas de propriedade e persistência com modelo independente em Python."""
from dataclasses import dataclass
import json
import random


ACOES = ('adicionar', 'substituir', 'retirar', 'remover', 'limpar', 'mover', 'liberar', 'arquivo')


@dataclass(frozen=True)
class Operacao:
    acao: str
    destino: int
    codigo: int
    indice: int
    reinserir: bool


@dataclass(frozen=True)
class CasoGerado:
    semente: int
    operacoes: tuple
    fonte: str
    saida: str
    arquivos: dict


def gerar_caso(semente, passos=40):
    gerador = random.Random(semente)
    # Nove inserções obrigatórias exercitam expansões 4 -> 8 -> 16.
    operacoes = tuple(Operacao('adicionar' if posicao < 9 else gerador.choice(ACOES),
        0 if posicao < 9 else gerador.randrange(2), gerador.randrange(10000),
        gerador.randrange(100), bool(gerador.randrange(2))) for posicao in range(passos))
    return montar_caso(semente, operacoes)


def montar_caso(semente, operacoes):
    """O modelo guarda valores e estados de donos, sem usar AST, IR ou backend.

    Índices são normalizados novamente após reduzir operações. Assim, o
    minimizador preserva programas válidos sem acessar posições inexistentes.
    """
    titulo = ('', 'Ação RS', '日本 RS', 'Cadastro 👩')[semente % 4]
    literal = json.dumps(titulo, ensure_ascii=False)
    fonte = [f'''tipo Documento {{
    codigo: inteiro
    titulo: texto
    dados: bytes
    marcas: lista[inteiro]
}}
funcao criar(numero: inteiro) -> Documento {{
    seja documento: Documento
    documento.codigo = numero
    copie(documento.titulo, {literal})
    adicione_byte(documento.dados, 0)
    adicione_byte(documento.dados, 255)
    adicione_byte(documento.dados, numero % 256)
    adicione(documento.marcas, numero + 1)
    adicione(documento.marcas, numero + 2)
    retorne mova(documento)
}}
funcao consultar(documento: emprestimo[Documento]) -> inteiro {{
    retorne documento.codigo + documento.dados[2] + caracteres(documento.titulo) + documento.marcas[0] + documento.marcas[1]
}}
funcao vazia() -> lista[Documento] {{
    seja documentos: lista[Documento]
    retorne mova(documentos)
}}
inicio {{
    seja primeira: lista[Documento]
    seja segunda: lista[Documento]
''']
    listas = [[], []]  # None representa um dono inativo, não uma lista vazia.
    nomes = ('primeira', 'segunda')
    saidas, arquivos = [], {}
    contador = 0
    def emitir(texto):
        fonte.append('    ' + texto)
    def ativar(destino):
        nonlocal contador
        if listas[destino] is None:
            contador += 1
            emitir(f'seja vazia_{contador} = vazia()')
            emitir(f'mova({nomes[destino]}, vazia_{contador})')
            listas[destino] = []
    def medida(codigo):
        return 3 * codigo + codigo % 256 + len(titulo) + 3
    for posicao, op in enumerate(operacoes):
        if op.acao not in ACOES or op.destino not in (0, 1) or not 0 <= op.codigo < 10000:
            raise ValueError('Operação gerada fora do contrato.')
        destino, outro = op.destino, 1 - op.destino
        ativar(destino)
        nome = nomes[destino]
        valores = listas[destino]
        if op.acao in ('substituir', 'retirar', 'remover') and not valores:
            emitir(f'adicione({nome}, criar({op.codigo}))')
            valores.append(op.codigo)
        indice = op.indice % len(valores) if valores else 0
        if op.acao == 'adicionar':
            emitir(f'adicione({nome}, criar({op.codigo}))')
            valores.append(op.codigo)
        elif op.acao == 'substituir':
            emitir(f'{nome}[{indice}] = criar({op.codigo})')
            valores[indice] = op.codigo
        elif op.acao == 'retirar':
            codigo = valores.pop(indice)
            emitir(f'seja retirado_{posicao} = retire({nome}, {indice})')
            emitir(f'escreva(consultar(empreste(retirado_{posicao})))')
            saidas.append(str(medida(codigo)))
            if op.reinserir:
                ativar(outro)
                emitir(f'adicione({nomes[outro]}, mova(retirado_{posicao}))')
                listas[outro].append(codigo)
        elif op.acao == 'remover':
            emitir(f'remova_ultimo({nome})')
            valores.pop()
        elif op.acao == 'limpar':
            emitir(f'limpe_lista({nome})')
            valores.clear()
        elif op.acao == 'mover':
            emitir(f'mova({nomes[outro]}, {nome})')
            listas[outro], listas[destino] = valores, None
        elif op.acao == 'liberar':
            emitir(f'libere({nome})')
            listas[destino] = None
        elif op.acao == 'arquivo':
            emitir(f'seja documento_{posicao} = criar({op.codigo})')
            emitir(f'seja para_gravar_{posicao}: bytes')
            emitir(f'mova(para_gravar_{posicao}, documento_{posicao}.dados)')
            emitir(f'grave_arquivo("dados.bin", para_gravar_{posicao})')
            emitir(f'seja recuperados_{posicao}: bytes')
            emitir(f'carregue_arquivo("dados.bin", recuperados_{posicao})')
            emitir(f'escreva(tamanho(recuperados_{posicao}))')
            for indice_byte in range(3):
                emitir(f'escreva(recuperados_{posicao}[{indice_byte}])')
            arquivos['dados.bin'] = bytes((0, 255, op.codigo % 256))
            saidas.extend(('3', '0', '255', str(op.codigo % 256)))
        # Ler todos os elementos após cada operação detecta ordem, conteúdo
        # e propriedade perdida; não comparamos dois backends como oráculo.
        for lista, nome_lista in zip(listas, nomes):
            if lista is None:
                emitir('escreva(-1)')
                saidas.append('-1')
                continue
            emitir(f'escreva(tamanho({nome_lista}))')
            saidas.append(str(len(lista)))
            if lista:
                emitir(f'para indice_{posicao}_{nome_lista} de 0 ate tamanho({nome_lista}) - 1 {{')
                emitir(f'    escreva(consultar(empreste({nome_lista}[indice_{posicao}_{nome_lista}])))')
                emitir('}')
                saidas.extend(str(medida(codigo)) for codigo in lista)
    emitir('}')
    return CasoGerado(semente, tuple(operacoes), '\n'.join(fonte) + '\n',
                     '\n'.join(saidas) + ('\n' if saidas else ''), arquivos)


def reduzir_caso(caso, reproduz):
    """Redução por remoção de blocos, mantendo o modelo e a semente.

    `reproduz` deve confirmar a MESMA classe de falha em execução real.
    Nenhuma remoção é aceita sem nova reprodução.
    """
    operacoes = list(caso.operacoes)
    divisao = 2
    while operacoes:
        tamanho = max(1, (len(operacoes) + divisao - 1) // divisao)
        reduziu = False
        for inicio in range(0, len(operacoes), tamanho):
            candidata = operacoes[:inicio] + operacoes[inicio + tamanho:]
            novo = montar_caso(caso.semente, candidata)
            if reproduz(novo):
                operacoes, reduziu = candidata, True
                divisao = max(2, divisao - 1)
                break
        if not reduziu:
            if divisao >= len(operacoes):
                break
            divisao = min(len(operacoes), divisao * 2)
    return montar_caso(caso.semente, operacoes)
