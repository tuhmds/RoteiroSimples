"""Conversoes RS confrontadas com int/str e configuracoes com oraculo separado."""
import json
from pathlib import Path
import random
import re
import sys
import tempfile
import unittest

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))
from backend import compilar
from compilador.modulos import carregar_fontes
from compilador.parser import analisar_programa
from testes.test_valores_dinamicos_rs042a import alvo_nativo, rodar

MINIMO, MAXIMO = -(1 << 63), (1 << 63) - 1
ESPACOS = ' \t\n\r\v\f'
IMPORTAR = 'importe "padrao/conversoes.rts" como conversoes\n'


def literal(valor):
    return json.dumps(valor, ensure_ascii=False)


def inteiro_esperado(texto):
    if texto == '':
        return 1, 0
    if re.fullmatch(r'[+-]?[0-9]+', texto) is None:
        return 2, 0
    valor = int(texto, 10)
    return (0, valor) if MINIMO <= valor <= MAXIMO else (3, 0)


def modulo(fonte):
    with tempfile.TemporaryDirectory() as pasta:
        arquivo = Path(pasta)/'principal.rts'
        arquivo.write_text(fonte, encoding='utf-8')
        return analisar_programa(carregar_fontes(arquivo).texto)


class TestesConversoesRS042U(unittest.TestCase):
    def verificar(self, fonte, esperado, niveis=tuple(range(9))):
        programa = modulo(fonte)
        for nivel in niveis:
            with self.subTest(nivel=nivel):
                for alvo in ('windows', 'linux'):
                    imagem = compilar(programa, alvo, nivel=nivel, otimizar=nivel > 0)
                    if alvo == alvo_nativo():
                        r, _ = rodar(imagem)
                self.assertEqual((r.returncode, r.stdout, r.stderr), (0, esperado, ''))

    def conferir_conversoes(self, entradas):
        fonte = IMPORTAR + 'inicio {\n'
        esperado = ''
        for entrada in entradas:
            codigo, valor = inteiro_esperado(entrada)
            fonte += f''' se verdadeiro {{
    seja origem: texto = {literal(entrada)}
    seja convertido = conversoes.inteiro_de_texto(empreste(origem))
    escreva(convertido.valido)
    escreva(convertido.codigo_erro)
'''
            esperado += f'{int(codigo == 0)}\n{codigo}\n'
            if codigo == 0:
                fonte += '''    escreva(convertido.valor)
    seja escrito = conversoes.texto_de_inteiro(convertido.valor)
    escreva(escrito.valido)
    escreva(escrito.valor)
'''
                esperado += f'{valor}\n1\n{valor}\n'
            fonte += ' }\n'
        self.verificar(fonte + '}', esperado)

    def test_extremos_sinais_zeros_e_formato_canonico(self):
        self.conferir_conversoes(['0', '-0', '+0', '000', '-000', '+00042',
            '1', '-1', '+1', str(MINIMO), str(MAXIMO), '+'+str(MAXIMO),
            str(MINIMO-1), str(MAXIMO+1), '-9223372036854775809', '+9223372036854775808'])

    def test_inteiros_gerados_com_oraculo_independente(self):
        aleatorio = random.Random(420210)
        valores = [aleatorio.randint(MINIMO, MAXIMO) for _ in range(64)]
        entradas = []
        for valor in valores:
            zeros = '0' * aleatorio.randrange(5)
            entradas.append(('-' if valor < 0 else aleatorio.choice(('', '+'))) + zeros + str(abs(valor)))
        self.conferir_conversoes(entradas)

    def test_potencias_de_dez_e_vizinhos(self):
        valores = {MINIMO, MINIMO+1, MAXIMO-1, MAXIMO}
        for expoente in range(19):
            for diferenca in (-1, 0, 1):
                valor = 10**expoente + diferenca
                valores.update((valor, -valor))
        self.conferir_conversoes([str(v) for v in sorted(valores)])

    def test_formato_invalido_prevalece_sobre_intervalo(self):
        self.conferir_conversoes(['', '+', '-', '--1', '+-1', '1-', ' 1', '1 ',
            '\t1', '1\n', '\0', '12\0', '1_000', '1.0', '1,0', '0x10', '1e3',
            'verdadeiro', '１２', '١٢', '−1', '🌱', '9'*1000, '-'+ '9'*1000,
            '9'*1000+'x', '-'+ '9'*1000+'\0', '92233720368547758080?'])

    def test_zeros_longos_sem_estouro_ou_limite_artificial_de_digitos(self):
        self.conferir_conversoes(['0'*3000, '-'+ '0'*3000, '+'+'0'*3000+'42',
                                 '-'+ '0'*3000+'9223372036854775808'])

    def test_emprestimos_de_campos_e_elementos_conservam_origem(self):
        fonte = IMPORTAR + '''tipo Medida {
    escrita: texto
}
funcao ler(medida: emprestimo[Medida]) -> resultado[inteiro] {
    retorne conversoes.inteiro_de_texto(medida.escrita)
}
inicio {
    seja medida: Medida
    copie(medida.escrita, "-42")
    seja a = ler(empreste(medida))
    escreva(a.valor)
    escreva(medida.escrita)
    seja valores: lista[texto]
    seja escrito = conversoes.texto_de_inteiro(-9223372036854775808)
    adicione(valores, mova(escrito.valor))
    seja b = conversoes.inteiro_de_texto(empreste(valores[0]))
    escreva(b.valor)
    escreva(tamanho(valores))
    seja retirado = retire(valores, 0)
    escreva(retirado)
}'''
        self.verificar(fonte, '-42\n-42\n-9223372036854775808\n1\n-9223372036854775808\n')

    def test_propagacao_e_continuacao_apos_falhas(self):
        fonte = IMPORTAR + '''funcao normalizar(origem: emprestimo[texto]) -> resultado[texto] {
    seja numero = conversoes.inteiro_de_texto(origem)
    propague numero
    retorne conversoes.texto_de_inteiro(numero.valor)
}
inicio {
    seja origem: texto = "invalido"
    seja erro = normalizar(empreste(origem))
    escreva(erro.valido)
    escreva(erro.codigo_erro)
    copie(origem, "+00042")
    seja sucesso = normalizar(empreste(origem))
    escreva(sucesso.valor)
    escreva(origem)
}'''
        self.verificar(fonte, '0\n2\n42\n+00042\n')

    def test_aparar_usa_espacos_ascii_e_copia_independente(self):
        aleatorio = random.Random(420211)
        entradas = ['', ESPACOS, ' \tAção 🌱é\r\n', '\0 RS \0', '\u00a042\u00a0',
                    '\u200342\u2003', 'a b', ' x\v y\f ']
        entradas += [''.join(aleatorio.choice(('A', 'ç', '🌱', '́', '\0', *ESPACOS))
                              for _ in range(20)) for _ in range(16)]
        fonte = 'importe "padrao/textos.rts" como textos\ninicio {\n'
        esperado = ''
        for entrada in entradas:
            aparado = entrada.strip(ESPACOS)
            fonte += f''' se verdadeiro {{
    seja origem: texto = {literal(entrada)}
    seja esperado: texto = {literal(aparado)}
    seja aparado = textos.aparar(empreste(origem))
    libere(origem)
    escreva(aparado.valido)
    escreva(aparado.valor == esperado)
    escreva(tamanho(aparado.valor))
    escreva(caracteres(aparado.valor))
 }}
'''
            esperado += f'1\n1\n{len(aparado.encode("utf-8"))}\n{len(aparado)}\n'
        self.verificar(fonte + '}', esperado)

    def test_formatacoes_tem_donos_independentes(self):
        fonte = IMPORTAR + '''inicio {
    seja primeiro = conversoes.texto_de_inteiro(-9223372036854775808)
    seja segundo = conversoes.texto_de_inteiro(-9223372036854775808)
    junte(primeiro.valor, "!")
    libere(primeiro.valor)
    escreva(segundo.valor)
    seja repetido = conversoes.inteiro_de_texto(empreste(segundo.valor))
    escreva(repetido.valor)
}'''
        self.verificar(fonte, '-9223372036854775808\n-9223372036854775808\n')

    def test_configuracoes_validas_e_ignoradas(self):
        fonte = 'importe "padrao/configuracoes.rts" como configuracoes\ninicio {\n'
        esperado = ''
        for entrada in ('', ESPACOS, ' \t# comentario=ruim', 'limite=+00042',
                        '\t ação 🌱 = -9223372036854775808\r\n', 'a=0', 'a=7', 'a=-8'):
            limpa = entrada.strip(ESPACOS)
            ignorada = not limpa or limpa.startswith('#')
            fonte += f''' se verdadeiro {{
    seja origem: texto = {literal(entrada)}
    seja entrada = configuracoes.linha_numerica(empreste(origem))
    libere(origem)
    escreva(entrada.valido)
    escreva(entrada.valor.ignorada)
'''
            esperado += f'1\n{int(ignorada)}\n'
            if not ignorada:
                chave, valor = limpa.split('=', 1)
                fonte += '    escreva(entrada.valor.chave)\n    escreva(entrada.valor.valor)\n'
                esperado += chave.strip(ESPACOS) + '\n' + str(int(valor.strip(ESPACOS))) + '\n'
            fonte += ' }\n'
        self.verificar(fonte+'}', esperado)

    def test_configuracoes_rejeitam_linhas_incompletas_e_numeros_invalidos(self):
        fonte = 'importe "padrao/configuracoes.rts" como configuracoes\ninicio {\n'
        entradas = [('sem igual', 4), ('=1', 5), (' \t = ', 5), ('a=', 1),
                    ('a=+', 2), ('a=1=2', 2), ('a=1 # comentario', 2),
                    ('a=9223372036854775808', 3), ('a=-9223372036854775809', 3),
                    ('a=１２', 2), ('a=\u00a042', 2), ('a=1\0', 2)]
        esperado = ''
        for entrada, codigo in entradas:
            fonte += f''' se verdadeiro {{
    seja origem: texto = {literal(entrada)}
    seja resposta = configuracoes.linha_numerica(empreste(origem))
    escreva(resposta.valido)
    escreva(resposta.codigo_erro)
 }}
'''
            esperado += f'0\n{codigo}\n'
        self.verificar(fonte+'}', esperado)

    def test_entradas_numericas_em_colecao_preservam_chaves_e_donos(self):
        fonte = '''importe "padrao/configuracoes.rts" como configuracoes
funcao mostrar(entrada: emprestimo[configuracoes.EntradaNumerica]) -> inteiro {
    escreva(entrada.chave)
    retorne entrada.valor
}
inicio {
    seja entradas: lista[configuracoes.EntradaNumerica]
    seja origem: texto = "tentativas=+0003"
    seja primeira = configuracoes.linha_numerica(empreste(origem))
    adicione(entradas, mova(primeira.valor))
    copie(origem, "espera=1000")
    seja segunda = configuracoes.linha_numerica(empreste(origem))
    adicione(entradas, mova(segunda.valor))
    libere(origem)
    escreva(mostrar(empreste(entradas[0])))
    escreva(mostrar(empreste(entradas[1])))
    seja retirado = retire(entradas, 0)
    limpe_lista(entradas)
    escreva(retirado.chave)
    escreva(retirado.valor)
}'''
        self.verificar(fonte, 'tentativas\n3\nespera\n1000\ntentativas\n3\n')

    def test_aplicacao_nativa_lf_crlf_limites_e_erros(self):
        p = analisar_programa(carregar_fontes(RAIZ/'exemplos/ferramentas/configuracao_numerica_rs042u.rts').texto)
        erro = 'Erro de configuracao na linha:\n2\nCodigo:\n'
        casos = [(b'# RS\n limite = +00042\n minimo=-9223372036854775808\n', 0,
                  'limite\n42\nminimo\n-9223372036854775808\n'),
                 (b'\r\n limite=42\r\n', 0, 'limite\n42\n'),
                 (b'a=1\nsem igual', 2, 'a\n1\n'+erro+'4\n'),
                 (b'a=1\nb=', 2, 'a\n1\n'+erro+'1\n'),
                 (b'a=1\nb=12x', 2, 'a\n1\n'+erro+'2\n'),
                 (b'a=1\nb=9223372036854775808', 2, 'a\n1\n'+erro+'3\n'),
                 (b'a=1\n=2', 2, 'a\n1\n'+erro+'5\n'),
                 (b'\xff', 2, 'Erro: configuracao nao e UTF-8 valido.\n'),
                 (b'', 0, ''),
                 (None, 2, 'Erro: configuracao_numerica.txt ausente ou recusado.\n')]
        for nivel in range(9):
            for alvo in ('windows', 'linux'):
                imagem = compilar(p, alvo, nivel=nivel, otimizar=nivel > 0)
                if alvo != alvo_nativo():
                    continue
                for dados, codigo, esperado in casos:
                    with self.subTest(nivel=nivel, dados=dados):
                        antes = None if dados is None else lambda pasta: (pasta/'configuracao_numerica.txt').write_bytes(dados)
                        r, _ = rodar(imagem, antes=antes)
                        self.assertEqual((r.returncode, r.stdout, r.stderr), (codigo, esperado, ''))

    def test_benchmark_tem_soma_independente(self):
        fonte = (RAIZ/'benchmarks/conversoes_rs042u.rts').read_text(encoding='utf-8')
        self.verificar(fonte, str(sum(range(-1000, 1000)))+'\n', niveis=(0, 8))


if __name__ == '__main__':
    unittest.main()
