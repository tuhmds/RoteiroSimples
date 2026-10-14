"""Análise conservadora dos efeitos da árvore sintática de toda a RS.

Não requer IR/SSA; funciona para arquivos, bytes, listas, funções e
recursos modernos. Uma operação desconhecida é sempre uma barreira.
Esta análise NÃO transforma o programa e não substitui a checagem
semântica de propriedade realizada pelo compilador.
"""
import json

from .contrato_efeitos import Efeitos, podem_trocar_de_ordem


def _ler(*nomes):
    return Efeitos(leituras=frozenset(nomes))


def _gravar(*nomes):
    return Efeitos(escritas=frozenset(nomes))


def _risco():
    return Efeitos(pode_falhar=True)


def _desconhecido():
    return Efeitos(pode_falhar=True, desconhecido=True, controle=True)


def _propriedade(acao, nome, *, arquivo=False, falha=False):
    return Efeitos(leituras=frozenset((nome,)),
                   escritas=frozenset((nome,)),
                   pode_falhar=falha, arquivos=arquivo,
                   propriedade=(f'{acao}:{nome}',))


_INDICES = frozenset((
    'indice', 'indice_bytes', 'indice_lista_dinamica',
    'indice_lista_emprestada',
))
_CONTAGENS = frozenset(('tamanho_texto', 'tamanho_bytes'))
_CONSULTAS_DINAMICAS = frozenset((
    'tamanho_texto_dinamico', 'capacidade_texto_dinamico', 'caracteres_texto', 'empreste_texto_dinamico',
    'tamanho_bytes_dinamicos', 'capacidade_bytes_dinamicos', 'empreste_bytes_dinamicos',
    'quantidade_lista_dinamica',
    'quantidade_lista_emprestada', 'capacidade_lista_dinamica',
    'capacidade_lista_emprestada', 'empreste_lista_dinamica',
))


def efeito_expressao_arvore(no):
    """Lê todas as dependências de uma expressão e avalia riscos de falha."""
    if not isinstance(no, tuple) or not no:
        return _desconhecido()
    operacao = no[0]
    if operacao in ('numero', 'logico'):
        return Efeitos()
    if operacao == 'var':
        return _ler(no[1])
    if operacao == 'empreste_registro':
        return _ler(no[1]).combinar(_risco())
    if operacao == 'empreste_registro_lista':
        e = _ler(no[1]).combinar(efeito_expressao_arvore(no[2])).combinar(_risco())
        return e.combinar(_gravar(no[3])) if len(no) == 4 else e
    if operacao in _CONTAGENS:
        return _ler(no[1])
    if operacao in _CONSULTAS_DINAMICAS:
        # Mesmo tamanho/capacidade verificam o estado vivo do descritor.
        return _ler(no[1]).combinar(_risco())
    if operacao == 'mova_registro_proprietario':
        return _propriedade('mover_registro', no[1], falha=True)
    if operacao == 'retire_registro_lista':
        return (_propriedade('retirar_registro', no[1], falha=True)
                .combinar(efeito_expressao_arvore(no[2])))
    if operacao == 'mova_valor_dinamico':
        return _propriedade('mover', no[1], falha=True)
    if operacao in _INDICES or operacao == 'byte_texto':
        return _ler(no[1]).combinar(
            efeito_expressao_arvore(no[2])).combinar(_risco())
    if operacao == 'neg':
        return efeito_expressao_arvore(no[1]).combinar(_risco())
    if operacao == 'bin':
        return (efeito_expressao_arvore(no[2])
                .combinar(efeito_expressao_arvore(no[3]))
                .combinar(_risco()))
    if operacao == 'comparacao':
        return efeito_expressao_arvore(no[2]).combinar(
            efeito_expressao_arvore(no[3]))
    if operacao == 'comparacao_texto':
        return efeito_expressao_arvore(no[2]).combinar(
            efeito_expressao_arvore(no[3])).combinar(_risco())
    if operacao == 'temporario_composto':
        return _gravar(no[1]).combinar(efeito_expressao_arvore(no[2]))
    if operacao == 'chamada':
        e = Efeitos()
        for arg in no[2]:
            e = e.combinar(efeito_expressao_arvore(arg))
        # Chamadas podem ter efeitos por seus corpos, inclusive IO
        # e recursos. Não presumir pureza nem ausência de alias.
        return e.combinar(_desconhecido())
    return _desconhecido()


def _expressao_e_gravacao(nome, no):
    return _gravar(nome).combinar(efeito_expressao_arvore(no))


def efeito_instrucao_arvore(no):
    """Efeito DIRETO; efeitos de sub-blocos são registrados separadamente."""
    operacao = str(no[0])
    # Literais, atribuições e coleções de armazenamento fixo.
    if operacao == 'texto':
        return Efeitos(saida=True)
    if operacao in ('atribua', 'copie_composto'):
        return _expressao_e_gravacao(no[1], no[2])
    if operacao in ('crie_texto', 'crie_bytes', 'crie_lista',
                    'crie_registro'):
        return _gravar(no[1])
    if operacao in ('limpe_texto', 'limpe_bytes'):
        return _gravar(no[1])
    if operacao in ('modifique_texto', 'modifique_texto_dinamico', 'modifique_bytes'):
        _, modo, nome, origem = no
        e = (_propriedade('modificar', nome, falha=True)
             if operacao in ('modifique_texto_dinamico', 'modifique_bytes') else _gravar(nome))
        if modo == 'junte':
            e = e.combinar(_ler(nome))
        if origem[0] == 'buffer':
            e = e.combinar(_ler(origem[1]))
        return e.combinar(_risco())
    if operacao == 'imprima_texto':
        return _ler(no[1]).combinar(Efeitos(saida=True, pode_falhar=True))
    if operacao == 'imprima_num':
        return efeito_expressao_arvore(no[1]).combinar(Efeitos(saida=True))
    if operacao in ('leia_int', 'leia_texto', 'leia_texto_dinamico'):
        return _gravar(no[1]).combinar(Efeitos(entrada=True, pode_falhar=True))
    if operacao == 'atribua_byte_dinamico':
        return (_propriedade('alterar', no[1], falha=True)
                .combinar(efeito_expressao_arvore(no[2]))
                .combinar(efeito_expressao_arvore(no[3])))
    if operacao == 'adicione_byte_dinamico':
        return (_propriedade('alterar', no[1], falha=True)
                .combinar(efeito_expressao_arvore(no[2])))
    if operacao in ('atribua_indice', 'atribua_byte',
                    'atribua_indice_dinamico'):
        return (_ler(no[1]).combinar(_gravar(no[1]))
                .combinar(efeito_expressao_arvore(no[2]))
                .combinar(efeito_expressao_arvore(no[3]))
                .combinar(_risco()))
    if operacao in ('leia_indice', 'leia_indice_dinamico'):
        return (_ler(no[1]).combinar(_gravar(no[1]))
                .combinar(efeito_expressao_arvore(no[2]))
                .combinar(Efeitos(entrada=True, pode_falhar=True)))
    if operacao == 'adicione_byte':
        return (_ler(no[1]).combinar(_gravar(no[1]))
                .combinar(efeito_expressao_arvore(no[2]))
                .combinar(_risco()))
    # Heap de listas com dono: todos os mutadores são barreiras, inclusive
    # quando a operação simples parece não tocar variáveis compartilhadas.
    if operacao in ('crie_lista_dinamica', 'crie_valor_dinamico'):
        return _propriedade('criar', no[1], falha=True)
    if operacao in ('mova_lista_dinamica', 'mova_valor_dinamico_comando'):
        destino, origem = no[1:3]
        return (_propriedade('receber', destino, falha=True)
                .combinar(_propriedade('mover', origem, falha=True)))
    if operacao == 'mova_registro_proprietario':
        return (_propriedade('receber_registro', no[1], falha=True)
                .combinar(_propriedade('mover_registro', no[2], falha=True)))
    if operacao == 'receba_registro_proprietario':
        return (_propriedade('receber_registro', no[1], falha=True)
                .combinar(efeito_expressao_arvore(no[2])))
    if operacao == 'receba_valor_dinamico':
        return (_propriedade('receber', no[1], falha=True)
                .combinar(efeito_expressao_arvore(no[2])))
    if operacao in ('adicione_lista_dinamica', 'adicione_colecao_proprietaria'):
        return (_propriedade('alterar', no[1], falha=True)
                .combinar(efeito_expressao_arvore(no[2])))
    if operacao == 'substitua_colecao_proprietaria':
        return (_propriedade('substituir_registro', no[1], falha=True)
                .combinar(efeito_expressao_arvore(no[2]))
                .combinar(efeito_expressao_arvore(no[3])))
    if operacao in ('limpe_lista_dinamica', 'remova_ultimo_lista_dinamica'):
        return _propriedade('alterar', no[1], falha=True)
    if operacao in ('libere_lista_dinamica', 'libere_valor_dinamico'):
        return _propriedade('liberar', no[1], falha=True)
    if operacao in ('limpe_texto_dinamico', 'limpe_bytes_dinamicos'):
        return _propriedade('limpar', no[1], falha=True)
    if operacao in ('codifique_utf8', 'decodifique_utf8'):
        return (_ler(no[2]).combinar(_gravar(no[3]))
                .combinar(_propriedade('converter_utf8', no[1], falha=True)))
    if operacao == 'libere_escopo_listas':
        e = Efeitos()
        for nome in no[1]:
            # O comando liberta listas e FECHA arquivos.
            e = e.combinar(_propriedade('liberar_escopo', nome,
                                       arquivo=True, falha=True))
        return e

    if operacao in ('carregue_texto_dinamico', 'carregue_bytes_dinamicos'):
        return _propriedade('preencher', no[2], arquivo=True, falha=True)
    if operacao in ('grave_arquivo', 'carregue_arquivo'):
        _, caminho, nome = no
        return Efeitos(leituras=frozenset((nome,)) if operacao == 'grave_arquivo'
                       else frozenset(),
                       escritas=frozenset((nome,)) if operacao == 'carregue_arquivo'
                       else frozenset(),
                       arquivos=True, pode_falhar=True)
    if operacao in ('grave_trecho', 'carregue_trecho'):
        e = efeito_expressao_arvore(no[3])
        if operacao == 'carregue_trecho':
            e = e.combinar(efeito_expressao_arvore(no[4]))
        e = e.combinar(_gravar(no[-1]))
        e = e.combinar(_ler(no[2]) if operacao == 'grave_trecho'
                      else _gravar(no[2]))
        return e.combinar(Efeitos(arquivos=True, pode_falhar=True))
    if operacao == 'crie_recurso':
        return _propriedade('declarar', no[1], arquivo=True)
    if operacao == 'abra_recurso':
        e = _propriedade('abrir', no[2], arquivo=True, falha=True)
        if isinstance(no[1], tuple) and no[1][0] == 'caminho_buffer':
            e = e.combinar(_ler(no[1][1]))
        return e.combinar(_gravar(no[4]))
    if operacao in ('feche_recurso', 'sincronize_recurso',
                    'bloqueie_recurso'):
        e = _propriedade(
            {'feche_recurso': 'fechar', 'sincronize_recurso': 'sincronizar',
             'bloqueie_recurso': 'bloquear'}[operacao], no[1],
            arquivo=True, falha=True)
        return e.combinar(_gravar(no[2]))
    if operacao in ('grave_em', 'carregue_de'):
        e = _ler(no[1])
        e = e.combinar(_ler(no[2]) if operacao == 'grave_em'
                      else _gravar(no[2]))
        e = e.combinar(efeito_expressao_arvore(no[3]))
        if operacao == 'carregue_de':
            e = e.combinar(efeito_expressao_arvore(no[4]))
        return (e.combinar(_gravar(no[-1]))
                .combinar(Efeitos(arquivos=True, pode_falhar=True)))
    if operacao == 'consulte_arquivo':
        return Efeitos(escritas=frozenset((no[2],)), arquivos=True, pode_falhar=True)
    if operacao == 'publique_arquivo':
        return Efeitos(escritas=frozenset((no[3],)),
                       arquivos=True, pode_falhar=True)

    if operacao == 'encerre':
        return (efeito_expressao_arvore(no[1])
                .combinar(Efeitos(encerra=True, controle=True,
                                 pode_falhar=True)))
    if operacao == 'retorne':
        return efeito_expressao_arvore(no[1]).combinar(
            Efeitos(controle=True, encerra=True))
    if operacao in ('pare', 'continue'):
        return Efeitos(controle=True)
    if operacao == 'se' or operacao == 'enquanto':
        return efeito_expressao_arvore(no[1]).combinar(
            Efeitos(controle=True))
    if operacao == 'para':
        return (_gravar(no[1]).combinar(efeito_expressao_arvore(no[2]))
                .combinar(efeito_expressao_arvore(no[3]))
                .combinar(Efeitos(controle=True, pode_falhar=True)))
    return _desconhecido()


def _subblocos(no):
    op = no[0]
    if op == 'se':
        return (('entao', no[2]), ('senao', no[3]))
    if op == 'enquanto':
        return (('corpo', no[2]),)
    if op == 'para':
        return (('corpo', no[5]),)
    return ()


def listar_efeitos_programa(programa):
    """Relatório linear e determinístico; preserva caminho dos sub-blocos."""
    itens = []

    def bloco(instrucoes, prefixo):
        for numero, instrucao in enumerate(instrucoes):
            local = f'{prefixo}.{numero}' if prefixo else str(numero)
            efeitos = efeito_instrucao_arvore(instrucao)
            itens.append({
                'caminho': local,
                'operacao': str(instrucao[0]),
                **efeitos.para_dict_completo(),
            })
            for nome, subbloco in _subblocos(instrucao):
                bloco(subbloco, f'{local}.{nome}')

    bloco(programa.instrucoes, 'inicio')
    for nome, funcao in sorted(getattr(programa, 'funcoes', {}).items()):
        bloco(funcao.programa.instrucoes, f'funcao:{nome}')
    return itens


def efeitos_programa_para_json(programa):
    return json.dumps({
        'versao': 'RS 0.40D',
        'escopo': 'diagnostico conservador; nao aplica otimizacoes',
        'instrucoes': listar_efeitos_programa(programa),
    }, ensure_ascii=False, indent=2) + '\n'


def formatar_efeitos_programa(programa):
    linhas = ['Efeitos e propriedade da RS 0.40D (análise conservadora)']
    for item in listar_efeitos_programa(programa):
        pontos = []
        for chave in ('leituras', 'escritas', 'propriedade'):
            if item[chave]:
                pontos.append(chave + '=' + ','.join(item[chave]))
        for chave in ('entrada', 'saida', 'arquivos', 'pode_falhar',
                      'controle', 'encerra', 'desconhecido'):
            if item[chave]:
                pontos.append(chave)
        linhas.append(f"  [{item['caminho']}] {item['operacao']}: "
                      + (', '.join(pontos) or 'sem efeitos observáveis'))
    return '\n'.join(linhas)
