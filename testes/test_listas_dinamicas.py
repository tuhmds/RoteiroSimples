"""RS 0.32: listas dinâmicas com propriedade única, memória nativa e tempo de vida."""
from pathlib import Path
import os
import subprocess
import sys
import tempfile
import unittest

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))
from compilador.parser import analisar_programa
from compilador.erros import ErroCompilacao


def executar(codigo, entrada=None):
    if sys.platform not in ('win32', 'linux') or (
            sys.platform == 'linux' and os.uname().machine != 'x86_64'):
        raise unittest.SkipTest('Requer Windows/Linux x86-64.')
    with tempfile.TemporaryDirectory() as pasta:
        fonte = Path(pasta) / 'principal.rts'
        fonte.write_text(codigo, encoding='utf-8')
        alvo = 'windows' if sys.platform == 'win32' else 'linux'
        saida = Path(pasta) / ('programa.exe' if alvo == 'windows' else 'programa')
        proc = subprocess.run(
            [sys.executable, str(RAIZ/'compilar.py'), str(fonte),
             '--alvo', alvo, '-O', '8', '-o', str(saida)],
            capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=30)
        if proc.returncode:
            raise AssertionError(proc.stderr + proc.stdout)
        return subprocess.run([str(saida)], input=entrada, capture_output=True,
                              text=True, encoding='utf-8', errors='replace', timeout=15)


class TestesListasDinamicas(unittest.TestCase):
    def test_crescimento_automatico_e_valores(self):
        fonte = """inicio {
            seja valores: lista[]
            escreva(tamanho(valores))
            escreva(capacidade(valores))
            para i de 0 ate 999 {
                adicione(valores, i * 2)
            }
            escreva(tamanho(valores))
            escreva(valores[0])
            escreva(valores[99])
            escreva(valores[999])
            valores[99] = -15
            escreva(valores[99])
            escreva(capacidade(valores))
        }"""
        resultado = executar(fonte)
        self.assertEqual(resultado.returncode, 0, resultado.stderr + resultado.stdout)
        linhas = resultado.stdout.splitlines()
        self.assertEqual(linhas[:6], ['0','0','1000','0','198','1998'])
        self.assertEqual(linhas[6], '-15')
        self.assertGreaterEqual(int(linhas[7]), 1000)

    def test_remocao_limpeza_e_reuso(self):
        fonte = """inicio {
            seja dados: lista[]
            adicione(dados, 10)
            adicione(dados, 20)
            remova_ultimo(dados)
            escreva(tamanho(dados))
            escreva(dados[0])
            limpe_lista(dados)
            escreva(tamanho(dados))
            adicione(dados, 99)
            escreva(dados[0])
        }"""
        resultado=executar(fonte)
        self.assertEqual((resultado.returncode, resultado.stdout),(0,'1\n10\n0\n99\n'))

    def test_propriedade_em_funcoes_e_reentrancia(self):
        fonte = """funcao somar(n: inteiro) -> inteiro {
            seja valores: lista[]
            seja total = 0
            para i de 0 ate 100 {
                adicione(valores, n + i)
            }
            para k de 0 ate 100 {
                total = total + valores[k]
            }
            retorne total
        }
        inicio {
            escreva(somar(0))
            escreva(somar(1))
            escreva(somar(2))
        }"""
        resultado = executar(fonte)
        self.assertEqual((resultado.returncode, resultado.stdout),(0,'5050\n5151\n5252\n'))

    def test_liberacao_explicita_e_segunda_liberacao_rejeitada(self):
        fonte = """inicio {
            seja colecao: lista[]
            adicione(colecao, 10)
            libere(colecao)
            escreva(123)
        }"""
        resultado=executar(fonte)
        self.assertEqual((resultado.returncode, resultado.stdout),(0,'123\n'))
        for comando in ('libere(colecao)', 'adicione(colecao, 42)', 'escreva(tamanho(colecao))',
                        'escreva(colecao[0])', 'remova_ultimo(colecao)'):
            fonte = """inicio {
                seja colecao: lista[]
                adicione(colecao, 10)
                libere(colecao)
                """+comando+"\n}"
            with self.subTest(comando=comando):
                r=executar(fonte)
                self.assertNotEqual(r.returncode,0)
                self.assertIn('liber',r.stdout.lower()+r.stderr.lower())

    def test_indices_invalidos(self):
        for expressao in ('colecao[0]', 'colecao[-1]', 'colecao[2]'):
            fonte="""inicio {
                seja colecao: lista[]
                adicione(colecao, 8)
                escreva("""+expressao+""")
            }"""
            if expressao == 'colecao[0]':
                r=executar(fonte)
                self.assertEqual((r.returncode,r.stdout),(0,'8\n'))
            else:
                r=executar(fonte)
                self.assertNotEqual(r.returncode,0)
                self.assertIn('indice', (r.stdout+r.stderr).lower().replace('í','i'))

    def test_ler_indice_existente(self):
        fonte="""inicio {
            seja colecao: lista[]
            adicione(colecao, 0)
            leia(colecao[0])
            escreva(colecao[0])
        }"""
        r=executar(fonte,'123\n')
        self.assertEqual((r.returncode,r.stdout),(0,'123\n'))

    def test_remover_lista_vazia_falha(self):
        r=executar("""inicio {
            seja colecao: lista[]
            remova_ultimo(colecao)
        }""")
        self.assertNotEqual(r.returncode,0)

    def test_proibir_copia_e_emprestimo_implicitos(self):
        proibidos=[
            """inicio {
                seja a: lista[]
                seja b = a
            }""",
            """inicio {
                seja a: lista[]
                seja b: lista[]
                a = b
            }""",
            """funcao receber(a: lista[]) -> inteiro {
                retorne 1
            }
            inicio {
                escreva(1)
            }""",
        ]
        for fonte in proibidos:
            with self.subTest(fonte=fonte):
                with self.assertRaises(ErroCompilacao):
                    analisar_programa(fonte)

    def test_lista_fixa_preservada(self):
        fonte="""inicio {
            seja fixa: lista[3]
            fixa[0] = 10
            fixa[2] = 30
            escreva(tamanho(fixa))
            escreva(fixa[2])
            seja movel: lista[]
            adicione(movel, 77)
            escreva(movel[0])
        }"""
        r=executar(fonte)
        self.assertEqual((r.returncode,r.stdout),(0,'3\n30\n77\n'))


    def test_rs033_mover_propriedade_e_reutilizar_destino(self):
        fonte = """inicio {
            seja origem: lista[]
            seja destino: lista[]
            adicione(origem, 11)
            adicione(origem, 22)
            adicione(destino, 99)
            mova(destino, origem)
            escreva(tamanho(destino))
            escreva(destino[0])
            escreva(destino[1])
            mova(origem, destino)
            escreva(origem[1])
        }"""
        r = executar(fonte)
        self.assertEqual((r.returncode, r.stdout), (0, '2\n11\n22\n22\n'), r.stderr)

    def test_rs033_origem_movida_inacessivel(self):
        fonte = """inicio {
            seja fonte: lista[]
            seja alvo: lista[]
            adicione(fonte, 5)
            mova(alvo, fonte)
            escreva(tamanho(fonte))
        }"""
        r = executar(fonte)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn('liber', (r.stdout + r.stderr).lower())

    def test_rs033_blocos_em_lacos_e_desvios(self):
        fonte = """inicio {
            seja soma = 0
            para i de 1 ate 6 {
                seja itens: lista[]
                adicione(itens, i)
                se i == 3 {
                    seja provisoria: lista[]
                    adicione(provisoria, 123)
                    continue
                }
                se i == 6 {
                    seja provisoria: lista[]
                    adicione(provisoria, 999)
                    pare
                }
                soma = soma + itens[0]
            }
            escreva(soma)
        }"""
        r = executar(fonte)
        self.assertEqual((r.returncode, r.stdout), (0, '12\n'), r.stderr)

    def test_rs033_retorno_antecipado_sem_descritor_nao_iniciado(self):
        fonte = """funcao valor(n: inteiro) -> inteiro {
            se n == 1 {
                seja imediata: lista[]
                adicione(imediata, 7)
                retorne imediata[0]
            }
            seja posterior: lista[]
            adicione(posterior, 9)
            retorne posterior[0]
        }
        inicio {
            escreva(valor(1))
            escreva(valor(2))
        }"""
        r = executar(fonte)
        self.assertEqual((r.returncode, r.stdout), (0, '7\n9\n'), r.stderr)

    def test_rs033_movimento_proprio_e_copias_proibidos(self):
        erros = [
            """inicio {
                seja dados: lista[]
                mova(dados, dados)
            }""",
            """inicio {
                seja dados: lista[]
                seja copia = dados
            }""",
            """inicio {
                seja dados: lista[]
                mova(dados, 8)
            }""",
        ]
        for codigo in erros:
            with self.subTest(codigo=codigo):
                with self.assertRaises(ErroCompilacao):
                    analisar_programa(codigo)

    def test_rs033_dono_externo_sobrevive_ao_continue(self):
        fonte = """inicio {
            seja externo: lista[]
            adicione(externo, 41)
            para i de 1 ate 3 {
                seja temporaria: lista[]
                adicione(temporaria, i)
                continue
            }
            escreva(externo[0])
        }"""
        r = executar(fonte)
        self.assertEqual((r.returncode, r.stdout), (0, '41\n'), r.stderr)


    def test_rs033_emprestimo_leitura_e_ausencia_de_copia(self):
        fonte = """funcao total(valores: emprestimo[lista]) -> inteiro {
            seja soma = 0
            para i de 0 ate tamanho(valores) - 1 {
                soma = soma + valores[i]
            }
            retorne soma
        }
        inicio {
            seja vendas: lista[]
            adicione(vendas, 8)
            adicione(vendas, 13)
            adicione(vendas, 21)
            escreva(total(empreste(vendas)))
            escreva(vendas[2])
            escreva(tamanho(vendas))
        }"""
        r = executar(fonte)
        self.assertEqual((r.returncode, r.stdout), (0, '42\n21\n3\n'), r.stderr)

    def test_rs033_emprestimo_aninhado_e_indice_variavel(self):
        fonte = """funcao ultimo(dados: emprestimo[lista]) -> inteiro {
            retorne dados[tamanho(dados) - 1]
        }
        funcao descrever(dados: emprestimo[lista]) -> inteiro {
            retorne ultimo(dados) + capacidade(dados)
        }
        inicio {
            seja numeros: lista[]
            adicione(numeros, 5)
            adicione(numeros, 7)
            escreva(descrever(empreste(numeros)))
            escreva(numeros[0])
        }"""
        r = executar(fonte)
        self.assertEqual((r.returncode, r.stdout), (0, '11\n5\n'), r.stderr)

    def test_rs033_emprestimo_de_lista_local_em_laco(self):
        fonte = """funcao dobrar(dados: emprestimo[lista]) -> inteiro {
            retorne dados[0] * 2
        }
        inicio {
            para i de 1 ate 3 {
                seja temporaria: lista[]
                adicione(temporaria, i)
                escreva(dobrar(empreste(temporaria)))
            }
        }"""
        r = executar(fonte)
        self.assertEqual((r.returncode, r.stdout), (0, '2\n4\n6\n'), r.stderr)

    def test_rs033_emprestimo_de_origem_movida_rejeitado_na_execucao(self):
        fonte = """funcao primeiro(dados: emprestimo[lista]) -> inteiro {
            retorne dados[0]
        }
        inicio {
            seja fonte: lista[]
            seja destino: lista[]
            adicione(fonte, 19)
            mova(destino, fonte)
            escreva(primeiro(empreste(fonte)))
        }"""
        r = executar(fonte)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn('liber', (r.stderr + r.stdout).lower())

    def test_rs033_indice_invalido_de_emprestimo(self):
        fonte = """funcao consultar(dados: emprestimo[lista]) -> inteiro {
            retorne dados[2]
        }
        inicio {
            seja numeros: lista[]
            adicione(numeros, 5)
            escreva(consultar(empreste(numeros)))
        }"""
        r = executar(fonte)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn('indice', (r.stderr + r.stdout).lower().replace('í','i'))

    def test_rs033_emprestimos_rejeitados_na_compilacao(self):
        casos = [
            # Proibir passagem de lista proprietária sem empréstimo explícito.
            """funcao contar(dados: emprestimo[lista]) -> inteiro {
                retorne tamanho(dados)
            }
            inicio {
                seja numeros: lista[]
                escreva(contar(numeros))
            }""",
            # Não pode transformar empréstimo em proprietário.
            """funcao f(dados: emprestimo[lista]) -> inteiro {
                adicione(dados, 10)
                retorne 0
            }
            inicio {
                escreva(1)
            }""",
            """funcao f(dados: emprestimo[lista]) -> inteiro {
                remova_ultimo(dados)
                retorne 0
            }
            inicio {
                escreva(1)
            }""",
            """funcao f(dados: emprestimo[lista]) -> inteiro {
                libere(dados)
                retorne 0
            }
            inicio {
                escreva(1)
            }""",
            """funcao f(dados: emprestimo[lista]) -> inteiro {
                mova(dados, dados)
                retorne 0
            }
            inicio {
                escreva(1)
            }""",
            """funcao f(dados: emprestimo[lista]) -> inteiro {
                leia(dados[0])
                retorne 0
            }
            inicio {
                escreva(1)
            }""",
            """funcao f(dados: emprestimo[lista]) -> inteiro {
                dados[0] = 8
                retorne 0
            }
            inicio {
                escreva(1)
            }""",
            """funcao f(dados: emprestimo[lista]) -> inteiro {
                seja ref = dados
                retorne 0
            }
            inicio {
                escreva(1)
            }""",
            """funcao f(dados: emprestimo[lista]) -> inteiro {
                dados = dados
                retorne 0
            }
            inicio {
                escreva(1)
            }""",
            """funcao f(dados: emprestimo[lista]) -> emprestimo[lista] {
                retorne dados
            }
            inicio {
                escreva(1)
            }""",
            """inicio {
                seja numeros: lista[]
                seja alias = empreste(numeros)
            }""",
            """inicio {
                seja numeros: lista[]
                escreva(empreste(numeros))
            }""",
            """inicio {
                seja numeros: lista[]
                escreva(empreste(numeros) == empreste(numeros))
            }""",
            """inicio {
                seja fixa: lista[1]
                escreva(empreste(fixa))
            }""",
        ]
        for fonte in casos:
            with self.subTest(fonte=fonte):
                with self.assertRaises(ErroCompilacao):
                    analisar_programa(fonte)

    def test_rs033_emprestimo_multiplos_argumentos(self):
        fonte = """funcao somar(a: inteiro, dados: emprestimo[lista], b: inteiro) -> inteiro {
            retorne a + dados[0] + b
        }
        inicio {
            seja valores: lista[]
            adicione(valores, 9)
            escreva(somar(5, empreste(valores), 7))
        }"""
        r = executar(fonte)
        self.assertEqual((r.returncode, r.stdout), (0, '21\n'), r.stderr)


    def test_rs033_emprestimo_vazio_e_dois_argumentos_de_leitura(self):
        fonte = """funcao combinado(a: emprestimo[lista], b: emprestimo[lista]) -> inteiro {
            retorne tamanho(a) * 100 + tamanho(b) + b[0]
        }
        inicio {
            seja vazia: lista[]
            seja preenchida: lista[]
            adicione(preenchida, 19)
            escreva(combinado(empreste(vazia), empreste(preenchida)))
            escreva(tamanho(vazia))
            escreva(preenchida[0])
        }"""
        resultado = executar(fonte)
        self.assertEqual((resultado.returncode, resultado.stdout),
                         (0, '20\n0\n19\n'), resultado.stderr)

    def test_rs033_emprestimo_nao_pode_escapar_de_funcao(self):
        fonte = """funcao obter(entrada: emprestimo[lista]) -> emprestimo[lista] {
            retorne entrada
        }
        inicio {
            seja valores: lista[]
            adicione(valores, 8)
            escreva(8)
        }"""
        with self.assertRaisesRegex(ErroCompilacao, 'nao pode ser retornado'):
            analisar_programa(fonte)

    def test_rs033_emprestimo_nao_pode_ser_guardado_apos_escopo(self):
        fonte = """funcao obter(entrada: emprestimo[lista]) -> inteiro {
            seja referencia = entrada
            retorne 0
        }
        inicio {
            seja dados: lista[]
            escreva(obter(empreste(dados)))
        }"""
        with self.assertRaisesRegex(ErroCompilacao, 'nao pode ser armazenado'):
            analisar_programa(fonte)

if __name__ == '__main__':
    unittest.main()
