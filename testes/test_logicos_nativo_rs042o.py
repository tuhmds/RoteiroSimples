"""Operadores logicos: ordem, falhas, donos e equivalencia nativa O0-O8."""
import random
import unittest

from backend import compilar
from compilador.estrategia import decidir_estrategia
from compilador.parser import analisar_programa
from testes.test_valores_dinamicos_rs042a import alvo_nativo, rodar

NIVEIS = tuple(range(9))
MARCAR = '''funcao marcar(codigo: inteiro, valor: logico) -> logico {
    escreva(codigo)
    retorne valor
}
'''


class TestesLogicosNativoRS042O(unittest.TestCase):
    def executar(self, fonte, esperado, entrada=None, niveis=NIVEIS,
                 gerador=None, arquivos=None):
        programa = analisar_programa(fonte)
        for nivel in niveis:
            with self.subTest(nivel=nivel):
                decisao = decidir_estrategia(programa, nivel, nivel > 0)
                if gerador:
                    self.assertEqual(decisao.gerador,
                                     gerador(nivel) if callable(gerador) else gerador)
                for alvo in ('windows', 'linux'):
                    imagem = compilar(programa, alvo, nivel=nivel, otimizar=nivel > 0)
                    self.assertTrue(imagem.startswith(b'MZ' if alvo == 'windows' else b'\x7fELF'))
                    if alvo == alvo_nativo():
                        resultado, presentes = rodar(imagem, entrada)
                self.assertEqual((resultado.returncode, resultado.stdout, resultado.stderr),
                                 (0, esperado, ''))
                if arquivos is not None:
                    self.assertEqual(presentes, arquivos)
        return programa

    def test_tabela_verdade_com_valores_recebidos_em_execucao(self):
        fonte = '''inicio {
    seja primeiro = 0
    seja segundo = 0
    leia(primeiro)
    leia(segundo)
    seja a = primeiro == 1
    seja b = segundo == 1
    escreva(a e b)
    escreva(a ou b)
    escreva(nao a)
    escreva(nao b)
    escreva(nao nao a)
}'''
        for a in (False, True):
            for b in (False, True):
                with self.subTest(a=a, b=b):
                    esperado = ''.join(str(int(v)) + '\n' for v in (a and b, a or b, not a, not b, a))
                    self.executar(fonte, esperado, f'{int(a)}\n{int(b)}\n',
                                  gerador=lambda n: 'ssa' if n >= 4 else 'intermediario')

    def test_precedencia_e_parenteses_na_execucao(self):
        fonte = '''inicio {
    escreva(verdadeiro ou falso e falso)
    escreva((verdadeiro ou falso) e falso)
    escreva(nao 2 + 3 * 4 < 15)
    escreva(nao 2 + 3 * 4 >= 15)
    escreva(nao falso e verdadeiro ou falso)
    escreva(verdadeiro == (nao falso))
}'''
        self.executar(fonte, '1\n0\n0\n1\n1\n1\n')

    def test_ordem_e_curto_circuito_com_chamadas_observaveis(self):
        fonte = MARCAR + '''inicio {
    escreva(marcar(11, falso) e marcar(12, verdadeiro))
    escreva(marcar(21, verdadeiro) ou marcar(22, falso))
    escreva(marcar(31, verdadeiro) e marcar(32, falso))
    escreva(marcar(41, falso) ou marcar(42, verdadeiro))
    escreva(nao marcar(51, falso))
    seja descartado = marcar(61, verdadeiro) e falso
    seja outro = marcar(71, falso) ou verdadeiro
}'''
        self.executar(fonte, '11\n0\n21\n1\n31\n32\n0\n41\n42\n1\n51\n1\n61\n71\n',
                      gerador=lambda n: 'ssa' if n >= 4 else 'intermediario')

    def test_falhas_do_lado_ignorado_nao_ocorrem(self):
        fonte = '''inicio {
    seja divisor = 0
    escreva(falso e 10 / divisor > 0)
    escreva(verdadeiro ou 10 / divisor > 0)
    escreva(falso e 9223372036854775807 + 1 > 0)
    escreva(verdadeiro ou -(-9223372036854775808) > 0)
    escreva(nao (falso e 10 % divisor == 0))
}'''
        self.executar(fonte, '0\n1\n0\n1\n1\n')

    def test_falhas_obrigatorias_permanecem_em_todos_os_niveis(self):
        expressoes = (
            ('verdadeiro e 10 / zero > 0', 'divis'),
            ('falso ou 10 / zero > 0', 'divis'),
            ('10 / zero > 0 e falso', 'divis'),
            ('10 / zero > 0 ou verdadeiro', 'divis'),
            ('verdadeiro e 9223372036854775807 + 1 > 0', 'estouro'),
            ('falso ou -(-9223372036854775808) > 0', 'estouro'),
        )
        for expressao, erro in expressoes:
            fonte = 'inicio {\n seja zero = 0\n escreva(' + expressao + ')\n escreva("INDEVIDO")\n}'
            programa = analisar_programa(fonte)
            for nivel in NIVEIS:
                with self.subTest(expressao=expressao, nivel=nivel):
                    for alvo in ('windows', 'linux'):
                        imagem = compilar(programa, alvo, nivel=nivel, otimizar=nivel > 0)
                        if alvo == alvo_nativo():
                            resultado, _ = rodar(imagem)
                    self.assertEqual(resultado.returncode, 1)
                    self.assertIn(erro, (resultado.stdout + resultado.stderr).lower())
                    self.assertNotIn('INDEVIDO', resultado.stdout)

    def test_indices_de_bytes_dinamicos_guardados_por_condicao(self):
        fonte = '''inicio {
    seja dados: bytes
    escreva(tamanho(dados) > 0 e dados[0] == 7)
    escreva(tamanho(dados) == 0 ou dados[0] == 7)
    adicione_byte(dados, 7)
    escreva(tamanho(dados) > 0 e dados[0] == 7)
    escreva(nao (tamanho(dados) == 0) e dados[0] == 7)
}'''
        self.executar(fonte, '0\n1\n1\n1\n', gerador='conservador')

    def test_transferencia_so_consumida_quando_direita_executa(self):
        fonte = '''funcao consumir(dados: bytes) -> logico {
    escreva(tamanho(dados))
    retorne verdadeiro
}
inicio {
    seja numero = 0
    leia(numero)
    seja deve = numero == 1
    seja dados: bytes
    adicione_byte(dados, 7)
    escreva(deve e consumir(mova(dados)))
    se nao deve {
        escreva(tamanho(dados))
    }
}'''
        self.executar(fonte, '0\n1\n', '0\n', gerador='conservador')
        self.executar(fonte, '1\n1\n', '1\n', gerador='conservador')

    def test_temporario_proprietario_na_chamada_ignorada_nao_e_criado(self):
        fonte = '''funcao criar() -> bytes {
    escreva(31)
    seja dados: bytes
    adicione_byte(dados, 7)
    retorne mova(dados)
}
funcao consumir(dados: bytes) -> logico {
    escreva(32)
    retorne tamanho(dados) == 1
}
inicio {
    escreva(falso e consumir(criar()))
    escreva(verdadeiro ou consumir(criar()))
    escreva(verdadeiro e consumir(criar()))
}'''
        self.executar(fonte, '0\n1\n31\n32\n1\n', gerador='conservador')

    def test_escrita_de_arquivo_nao_antecipa_o_lado_direito(self):
        funcao = '''funcao gravar() -> logico {
    seja dados: bytes[1]
    adicione_byte(dados, 77)
    grave_arquivo("logica.rsd", dados)
    retorne verdadeiro
}
inicio {
'''
        self.executar(funcao + ' escreva(falso e gravar())\n escreva(verdadeiro ou gravar())\n}',
                      '0\n1\n', gerador='conservador', arquivos={})
        self.executar(funcao + ' escreva(verdadeiro e gravar())\n}',
                      '1\n', gerador='conservador', arquivos={'logica.rsd': b'M'})

    def test_lacos_retornos_e_juncoes_com_valores_vivos(self):
        fonte = '''funcao calcular(limite: inteiro) -> inteiro {
    seja indice = 0
    seja total = 0
    enquanto indice < limite e nao (indice >= 8) {
        indice = indice + 1
        se indice == 2 ou indice == 4 {
            continue
        }
        total = total + indice
        se total >= 15 e indice > 3 {
            pare
        }
    }
    se nao (total < 15) e total < 30 {
        retorne total
    }
    retorne -1
}
inicio {
    escreva(calcular(10))
    escreva(calcular(1))
}'''
        self.executar(fonte, '15\n-1\n', gerador=lambda n: 'ssa' if n >= 4 else 'intermediario')

    def test_chamadas_com_logicos_dentro_de_argumentos_e_pilha_ocupada(self):
        fonte = MARCAR + '''funcao escolher(a: inteiro, teste: logico, b: inteiro) -> inteiro {
    se teste {
        retorne a + b
    }
    retorne a - b
}
funcao calcular(numero: inteiro) -> inteiro {
    seja a = numero + 10
    seja b = numero + 20
    seja c = numero + 30
    seja d = numero + 40
    seja quinto = numero + 50
    seja f = numero + 60
    seja g = numero + 70
    retorne a + b + c + d + quinto + f + g + escolher(5, marcar(81, falso) ou marcar(82, verdadeiro), 7)
}
inicio {
    escreva(100 + escolher(1, falso e marcar(91, verdadeiro), calcular(2)))
}'''
        self.executar(fonte, '81\n82\n-205\n', gerador=lambda n: 'ssa' if n >= 4 else 'intermediario')

    def test_arvores_geradas_com_oraculo_independente_de_valores_e_tracos(self):
        aleatorio = random.Random(42015)
        contador = 0

        def gerar(profundidade):
            nonlocal contador
            if profundidade == 0 or aleatorio.random() < .28:
                contador += 1
                return ('folha', contador, aleatorio.randrange(3))
            operador = aleatorio.choice(('e', 'ou', 'nao'))
            esquerda = gerar(profundidade - 1)
            return (operador, esquerda) if operador == 'nao' else (operador, esquerda, gerar(profundidade - 1))

        arvores = [gerar(4) for _ in range(18)]

        def fonte(no):
            if no[0] == 'folha':
                return f'marcar({no[1]}, numero / {1 << no[2]} % 2 == 1)'
            if no[0] == 'nao':
                return 'nao (' + fonte(no[1]) + ')'
            return '(' + fonte(no[1]) + ') ' + no[0] + ' (' + fonte(no[2]) + ')'

        def avaliar(no, numero, traco):
            if no[0] == 'folha':
                traco.append(no[1])
                return bool((numero >> no[2]) & 1)
            if no[0] == 'nao':
                return not avaliar(no[1], numero, traco)
            esquerda = avaliar(no[1], numero, traco)
            if no[0] == 'e':
                return avaliar(no[2], numero, traco) if esquerda else False
            return True if esquerda else avaliar(no[2], numero, traco)

        programa = MARCAR + 'inicio {\n seja numero = 0\n leia(numero)\n'
        for indice, arvore in enumerate(arvores):
            programa += f' escreva({900 + indice})\n escreva(' + fonte(arvore) + ')\n'
        programa += '}'
        for numero in (0, 3, 7):
            traco = []
            for indice, arvore in enumerate(arvores):
                traco.append(900 + indice)
                traco.append(int(avaliar(arvore, numero, traco)))
            esperado = ''.join(str(valor) + '\n' for valor in traco)
            self.executar(programa, esperado, f'{numero}\n',
                          gerador=lambda n: 'ssa' if n >= 4 else 'intermediario')
