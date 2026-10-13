"""Conversoes explicitas: oraculo Python, donos, vistas e erros recuperaveis."""
from pathlib import Path
import random
import sys
import tempfile
import unittest

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))
from backend import compilar
from compilador.efeitos_programa import efeito_instrucao_arvore
from compilador.erros import ErroCompilacao
from compilador.estrategia import decidir_estrategia
from compilador.modulos import carregar_fontes
from compilador.parser import analisar_programa
from testes.test_valores_dinamicos_rs042a import alvo_nativo, rodar


def programa_modulo(fonte):
    with tempfile.TemporaryDirectory() as pasta:
        caminho = Path(pasta) / 'principal.rts'
        caminho.write_text(fonte, encoding='utf-8')
        return analisar_programa(carregar_fontes(caminho).texto)


class TestesUtf8RS042M(unittest.TestCase):
    def verificar(self, fonte, esperado, niveis=(0, 8), arquivos=None):
        programa = analisar_programa(fonte)
        for nivel in niveis:
            with self.subTest(nivel=nivel):
                self.assertEqual(decidir_estrategia(programa, nivel, nivel > 0).gerador, 'conservador')
                r, _ = rodar(compilar(programa, alvo_nativo(), nivel=nivel, otimizar=nivel > 0), antes=arquivos)
                self.assertEqual((r.returncode, r.stdout), (0, esperado), r.stderr)

    def test_ida_volta_nove_niveis_copia_independente_e_nul(self):
        fonte = '''inicio {
            seja origem: texto
            seja dados: bytes
            seja volta: texto
            seja estado = 9
            copie(origem, "Ação 🌱")
            codifique_utf8(dados, origem, estado)
            escreva(estado)
            libere(origem)
            adicione_byte(dados, 0)
            decodifique_utf8(volta, dados, estado)
            escreva(estado)
            libere(dados)
            escreva(volta)
            escreva(caracteres(volta))
            escreva(tamanho(volta))
        }'''
        self.verificar(fonte, '0\n0\nAção 🌱\0\n7\n12\n', tuple(range(9)))

    def test_sequencias_invalidas_geradas_preservam_destino_e_origem(self):
        rng = random.Random(4213)
        casos = [bytes([n]) for n in range(256)] + [
            b'\xc0\x80', b'\xc1\xbf', b'\xe0\x9f\xbf', b'\xed\xa0\x80',
            b'\xf0\x8f\xbf\xbf', b'\xf4\x90\x80\x80', b'\xf5\x80\x80\x80',
            b'\xe2\x82', b'\xf0\x90\x80', b'\xc2A', b'A\x80', b'\xe2\xc2\xa2',
            b'', b'\xc2\x80', b'\xe0\xa0\x80', b'\xed\x9f\xbf',
            b'\xf0\x90\x80\x80', b'\xf4\x8f\xbf\xbf',
        ] + [rng.randbytes(rng.randrange(2, 8)) for _ in range(80)]
        comandos, esperado = [], []
        for dados in casos:
            try:
                texto = dados.decode('utf-8')
                valido = True
            except UnicodeDecodeError:
                valido = False
            comandos += ['limpe(dados)', 'copie(destino, "guardado")']
            comandos += [f'adicione_byte(dados, {n})' for n in dados]
            comandos += ['decodifique_utf8(destino, dados, estado)', 'escreva(estado)',
                         'escreva(tamanho(dados))', 'escreva(tamanho(destino))', 'escreva(caracteres(destino))']
            esperado += [str(int(not valido)), str(len(dados)), str(len(dados) if valido else 8), str(len(texto) if valido else 8)]
            comandos += ['se estado != 0 {', 'escreva(destino == guardado)', '}']
            if not valido:
                esperado.append('1')
            for indice, valor in enumerate(dados):
                comandos.append(f'escreva(dados[{indice}])')
                esperado.append(str(valor))
                if valido:
                    comandos.append(f'escreva(byte_em(destino, {indice}))')
                    esperado.append(str(valor))
        fonte = 'inicio {\n seja dados: bytes\n seja destino: texto\n seja guardado: texto\n copie(guardado, "guardado")\n seja estado = 0\n' + '\n'.join(comandos) + '\n}'
        self.verificar(fonte, '\n'.join(esperado) + '\n')

    def test_fontes_fixas_grandes_e_texto_fixo_invalido_retornam_erro(self):
        fonte = '''inicio {
            seja origem: texto[16384]
            seja dados: bytes
            seja volta: texto
            seja estado = 0
            para indice de 0 ate 4095 {
                junte(origem, "ç")
            }
            codifique_utf8(dados, origem, estado)
            escreva(estado)
            decodifique_utf8(volta, dados, estado)
            escreva(caracteres(volta))
            carregue_arquivo("invalido.txt", origem)
            codifique_utf8(dados, origem, estado)
            escreva(estado)
            escreva(tamanho(dados))
            seja fixos: bytes[8]
            adicione_byte(fixos, 255)
            decodifique_utf8(volta, fixos, estado)
            escreva(estado)
            escreva(caracteres(volta))
        }'''
        self.verificar(fonte, '0\n4096\n1\n8192\n1\n4096\n', arquivos=lambda p: (p/'invalido.txt').write_bytes(b'\xff'))

    def test_modulo_utf8_vistas_de_campos_e_resultados(self):
        programa = programa_modulo('''importe "padrao/utf8.rts" como utf8
tipo Documento {
    titulo: texto
    dados: bytes
}
funcao converter(documento: emprestimo[Documento]) -> resultado[bytes] {
    retorne utf8.codificar(documento.titulo)
}
inicio {
    seja documento: Documento
    copie(documento.titulo, "RS")
    seja dados = converter(empreste(documento))
    libere(documento.titulo)
    seja volta = utf8.decodificar(empreste(dados.valor))
    escreva(volta.valor)
    adicione_byte(documento.dados, 255)
    seja falha = utf8.decodificar(empreste(documento.dados))
    escreva(falha.valido)
    escreva(falha.codigo_erro)
    escreva(tamanho(falha.valor))
    escreva(tamanho(documento.dados))
}''')
        for alvo in ('windows', 'linux'):
            imagem = compilar(programa, alvo, nivel=8, otimizar=True)
            if alvo == alvo_nativo():
                r, _ = rodar(imagem)
                self.assertEqual((r.returncode, r.stdout), (0, 'RS\n0\n1\n0\n1\n'), r.stderr)

    def test_rejeita_tipos_destino_fixo_emprestimo_e_estado_incorretos(self):
        for comando in ('codifique_utf8(nome, nome, estado)', 'decodifique_utf8(dados, dados, estado)',
                        'codifique_utf8(dados, dados, estado)', 'decodifique_utf8(nome, nome, estado)',
                        'codifique_utf8(fixos, nome, estado)', 'decodifique_utf8(nome, dados, sinal)',
                        'codifique_utf8(dados, nome)', 'decodifique_utf8(nome, dados, estado, estado)'):
            fonte = 'inicio {\n seja nome: texto\n seja dados: bytes\n seja fixos: bytes[8]\n seja estado = 0\n seja sinal = falso\n' + comando + '\n}'
            with self.subTest(comando=comando), self.assertRaises(ErroCompilacao):
                analisar_programa(fonte)

    def test_rejeita_escrita_em_registro_emprestado(self):
        for comando in ('codifique_utf8(doc.dados, origem, estado)', 'decodifique_utf8(doc.titulo, dados, estado)',
                        'codifique_utf8(dados, origem, doc.estado)'):
            fonte = '''tipo Documento {
    dados: bytes
    titulo: texto
    estado: inteiro
}
funcao alterar(doc: emprestimo[Documento], origem: emprestimo[texto]) -> inteiro {
    seja dados: bytes
    seja estado = 0
''' + comando + '''
    retorne estado
}
inicio {
    escreva(1)
}'''
            with self.subTest(comando=comando), self.assertRaises(ErroCompilacao):
                analisar_programa(fonte)

    def test_novos_nomes_reservados(self):
        for nome in ('codifique_utf8', 'decodifique_utf8'):
            for fonte in (f'inicio {{\n seja {nome} = 1\n}}',
                          f'funcao {nome}() -> inteiro {{\n retorne 1\n}}\ninicio {{\n escreva(1)\n}}',
                          f'tipo {nome} {{\n codigo: inteiro\n}}\ninicio {{\n escreva(1)\n}}'):
                with self.subTest(nome=nome, fonte=fonte), self.assertRaises(ErroCompilacao):
                    analisar_programa(fonte)

    def test_efeitos_registram_origem_destino_estado_e_falha(self):
        for comando in ('codifique_utf8', 'decodifique_utf8'):
            efeito = efeito_instrucao_arvore((comando, 'destino', 'origem', 'estado'))
            self.assertIn('origem', efeito.leituras)
            self.assertTrue({'destino', 'estado'} <= efeito.escritas)
            self.assertTrue(efeito.pode_falhar)


if __name__ == '__main__':
    unittest.main()
