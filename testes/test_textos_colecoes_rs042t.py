"""Coleções de textos e biblioteca UTF-8 confrontadas com oráculos Python."""
import json
from pathlib import Path
import random
import sys
import tempfile
import unittest

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))
from backend import compilar
from compilador.disposicao_tipos import palavras_tipo
from compilador.erros import ErroCompilacao
from compilador.efeitos_programa import efeito_expressao_arvore
from compilador.modulos import carregar_fontes
from compilador.parser import analisar_programa
from compilador.propriedade import TIPO_TEXTO_DINAMICO, eh_colecao_proprietaria
from testes.test_valores_dinamicos_rs042a import alvo_nativo, rodar

MOSTRAR = '''funcao mostrar(nome: emprestimo[texto]) -> inteiro {
    escreva(nome)
    retorne caracteres(nome)
}
'''
CRIAR = '''funcao criar() -> texto {
    seja nome: texto = "Ação 🌱"
    retorne mova(nome)
}
'''


def modulo(fonte):
    with tempfile.TemporaryDirectory() as pasta:
        arquivo = Path(pasta) / 'principal.rts'
        arquivo.write_text(fonte, encoding='utf-8')
        return analisar_programa(carregar_fontes(arquivo).texto)


class TestesTextosColecoesRS042T(unittest.TestCase):
    def verificar(self, fonte, esperado, niveis=tuple(range(9)), antes=None, codigo=0):
        programa = modulo(fonte) if fonte.startswith('importe ') else analisar_programa(fonte)
        for nivel in niveis:
            with self.subTest(nivel=nivel):
                for alvo in ('windows', 'linux'):
                    imagem = compilar(programa, alvo, nivel=nivel, otimizar=nivel > 0)
                    if alvo == alvo_nativo():
                        resultado, _ = rodar(imagem, antes=antes)
                self.assertEqual((resultado.returncode, resultado.stdout, resultado.stderr), (codigo, esperado, ''))
        return programa

    def test_disposicao_comum_e_colecao_de_descritores(self):
        p = analisar_programa('inicio {\n seja nomes: lista[texto]\n}')
        tipo = p.tipos['nomes']
        self.assertEqual(tipo, ('lista_dinamica', TIPO_TEXTO_DINAMICO))
        self.assertTrue(eh_colecao_proprietaria(tipo, p.registros))
        self.assertEqual(palavras_tipo(tipo, {}), 3)
        self.assertEqual(palavras_tipo(tipo[1], {}), 3)

    def test_crescimento_substituicao_retirada_e_descarte_nove_niveis(self):
        fonte = CRIAR + MOSTRAR + '''inicio {
    seja nomes: lista[texto]
    para indice de 0 ate 256 {
        adicione(nomes, criar())
    }
    nomes[42] = criar()
    seja primeiro: texto = retire(nomes, 0)
    seja ultimo = retire(nomes, tamanho(nomes) - 1)
    escreva(primeiro)
    escreva(ultimo)
    seja quantidade = mostrar(empreste(nomes[41]))
    escreva(quantidade)
    escreva(tamanho(nomes))
    remova_ultimo(nomes)
    limpe_lista(nomes)
    adicione(nomes, mova(primeiro))
    escreva(tamanho(nomes))
}'''
        self.verificar(fonte, 'Ação 🌱\nAção 🌱\nAção 🌱\n6\n255\n1\n')

    def test_campos_aninhados_lista_emprestada_e_resultado_lista(self):
        fonte = '''tipo Catalogo {
    nomes: lista[texto]
}
''' + CRIAR + MOSTRAR + '''funcao consultar(nomes: emprestimo[lista[texto]]) -> inteiro {
    retorne mostrar(empreste(nomes[0]))
}
funcao produzir() -> resultado[lista[texto]] {
    seja nomes: lista[texto]
    adicione(nomes, criar())
    retorne sucesso[lista[texto]](mova(nomes))
}
inicio {
    seja catalogo: Catalogo
    seja resposta = produzir()
    mova(catalogo.nomes, resposta.valor)
    escreva(consultar(empreste(catalogo.nomes)))
    seja catalogos: lista[Catalogo]
    adicione(catalogos, mova(catalogo))
    limpe_lista(catalogos)
}'''
        self.verificar(fonte, 'Ação 🌱\n6\n')

    def test_retirada_direta_em_argumentos_e_retorno_nao_duplica_dono(self):
        fonte = CRIAR + '''funcao combinar(a: texto, b: texto) -> texto {
    junte(a, b)
    retorne mova(a)
}
funcao extrair(nomes: lista[texto]) -> texto {
    retorne retire(nomes, 0)
}
inicio {
    seja nomes: lista[texto]
    adicione(nomes, criar())
    adicione(nomes, criar())
    adicione(nomes, criar())
    seja combinado = combinar(retire(nomes, 0), retire(nomes, 0))
    escreva(combinado)
    seja ultimo = extrair(mova(nomes))
    escreva(ultimo)
}'''
        self.verificar(fonte, 'Ação 🌱Ação 🌱\nAção 🌱\n')

    def test_mover_lista_descarta_destino_e_escopos_preservam_origem(self):
        fonte = CRIAR + '''inicio {
    seja origem: lista[texto]
    seja destino: lista[texto]
    adicione(origem, criar())
    adicione(destino, criar())
    mova(destino, origem)
    para indice de 0 ate 20 {
        seja locais: lista[texto]
        adicione(locais, criar())
        se indice == 0 {
            continue
        }
        pare
    }
    escreva(tamanho(destino))
}'''
        self.verificar(fonte, '1\n')

    def test_rejeita_copias_alias_e_emprestimos_que_escapam(self):
        cabecalho = CRIAR + MOSTRAR + '''funcao consumir(nome: emprestimo[texto], nomes: lista[texto]) -> inteiro {
    retorne caracteres(nome)
}
'''
        base = cabecalho + 'inicio {\n seja nomes: lista[texto]\n adicione(nomes, criar())\n'
        for instrucao in ('seja copia = nomes[0]', 'seja copia: texto = nomes[0]',
                          'adicione(nomes, nomes[0])', 'nomes[0] = nomes[0]',
                          'seja vista = empreste(nomes[0])',
                          'escreva(consumir(empreste(nomes[0]), mova(nomes)))',
                          'escreva(mostrar(empreste(nomes[verdadeiro])))'):
            with self.subTest(instrucao=instrucao), self.assertRaises(ErroCompilacao):
                analisar_programa(base + instrucao + '\n}')
        with self.assertRaises(ErroCompilacao):
            analisar_programa('funcao errada(nomes: emprestimo[lista[texto]]) -> texto {\n retorne retire(nomes, 0)\n}\ninicio {\n escreva(1)\n}')

    def test_emprestimo_tem_efeito_de_leitura_indice_e_reserva(self):
        p = analisar_programa(CRIAR + MOSTRAR + 'inicio {\n seja nomes: lista[texto]\n adicione(nomes, criar())\n escreva(mostrar(empreste(nomes[0])))\n}')
        chamada = p.instrucoes[-1][1]
        vista = chamada[2][0]
        self.assertEqual(vista[0], 'empreste_texto_lista')
        efeito = efeito_expressao_arvore(vista)
        self.assertIn('nomes', efeito.leituras)
        self.assertIn(vista[3], efeito.escritas)
        self.assertTrue(efeito.pode_falhar)

    def test_indices_invalidos_e_dono_movido_falham_controladamente(self):
        for consulta in ('empreste(nomes[-1])', 'empreste(nomes[1])'):
            fonte = CRIAR + MOSTRAR + 'inicio {\n seja nomes: lista[texto]\n adicione(nomes, criar())\n escreva(mostrar(' + consulta + '))\n}'
            p = analisar_programa(fonte)
            for nivel in (0, 8):
                r, _ = rodar(compilar(p, alvo_nativo(), nivel=nivel, otimizar=nivel > 0))
                self.assertEqual(r.returncode, 1)
                self.assertIn('ndice', r.stdout)
        p = analisar_programa(CRIAR + 'inicio {\n seja nomes: lista[texto]\n seja nome = criar()\n adicione(nomes, mova(nome))\n escreva(nome)\n}')
        r, _ = rodar(compilar(p, alvo_nativo(), nivel=8))
        self.assertEqual(r.returncode, 1)
        self.assertIn('movimentacao', r.stdout)

    def test_busca_e_recorte_usam_caracteres_unicode(self):
        fonte = '''importe "padrao/textos.rts" como textos
inicio {
    seja fonte: texto = "Ação 🌱é"
    seja padrao: texto = "🌱"
    seja busca = textos.encontrar(empreste(fonte), empreste(padrao))
    escreva(busca.valido)
    escreva(busca.valor)
    seja recorte = textos.recortar(empreste(fonte), 5, 2)
    escreva(recorte.valor)
    escreva(caracteres(recorte.valor))
    copie(padrao, "é")
    seja ausente = textos.encontrar(empreste(fonte), empreste(padrao))
    escreva(ausente.valor)
    limpe(padrao)
    seja vazio = textos.encontrar(empreste(fonte), empreste(padrao))
    escreva(vazio.valor)
}'''
        self.verificar(fonte, '1\n5\n🌱e\n2\n-1\n0\n')

    def test_limites_de_recorte_sao_recuperaveis_sem_estouro(self):
        fonte = 'importe "padrao/textos.rts" como textos\ninicio {\n seja fonte: texto = "🌱RS"\n'
        esperado = ''
        for i, (posicao, quantidade, codigo) in enumerate(((-1, 0, 2), (4, 0, 2), (0, -1, 3),
                    (1, 3, 3), (1, 9223372036854775807, 3), (9223372036854775807, 0, 2), (3, 0, 0))):
            fonte += f' seja resposta_{i} = textos.recortar(empreste(fonte), {posicao}, {quantidade})\n escreva(resposta_{i}.codigo_erro)\n'
            esperado += f'{codigo}\n'
        self.verificar(fonte + '}', esperado)

    def test_separar_e_juntar_confrontam_split_independente(self):
        aleatorio = random.Random(420200)
        casos = [('', '|'), ('|a||b|', '|'), ('🌱A🌱🌱', '🌱'), ('éé', 'é')]
        for _ in range(12):
            origem = ''.join(aleatorio.choice(('A', 'ç', '🌱', 'é', '|', '\0', '\n'))
                             for _ in range(aleatorio.randint(0, 35)))
            casos.append((origem, aleatorio.choice(('|', '🌱', 'ç', 'AA'))))
        fonte = 'importe "padrao/textos.rts" como textos\n' + MOSTRAR + 'inicio {\n'
        esperado = ''
        for i, (origem, separador) in enumerate(casos):
            fonte += f''' se verdadeiro {{
    seja fonte_{i}: texto = {json.dumps(origem, ensure_ascii=False)}
    seja separador_{i}: texto = {json.dumps(separador, ensure_ascii=False)}
    seja partes = textos.separar(empreste(fonte_{i}), empreste(separador_{i}))
    escreva(partes.valido)
    escreva(tamanho(partes.valor))
    para indice de 0 ate tamanho(partes.valor) - 1 {{
        seja comprimento = mostrar(empreste(partes.valor[indice]))
        escreva(comprimento)
    }}
    seja unido = textos.juntar(empreste(partes.valor), empreste(separador_{i}))
    escreva(unido.valor == fonte_{i})
 }}
'''
            partes = origem.split(separador)
            esperado += '1\n' + str(len(partes)) + '\n' + ''.join(p + '\n' + str(len(p)) + '\n' for p in partes) + '1\n'
        self.verificar(fonte + '}', esperado)

    def test_separador_vazio_e_lista_vazia_tem_contratos_distintos(self):
        fonte = '''importe "padrao/textos.rts" como textos
inicio {
    seja fonte: texto = "RS"
    seja vazio: texto
    seja partes = textos.separar(empreste(fonte), empreste(vazio))
    escreva(partes.valido)
    escreva(partes.codigo_erro)
    escreva(tamanho(partes.valor))
    seja nomes: lista[texto]
    seja unido = textos.juntar(empreste(nomes), empreste(vazio))
    escreva(unido.valido)
    escreva(tamanho(unido.valor))
}'''
        self.verificar(fonte, '0\n4\n0\n1\n0\n')

    def test_busca_e_recorte_gerados_com_oraculo_independente(self):
        aleatorio = random.Random(420201)
        fonte = 'importe "padrao/textos.rts" como textos\ninicio {\n'
        esperado = ''
        for _ in range(16):
            origem = ''.join(aleatorio.choice(('A', 'ç', '🌱', 'e', '́', '\0'))
                             for _ in range(aleatorio.randint(0, 25)))
            posicao = aleatorio.randint(0, len(origem))
            quantidade = aleatorio.randint(0, len(origem) - posicao)
            procurado = aleatorio.choice((origem[posicao:posicao+quantidade], 'ausente', '́'))
            fonte += f''' se verdadeiro {{
    seja origem: texto = {json.dumps(origem, ensure_ascii=False)}
    seja procurado: texto = {json.dumps(procurado, ensure_ascii=False)}
    seja esperado: texto = {json.dumps(origem[posicao:posicao+quantidade], ensure_ascii=False)}
    seja busca = textos.encontrar(empreste(origem), empreste(procurado))
    escreva(busca.valido)
    escreva(busca.valor)
    seja recorte = textos.recortar(empreste(origem), {posicao}, {quantidade})
    escreva(recorte.valido)
    escreva(recorte.valor == esperado)
 }}
'''
            esperado += f'1\n{origem.find(procurado)}\n1\n1\n'
        self.verificar(fonte + '}', esperado)

    def test_resultados_de_listas_escalares_usam_a_mesma_especializacao(self):
        fonte = '''funcao produzir() -> resultado[lista[inteiro]] {
    seja valores: lista[inteiro]
    adicione(valores, 42)
    retorne sucesso[lista[inteiro]](mova(valores))
}
inicio {
    seja resposta = produzir()
    escreva(resposta.valor[0])
    seja falha = falha[lista[inteiro]](7)
    escreva(falha.codigo_erro)
    escreva(tamanho(falha.valor))
}'''
        self.verificar(fonte, '42\n7\n0\n')

    def test_benchmark_tem_resultado_calculado_independentemente(self):
        fonte = carregar_fontes(RAIZ/'benchmarks/textos_rs042t.rts').texto
        self.verificar(fonte, str(200 * len('Ação|🌱||RS|'.split('|'))) + '\n', niveis=(0, 8))

    def test_arquivo_utf8_invalido_e_limites_retornam_erros_e_permitem_continuar(self):
        fonte = '''importe "padrao/textos.rts" como textos
importe "padrao/utf8.rts" como utf8
inicio {
    seja bytes_lidos: bytes
    carregue_arquivo("invalido.txt", bytes_lidos)
    seja decodificado = utf8.decodificar(empreste(bytes_lidos))
    escreva(decodificado.codigo_erro)
    seja origem: texto = "RS"
    seja separador: texto = "|"
    seja busca = textos.encontrar(empreste(origem), empreste(separador))
    escreva(busca.valor)
    seja recorte = textos.recortar(empreste(origem), 0, 3)
    escreva(recorte.codigo_erro)
    limpe(separador)
    seja partes = textos.separar(empreste(origem), empreste(separador))
    escreva(partes.codigo_erro)
    seja nomes: lista[texto]
    adicione(nomes, mova(origem))
    seja unido = textos.juntar(empreste(nomes), empreste(separador))
    escreva(unido.codigo_erro)
    escreva("continua")
}'''
        self.verificar(fonte, '1\n-1\n3\n4\n0\ncontinua\n', antes=lambda p: (p/'invalido.txt').write_bytes(b'\xff'))

    def test_aplicacao_configuracao_lf_crlf_erro_e_ausencia(self):
        fonte = carregar_fontes(RAIZ/'exemplos/ferramentas/ler_configuracao_rs042t.rts').texto
        p = analisar_programa(fonte)
        casos = ((b'# RS\n nome = A\xc3\xa7\xc3\xa3o \xf0\x9f\x8c\xb1\n vazio=\n', 0, 'nome\nAção 🌱\nvazio\n\n'),
                 (b'\r\n nome=RS\r\n', 0, 'nome\nRS\n'),
                 (b'nome=RS\nsem separador\n', 2, 'nome\nRS\nErro de configuracao na linha:\n2\nCodigo:\n5\n'),
                 (b'\xff', 2, 'Erro: configuracao nao e UTF-8 valido.\n'),
                 (None, 2, 'Erro: configuracao.txt ausente ou recusado.\n'))
        for nivel in range(9):
            imagem = compilar(p, alvo_nativo(), nivel=nivel, otimizar=nivel > 0)
            for dados, codigo, esperado in casos:
                with self.subTest(nivel=nivel, dados=dados):
                    r, _ = rodar(imagem, antes=(lambda pasta: (pasta/'configuracao.txt').write_bytes(dados)) if dados is not None else None)
                    self.assertEqual((r.returncode, r.stdout, r.stderr), (codigo, esperado, ''))


if __name__ == '__main__':
    unittest.main()
