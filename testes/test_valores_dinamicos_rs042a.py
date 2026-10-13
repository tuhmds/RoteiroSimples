"""RS 0.42A.1: propriedade em chamadas, retornos e recursos nativos reais."""
import os
from pathlib import Path
import random
import struct
import subprocess
import sys
import tempfile
import unittest

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))
from backend import compilar
from backend.x86_64 import montar_codigo
from backend.windows_pe import montar_pe
from backend.linux_elf import montar_elf
from compilador.estrategia import decidir_estrategia
from compilador.modulos import carregar_fontes
from compilador.parser import analisar_programa

NIVEIS = tuple(range(9))

def alvo_nativo():
    if sys.platform == 'win32':
        return 'windows'
    if sys.platform == 'linux' and os.uname().machine == 'x86_64':
        return 'linux'
    raise unittest.SkipTest('Execucao exige Windows x64 ou Linux x86-64.')

def rodar(imagem, entrada=None, antes=None):
    alvo = alvo_nativo()
    with tempfile.TemporaryDirectory() as pasta:
        arquivo = Path(pasta) / ('programa.exe' if alvo == 'windows' else 'programa')
        arquivo.write_bytes(imagem)
        if alvo == 'linux':
            arquivo.chmod(0o755)
        if antes:
            antes(Path(pasta))
        resultado = subprocess.run([str(arquivo)], input=entrada, cwd=pasta,
            capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=20)
        arquivos = {p.name: p.read_bytes() for p in Path(pasta).iterdir()
                    if p.is_file() and p != arquivo}
        return resultado, arquivos

class TestesValoresDinamicosRS042A(unittest.TestCase):
    def verificar(self, fonte, esperado, entrada=None, niveis=NIVEIS):
        programa = analisar_programa(fonte)
        for nivel in niveis:
            with self.subTest(nivel=nivel):
                decisao = decidir_estrategia(programa, nivel, nivel > 0)
                self.assertEqual(decisao.gerador, 'conservador')
                imagem = compilar(programa, alvo_nativo(), otimizar=nivel > 0, nivel=nivel)
                resultado, _ = rodar(imagem, entrada)
                self.assertEqual((resultado.returncode, resultado.stdout), (0, esperado), resultado.stderr)

    def test_fabricas_vazias_pequenas_e_grandes_nove_niveis(self):
        for quantidade in (0, 1, 257, 4097):
            fonte = f'''funcao criar(quantidade: inteiro) -> lista[inteiro] {{
                seja valores: lista[inteiro]
                para indice de 0 ate quantidade - 1 {{
                    adicione(valores, indice * 3)
                }}
                retorne mova(valores)
            }}
            inicio {{
                seja recebidos: lista[inteiro] = criar({quantidade})
                escreva(tamanho(recebidos))
                se tamanho(recebidos) > 0 {{
                    escreva(recebidos[0])
                    escreva(recebidos[tamanho(recebidos) - 1])
                }}
                escreva(capacidade(recebidos) >= tamanho(recebidos))
            }}'''
            esperado = f'{quantidade}\n' + (f'0\n{(quantidade-1)*3}\n' if quantidade else '') + '1\n'
            self.verificar(fonte, esperado)

    def test_consumo_retorno_encadeado_e_temporarios(self):
        fonte = '''funcao criar() -> lista[] {
            seja valores: lista[]
            adicione(valores, 11)
            retorne mova(valores)
        }
        funcao acrescentar(valores: lista[], numero: inteiro) -> lista[] {
            adicione(valores, numero)
            retorne mova(valores)
        }
        funcao encaminhar(valores: lista[], numero: inteiro) -> lista[] {
            retorne acrescentar(mova(valores), numero)
        }
        funcao somar(valores: emprestimo[lista]) -> inteiro {
            retorne valores[0] + valores[1]
        }
        inicio {
            seja origem = criar()
            seja resultado = encaminhar(mova(origem), 22)
            escreva(somar(empreste(resultado)))
            seja outro = encaminhar(acrescentar(criar(), 7), 9)
            escreva(tamanho(outro))
            escreva(outro[2])
            seja recebido = mova(resultado)
            escreva(recebido[1])
            libere(recebido)
        }'''
        self.verificar(fonte, '33\n3\n9\n22\n')

    def test_listas_logicas_e_registros_com_texto_utf8(self):
        fonte = '''tipo Marcacao {
            numero: inteiro
            nome: texto[8]
        }
        funcao logicos() -> lista[logico] {
            seja valores: lista[logico]
            adicione(valores, verdadeiro)
            adicione(valores, falso)
            retorne mova(valores)
        }
        funcao registros() -> lista[Marcacao] {
            seja valores: lista[Marcacao]
            seja local: Marcacao
            local.numero = 17
            copie(local.nome, "ação")
            adicione(valores, local)
            local.numero = 99
            retorne mova(valores)
        }
        funcao encaminhar(valores: lista[Marcacao]) -> lista[Marcacao] {
            retorne mova(valores)
        }
        inicio {
            seja sinais = logicos()
            escreva(sinais[0])
            escreva(sinais[1])
            seja linhas = encaminhar(registros())
            seja encontrada: Marcacao = linhas[0]
            escreva(encontrada.numero)
            escreva(encontrada.nome)
        }'''
        self.verificar(fonte, '1\n0\n17\nação\n')

    def test_retorno_antecipado_e_donos_de_blocos(self):
        fonte = '''funcao selecionar(limite: inteiro) -> lista[] {
            seja externa: lista[]
            adicione(externa, 99)
            para indice de 0 ate 3 {
                seja interna: lista[]
                adicione(interna, indice)
                se indice == limite {
                    retorne mova(interna)
                }
            }
            retorne mova(externa)
        }
        inicio {
            para rodada de 0 ate 19 {
                seja recebida = selecionar(2)
                escreva(recebida[0])
            }
            seja ultima = selecionar(9)
            escreva(ultima[0])
        }'''
        self.verificar(fonte, '2\n'*20 + '99\n')

    def test_dados_gerados_reproduziveis_e_argumentos_mistos(self):
        gerador = random.Random(42001)
        valores = [gerador.randrange(-10000,10000) for _ in range(113)]
        inclusoes = '\n'.join(f'            adicione(dados, {valor})' for valor in valores)
        fonte = '''funcao criar() -> lista[] {
            seja dados: lista[]
''' + inclusoes + '''
            retorne mova(dados)
        }
        funcao calcular(a: inteiro, dados: lista[], b: inteiro) -> inteiro {
            seja total = a + b
            para indice de 0 ate tamanho(dados) - 1 {
                total = total + dados[indice]
            }
            retorne total
        }
        inicio {
            escreva(calcular(7, criar(), 11))
        }'''
        self.verificar(fonte, f'{sum(valores)+18}\n')

    def test_uso_apos_consumo_liberacao_e_indice_invalidos(self):
        cabecalho = '''funcao receber(dados: lista[]) -> inteiro {
            retorne tamanho(dados)
        }
        inicio {
            seja dados: lista[]
            adicione(dados, 17)
'''
        casos = (
            ('            escreva(receber(mova(dados)))\n            escreva(dados[0])', 'liber'),
            ('            libere(dados)\n            escreva(receber(mova(dados)))', 'liber'),
            ('            seja novo = mova(dados)\n            escreva(novo[1])', 'indice'),
            ('            seja novo = mova(dados)\n            escreva(novo[-1])', 'indice'),
            ('            dados[0] = receber(mova(dados))', 'liber'),
        )
        for comandos, mensagem in casos:
            fonte = cabecalho + comandos + '\n}'
            for nivel in (0,4,8):
                with self.subTest(comandos=comandos,nivel=nivel):
                    resultado, _ = rodar(compilar(analisar_programa(fonte), alvo_nativo(),
                                                   otimizar=nivel>0,nivel=nivel))
                    self.assertEqual(resultado.returncode,1,resultado.stderr)
                    self.assertIn(mensagem,(resultado.stdout+resultado.stderr).lower().replace('í','i'))

    def test_atribuicao_preserva_valor_quando_outra_lista_e_consumida(self):
        fonte = """funcao consumir(origem: lista[]) -> inteiro {
            retorne origem[0]
        }
        inicio {
            seja destino: lista[]
            adicione(destino, 10)
            adicione(destino, 11)
            seja origem: lista[]
            adicione(origem, 42)
            destino[1] = consumir(mova(origem))
            escreva(destino[0])
            escreva(destino[1])
        }"""
        self.verificar(fonte, '10\n42\n')

    def test_chamadas_em_indices_preservam_temporarios_da_expressao(self):
        fonte = '''funcao criar() -> lista[] {
            seja dados: lista[]
            adicione(dados, 17)
            retorne mova(dados)
        }
        funcao indice(dados: lista[]) -> inteiro {
            retorne 0
        }
        funcao combinar(a: inteiro, b: inteiro) -> inteiro {
            retorne a + b
        }
        funcao ler(dados: emprestimo[lista]) -> inteiro {
            retorne combinar(1, 1 + dados[indice(criar())])
        }
        inicio {
            seja dados: lista[]
            adicione(dados, 42)
            escreva(dados[indice(criar())])
            escreva(1 + dados[indice(criar())])
            escreva(combinar(1, dados[indice(criar())]))
            escreva(ler(empreste(dados)))
        }'''
        self.verificar(fonte, '42\n43\n43\n44\n')

    def test_recursao_com_donos_respeita_limite_de_pilha(self):
        fonte = '''funcao repetir(numero: inteiro) -> lista[] {
            seja valores: lista[]
            adicione(valores, numero)
            retorne repetir(numero + 1)
        }
        inicio {
            seja resultado = repetir(0)
            escreva(tamanho(resultado))
        }'''
        for nivel in (0,8):
            with self.subTest(nivel=nivel):
                resultado, _ = rodar(compilar(analisar_programa(fonte),alvo_nativo(),
                                               otimizar=nivel>0,nivel=nivel))
                self.assertEqual(resultado.returncode,1,resultado.stderr)
                self.assertIn('limite seguro de pilha',resultado.stdout+resultado.stderr)

    def test_recursao_contabiliza_argumentos_proprietarios(self):
        for quantidade in (4, 10):
            nomes = [f'dados{indice}' for indice in range(quantidade)]
            parametros = ', '.join(f'{nome}: lista[]' for nome in nomes)
            argumentos = ', '.join(f'mova({nome})' for nome in nomes)
            declaracoes = '\n'.join(f'seja {nome}: lista[]' for nome in nomes)
            fonte = f'''funcao repetir(numero: inteiro, {parametros}) -> lista[] {{
                se numero == 0 {{
                    retorne mova(dados0)
                }}
                retorne repetir(numero - 1, {argumentos})
            }}
            inicio {{
                {declaracoes}
                seja resultado = repetir(100000, {argumentos})
                escreva(tamanho(resultado))
            }}'''
            for nivel in (0, 8):
                with self.subTest(quantidade=quantidade, nivel=nivel):
                    resultado, _ = rodar(compilar(analisar_programa(fonte), alvo_nativo(),
                                                  otimizar=nivel > 0, nivel=nivel))
                    self.assertEqual(resultado.returncode, 1, resultado.stderr)
                    self.assertIn('limite seguro de pilha', resultado.stdout + resultado.stderr)
            self.verificar(fonte.replace('repetir(100000,', 'repetir(25,'), '0\n', niveis=(0, 8))

    def test_recursao_contabiliza_argumentos_pendentes(self):
        nomes = [f'dados{indice}' for indice in range(12)]
        parametros = ', '.join(f'{nome}: lista[]' for nome in nomes)
        argumentos = ', '.join(f'mova({nome})' for nome in nomes)
        declaracoes = '\n'.join(f'seja {nome}: lista[]' for nome in nomes)
        fonte = f'''funcao escolher({parametros}, resultado: lista[]) -> lista[] {{
            retorne mova(resultado)
        }}
        funcao criar(numero: inteiro) -> lista[] {{
            {declaracoes}
            se numero == 0 {{
                retorne mova(dados0)
            }}
            retorne escolher({argumentos}, criar(numero - 1))
        }}
        inicio {{
            seja resultado = criar(100000)
            escreva(tamanho(resultado))
        }}'''
        for nivel in (0, 8):
            with self.subTest(nivel=nivel):
                resultado, _ = rodar(compilar(analisar_programa(fonte), alvo_nativo(),
                                              otimizar=nivel > 0, nivel=nivel))
                self.assertEqual(resultado.returncode, 1, resultado.stderr)
                self.assertIn('limite seguro de pilha', resultado.stdout + resultado.stderr)
        self.verificar(fonte.replace('criar(100000)', 'criar(25)'), '0\n', niveis=(0, 8))

    def test_orcamento_protege_quadros_e_copias_grandes(self):
        principal = '''inicio {
            seja dados: bytes[600000]
            escreva(42)
        }'''
        funcao = '''funcao grande() -> inteiro {
            seja dados: bytes[600000]
            retorne 42
        }
        inicio {
            escreva(grande())
        }'''
        for fonte in (principal, funcao):
            self.verificar(fonte, '42\n', niveis=(0, 8))
        casos = (
            funcao.replace('escreva(grande())', 'seja reserva: bytes[600000]\n escreva(grande())'),
            '''funcao aceitar(dados: bytes[600000]) -> inteiro {
                retorne 42
            }
            inicio {
                seja dados: bytes[600000]
                escreva(aceitar(dados))
            }''',
        )
        for fonte in casos:
            for nivel in (0, 8):
                with self.subTest(fonte=fonte, nivel=nivel):
                    resultado, _ = rodar(compilar(analisar_programa(fonte), alvo_nativo(),
                                                  otimizar=nivel > 0, nivel=nivel))
                    self.assertEqual(resultado.returncode, 1, resultado.stderr)
                    self.assertIn('limite seguro de pilha', resultado.stdout + resultado.stderr)

    def test_recursao_com_sondagem_preserva_orcamento(self):
        fonte = '''funcao repetir(numero: inteiro) -> inteiro {
            seja dados: bytes[7000]
            adicione_byte(dados, 42)
            se numero == 0 {
                retorne dados[0]
            }
            retorne repetir(numero - 1)
        }
        inicio {
            escreva(repetir(100000))
        }'''
        for nivel in (0, 8):
            with self.subTest(nivel=nivel):
                resultado, _ = rodar(compilar(analisar_programa(fonte), alvo_nativo(),
                                              otimizar=nivel > 0, nivel=nivel))
                self.assertEqual(resultado.returncode, 1, resultado.stderr)
                self.assertIn('limite seguro de pilha', resultado.stdout + resultado.stderr)
        self.verificar(fonte.replace('repetir(100000)', 'repetir(25)'), '42\n', niveis=(0, 8))

    def test_quadro_principal_acima_do_orcamento_e_rejeitado(self):
        from compilador.erros import ErroCompilacao
        programa = analisar_programa('''inicio {
            seja dados: bytes[800000]
            escreva(42)
        }''')
        for alvo in ('windows', 'linux'):
            with self.subTest(alvo=alvo):
                with self.assertRaisesRegex(ErroCompilacao, 'pilha'):
                    compilar(programa, alvo, otimizar=False, nivel=0)

    def test_falha_de_alocacao_simulada_no_executavel(self):
        fonte = '''funcao criar() -> lista[] {
            seja valores: lista[]
            adicione(valores, 42)
            retorne mova(valores)
        }
        inicio {
            seja recebidos = criar()
            escreva(recebidos[0])
        }'''
        alvo = alvo_nativo()
        g,mensagens = montar_codigo(analisar_programa(fonte), alvo=='windows')
        imagem = bytearray(montar_pe(g,mensagens) if alvo=='windows' else montar_elf(g,mensagens))
        inicio = g.rotulos['rs_lista_alocar']
        fim = g.rotulos['rs_lista_desalocar']
        codigo = bytes(g.codigo[inicio:fim])
        if alvo=='windows':
            chamadas=[pos for pos in range(len(codigo)-1) if codigo[pos:pos+2]==b'\xff\x15']
            self.assertEqual(len(chamadas),1)
            pos=inicio+chamadas[0]
            trecho=bytes(g.codigo[pos:pos+6])
            substituto=b'\x31\xc0'+b'\x90'*4
        else:
            trecho=b'\xb8\x09\x00\x00\x00\x0f\x05'
            self.assertEqual(codigo.count(trecho),1)
            substituto=b'\x48\xc7\xc0\xf4\xff\xff\xff'  # retorno -ENOMEM
        self.assertEqual(imagem.count(trecho),1)
        pos=imagem.index(trecho)
        imagem[pos:pos+len(trecho)]=substituto
        resultado, _ = rodar(bytes(imagem))
        self.assertEqual(resultado.returncode,1,resultado.stderr)
        self.assertIn('reservar',resultado.stdout+resultado.stderr)

    def test_biblioteca_consulta_listas_arbitrarias_sem_copia(self):
        fonte = '''importe "padrao/listas.rts" como listas
inicio {
    seja valores: lista[]
    para indice de 0 ate 99 {
        adicione(valores, indice)
    }
    escreva(listas.buscar(empreste(valores), 72))
    escreva(listas.contar(empreste(valores), 11))
    escreva(listas.contem(empreste(valores), 101))
    escreva(listas.crescente(empreste(valores)))
    seja selecionados = listas.selecionar_intervalo(empreste(valores), 20, 22)
    escreva(tamanho(selecionados))
    escreva(selecionados[0])
    escreva(selecionados[2])
    escreva(tamanho(valores))
}'''
        with tempfile.TemporaryDirectory() as pasta:
            p=Path(pasta)/'principal.rts'
            p.write_text(fonte,encoding='utf-8')
            reunidas=carregar_fontes(p)
        self.verificar(reunidas.texto,'72\n1\n0\n1\n3\n20\n22\n100\n')

    def test_cadastro_em_rs_atualiza_grava_e_recupera(self):
        fonte=(RAIZ/'exemplos/aplicacoes/cadastro_pessoas_rs042a.rts').read_text(encoding='utf-8')
        programa=analisar_programa(fonte)
        esperado=('Codigo para atualizar:\nNova idade:\nCredito total em centavos:\n3750\n'
                  'Registros recuperados:\n3\nIdade recuperada:\n37\n')
        registros=((1,20,1000),(2,37,1250),(3,40,1500))
        for nivel in NIVEIS:
            with self.subTest(nivel=nivel):
                resultado,arquivos=rodar(compilar(programa,alvo_nativo(),otimizar=nivel>0,nivel=nivel),'2\n37\n')
                self.assertEqual((resultado.returncode,resultado.stdout),(0,esperado),resultado.stderr)
                self.assertEqual(arquivos['cadastro.rsd'],b''.join(struct.pack('<qqq',*r) for r in registros))

    def test_cadastro_rejeita_entrada_invalida_e_preserva_destino(self):
        fonte=(RAIZ/'exemplos/aplicacoes/cadastro_pessoas_rs042a.rts').read_text(encoding='utf-8')
        imagem=compilar(analisar_programa(fonte),alvo_nativo(),nivel=8)
        for entrada in ('0\n20\n','2\n151\n','99\n20\n'):
            resultado,arquivos=rodar(imagem,entrada)
            self.assertEqual(resultado.returncode,1)
            self.assertIn('Erro:',resultado.stdout)
            self.assertNotIn('cadastro.rsd',arquivos)
        original=b'ARQUIVO ANTERIOR'
        resultado,arquivos=rodar(imagem,'2\n37\n',lambda pasta:(pasta/'cadastro.rsd').write_bytes(original))
        self.assertEqual(resultado.returncode,2)
        self.assertEqual(arquivos['cadastro.rsd'],original)

if __name__=='__main__':
    unittest.main()
