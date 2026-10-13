"""Transferência de agregados com donos em chamadas e retornos nativos."""
from pathlib import Path
import sys
import tempfile
import unittest

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))
from backend import compilar
from backend.x86_64 import montar_codigo
from backend.windows_pe import montar_pe
from backend.linux_elf import montar_elf
from compilador.erros import ErroCompilacao
from compilador.modulos import carregar_fontes
from compilador.parser import analisar_programa
from compilador.propriedade import contrato_valor
from testes.test_valores_dinamicos_rs042a import alvo_nativo, rodar

CABECALHO = '''tipo Interno {
    titulo: texto
    marcas: lista[logico]
}
tipo Documento {
    codigo: inteiro
    interno: Interno
    conteudo: bytes
}
funcao criar(codigo: inteiro) -> Documento {
    seja documento: Documento
    documento.codigo = codigo
    copie(documento.interno.titulo, "Ação RS")
    adicione(documento.interno.marcas, verdadeiro)
    adicione_byte(documento.conteudo, 0)
    adicione_byte(documento.conteudo, 255)
    retorne mova(documento)
}
funcao transportar(documento: Documento) -> Documento {
    retorne mova(documento)
}
funcao consumir(documento: Documento) -> inteiro {
    escreva(documento.interno.titulo)
    escreva(documento.interno.marcas[0])
    retorne documento.codigo + documento.conteudo[1]
}
'''


class TestesRegistrosFuncoesRS042F(unittest.TestCase):
    def verificar(self, fonte, esperado, niveis=(0, 8), erro=None):
        programa = analisar_programa(fonte)
        for nivel in niveis:
            with self.subTest(nivel=nivel):
                # Ambos os formatos são gerados; a execução usa o SO real.
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

    def test_fabrica_transporte_e_temporarios_nove_niveis(self):
        fonte = CABECALHO + '''funcao encaminhar(documento: Documento) -> Documento {
    retorne transportar(mova(documento))
}
inicio {
    seja origem: Documento = criar(10)
    seja destino = encaminhar(mova(origem))
    seja movido: Documento = mova(destino)
    escreva(consumir(mova(movido)))
    escreva(consumir(encaminhar(transportar(criar(20)))))
}'''
        self.verificar(fonte, 'Ação RS\n1\n265\nAção RS\n1\n275\n', tuple(range(9)))

    def test_exemplo_publico_nove_niveis(self):
        fonte = (RAIZ / 'exemplos/aplicacoes/documento_registro_rs042f.rts').read_text(encoding='utf-8')
        self.verificar(fonte, 'Relatório RS\n65\n52\nRelatório RS\n65\n62\n', tuple(range(9)))

    def test_subregistro_transferido_e_retorno_antecipado(self):
        fonte = CABECALHO + '''funcao devolver(interno: Interno, escolha: logico) -> Interno {
    se escolha {
        seja movido = mova(interno)
        retorne mova(movido)
    }
    retorne mova(interno)
}
inicio {
    seja documento = criar(5)
    seja interno = devolver(mova(documento.interno), verdadeiro)
    escreva(interno.titulo)
    escreva(documento.conteudo[1])
    seja outro = criar(6)
    seja segundo: Interno = devolver(mova(outro.interno), falso)
    escreva(segundo.marcas[0])
}'''
        self.verificar(fonte, 'Ação RS\n255\n1\n')

    def test_multiplos_parametros_registros_fixos_e_alinhamento(self):
        fonte = '''tipo Simples {
    numero: inteiro
}
tipo Caixa {
    nome: texto
    assinatura: bytes[9]
    valores: lista[3]
    simples: Simples
}
funcao criar(numero: inteiro) -> Caixa {
    seja caixa: Caixa
    copie(caixa.nome, "RS")
    para indice de 0 ate 8 {
        adicione_byte(caixa.assinatura, 253)
    }
    caixa.valores[2] = numero
    caixa.simples.numero = numero + 1
    retorne mova(caixa)
}
funcao combinar(a: Caixa, x: inteiro, b: Caixa, simples: Simples) -> inteiro {
    retorne a.valores[2] + b.simples.numero + x + simples.numero + b.assinatura[8]
}
inicio {
    seja simples: Simples
    simples.numero = 4
    escreva(2 + combinar(criar(10), 3, criar(20), simples) * 2)
    escreva(simples.numero)
}'''
        self.verificar(fonte, '584\n4\n', tuple(range(9)))

    def test_registros_copiaveis_continuam_por_valor(self):
        fonte = '''tipo Valor {
    numero: inteiro
    ativo: logico
}
funcao mudar(valor: Valor) -> Valor {
    valor.numero = 99
    retorne valor
}
inicio {
    seja original: Valor
    original.numero = 17
    original.ativo = verdadeiro
    seja copia = mudar(mudar(original))
    escreva(copia.numero)
    escreva(original.numero)
    escreva(original.ativo)
}'''
        self.verificar(fonte, '99\n17\n1\n', tuple(range(9)))

    def test_loop_reutiliza_temporarios_e_descarta_escopos(self):
        fonte = CABECALHO + '''funcao somar(documento: Documento) -> inteiro {
    retorne documento.codigo
}
inicio {
    seja soma = 0
    para indice de 1 ate 80 {
        seja documento = transportar(criar(indice))
        se indice == 1 {
            continue
        }
        se indice == 80 {
            pare
        }
        soma = soma + somar(transportar(mova(documento)))
    }
    escreva(soma)
}'''
        self.verificar(fonte, '3159\n')

    def test_registro_vazio_e_ramos_sem_temporario_alcancado(self):
        fonte = CABECALHO + '''funcao escolher(escolha: logico) -> Documento {
    seja vazio: Documento
    se escolha {
        retorne transportar(criar(7))
    }
    retorne mova(vazio)
}
inicio {
    seja vazio = escolher(falso)
    escreva(tamanho(vazio.interno.titulo))
    escreva(tamanho(vazio.conteudo))
    seja cheio = escolher(verdadeiro)
    escreva(cheio.codigo)
}'''
        self.verificar(fonte, '0\n0\n7\n')

    def test_origem_consumida_e_registro_parcial_falham_controladamente(self):
        entradas = [
            '''seja origem = criar(1)
    seja destino = transportar(mova(origem))
    escreva(origem.interno.titulo)''',
            '''seja origem = criar(1)
    seja destino = transportar(mova(origem))
    seja outro = transportar(mova(origem))''',
            '''seja origem = criar(1)
    seja titulo = mova(origem.interno.titulo)
    seja destino = transportar(mova(origem))''',
        ]
        for corpo in entradas:
            with self.subTest(corpo=corpo):
                self.verificar(CABECALHO + 'inicio {\n    ' + corpo + '\n    escreva("INDEVIDO")\n}', '',
                               erro='movimentacao ou liberacao')

    def test_retorno_de_registro_parcial_falha_controladamente(self):
        fonte = CABECALHO + '''funcao parcial(documento: Documento) -> Documento {
    seja titulo = mova(documento.interno.titulo)
    retorne mova(documento)
}
inicio {
    seja recebido = parcial(criar(1))
    escreva("INDEVIDO")
}'''
        self.verificar(fonte, '', erro='movimentacao ou liberacao')

    def test_recursao_transfere_dono_e_respeita_limite_seguro(self):
        fonte = CABECALHO + '''funcao recursiva(documento: Documento, vezes: inteiro) -> Documento {
    se vezes == 0 {
        retorne mova(documento)
    }
    retorne recursiva(mova(documento), vezes - 1)
}
inicio {
    seja documento = recursiva(criar(7), 100)
    escreva(documento.codigo)
}'''
        self.verificar(fonte, '7\n')
        self.verificar(fonte.replace('criar(7), 100', 'criar(7), 100000'), '', erro='limite seguro de pilha')

    def test_rejeita_copias_implicitas_e_comparacao(self):
        entradas = [
            ('escreva(consumir(origem))', 'exige mova'),
            ('seja destino: Documento = origem', 'exige mova'),
            ('seja destino = origem', 'copia implicita'),
            ('seja destino: Documento\n    destino = origem', 'nao pode ser copiado'),
            ('escreva(origem == origem)', 'nao admite comparacao'),
            ('seja documentos: lista[Documento]', 'transferencia por elemento'),
        ]
        for corpo, mensagem in entradas:
            with self.subTest(corpo=corpo), self.assertRaisesRegex(ErroCompilacao, mensagem):
                analisar_programa(CABECALHO + 'inicio {\n    seja origem = criar(1)\n    ' + corpo + '\n}')
        with self.assertRaisesRegex(ErroCompilacao, 'retorno proprietario exige mova'):
            analisar_programa(CABECALHO + '''funcao errado(documento: Documento) -> Documento {
    retorne documento
}
inicio {
    escreva(1)
}''')

    def test_rejeita_consumos_sobrepostos_em_qualquer_ordem(self):
        funcoes = '''funcao dois(a: Documento, b: Documento) -> inteiro {
    retorne 1
}
funcao campo(a: Documento, b: texto) -> inteiro {
    retorne 1
}
funcao interno(a: Interno, b: Documento) -> inteiro {
    retorne 1
}
funcao texto_primeiro(a: texto, b: Documento) -> inteiro {
    retorne 1
}
'''
        for chamada in ('dois(mova(origem), mova(origem))',
                        'campo(mova(origem), mova(origem.interno.titulo))',
                        'interno(mova(origem.interno), mova(origem))',
                        'texto_primeiro(mova(origem.interno.titulo), transportar(mova(origem)))'):
            with self.subTest(chamada=chamada), self.assertRaisesRegex(ErroCompilacao, 'mais de uma vez'):
                analisar_programa(CABECALHO + funcoes + 'inicio {\n    seja origem = criar(1)\n    escreva(' + chamada + ')\n}')

    def test_rejeita_emprestimo_de_campo_junto_com_transferencia(self):
        funcoes = '''funcao consultar(a: Documento, b: emprestimo[texto]) -> inteiro {
    retorne tamanho(b)
}
funcao medir(a: emprestimo[bytes]) -> inteiro {
    retorne tamanho(a)
}
funcao com_medida(n: inteiro, a: Documento) -> inteiro {
    retorne n
}
'''
        for chamada in ('consultar(mova(origem), empreste(origem.interno.titulo))',
                        'consultar(transportar(mova(origem)), empreste(origem.interno.titulo))',
                        'com_medida(medir(empreste(origem.conteudo)), mova(origem))'):
            with self.subTest(chamada=chamada), self.assertRaisesRegex(ErroCompilacao, 'emprestar e mover'):
                analisar_programa(CABECALHO + funcoes + 'inicio {\n    seja origem = criar(1)\n    escreva(' + chamada + ')\n}')

    def test_tipo_exato_e_emprestimos_recursos_continuam_restritos(self):
        for fonte, mensagem in (
            (CABECALHO + '''inicio {
    seja interno: Interno
    seja documento: Documento = mova(interno)
}''', 'tipo incompat'),
            (CABECALHO + '''funcao consultar(a: emprestimo[Documento]) -> inteiro {
    retorne 1
}
inicio {
    escreva(1)
}''', 'tipo inv'),
            ('''tipo Recurso {
    arquivo: arquivo
}
inicio {
    escreva(1)
}''', 'tipo de campo desconhecido'),
        ):
            with self.subTest(fonte=fonte[-100:]), self.assertRaisesRegex(ErroCompilacao, mensagem):
                analisar_programa(fonte)

    def test_contrato_agregado_preserva_largura_e_donos_folhas(self):
        programa = analisar_programa(CABECALHO + 'inicio {\n    seja documento: Documento\n}')
        contrato = contrato_valor('Documento', programa.registros)
        self.assertEqual((contrato.classe, contrato.pode_copiar, contrato.precisa_descartar, contrato.palavras),
                         ('agregado_proprietario', False, True, 10))

    def test_campos_disjuntos_podem_ser_consumidos_na_mesma_chamada(self):
        fonte = CABECALHO + '''funcao separados(a: Interno, b: bytes) -> inteiro {
    retorne caracteres(a.titulo) + b[1]
}
inicio {
    seja origem = criar(1)
    escreva(separados(mova(origem.interno), mova(origem.conteudo)))
}'''
        self.verificar(fonte, '262\n')

    def test_modulo_rs_com_registro_proprietario_publico(self):
        with tempfile.TemporaryDirectory() as pasta:
            modulo = Path(pasta) / 'documentos.rts'
            modulo.write_text(CABECALHO, encoding='utf-8')
            principal = Path(pasta) / 'principal.rts'
            principal.write_text('''importe "documentos.rts" como documentos
inicio {
    seja origem: documentos.Documento = documentos.criar(3)
    escreva(documentos.consumir(documentos.transportar(mova(origem))))
}''', encoding='utf-8')
            self.verificar(carregar_fontes(principal).texto, 'Ação RS\n1\n258\n')

    def test_resultados_com_donos_continuam_rejeitados(self):
        with self.assertRaisesRegex(ErroCompilacao, 'campo proprietario nao pode receber atribuicao implicita'):
            analisar_programa(CABECALHO + '''inicio {
    seja origem = criar(1)
    seja resposta: resultado[Documento] = sucesso[Documento](mova(origem))
}''')

    def test_falha_de_alocacao_em_fabrica_de_registro_e_controlada(self):
        programa = analisar_programa(CABECALHO + '''inicio {
    seja documento = transportar(criar(1))
    escreva("INDEVIDO")
}''')
        alvo = alvo_nativo()
        gerador, mensagens = montar_codigo(programa, alvo == 'windows')
        imagem = bytearray(montar_pe(gerador, mensagens) if alvo == 'windows'
                           else montar_elf(gerador, mensagens))
        alocador = bytes(gerador.codigo[gerador.rotulos['rs_lista_alocar']:gerador.rotulos['rs_lista_desalocar']])
        if alvo == 'windows':
            posicao = alocador.index(b'\xff\x15')
            trecho = alocador[posicao:posicao+6]
            falha = b'\x31\xc0' + b'\x90' * 4
        else:
            trecho = b'\xb8\x09\x00\x00\x00\x0f\x05'
            falha = b'\x48\xc7\xc0\xf4\xff\xff\xff'  # -ENOMEM
        self.assertEqual(imagem.count(trecho), 1)
        posicao = imagem.index(trecho)
        imagem[posicao:posicao+len(trecho)] = falha
        resultado, _ = rodar(bytes(imagem))
        self.assertEqual(resultado.returncode, 1, resultado.stdout + resultado.stderr)
        self.assertIn('reservar', resultado.stdout + resultado.stderr)
        self.assertNotIn('INDEVIDO', resultado.stdout)

    def test_campos_homonimos_preservam_tipo_de_subregistro_e_temporario(self):
        fonte = '''tipo Nome {
    titulo: texto
}
tipo Documento {
    titulo: Nome
}
funcao transportar(nome: Nome) -> Nome {
    retorne mova(nome)
}
funcao criar() -> Documento {
    seja documento: Documento
    copie(documento.titulo.titulo, "RS")
    retorne mova(documento)
}
funcao encaminhar(documento: Documento) -> Documento {
    retorne mova(documento)
}
inicio {
    seja documento = encaminhar(criar())
    seja nome = transportar(mova(documento.titulo))
    escreva(nome.titulo)
}'''
        self.verificar(fonte, 'RS\n', tuple(range(9)))


if __name__ == '__main__':
    unittest.main()
