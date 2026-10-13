"""Coleções com donos por elemento, executadas como PE/ELF reais."""
from pathlib import Path
import sys
import unittest

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))
from backend import compilar
from compilador.erros import ErroCompilacao
from compilador.modulos import carregar_fontes
from compilador.parser import analisar_programa
from testes.test_valores_dinamicos_rs042a import alvo_nativo, rodar

COMUM = '''tipo Interno {
    titulo: texto
}
tipo Documento {
    codigo: inteiro
    interno: Interno
    conteudo: bytes
    marcas: lista[logico]
}
funcao criar(numero: inteiro) -> Documento {
    seja documento: Documento
    documento.codigo = numero
    copie(documento.interno.titulo, "Registro RS")
    adicione_byte(documento.conteudo, numero % 256)
    adicione(documento.marcas, verdadeiro)
    retorne mova(documento)
}
'''


class TestesColecoesProprietariasRS042H(unittest.TestCase):
    def verificar(self, fonte, esperado, niveis=(0, 8), erro=None):
        programa = analisar_programa(fonte)
        for nivel in niveis:
            with self.subTest(nivel=nivel):
                for alvo in ('windows', 'linux'):
                    imagem = compilar(programa, alvo, nivel=nivel, otimizar=nivel > 0)
                    if alvo == alvo_nativo():
                        resultado, _ = rodar(imagem)
                if erro:
                    self.assertEqual(resultado.returncode, 1, resultado.stdout + resultado.stderr)
                    self.assertIn(erro, resultado.stdout + resultado.stderr)
                    self.assertNotIn('INDEVIDO', resultado.stdout)
                else:
                    self.assertEqual((resultado.returncode, resultado.stdout), (0, esperado), resultado.stderr)

    def test_crescimento_substituicao_retirada_e_ordem_nove_niveis(self):
        fonte = COMUM + '''inicio {
    seja documentos: lista[Documento]
    para numero de 0 ate 256 {
        adicione(documentos, criar(numero))
    }
    escreva(tamanho(documentos))
    documentos[42] = criar(255)
    seja primeiro = retire(documentos, 0)
    seja meio: Documento = retire(documentos, 128)
    seja ultimo = retire(documentos, tamanho(documentos) - 1)
    escreva(primeiro.codigo)
    escreva(meio.codigo)
    escreva(ultimo.codigo)
    escreva(tamanho(documentos))
    escreva(meio.interno.titulo)
    escreva(meio.conteudo[0])
    escreva(meio.marcas[0])
    seja soma = 0
    enquanto tamanho(documentos) > 0 {
        seja documento = retire(documentos, 0)
        soma = soma + documento.codigo
    }
    escreva(soma)
    adicione(documentos, mova(primeiro))
    remova_ultimo(documentos)
    escreva(tamanho(documentos))
}'''
        self.verificar(fonte, '257\n0\n129\n256\n254\nRegistro RS\n129\n1\n32724\n0\n', tuple(range(9)))

    def test_listas_em_funcoes_temporarios_e_retorno_por_retirada(self):
        fonte = COMUM + '''funcao montar(numero: inteiro) -> lista[Documento] {
    seja documentos: lista[Documento]
    adicione(documentos, criar(numero))
    adicione(documentos, criar(numero + 1))
    retorne mova(documentos)
}
funcao contar(documentos: emprestimo[lista[Documento]]) -> inteiro {
    retorne tamanho(documentos) + capacidade(documentos)
}
funcao encaminhar(documentos: lista[Documento]) -> lista[Documento] {
    retorne mova(documentos)
}
funcao primeiro(documentos: lista[Documento]) -> Documento {
    retorne retire(documentos, 0)
}
funcao consultar(n: inteiro, documento: Documento) -> inteiro {
    retorne n + documento.codigo
}
inicio {
    seja documentos = encaminhar(montar(17))
    escreva(contar(empreste(documentos)))
    escreva(consultar(3, retire(documentos, 0)))
    adicione(documentos, retire(documentos, 0))
    seja escolhido = primeiro(mova(documentos))
    escreva(escolhido.codigo)
    seja outro = primeiro(encaminhar(montar(42)))
    escreva(outro.codigo)
}'''
        self.verificar(fonte, '6\n20\n18\n42\n', tuple(range(9)))

    def test_colecoes_aninhadas_em_registros_resultados_e_listas(self):
        fonte = COMUM.replace('funcao criar', '''tipo Catalogo {
    titulo: texto
    documentos: lista[Documento]
}
tipo Grupo {
    catalogos: lista[Catalogo]
}
funcao criar''', 1) + '''funcao montar() -> resultado[Grupo] {
    seja catalogo: Catalogo
    copie(catalogo.titulo, "Coleção")
    adicione(catalogo.documentos, criar(17))
    adicione(catalogo.documentos, criar(42))
    seja grupo: Grupo
    adicione(grupo.catalogos, mova(catalogo))
    retorne sucesso[Grupo](mova(grupo))
}
inicio {
    seja resposta = montar()
    seja grupo = mova(resposta.valor)
    seja catalogo = retire(grupo.catalogos, 0)
    escreva(catalogo.titulo)
    seja documento = retire(catalogo.documentos, 1)
    escreva(documento.codigo)
    limpe_lista(catalogo.documentos)
    adicione(catalogo.documentos, mova(documento))
    adicione(grupo.catalogos, mova(catalogo))
    libere(grupo.catalogos)
}'''
        self.verificar(fonte, 'Coleção\n42\n', tuple(range(9)))

    def test_limpeza_preserva_capacidade_e_reuso_sem_descritores_velhos(self):
        fonte = COMUM + '''inicio {
    seja documentos: lista[Documento]
    para numero de 0 ate 8 {
        adicione(documentos, criar(numero))
    }
    seja reserva = capacidade(documentos)
    limpe_lista(documentos)
    escreva(tamanho(documentos))
    escreva(capacidade(documentos) == reserva)
    para numero de 17 ate 18 {
        adicione(documentos, criar(numero))
    }
    seja primeiro = retire(documentos, 0)
    seja segundo = retire(documentos, 0)
    escreva(primeiro.codigo)
    escreva(segundo.codigo)
    escreva(tamanho(documentos))
}'''
        self.verificar(fonte, '0\n1\n17\n18\n0\n')

    def test_movimento_de_lista_descarta_antigo_destino_e_preserva_origem(self):
        fonte = COMUM + '''inicio {
    seja origem: lista[Documento]
    seja destino: lista[Documento]
    adicione(origem, criar(17))
    adicione(destino, criar(99))
    mova(destino, origem)
    seja escolhido = retire(destino, 0)
    escreva(escolhido.codigo)
    seja outra = mova(destino)
    escreva(tamanho(outra))
}'''
        self.verificar(fonte, '17\n0\n')

    def test_retirada_em_substituicao_revalida_indice_apos_diminuir_lista(self):
        fonte = COMUM + '''inicio {
    seja documentos: lista[Documento]
    adicione(documentos, criar(17))
    adicione(documentos, criar(42))
    documentos[0] = retire(documentos, 1)
    seja documento = retire(documentos, 0)
    escreva(documento.codigo)
}'''
        self.verificar(fonte, '42\n')
        fonte = fonte.replace('documentos[0] = retire(documentos, 1)', 'documentos[1] = retire(documentos, 0)')
        self.verificar(fonte, '', erro='índice')

    def test_indice_e_avaliado_uma_vez_e_antes_do_valor(self):
        fonte = COMUM + '''funcao indice() -> inteiro {
    escreva("indice")
    retorne 0
}
funcao novo() -> Documento {
    escreva("valor")
    retorne criar(42)
}
inicio {
    seja documentos: lista[Documento]
    adicione(documentos, criar(17))
    documentos[indice()] = novo()
    seja escolhido = retire(documentos, indice())
    escreva(escolhido.codigo)
}'''
        self.verificar(fonte, 'indice\nvalor\nindice\n42\n')
        fonte = fonte.replace('retorne 0', 'retorne -1').replace('escreva("valor")', 'escreva("INDEVIDO")')
        self.verificar(fonte, '', erro='índice')

    def test_lista_consumida_no_valor_nao_deixa_ponteiro_antigo(self):
        fonte = COMUM + '''funcao consumir(documentos: lista[Documento]) -> Documento {
    retorne retire(documentos, 0)
}
inicio {
    seja documentos: lista[Documento]
    adicione(documentos, criar(17))
    documentos[0] = consumir(mova(documentos))
    escreva("INDEVIDO")
}'''
        self.verificar(fonte, '', erro='liberacao')

    def test_estados_inativos_e_limites_falham_controladamente(self):
        for corpo, erro in (
            ('seja escolhido = retire(documentos, -1)', 'índice'),
            ('seja escolhido = retire(documentos, 1)', 'índice'),
            ('limpe_lista(documentos)\n    remova_ultimo(documentos)', 'índice'),
            ('libere(documentos)\n    seja escolhido = retire(documentos, 0)', 'liberacao'),
            ('seja outra = mova(documentos)\n    adicione(documentos, criar(2))', 'liberacao'),
            ('seja d = criar(3)\n    libere(d.conteudo)\n    adicione(documentos, mova(d))', 'movimentacao ou liberacao'),
        ):
            with self.subTest(corpo=corpo):
                self.verificar(COMUM + 'inicio {\n    seja documentos: lista[Documento]\n    adicione(documentos, criar(1))\n    ' + corpo + '\n    escreva("INDEVIDO")\n}', '', erro=erro)

    def test_retornos_antecipados_continue_pare_e_escopos(self):
        fonte = COMUM + '''funcao conferir(escolha: inteiro) -> inteiro {
    seja documentos: lista[Documento]
    adicione(documentos, criar(17))
    se escolha == 1 {
        retorne tamanho(documentos)
    }
    para numero de 0 ate 5 {
        seja locais: lista[Documento]
        adicione(locais, criar(numero))
        se numero == 0 {
            continue
        }
        se numero == 5 {
            pare
        }
        seja escolhido = retire(locais, 0)
    }
    retorne 42
}
inicio {
    escreva(conferir(1))
    escreva(conferir(0))
}'''
        self.verificar(fonte, '1\n42\n')

    def test_exemplo_publico_com_biblioteca_rs_nove_niveis(self):
        fonte = carregar_fontes(RAIZ / 'exemplos/aplicacoes/colecao_documentos_rs042h.rts').texto
        self.verificar(fonte, '10\nColeção RS\n3\n42\n8\n0\n0\n', tuple(range(9)))

    def test_rejeita_copias_na_insercao_substituicao_e_leitura(self):
        for corpo, erro in (
            ('adicione(documentos, d)', 'nao pode copiar dono'),
            ('documentos[0] = d', 'nao pode copiar dono'),
            ('seja copia = documentos[0]', 'nao pode ser copiado por indice'),
            ('seja copia: Documento = documentos[0]', 'nao pode ser copiado por indice'),
        ):
            with self.subTest(corpo=corpo), self.assertRaisesRegex(ErroCompilacao, erro):
                analisar_programa(COMUM + 'inicio {\n    seja documentos: lista[Documento]\n    seja d = criar(1)\n    ' + corpo + '\n}')

    def test_emprestimo_so_consulta_lista_sem_copiar_elementos(self):
        fonte = COMUM + '''funcao errado(documentos: emprestimo[lista[Documento]]) -> Documento {
    retorne documentos[0]
}
inicio {
    escreva(1)
}'''
        with self.assertRaisesRegex(ErroCompilacao, 'nao pode ser copiado por indice'):
            analisar_programa(fonte)
        with self.assertRaisesRegex(ErroCompilacao, 'retire exige'):
            analisar_programa(fonte.replace('documentos[0]', 'retire(documentos, 0)'))

    def test_rejeita_retirada_junto_com_consumo_ou_emprestimo(self):
        funcoes = '''funcao numero(documentos: lista[Documento]) -> inteiro {
    retorne 0
}
funcao combinar(a: Documento, b: lista[Documento]) -> inteiro {
    retorne 0
}
funcao consultar(a: Documento, b: emprestimo[lista[Documento]]) -> inteiro {
    retorne 0
}
'''
        for expr in ('retire(documentos, numero(mova(documentos)))',
                     'combinar(retire(documentos, 0), mova(documentos))',
                     'consultar(retire(documentos, 0), empreste(documentos))'):
            with self.subTest(expr=expr), self.assertRaisesRegex(ErroCompilacao, 'retire nao pode compartilhar'):
                analisar_programa(COMUM + funcoes + 'inicio {\n    seja documentos: lista[Documento]\n    seja x = ' + expr + '\n}')

    def test_limite_de_aninhamento_e_grafo_com_campos_repetidos(self):
        def fonte(niveis):
            linhas = ['tipo Nivel0 {', '    titulo: texto', '}']
            for numero in range(1, niveis):
                linhas.extend((f'tipo Nivel{numero} {{', f'    a: lista[Nivel{numero-1}]', f'    b: lista[Nivel{numero-1}]', '}'))
            linhas.extend(('inicio {', f'    seja valores: lista[Nivel{niveis-1}]', '    escreva(tamanho(valores))', '}'))
            return '\n'.join(linhas)
        self.verificar(fonte(32), '0\n', (0,))
        programa = analisar_programa(fonte(33))
        for alvo in ('windows', 'linux'):
            with self.subTest(alvo=alvo), self.assertRaisesRegex(ErroCompilacao, '32 niveis'):
                compilar(programa, alvo)


if __name__ == '__main__':
    unittest.main()
