"""Execução nativa de texto crescente: UTF-8, propriedade, arquivos e falhas."""
import json
from pathlib import Path
import random
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
from compilador.parser import analisar_programa
from compilador.modulos import carregar_fontes
from testes.test_valores_dinamicos_rs042a import alvo_nativo


def executar_imagem(imagem, entrada=b'', antes=None):
    alvo = alvo_nativo()
    with tempfile.TemporaryDirectory() as pasta:
        pasta = Path(pasta)
        arquivo = pasta / ('texto.exe' if alvo == 'windows' else 'texto')
        arquivo.write_bytes(imagem)
        if alvo == 'linux':
            arquivo.chmod(0o755)
        if antes:
            antes(pasta)
        resultado = subprocess.run([str(arquivo)], input=entrada, cwd=pasta,
                                   capture_output=True, timeout=25)
        arquivos = {p.name: p.read_bytes() for p in pasta.iterdir() if p.is_file() and p != arquivo}
        return resultado, arquivos


class TestesTextoDinamicoNativoRS042A(unittest.TestCase):
    def verificar(self, fonte, esperado, entrada=b'', niveis=range(9), antes=None):
        p = analisar_programa(fonte)
        resultados = []
        for nivel in niveis:
            with self.subTest(nivel=nivel):
                r, arquivos = executar_imagem(compilar(p, alvo_nativo(), nivel=nivel, otimizar=nivel > 0), entrada, antes)
                self.assertEqual((r.returncode, r.stdout), (0, esperado), r.stderr)
                resultados.append(arquivos)
        return resultados

    def erro(self, fonte, mensagem, entrada=b'', antes=None):
        for nivel in (0, 4, 8):
            with self.subTest(nivel=nivel):
                r, _ = executar_imagem(compilar(analisar_programa(fonte), alvo_nativo(), nivel=nivel,
                                               otimizar=nivel > 0), entrada, antes)
                self.assertEqual(r.returncode, 1, r.stderr)
                self.assertIn(mensagem, r.stdout + r.stderr)

    def test_vazio_nao_exige_capacidade_e_pode_ser_transferido(self):
        fonte = '''funcao vazio() -> texto {
            seja nome: texto
            retorne mova(nome)
        }
        inicio {
            seja nome = vazio()
            escreva(nome)
            escreva(tamanho(nome))
            escreva(caracteres(nome))
            escreva(capacidade(nome))
            grave_arquivo("vazio.txt", nome)
        }'''
        for arquivos in self.verificar(fonte, b'\n0\n0\n0\n'):
            self.assertEqual(arquivos['vazio.txt'], b'')

    def test_utf8_bytes_escalares_e_nul_preservados(self):
        conteudo = 'ação😀e\u0301\x00'
        literal = json.dumps(conteudo, ensure_ascii=False)
        fonte = f'''inicio {{
            seja nome: texto = {literal}
            escreva(nome)
            escreva(tamanho(nome))
            escreva(caracteres(nome))
            escreva(capacidade(nome) >= tamanho(nome))
            grave_arquivo("utf8.txt", nome)
        }}'''
        bruto = conteudo.encode('utf-8')
        esperado = bruto + f'\n{len(bruto)}\n{len(conteudo)}\n1\n'.encode()
        for arquivos in self.verificar(fonte, esperado):
            self.assertEqual(arquivos['utf8.txt'], bruto)

    def test_expansao_limpeza_e_reuso_preservam_capacidade(self):
        fonte = '''inicio {
            seja nome: texto
            para indice de 1 ate 5000 {
                junte(nome, "ação😀")
            }
            escreva(tamanho(nome))
            escreva(caracteres(nome))
            seja capacidade_anterior = capacidade(nome)
            limpe(nome)
            escreva(tamanho(nome))
            escreva(capacidade(nome) == capacidade_anterior)
            copie(nome, "新")
            escreva(nome)
            escreva(tamanho(nome))
            escreva(capacidade(nome) == capacidade_anterior)
        }'''
        self.verificar(fonte, '50000\n25000\n0\n1\n新\n3\n1\n'.encode())

    def test_autoconcatenacao_com_realocacao_e_copia_explicita(self):
        fonte = '''inicio {
            seja nome: texto = "a😀"
            junte(nome, nome)
            junte(nome, nome)
            escreva(nome)
            copie(nome, nome)
            seja copia: texto
            copie(copia, nome)
            limpe(nome)
            escreva(copia)
            escreva(tamanho(nome))
        }'''
        self.verificar(fonte, (('a😀' * 4 + '\n') * 2 + '0\n').encode())

    def test_transferencias_emprestimos_temporarios_e_regressoes_mistas(self):
        fonte = '''funcao criar() -> texto {
            seja nome: texto = "Olá"
            retorne mova(nome)
        }
        funcao concluir(nome: texto, itens: lista[]) -> texto {
            se itens[0] == 17 {
                junte(nome, "😀")
            }
            retorne mova(nome)
        }
        funcao encaminhar(nome: texto, itens: lista[]) -> texto {
            retorne concluir(mova(nome), mova(itens))
        }
        funcao consultar(nome: emprestimo[texto]) -> inteiro {
            retorne tamanho(nome) + caracteres(nome)
        }
        inicio {
            seja itens: lista[]
            adicione(itens, 17)
            seja recebido = encaminhar(criar(), mova(itens))
            escreva(recebido)
            escreva(1 + consultar(empreste(recebido)))
            seja destino: texto = "antigo"
            mova(destino, recebido)
            escreva(destino)
        }'''
        self.verificar(fonte, 'Olá😀\n13\nOlá😀\n'.encode())

    def test_retornos_antecipados_pare_continue_e_donos_de_blocos(self):
        fonte = '''funcao escolher(numero: inteiro) -> texto {
            seja externo: texto = "externo"
            para indice de 0 ate 4 {
                seja interno: texto = "ação"
                se indice == numero {
                    retorne mova(interno)
                }
                se indice == 1 {
                    continue
                }
                se indice == 3 {
                    pare
                }
            }
            retorne mova(externo)
        }
        inicio {
            para indice de 1 ate 10 {
                seja nome = escolher(2)
                escreva(nome)
            }
            seja final = escolher(9)
            escreva(final)
        }'''
        self.verificar(fonte, ('ação\n' * 10 + 'externo\n').encode())

    def test_comparacao_e_interacao_com_texto_fixo(self):
        fonte = '''funcao comparar(nome: emprestimo[texto], outro: emprestimo[texto]) -> logico {
            retorne nome == outro
        }
        inicio {
            seja a: texto = "ação"
            seja b: texto[20]
            copie(b, a)
            escreva(a == b)
            seja c: texto
            copie(c, b)
            escreva(comparar(empreste(a), empreste(c)))
            junte(c, "!")
            escreva(a != c)
            escreva(byte_em(a, 1))
            escreva(1 + caracteres(a))
        }'''
        self.verificar(fonte, b'1\n1\n1\n195\n5\n')

    def test_memoria_compartilhada_preserva_leitura_de_registro_emprestado(self):
        fonte = '''tipo Marcacao {
            codigo: inteiro
            nome: texto[8]
        }
        funcao consultar(itens: emprestimo[lista[Marcacao]]) -> inteiro {
            seja local: Marcacao = itens[0]
            retorne local.codigo + tamanho(local.nome)
        }
        inicio {
            seja itens: lista[Marcacao]
            seja local: Marcacao
            local.codigo = 17
            copie(local.nome, "ação")
            adicione(itens, local)
            escreva(consultar(empreste(itens)))
            seja nome: texto = "lido"
            escreva(nome)
        }'''
        p = analisar_programa(fonte)
        for nivel in range(9):
            for alvo in ('windows', 'linux'):
                self.assertTrue(compilar(p, alvo, nivel=nivel, otimizar=nivel > 0))
        self.verificar(fonte, b'23\nlido\n')

    def test_entrada_grande_crlf_e_cache_compartilhado_com_inteiros(self):
        nome = 'ação😀' * 5000
        fonte = '''inicio {
            seja numero = 0
            leia(numero)
            seja nome: texto
            leia(nome)
            seja proximo = 0
            leia(proximo)
            escreva(numero)
            escreva(tamanho(nome))
            escreva(caracteres(nome))
            escreva(proximo)
            grave_arquivo("entrada.txt", nome)
        }'''
        entrada = ('7\r\n' + nome + '\r\n19\n').encode()
        for arquivos in self.verificar(fonte, b'7\n50000\n25000\n19\n', entrada):
            self.assertEqual(arquivos['entrada.txt'], nome.encode())

    def test_entrada_vazia_e_eof_sem_quebra(self):
        fonte = '''inicio {
            seja nome: texto
            leia(nome)
            escreva(nome)
            escreva(caracteres(nome))
        }'''
        for entrada, esperado in ((b'', b'\n0\n'), (b'\n', b'\n0\n'), ('fim😀'.encode(), 'fim😀\n4\n'.encode())):
            self.verificar(fonte, esperado, entrada, niveis=(0, 8))

    def test_todos_limites_legais_de_utf8_na_leitura_de_arquivo(self):
        valores = (0, 0x7f, 0x80, 0x7ff, 0x800, 0xd7ff, 0xe000, 0xffff, 0x10000, 0x10ffff)
        conteudo = ''.join(map(chr, valores)).encode()
        fonte = '''inicio {
            seja nome: texto
            carregue_arquivo("origem.txt", nome)
            escreva(caracteres(nome))
            grave_arquivo("copia.txt", nome)
        }'''
        for arquivos in self.verificar(fonte, b'10\n', antes=lambda p: (p / 'origem.txt').write_bytes(conteudo)):
            self.assertEqual(arquivos['copia.txt'], conteudo)

    def test_rejeita_utf8_invalido_na_entrada_e_em_arquivos(self):
        invalidos = (b'\x80', b'\xc0\xaf', b'\xe0\x80\x80', b'\xed\xa0\x80',
                     b'\xf0\x80\x80\x80', b'\xf4\x90\x80\x80', b'\xf5\x80\x80\x80',
                     b'\xc2', b'\xe2\x82', b'\xf0\x9f\x98', b'\xc2A')
        entrada = 'inicio {\n seja nome: texto\n leia(nome)\n escreva(nome)\n}'
        arquivo = 'inicio {\n seja nome: texto\n carregue_arquivo("origem.txt", nome)\n escreva(nome)\n}'
        for invalido in invalidos:
            with self.subTest(invalido=invalido):
                self.erro(entrada, b'UTF-8', invalido)
                self.erro(arquivo, b'UTF-8', antes=lambda p: (p / 'origem.txt').write_bytes(invalido))

    def test_copia_de_buffer_fixo_invalido_nao_contamina_texto_dinamico(self):
        fonte = '''inicio {
            seja origem: texto[8]
            carregue_arquivo("origem.txt", origem)
            seja nome: texto
            copie(nome, origem)
        }'''
        self.erro(fonte, b'UTF-8', antes=lambda p: (p / 'origem.txt').write_bytes(b'\xff'))

    def test_uso_apos_transferencia_liberacao_e_indices_invalidos(self):
        for comando in ('seja outro = mova(nome)\n escreva(nome)', 'libere(nome)\n junte(nome, "x")',
                        'libere(nome)\n leia(nome)', 'libere(nome)\n carregue_arquivo("origem.txt", nome)'):
            self.erro('inicio {\n seja nome: texto = "a"\n' + comando + '\n}', b'liberacao')
        for indice in ('-1', '1', '9223372036854775807'):
            self.erro('inicio {\n seja nome: texto = "a"\n escreva(byte_em(nome, ' + indice + '))\n}', b'limites')

    def test_indice_que_consume_o_texto_falha_antes_de_ler_ponteiro(self):
        fonte = '''funcao consumir(nome: texto) -> inteiro {
            retorne 0
        }
        inicio {
            seja nome: texto = "a"
            escreva(byte_em(nome, consumir(mova(nome))))
        }'''
        self.erro(fonte, b'liberacao')

    def test_copia_para_texto_fixo_nao_trunca_utf8(self):
        fonte = '''inicio {
            seja nome: texto = "😀"
            seja destino: texto[3]
            copie(destino, nome)
        }'''
        self.erro(fonte, b'capacidade')

    def test_persistencia_grande_com_chamadas_de_arquivo_fragmentadas(self):
        conteudo = ('ação😀\n' * 105000).encode()
        fonte = '''funcao recuperar() -> texto {
            seja nome: texto
            carregue_arquivo("origem.txt", nome)
            retorne mova(nome)
        }
        inicio {
            seja nome = recuperar()
            escreva(tamanho(nome))
            escreva(caracteres(nome))
            grave_arquivo("copia.txt", nome)
        }'''
        esperado = f'{len(conteudo)}\n630000\n'.encode()
        for arquivos in self.verificar(fonte, esperado, antes=lambda p: (p / 'origem.txt').write_bytes(conteudo)):
            self.assertEqual(arquivos['copia.txt'], conteudo)

    def test_leitura_nao_reserva_memoria_so_para_detectar_eof(self):
        fonte = '''inicio {
            seja nome: texto
            carregue_arquivo("origem.txt", nome)
            escreva(tamanho(nome))
            escreva(capacidade(nome))
        }'''
        for tamanho, capacidade in ((0, 0), (1, 4), (4, 4), (4096, 4096), (4097, 8192)):
            self.verificar(fonte, f'{tamanho}\n{capacidade}\n'.encode(), niveis=(0, 8),
                           antes=lambda p: (p / 'origem.txt').write_bytes(b'A' * tamanho))

    def test_dados_unicode_gerados_reproduziveis(self):
        gerador = random.Random(42002)
        valores = [gerador.choice((0x41, 0xe9, 0x4e2d, 0x1f600, 0x0301)) for _ in range(2049)]
        nome = ''.join(map(chr, valores))
        fonte = 'inicio {\n seja nome: texto\n leia(nome)\n escreva(caracteres(nome))\n grave_arquivo("nome.txt", nome)\n}'
        for arquivos in self.verificar(fonte, b'2049\n', nome.encode()):
            self.assertEqual(arquivos['nome.txt'], nome.encode())

    def test_recursao_com_textos_respeita_pilha(self):
        fonte = '''funcao repetir(numero: inteiro, nome: texto) -> texto {
            se numero == 0 {
                retorne mova(nome)
            }
            retorne repetir(numero - 1, mova(nome))
        }
        inicio {
            seja nome: texto = "ação"
            seja recebido = repetir(100000, mova(nome))
            escreva(recebido)
        }'''
        self.erro(fonte, b'limite seguro de pilha')
        self.verificar(fonte.replace('repetir(100000,', 'repetir(25,'), 'ação\n'.encode(), niveis=(0, 8))

    def test_falha_de_alocacao_simulada_no_executavel_real(self):
        p = analisar_programa('inicio {\n seja nome: texto = "ação"\n escreva(nome)\n}')
        alvo = alvo_nativo()
        g, mensagens = montar_codigo(p, alvo == 'windows')
        imagem = bytearray(montar_pe(g, mensagens) if alvo == 'windows' else montar_elf(g, mensagens))
        codigo = g.codigo[g.rotulos['rs_lista_alocar']:g.rotulos['rs_lista_desalocar']]
        if alvo == 'windows':
            pos = codigo.index(b'\xff\x15')
            trecho = bytes(codigo[pos:pos+6])
            novo = b'\x31\xc0' + b'\x90' * 4
        else:
            trecho = b'\xb8\x09\x00\x00\x00\x0f\x05'
            novo = b'\x48\xc7\xc0\xf4\xff\xff\xff'
        self.assertEqual(imagem.count(trecho), 1)
        pos = imagem.index(trecho)
        imagem[pos:pos+len(trecho)] = novo
        r, _ = executar_imagem(bytes(imagem))
        self.assertEqual(r.returncode, 1, r.stderr)
        self.assertIn(b'reservar', r.stdout + r.stderr)

    def test_estouro_de_comprimento_e_interrompido_antes_da_alocacao(self):
        p = analisar_programa('inicio {\n seja nome: texto\n junte(nome, "x")\n}')
        # Injeção de estado impossível pela sintaxe: exercita ADD com overflow
        # no executável, sem pedir exabytes ao hospedeiro nem desreferenciar NULL.
        p.variaveis['comprimento_simulado'] = p.variaveis['nome'] + 1
        p.tipos['comprimento_simulado'] = 'inteiro'
        p.instrucoes.insert(1, ('atribua', 'comprimento_simulado', ('numero', (1 << 63) - 1)))
        for nivel in (0, 8):
            r, _ = executar_imagem(compilar(p, alvo_nativo(), nivel=nivel, otimizar=nivel > 0))
            self.assertEqual(r.returncode, 1, r.stderr)
            self.assertIn(b'memoria', r.stdout + r.stderr)

    def test_biblioteca_em_rs_duplica_e_concatena_explicitamente(self):
        fonte = '''importe "padrao/textos.rts" como textos
inicio {
    seja nome: texto = "ação😀"
    seja copia = textos.duplicar(empreste(nome))
    seja repetido = textos.concatenar(empreste(nome), empreste(nome))
    escreva(copia)
    escreva(repetido)
    escreva(nome == copia)
    escreva(textos.vazio(empreste(nome)))
}'''
        with tempfile.TemporaryDirectory() as pasta:
            arquivo = Path(pasta) / 'principal.rts'
            arquivo.write_text(fonte, encoding='utf-8')
            p = carregar_fontes(arquivo)
        self.verificar(p.texto, 'ação😀\nação😀ação😀\n1\n0\n'.encode())

    def test_aplicacao_documento_recebe_nome_variavel_e_recupera_arquivo(self):
        fonte = (RAIZ / 'exemplos/aplicacoes/documento_utf8_rs042a.rts').read_text(encoding='utf-8')
        nome = 'Ana ação😀 ' * 1000
        documento = ('Pessoa: ' + nome + '\nDocumento criado em RoteiroSimples.\n').encode()
        esperado = b'Nome completo:\n' + documento + b'\nDocumento gravado e recuperado.\n'
        for arquivos in self.verificar(fonte, esperado, (nome + '\n').encode()):
            self.assertEqual(arquivos['pessoa_utf8.txt'], documento)
        self.erro(fonte, b'informe um nome', b'\n')


if __name__ == '__main__':
    unittest.main()
