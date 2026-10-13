"""Executáveis reais: bytes arbitrários, crescimento, propriedade e falhas."""
from pathlib import Path
import random
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
from testes.test_texto_dinamico_nativo_rs042a import executar_imagem
from testes.test_valores_dinamicos_rs042a import alvo_nativo


class TestesBytesDinamicosNativoRS042A(unittest.TestCase):
    def verificar(self, fonte, esperado, niveis=range(9), antes=None):
        p = analisar_programa(fonte)
        arquivos_observados = []
        for nivel in niveis:
            with self.subTest(nivel=nivel):
                r, arquivos = executar_imagem(compilar(p, alvo_nativo(), nivel=nivel, otimizar=nivel > 0), antes=antes)
                self.assertEqual((r.returncode, r.stdout), (0, esperado), r.stderr)
                arquivos_observados.append(arquivos)
        return arquivos_observados

    def erro(self, fonte, mensagem, antes=None):
        for nivel in (0, 4, 8):
            with self.subTest(nivel=nivel):
                r, _ = executar_imagem(compilar(analisar_programa(fonte), alvo_nativo(), nivel=nivel,
                                               otimizar=nivel > 0), antes=antes)
                self.assertEqual(r.returncode, 1, r.stderr)
                self.assertIn(mensagem, r.stdout + r.stderr)

    def test_vazio_transferencia_e_arquivo_sem_alocacao(self):
        fonte = '''funcao vazio() -> bytes {
            seja dados: bytes
            retorne mova(dados)
        }
        inicio {
            seja dados = vazio()
            escreva(tamanho(dados))
            escreva(capacidade(dados))
            grave_arquivo("vazio.bin", dados)
        }'''
        for arquivos in self.verificar(fonte, b'0\n0\n'):
            self.assertEqual(arquivos['vazio.bin'], b'')

    def test_todos_os_bytes_crescem_e_preservam_nul_e_utf8_invalido(self):
        fonte = '''inicio {
            seja dados: bytes
            para indice de 0 ate 1024 {
                adicione_byte(dados, indice % 256)
            }
            escreva(tamanho(dados))
            escreva(capacidade(dados))
            escreva(dados[0])
            escreva(dados[255])
            escreva(dados[1024])
            grave_arquivo("todos.bin", dados)
        }'''
        for arquivos in self.verificar(fonte, b'1025\n2048\n0\n255\n0\n'):
            self.assertEqual(arquivos['todos.bin'], bytes(range(256)) * 4 + b'\0')

    def test_limpeza_reutilizacao_e_substituicao_preservam_capacidade(self):
        fonte = '''inicio {
            seja dados: bytes
            para indice de 0 ate 99 {
                adicione_byte(dados, indice)
            }
            seja anterior = capacidade(dados)
            limpe(dados)
            escreva(tamanho(dados))
            adicione_byte(dados, 0)
            dados[0] = 255
            escreva(dados[0])
            escreva(capacidade(dados) == anterior)
        }'''
        self.verificar(fonte, b'0\n255\n1\n')

    def test_autoacrescimo_com_realocacao_e_autocopia(self):
        fonte = '''inicio {
            seja dados: bytes
            adicione_byte(dados, 0)
            adicione_byte(dados, 255)
            adicione_byte(dados, 192)
            adicione_byte(dados, 128)
            junte(dados, dados)
            copie(dados, dados)
            escreva(tamanho(dados))
            escreva(capacidade(dados))
            grave_arquivo("duplicado.bin", dados)
        }'''
        for arquivos in self.verificar(fonte, b'8\n8\n'):
            self.assertEqual(arquivos['duplicado.bin'], b'\0\xff\xc0\x80' * 2)

    def test_copia_explicita_independente_e_acrescimo_de_buffer_fixo(self):
        fonte = '''inicio {
            seja fixo: bytes[8]
            adicione_byte(fixo, 255)
            adicione_byte(fixo, 0)
            seja a: bytes
            copie(a, fixo)
            seja b: bytes
            copie(b, a)
            a[0] = 1
            junte(b, fixo)
            copie(fixo, b)
            junte(fixo, fixo)
            escreva(a[0])
            grave_arquivo("fixo.bin", fixo)
        }'''
        for arquivos in self.verificar(fonte, b'1\n'):
            self.assertEqual(arquivos['fixo.bin'], b'\xff\0' * 4)

    def test_funcao_retorno_aninhado_transferencia_e_emprestimo(self):
        fonte = '''funcao criar() -> bytes {
            seja dados: bytes
            adicione_byte(dados, 255)
            retorne mova(dados)
        }
        funcao encaminhar(dados: bytes) -> bytes {
            adicione_byte(dados, 0)
            retorne mova(dados)
        }
        funcao soma(dados: emprestimo[bytes]) -> inteiro {
            retorne dados[0] + dados[1] + tamanho(dados) + capacidade(dados)
        }
        inicio {
            seja recebido = encaminhar(criar())
            seja outro: bytes = mova(recebido)
            escreva(10 + soma(empreste(outro)))
            escreva(outro[0] + soma(empreste(outro)))
        }'''
        self.verificar(fonte, b'271\n516\n')

    def test_emprestimo_retransmitido_pode_gravar_arquivo(self):
        fonte = '''funcao publicar(dados: emprestimo[bytes]) -> inteiro {
            grave_arquivo("emprestado.bin", dados)
            retorne dados[0]
        }
        funcao encaminhar(dados: emprestimo[bytes]) -> inteiro {
            retorne publicar(dados)
        }
        inicio {
            seja dados: bytes
            adicione_byte(dados, 255)
            escreva(encaminhar(empreste(dados)))
            escreva(dados[0])
        }'''
        for arquivos in self.verificar(fonte, b'255\n255\n'):
            self.assertEqual(arquivos['emprestado.bin'], b'\xff')

    def test_mova_descarta_destino_e_ressuscita_destino_liberado(self):
        fonte = '''inicio {
            seja a: bytes
            adicione_byte(a, 1)
            seja b: bytes
            adicione_byte(b, 255)
            mova(a, b)
            escreva(a[0])
            seja c: bytes
            libere(c)
            mova(c, a)
            escreva(c[0])
        }'''
        self.verificar(fonte, b'255\n255\n')

    def test_arquivo_maior_que_bloco_e_recuperacao_em_funcao(self):
        conteudo = bytes(range(256)) * 5000
        fonte = '''funcao recuperar() -> bytes {
            seja dados: bytes
            carregue_arquivo("origem.bin", dados)
            retorne mova(dados)
        }
        inicio {
            seja dados = recuperar()
            escreva(tamanho(dados))
            escreva(dados[1279999])
            grave_arquivo("copia.bin", dados)
        }'''
        for arquivos in self.verificar(fonte, b'1280000\n255\n', antes=lambda p: (p / 'origem.bin').write_bytes(conteudo)):
            self.assertEqual(arquivos['copia.bin'], conteudo)

    def test_eof_exato_e_releitura_reusam_capacidade(self):
        fonte = '''inicio {
            seja dados: bytes
            carregue_arquivo("origem.bin", dados)
            escreva(tamanho(dados))
            escreva(capacidade(dados))
            carregue_arquivo("curto.bin", dados)
            escreva(tamanho(dados))
            escreva(capacidade(dados))
        }'''
        for tamanho, capacidade in ((0, 0), (1, 4), (4, 4), (4096, 4096), (4097, 8192)):
            def antes(pasta):
                (pasta / 'origem.bin').write_bytes(b'\xff' * tamanho)
                (pasta / 'curto.bin').write_bytes(b'')
            self.verificar(fonte, f'{tamanho}\n{capacidade}\n0\n{capacidade}\n'.encode(), niveis=(0, 8), antes=antes)

    def test_arquivo_fixo_binario_preserva_conteudo_e_rejeita_excesso(self):
        fonte = 'inicio {\n seja dados: bytes[4]\n carregue_arquivo("origem.bin", dados)\n grave_arquivo("copia.bin", dados)\n escreva(tamanho(dados))\n}'
        for arquivos in self.verificar(fonte, b'4\n', antes=lambda p: (p / 'origem.bin').write_bytes(b'\0\xff\xc0\x80')):
            self.assertEqual(arquivos['copia.bin'], b'\0\xff\xc0\x80')
        self.erro(fonte, b'capacidade', antes=lambda p: (p / 'origem.bin').write_bytes(b'12345'))

    def test_texto_e_binario_no_mesmo_programa_validam_somente_texto(self):
        fonte = '''inicio {
            seja dados: bytes
            carregue_arquivo("origem.bin", dados)
            grave_arquivo("copia.bin", dados)
            seja nome: texto
            carregue_arquivo("nome.txt", nome)
            escreva(nome)
        }'''
        def antes(pasta):
            (pasta / 'origem.bin').write_bytes(b'\xff\0\xc0\x80')
            (pasta / 'nome.txt').write_bytes('ação😀'.encode())
        for arquivos in self.verificar(fonte, 'ação😀\n'.encode(), antes=antes):
            self.assertEqual(arquivos['copia.bin'], b'\xff\0\xc0\x80')
        self.erro(fonte, b'UTF-8', antes=lambda p: ((p / 'origem.bin').write_bytes(b'\xff'), (p / 'nome.txt').write_bytes(b'\xff')))

    def test_valores_byte_invalidos_nao_sao_truncados(self):
        for valor in ('-1', '256', '9223372036854775807'):
            self.erro('inicio {\n seja dados: bytes\n adicione_byte(dados, ' + valor + ')\n}', b'byte')
            self.erro('inicio {\n seja dados: bytes\n adicione_byte(dados, 0)\n dados[0] = ' + valor + '\n}', b'byte')

    def test_indices_negativos_no_limite_e_vazios_falham(self):
        for indice in ('-1', '1', '9223372036854775807'):
            for comando in ('escreva(dados[' + indice + '])', 'dados[' + indice + '] = 0'):
                self.erro('inicio {\n seja dados: bytes\n adicione_byte(dados, 0)\n' + comando + '\n}', b'indice')
        self.erro('inicio {\n seja dados: bytes\n escreva(dados[0])\n}', b'indice')

    def test_indice_emprestado_valida_limites(self):
        fonte = '''funcao consultar(dados: emprestimo[bytes]) -> inteiro {
            retorne dados[1]
        }
        inicio {
            seja dados: bytes
            adicione_byte(dados, 0)
            escreva(consultar(empreste(dados)))
        }'''
        self.erro(fonte, b'indice')

    def test_uso_apos_mova_e_libere_e_detectado(self):
        for acao in ('libere(dados)', 'seja outro: bytes = mova(dados)'):
            for comando in ('escreva(tamanho(dados))', 'escreva(capacidade(dados))',
                            'adicione_byte(dados, 0)', 'dados[0] = 0', 'escreva(dados[0])',
                            'limpe(dados)', 'libere(dados)', 'copie(dados, dados)',
                            'grave_arquivo("dados.bin", dados)', 'carregue_arquivo("dados.bin", dados)'):
                self.erro('inicio {\n seja dados: bytes\n adicione_byte(dados, 0)\n' + acao + '\n' + comando + '\n}', b'movimentacao ou liberacao')

    def test_expressao_consumidora_do_destino_nao_causa_acesso_liberado(self):
        prefixo = '''funcao consumir(dados: bytes) -> inteiro {
            escreva(7)
            retorne 0
        }
        inicio {
            seja dados: bytes
            adicione_byte(dados, 1)
'''
        for comando in ('escreva(dados[consumir(mova(dados))])',
                        'dados[0] = consumir(mova(dados))',
                        'dados[consumir(mova(dados))] = 0',
                        'adicione_byte(dados, consumir(mova(dados)))'):
            for nivel in (0, 4, 8):
                r, _ = executar_imagem(compilar(analisar_programa(prefixo + comando + '\n}'), alvo_nativo(), nivel=nivel, otimizar=nivel > 0))
                self.assertEqual(r.returncode, 1, r.stderr)
                self.assertIn(b'movimentacao ou liberacao', r.stdout + r.stderr)
                self.assertEqual(r.stdout.count(b'7\n'), 1)

    def test_copia_e_acrescimo_de_emprestimo_preservam_origem(self):
        fonte = '''funcao ampliar(vista: emprestimo[bytes]) -> bytes {
            seja dados: bytes
            copie(dados, vista)
            junte(dados, vista)
            retorne mova(dados)
        }
        inicio {
            seja dados: bytes
            adicione_byte(dados, 255)
            seja copia = ampliar(empreste(dados))
            escreva(tamanho(copia))
            escreva(copia[1])
            escreva(tamanho(dados))
        }'''
        self.verificar(fonte, b'2\n255\n1\n')

    def test_falha_de_alocacao_simulada_usa_o_unico_alocador(self):
        p = analisar_programa('inicio {\n seja dados: bytes\n adicione_byte(dados, 255)\n}')
        alvo = alvo_nativo()
        g, mensagens = montar_codigo(p, alvo == 'windows')
        imagem = bytearray(montar_pe(g, mensagens) if alvo == 'windows' else montar_elf(g, mensagens))
        codigo = g.codigo[g.rotulos['rs_lista_alocar']:g.rotulos['rs_lista_desalocar']]
        if alvo == 'windows':
            pos = codigo.index(b'\xff\x15')
            trecho, novo = bytes(codigo[pos:pos+6]), b'\x31\xc0' + b'\x90' * 4
        else:
            trecho, novo = b'\xb8\x09\x00\x00\x00\x0f\x05', b'\x48\xc7\xc0\xf4\xff\xff\xff'
        self.assertEqual(imagem.count(trecho), 1)
        pos = imagem.index(trecho)
        imagem[pos:pos+len(trecho)] = novo
        r, _ = executar_imagem(bytes(imagem))
        self.assertEqual(r.returncode, 1, r.stderr)
        self.assertIn(b'reservar', r.stdout + r.stderr)

    def test_estouro_de_comprimento_interrompido_antes_do_heap(self):
        for comando in ('adicione_byte(dados, 1)', 'junte(dados, origem)'):
            p = analisar_programa('inicio {\n seja dados: bytes\n seja origem: bytes\n adicione_byte(origem, 1)\n' + comando + '\n}')
            p.variaveis['comprimento_simulado'] = p.variaveis['dados'] + 1
            p.tipos['comprimento_simulado'] = 'inteiro'
            p.instrucoes.insert(len(p.instrucoes)-1, ('atribua', 'comprimento_simulado', ('numero', (1 << 63) - 1)))
            for nivel in (0, 8):
                r, _ = executar_imagem(compilar(p, alvo_nativo(), nivel=nivel, otimizar=nivel > 0))
                self.assertEqual(r.returncode, 1, r.stderr)
                self.assertIn(b'memoria', r.stdout + r.stderr)

    def test_copia_para_fixo_nao_trunca_dados(self):
        for modo in ('copie', 'junte'):
            fonte = 'inicio {\n seja fixo: bytes[1]\n seja dados: bytes\n adicione_byte(dados, 0)\n adicione_byte(dados, 255)\n' + modo + '(fixo, dados)\n}'
            self.erro(fonte, b'capacidade')

    def test_dados_gerados_reproduziveis(self):
        gerador = random.Random(42003)
        conteudo = bytes(gerador.randrange(256) for _ in range(8193))
        fonte = 'inicio {\n seja dados: bytes\n carregue_arquivo("origem.bin", dados)\n junte(dados, dados)\n grave_arquivo("copia.bin", dados)\n escreva(tamanho(dados))\n}'
        for arquivos in self.verificar(fonte, b'16386\n', antes=lambda p: (p / 'origem.bin').write_bytes(conteudo)):
            self.assertEqual(arquivos['copia.bin'], conteudo * 2)

    def test_recursao_com_donos_respeita_orcamento_de_pilha(self):
        fonte = '''funcao repetir(n: inteiro, dados: bytes) -> bytes {
            se n == 0 {
                retorne mova(dados)
            }
            retorne repetir(n - 1, mova(dados))
        }
        inicio {
            seja dados: bytes
            adicione_byte(dados, 255)
            seja recebido = repetir(25, mova(dados))
            escreva(recebido[0])
        }'''
        self.verificar(fonte, b'255\n', niveis=(0, 8))
        self.erro(fonte.replace('repetir(25,', 'repetir(100000,'), b'limite seguro de pilha')

    def test_biblioteca_em_rs_compara_copia_concatena_e_calcula_soma(self):
        fonte = '''importe "padrao/binarios.rts" como binarios
inicio {
    seja a: bytes
    adicione_byte(a, 255)
    adicione_byte(a, 0)
    seja b = binarios.duplicar(empreste(a))
    escreva(binarios.iguais(empreste(a), empreste(b)))
    b[0] = 0
    escreva(binarios.iguais(empreste(a), empreste(b)))
    seja c = binarios.concatenar(empreste(a), empreste(b))
    escreva(tamanho(c))
    escreva(binarios.soma_verificacao(empreste(c)))
    seja vazio: bytes
    escreva(binarios.iguais(empreste(a), empreste(vazio)))
    escreva(binarios.iguais(empreste(vazio), empreste(vazio)))
    escreva(binarios.soma_verificacao(empreste(vazio)))
}'''
        with tempfile.TemporaryDirectory() as pasta:
            caminho = Path(pasta) / 'principal.rts'
            caminho.write_text(fonte, encoding='utf-8')
            fonte = carregar_fontes(caminho).texto
        self.verificar(fonte, b'1\n0\n4\n255\n0\n1\n0\n')

    def test_aplicacao_nativa_grava_recupera_e_valida_binario_variavel(self):
        fonte = carregar_fontes(RAIZ / 'exemplos/aplicacoes/arquivo_binario_rs042a.rts').texto
        conteudo = bytes(range(256)) * 32 + b'\0\0\xff'
        esperado = f'Arquivo binario gravado e recuperado.\n8195\n{sum(conteudo) % 65536}\n0\n255\n'.encode()
        for arquivos in self.verificar(fonte, esperado):
            self.assertEqual(arquivos['dados_variaveis.bin'], conteudo)

    def test_chamada_com_argumentos_aninhados_em_acrescimo_e_indice(self):
        fonte = '''funcao somar(a: inteiro, b: inteiro) -> inteiro {
            retorne a + b
        }
        inicio {
            seja dados: bytes
            adicione_byte(dados, somar(100, somar(50, 105)))
            dados[somar(0, 0)] = somar(1, 2)
            escreva(10 + dados[somar(0, 0)])
        }'''
        self.verificar(fonte, b'13\n')


if __name__ == '__main__':
    unittest.main()
