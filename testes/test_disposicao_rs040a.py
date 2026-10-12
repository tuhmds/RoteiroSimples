"""RS 0.40A — contratos de disposicao, cópia e realocação de registros binários.

Teste diferencial no executável nativo: compara O0 a O8 e valida os
dados após crescimento/reuso de listas proprietárias.
"""
from pathlib import Path
import os
import subprocess
import sys
import tempfile
import unittest

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))
from compilador.disposicao_tipos import palavras_tipo
from compilador.parser import analisar_programa
from backend import compilar
from backend.listas_dinamicas import largura_elemento


class RegistrosDeTeste:
    registros = {
        'Dentro': (('primeiro', 'inteiro'), ('dados', ('bytes', 9)),
                   ('ultima', 'logico')),
        'Fora': (('id', 'inteiro'), ('interno', 'Dentro'),
                 ('titulo', ('texto', 17)), ('numeros', ('lista', 'inteiro', 3))),
    }


def fonte_registro(capacidade, quantidade=24):
    if capacidade < 2:
        acrescentos = 'adicione_byte(item.bloco.dados, i)'
        consulta_segundo = ''
        esperado_segundo = ''
    else:
        acrescentos = ('adicione_byte(item.bloco.dados, i)\n'
                       '        adicione_byte(item.bloco.dados, 255)')
        consulta_segundo = ('    escreva(primeiro.bloco.dados[1])\n'
                            '    escreva(ultimo.bloco.dados[1])\n')
        esperado_segundo = '255\n255\n'
    fonte = f"""tipo Miolo {{
        dados: bytes[{capacidade}]
        contador: inteiro
    }}
    tipo Pacote {{
        codigo: inteiro
        bloco: Miolo
        encerramento: inteiro
    }}
    inicio {{
        seja item: Pacote
        seja registros: lista[Pacote]
        para i de 1 ate {quantidade} {{
            limpe(item.bloco.dados)
            {acrescentos}
            item.codigo = i * 10
            item.bloco.contador = i * 100
            item.encerramento = i * 1000
            adicione(registros, item)
        }}
        escreva(tamanho(registros))
        seja primeiro: Pacote = registros[0]
        seja ultimo: Pacote = registros[{quantidade - 1}]
        escreva(primeiro.codigo)
        escreva(primeiro.bloco.dados[0])
        escreva(primeiro.bloco.contador)
        escreva(primeiro.encerramento)
        escreva(ultimo.codigo)
        escreva(ultimo.bloco.dados[0])
        escreva(ultimo.bloco.contador)
        escreva(ultimo.encerramento)
        {consulta_segundo}
        // A substituicao nao deve alterar outro elemento.
        item.codigo = 777
        limpe(item.bloco.dados)
        adicione_byte(item.bloco.dados, 88)
        item.bloco.contador = 999
        item.encerramento = 123
        registros[1] = item
        seja substituido: Pacote = registros[1]
        escreva(substituido.bloco.dados[0])
        escreva(substituido.bloco.contador)
        escreva(substituido.encerramento)
        escreva(primeiro.bloco.dados[0])
        remova_ultimo(registros)
        escreva(tamanho(registros))
    }}"""
    esperado = (f'{quantidade}\n10\n1\n100\n1000\n'
                f'{quantidade * 10}\n{quantidade}\n'
                f'{quantidade * 100}\n{quantidade * 1000}\n'
                + esperado_segundo + f'88\n999\n123\n1\n{quantidade-1}\n')
    return fonte, esperado


def alvo():
    if sys.platform == 'win32':
        return 'windows'
    if sys.platform == 'linux' and os.uname().machine == 'x86_64':
        return 'linux'
    raise unittest.SkipTest('Somente execução nativa Windows/Linux x86-64.')


def executar(codigo, nivel, pasta, nome):
    programa = analisar_programa(codigo)
    destino = Path(pasta)/(nome+('.exe' if alvo() == 'windows' else ''))
    destino.write_bytes(compilar(programa, alvo(), otimizar=nivel > 0, nivel=nivel))
    if alvo() == 'linux':
        destino.chmod(0o700)
    return subprocess.run([str(destino)], cwd=pasta,
                          capture_output=True, text=True, encoding='utf-8',
                          errors='replace', timeout=20)


class TestesDisposicaoRS040A(unittest.TestCase):
    def test_larguras_concordam_para_tipos_compostos(self):
        registros = RegistrosDeTeste.registros
        instancia = RegistrosDeTeste()
        for capacidade in (1, 8, 9, 16, 64):
            with self.subTest(capacidade=capacidade):
                dados = ('bytes', capacidade)
                correto = 1 + (capacidade + 7)//8
                self.assertEqual(palavras_tipo(dados, registros), correto)
                self.assertEqual(
                    largura_elemento(instancia, ('lista_dinamica', dados)), correto)
                tipo_registro = (('codigo', 'inteiro'), ('dados', dados),
                                 ('fim', 'inteiro'))
                registros_temporarios = dict(registros, Pacote=tipo_registro)
                g = type('EmissorDeTeste', (), {'registros': registros_temporarios})()
                esperado = correto + 2
                self.assertEqual(palavras_tipo('Pacote', registros_temporarios), esperado)
                self.assertEqual(largura_elemento(g, ('lista_dinamica', 'Pacote')),
                                 esperado)
        # Mistura níveis: registro contendo bytes, listas fixas e texto.
        self.assertEqual(palavras_tipo('Dentro', registros), 5)
        self.assertEqual(palavras_tipo('Fora', registros), 1 + 5 + 4 + 3)
        self.assertEqual(largura_elemento(instancia, ('lista_dinamica', 'Fora')),
                         1 + 5 + 4 + 3)

    def test_largura_de_registro_binario_nunca_eh_uma_palavra(self):
        registros = {'Registro': (('cabecalho', ('bytes', 9)),
                                 ('codigo', 'inteiro'))}
        g = type('EmissorDeTeste', (), {'registros': registros})()
        self.assertEqual(largura_elemento(g, ('lista_dinamica', 'Registro')), 4)

    def test_crescimento_registro_com_bytes_na_execucao(self):
        for capacidade in (1, 8, 9, 16, 64):
            for nivel in (0, 8):
                with self.subTest(capacidade=capacidade,nivel=nivel):
                    codigo, esperado = fonte_registro(capacidade)
                    with tempfile.TemporaryDirectory() as pasta:
                        retorno = executar(codigo, nivel, pasta,
                                           f'registros_{capacidade}_{nivel}')
                        self.assertEqual((retorno.returncode, retorno.stdout),
                                         (0, esperado), retorno.stderr)

    def test_paridade_nove_niveis_registro_com_bytes(self):
        codigo, esperado = fonte_registro(9, quantidade=18)
        with tempfile.TemporaryDirectory() as pasta:
            for nivel in range(9):
                with self.subTest(nivel=nivel):
                    retorno = executar(codigo, nivel, pasta, f'paridade_{nivel}')
                    self.assertEqual((retorno.returncode, retorno.stdout),
                                     (0, esperado), retorno.stderr)


if __name__ == '__main__':
    unittest.main()
