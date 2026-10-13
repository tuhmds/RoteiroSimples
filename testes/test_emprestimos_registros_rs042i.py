"""Vistas de registros em chamadas: leitura nativa e rejeições de alias."""
from pathlib import Path
import sys
import unittest

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))
from backend import compilar
from compilador.erros import ErroCompilacao
from compilador.efeitos_programa import efeito_expressao_arvore
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
    copie(documento.interno.titulo, "Ação RS")
    adicione_byte(documento.conteudo, numero % 256)
    adicione(documento.marcas, verdadeiro)
    retorne mova(documento)
}
funcao consultar(documento: emprestimo[Documento]) -> inteiro {
    retorne documento.codigo + documento.conteudo[0] + caracteres(documento.interno.titulo) + tamanho(documento.marcas)
}
'''


class TestesEmprestimosRegistrosRS042I(unittest.TestCase):
    def verificar(self, fonte, esperado='', niveis=(0, 8), erro=None):
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

    def test_consultas_sem_retirar_crescimento_e_reuso_nove_niveis(self):
        fonte = COMUM + '''inicio {
    seja documentos: lista[Documento]
    para codigo de 0 ate 256 {
        adicione(documentos, criar(codigo))
    }
    seja soma = 0
    para indice de 0 ate tamanho(documentos) - 1 {
        soma = soma + consultar(empreste(documentos[indice]))
    }
    escreva(soma)
    escreva(tamanho(documentos))
    documentos[42] = criar(200)
    escreva(consultar(empreste(documentos[42])))
    seja retirado = retire(documentos, 0)
    escreva(consultar(empreste(retirado)))
    escreva(consultar(empreste(documentos[0])))
    limpe_lista(documentos)
    adicione(documentos, criar(255))
    escreva(consultar(empreste(documentos[0])))
}'''
        self.verificar(fonte, '67592\n257\n408\n8\n10\n518\n', tuple(range(9)))

    def test_lista_emprestada_retransmissao_registro_e_campos(self):
        fonte = COMUM + '''funcao medir(titulo: emprestimo[texto], conteudo: emprestimo[bytes], marcas: emprestimo[lista[logico]]) -> inteiro {
    retorne tamanho(titulo) + conteudo[0] + tamanho(marcas)
}
funcao encaminhar(documento: emprestimo[Documento]) -> inteiro {
    retorne consultar(documento) + consultar(empreste(documento)) + medir(documento.interno.titulo, documento.conteudo, documento.marcas)
}
funcao pesquisar(documentos: emprestimo[lista[Documento]], codigo: inteiro) -> inteiro {
    seja indice = 0
    enquanto indice < tamanho(documentos) {
        se encaminhar(empreste(documentos[indice])) == codigo {
            retorne indice
        }
        indice = indice + 1
    }
    retorne -1
}
inicio {
    seja documentos: lista[Documento]
    adicione(documentos, criar(3))
    adicione(documentos, criar(4))
    escreva(pesquisar(empreste(documentos), 41))
    escreva(pesquisar(empreste(documentos), 46))
    escreva(tamanho(documentos))
}'''
        self.verificar(fonte, '0\n1\n2\n', tuple(range(9)))

    def test_colecoes_aninhadas_e_subregistro_emprestado(self):
        catalogo = '''tipo Catalogo {
    documentos: lista[Documento]
    nome: texto
}
'''
        fonte = COMUM.replace('funcao criar', catalogo + 'funcao criar', 1) + '''funcao ler_interno(interno: emprestimo[Interno]) -> inteiro {
    escreva(interno.titulo)
    retorne caracteres(interno.titulo)
}
funcao ler(documento: emprestimo[Documento]) -> inteiro {
    retorne ler_interno(documento.interno) + ler_interno(empreste(documento.interno))
}
funcao total(catalogo: emprestimo[Catalogo]) -> inteiro {
    seja soma = 0
    para indice de 0 ate tamanho(catalogo.documentos) - 1 {
        soma = soma + ler(empreste(catalogo.documentos[indice]))
    }
    retorne soma
}
inicio {
    seja catalogo: Catalogo
    adicione(catalogo.documentos, criar(1))
    seja catalogos: lista[Catalogo]
    adicione(catalogos, mova(catalogo))
    escreva(total(empreste(catalogos[0])))
    escreva(tamanho(catalogos))
}'''
        self.verificar(fonte, 'Ação RS\nAção RS\n14\n1\n')

    def test_alinhamento_argumentos_impares_temporarios_e_recursao(self):
        fonte = COMUM + '''funcao combinar(numero: inteiro, documento: emprestimo[Documento], outro: Documento, final: inteiro) -> inteiro {
    retorne numero + consultar(documento) + outro.codigo + final
}
funcao repetir(documento: emprestimo[Documento], restante: inteiro) -> inteiro {
    se restante == 0 {
        retorne consultar(documento)
    }
    retorne repetir(documento, restante - 1)
}
inicio {
    seja documentos: lista[Documento]
    adicione(documentos, criar(10))
    escreva(7 + combinar(3, empreste(documentos[0]), criar(5), 9))
    seja outro = criar(5)
    escreva(combinar(3, empreste(documentos[0]), mova(outro), 9))
    escreva(repetir(empreste(documentos[0]), 25))
    escreva(consultar(empreste(documentos[0])) + consultar(empreste(documentos[0])))
}'''
        self.verificar(fonte, '52\n45\n28\n56\n', tuple(range(9)))

    def test_registro_copiavel_buffers_fixos_e_retorno_de_campo_por_valor(self):
        fonte = '''tipo Linha {
    codigo: inteiro
    nome: texto[16]
    binario: bytes[8]
    numeros: lista[3]
}
funcao nome(linha: emprestimo[Linha]) -> texto[16] {
    retorne linha.nome
}
funcao ler(linha: emprestimo[Linha]) -> inteiro {
    escreva(linha.nome)
    retorne linha.codigo + linha.binario[0] + linha.numeros[0]
}
inicio {
    seja linha: Linha
    linha.codigo = 10
    copie(linha.nome, "RS")
    adicione_byte(linha.binario, 255)
    linha.numeros[0] = 7
    seja linhas: lista[Linha]
    adicione(linhas, linha)
    escreva(ler(empreste(linhas[0])))
    seja copia = nome(empreste(linha))
    junte(copia, "!")
    escreva(copia)
    escreva(linha.nome)
}'''
        self.verificar(fonte, 'RS\n272\nRS!\nRS\n')

    def test_indice_avaliado_uma_vez_antes_de_ler(self):
        fonte = COMUM + '''funcao indice() -> inteiro {
    escreva("INDICE")
    retorne 0
}
inicio {
    seja documentos: lista[Documento]
    adicione(documentos, criar(2))
    escreva(consultar(empreste(documentos[indice()])))
}'''
        self.verificar(fonte, 'INDICE\n12\n')

    def test_indice_negativo_vazio_e_acima_do_limite(self):
        for preparo, indice in (('', '0'), ('adicione(documentos, criar(1))', '-1'),
                                 ('adicione(documentos, criar(1))', '1')):
            with self.subTest(indice=indice):
                self.verificar(COMUM + 'inicio {\n seja documentos: lista[Documento]\n' + preparo +
                    '\n escreva(consultar(empreste(documentos[' + indice + '])))\n escreva("INDEVIDO")\n}', erro='ndice')

    def test_lista_inativa_e_registro_parcialmente_inativo(self):
        for corpo in ('seja documentos: lista[Documento]\n libere(documentos)\n escreva(consultar(empreste(documentos[0])))',
                      'seja documento = criar(1)\n libere(documento.interno.titulo)\n escreva(consultar(empreste(documento)))'):
            self.verificar(COMUM + 'inicio {\n' + corpo + '\n escreva("INDEVIDO")\n}', erro='liberacao')

    def test_rejeita_consumir_ou_retirar_lista_durante_emprestimo(self):
        funcoes = '''funcao consumir(documentos: lista[Documento]) -> inteiro {
    retorne tamanho(documentos)
}
funcao juntar(documento: emprestimo[Documento], numero: inteiro) -> inteiro {
    retorne documento.codigo + numero
}
funcao juntar_inverso(numero: inteiro, documento: emprestimo[Documento]) -> inteiro {
    retorne documento.codigo + numero
}
funcao consumir_registro(documento: Documento) -> inteiro {
    retorne documento.codigo
}
'''
        for chamada in ('juntar(empreste(documentos[0]), consumir(mova(documentos)))',
                        'juntar(empreste(documentos[consumir(mova(documentos))]), 1)',
                        'juntar(empreste(documentos[0]), consumir_registro(retire(documentos, 0)))',
                        'juntar_inverso(consumir_registro(retire(documentos, 0)), empreste(documentos[0]))'):
            with self.subTest(chamada=chamada), self.assertRaisesRegex(ErroCompilacao, 'emprestar e mover|retire nao pode'):
                analisar_programa(COMUM + funcoes + 'inicio {\n seja documentos: lista[Documento]\n escreva(' + chamada + ')\n}')

    def test_rejeita_consumo_de_pai_e_folha_do_registro_emprestado(self):
        for consumo in ('usar(mova(documento))', 'usar_texto(mova(documento.interno.titulo))'):
            fonte = COMUM + '''funcao usar(documento: Documento) -> inteiro {
    retorne documento.codigo
}
funcao usar_texto(texto: texto) -> inteiro {
    retorne tamanho(texto)
}
funcao juntar(documento: emprestimo[Documento], numero: inteiro) -> inteiro {
    retorne numero
}
inicio {
    seja documento = criar(1)
    escreva(juntar(empreste(documento), ''' + consumo + '''))
}'''
            with self.subTest(consumo=consumo), self.assertRaisesRegex(ErroCompilacao, 'emprestar e mover'):
                analisar_programa(fonte)

    def test_rejeita_consumo_do_registro_que_contem_a_lista(self):
        catalogo = '''tipo Catalogo {
    documentos: lista[Documento]
}
'''
        fonte = COMUM.replace('funcao criar', catalogo + 'funcao criar', 1) + '''funcao usar(catalogo: Catalogo) -> inteiro {
    retorne tamanho(catalogo.documentos)
}
funcao juntar(documento: emprestimo[Documento], numero: inteiro) -> inteiro {
    retorne numero
}
inicio {
    seja catalogo: Catalogo
    escreva(juntar(empreste(catalogo.documentos[0]), usar(mova(catalogo))))
}'''
        with self.assertRaisesRegex(ErroCompilacao, 'emprestar e mover'):
            analisar_programa(fonte)

    def test_rejeita_alteracoes_de_campos_dinamicos_e_escalares(self):
        for comando in ('documento.codigo = 3', 'copie(documento.interno.titulo, "X")',
                        'adicione_byte(documento.conteudo, 0)', 'documento.conteudo[0] = 1',
                        'adicione(documento.marcas, falso)', 'remova_ultimo(documento.marcas)',
                        'limpe_lista(documento.marcas)', 'libere(documento.interno.titulo)',
                        'libere(documento.conteudo)', 'libere(documento.marcas)',
                        'seja titulo: texto = mova(documento.interno.titulo)'):
            fonte = COMUM + 'funcao alterar(documento: emprestimo[Documento]) -> inteiro {\n' + comando + '\n retorne 0\n}\ninicio {\n escreva(1)\n}'
            with self.subTest(comando=comando), self.assertRaises(ErroCompilacao):
                analisar_programa(fonte)

    def test_rejeita_alteracoes_de_campos_fixos_e_subregistro(self):
        tipos = '''tipo Interno {
    numero: inteiro
}
tipo Fixo {
    interno: Interno
    titulo: texto[8]
    conteudo: bytes[8]
    numeros: lista[3]
}
'''
        for comando in ('fixo.interno.numero = 1', 'fixo.interno = outro', 'copie(fixo.titulo, "X")',
                        'limpe(fixo.titulo)', 'limpe(fixo.conteudo)', 'adicione_byte(fixo.conteudo, 1)',
                        'fixo.conteudo[0] = 2', 'fixo.numeros[0] = 3',
                        'carregue_arquivo("entrada.txt", fixo.titulo)'):
            with self.subTest(comando=comando), self.assertRaises(ErroCompilacao):
                analisar_programa(tipos + 'funcao alterar(fixo: emprestimo[Fixo], outro: Interno) -> inteiro {\n' + comando + '\n retorne 0\n}\ninicio {\n escreva(1)\n}')

    def test_rejeita_armazenamento_retorno_e_tipo_nominal_incorreto(self):
        for trecho in ('inicio {\n seja documento = criar(1)\n seja vista = empreste(documento)\n}',
                       'funcao devolver(documento: emprestimo[Documento]) -> emprestimo[Documento] {\n retorne documento\n}\ninicio {\n escreva(1)\n}',
                       'funcao devolver(documento: emprestimo[Documento]) -> Documento {\n retorne documento\n}\ninicio {\n escreva(1)\n}',
                       'inicio {\n seja documentos: lista[Documento]\n seja vista: emprestimo[Documento]\n}',
                       'inicio {\n seja interno: Interno\n escreva(consultar(empreste(interno)))\n}'):
            with self.subTest(trecho=trecho), self.assertRaises(ErroCompilacao):
                analisar_programa(COMUM + trecho)

    def test_indice_nao_inteiro_e_lista_de_escalar(self):
        for lista, indice in (('Documento', 'verdadeiro'), ('inteiro', '0')):
            with self.subTest(lista=lista), self.assertRaises(ErroCompilacao):
                analisar_programa(COMUM + 'inicio {\n seja documentos: lista[' + lista + ']\n escreva(consultar(empreste(documentos[' + indice + '])))\n}')

    def test_efeitos_preservam_indice_leitura_e_risco(self):
        no = ('empreste_registro_lista', 'documentos', ('chamada', 'indice', ()), 'vista')
        efeito = efeito_expressao_arvore(no)
        self.assertEqual(efeito.leituras, frozenset(('documentos',)))
        self.assertEqual(efeito.escritas, frozenset(('vista',)))
        self.assertTrue(efeito.pode_falhar and efeito.desconhecido)
        self.assertEqual(efeito.propriedade, ())

    def test_texto_vazio_grande_copia_explicita_e_resultado_com_dono_novo(self):
        fonte = '''tipo Mensagem {
    titulo: texto
    dados: bytes
}
funcao medir(mensagem: emprestimo[Mensagem]) -> inteiro {
    retorne caracteres(mensagem.titulo) + tamanho(mensagem.dados)
}
funcao copiar(mensagem: emprestimo[Mensagem]) -> resultado[texto] {
    seja novo: texto
    copie(novo, mensagem.titulo)
    retorne sucesso[texto](mova(novo))
}
inicio {
    seja mensagens: lista[Mensagem]
    seja mensagem: Mensagem
    adicione(mensagens, mova(mensagem))
    escreva(medir(empreste(mensagens[0])))
    seja grande: Mensagem
    para indice de 0 ate 4095 {
        junte(grande.titulo, "ç")
        adicione_byte(grande.dados, indice % 256)
    }
    adicione(mensagens, mova(grande))
    escreva(medir(empreste(mensagens[1])))
    seja resposta = copiar(empreste(mensagens[1]))
    libere(mensagens)
    escreva(caracteres(resposta.valor))
    escreva(tamanho(resposta.valor))
}'''
        self.verificar(fonte, '0\n8192\n4096\n8192\n')

    def test_sondagem_e_orcamento_da_vista_com_buffer_fixo_grande(self):
        fonte = '''tipo Grande {
    dados: bytes[32768]
    titulo: texto
}
funcao medir(grande: emprestimo[Grande]) -> inteiro {
    retorne grande.dados[0] + tamanho(grande.titulo)
}
inicio {
    seja grande: Grande
    adicione_byte(grande.dados, 255)
    copie(grande.titulo, "RS")
    seja registros: lista[Grande]
    adicione(registros, mova(grande))
    escreva(medir(empreste(registros[0])))
}'''
        self.verificar(fonte, '257\n')

    def test_exemplo_publico_de_pesquisa_inteiramente_em_rs(self):
        fonte = carregar_fontes(RAIZ / 'exemplos/aplicacoes/pesquisa_documentos_rs042i.rts').texto
        self.verificar(fonte, '1\n-1\n3\n9\nAção\n255\n3\n', tuple(range(9)))

    def test_vista_temporaria_conta_no_limite_do_quadro_principal(self):
        fonte = '''tipo Grande {
    dados: bytes[400000]
}
funcao medir(grande: emprestimo[Grande]) -> inteiro {
    retorne tamanho(grande.dados)
}
inicio {
    seja grande: Grande
    seja registros: lista[Grande]
    adicione(registros, grande)
    escreva(medir(empreste(registros[0])))
}'''
        programa = analisar_programa(fonte)
        for alvo in ('windows', 'linux'):
            with self.subTest(alvo=alvo), self.assertRaisesRegex(ErroCompilacao, 'limite seguro de pilha'):
                compilar(programa, alvo, nivel=0, otimizar=False)

    def test_recursao_com_vista_encerra_pelo_orcamento_sem_violar_pilha(self):
        fonte = COMUM + '''funcao repetir(documento: emprestimo[Documento], restante: inteiro) -> inteiro {
    se restante == 0 {
        retorne consultar(documento)
    }
    retorne repetir(documento, restante - 1)
}
inicio {
    seja documentos: lista[Documento]
    adicione(documentos, criar(1))
    escreva(repetir(empreste(documentos[0]), 1000000))
    escreva("INDEVIDO")
}'''
        self.verificar(fonte, erro='limite seguro de pilha')
