"""RS 0.41.4 — saída fatal com pilha alinhada e auxiliares desenroláveis.

Os testes estruturais examinam os bytes x86-64 e a tabela PE. Os testes
dinâmicos são executados somente no Windows para evitar falsa aprovação.
"""
import os
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import unittest

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

from backend import compilar
from backend.x86_64 import montar_codigo
from backend.desenrolamento_windows import gerar_desenrolamentos
from compilador.parser import analisar_programa
from compilador.erros import ErroCompilacao


FONTES = {
    'arquivos': """inicio {
        seja atual: texto[32]
        seja dados: bytes[8]
        seja estado = 0
        seja recurso: arquivo
        copie(atual, "ABCDE")
        grave_arquivo("arquivo.rsd", atual)
        carregue_arquivo("arquivo.rsd", atual)
        adicione_byte(dados, 67)
        grave_trecho("arquivo.rsd", dados, 2, estado)
        carregue_trecho("arquivo.rsd", dados, 2, 1, estado)
        abra_arquivo("arquivo.rsd", recurso, "alteracao", estado)
        feche_arquivo(recurso, estado)
        publique_arquivo("arquivo.rsd", "final.rsd", estado)
        escreva(estado)
    }""",
    'listas': """inicio {
        seja primeira: lista[inteiro]
        seja segunda: lista[inteiro]
        adicione(primeira, 17)
        mova(segunda, primeira)
        escreva(segunda[0])
        libere(segunda)
    }""",
}


class TestesQuadrosAuxiliaresRS0414(unittest.TestCase):
    def test_familias_de_arquivo_recebem_descricoes_verificadas(self):
        g, _ = montar_codigo(analisar_programa(FONTES['arquivos']), True)
        nomes = {d['inicio'] for d in g.desenrolamentos}
        obrigatorios = {
            'rs_inicio_principal', 'rs_arquivo_gravar',
            'rs_arquivo_carregar', 'rs_trecho_gravar',
            'rs_trecho_carregar', 'rs_abrir_recurso',
            'rs_abrir_caminho_verificado', 'rs_recurso_gravar',
            'rs_recurso_ler', 'rs_publicar_arquivo',
        }
        self.assertTrue(obrigatorios <= nomes, obrigatorios - nomes)
        aux = [d for d in g.desenrolamentos
               if d.get('prologo') == 'auxiliar_preservado']
        self.assertGreaterEqual(len(aux), 9)
        for d in aux:
            with self.subTest(nome=d['inicio']):
                ini = g.rotulos[d['inicio']]
                pos = g.rotulos[d['fim_prologo']]
                fim = g.rotulos[d['fim']]
                self.assertTrue(ini < pos < fim)
                self.assertEqual(d['quadro'] % 16, 0)
                self.assertEqual(bytes(g.codigo[fim-8:fim]),
                                 bytes.fromhex('48 8D 65 00 5D 5E 5F C3'))

        tabela, infos = gerar_desenrolamentos(g, 0x1000, 0xA000)
        self.assertEqual(len(tabela), len(g.desenrolamentos) * 12)
        self.assertGreater(len(infos), 0)
        intervalos = [struct.unpack_from('<III', tabela, i)
                     for i in range(0, len(tabela), 12)]
        self.assertEqual(intervalos, sorted(intervalos))
        for atual, prox in zip(intervalos, intervalos[1:]):
            self.assertLessEqual(atual[1], prox[0])

    def test_auxiliares_de_lista_recebem_descricoes_reais(self):
        g, _ = montar_codigo(analisar_programa(FONTES['listas']), True)
        nomes = {d['inicio'] for d in g.desenrolamentos}
        esperado = {
            'rs_lista_liberar_descritor',
            'rs_lista_mover_descritor',
            'rs_lista_acrescentar',
        }
        self.assertTrue(esperado <= nomes, esperado - nomes)
        tabela, dados = gerar_desenrolamentos(g, 0x1000, 0xA000)
        self.assertEqual(len(tabela), len(g.desenrolamentos)*12)
        self.assertTrue(dados)

    def test_corromper_prologo_auxiliar_interrompe_compilacao(self):
        g, _ = montar_codigo(analisar_programa(FONTES['arquivos']), True)
        inicio = g.rotulos['rs_arquivo_gravar']
        g.codigo[inicio] = 0x90
        with self.assertRaisesRegex(ErroCompilacao, 'Quadro auxiliar'):
            gerar_desenrolamentos(g, 0x1000, 0xA000)

    def test_saidas_fatais_reservam_espaco_de_sombra(self):
        fonte = """inicio {
            seja dados: bytes[3]
            seja atual: texto[8]
            seja numero = 0
            leia(numero)
            adicione_byte(dados, 5)
            copie(atual, "A")
            escreva(numero / 2)
        }"""
        g, _ = montar_codigo(analisar_programa(fonte), True)
        prefixo = b'\x48\x83\xE4\xF0\x48\x83\xEC\x30'
        nomes = [
            'erro_divisao_zero',
            'erro_entrada_invalida',
            'erro_entrada_limite',
            'erro_bytes_capacidade',
            'erro_texto_capacidade',
        ]
        for nome in nomes:
            with self.subTest(nome=nome):
                indice = g.rotulos[nome]
                self.assertEqual(g.codigo[indice:indice+len(prefixo)],
                                 prefixo)

    def test_erros_com_e_sem_listas_preservam_status_nativo(self):
        if sys.platform != 'win32':
            self.skipTest('Execução exigiria Windows.')
        casos = [
            ("""inicio {
                seja a = 1
                seja b = 0
                escreva(a / b)
            }""", 'divisão por zero'),
            ("""inicio {
                seja valor = 0
                leia(valor)
                escreva(valor)
            }""", 'entrada invalida'),
            ("""inicio {
                seja dados: bytes[2]
                adicione_byte(dados, 300)
            }""", 'byte deve estar'),
        ]
        with tempfile.TemporaryDirectory() as pasta:
            for indice, (fonte, trecho) in enumerate(casos):
                for nivel in (0, 4, 8):
                    with self.subTest(caso=indice, nivel=nivel):
                        imagem = compilar(analisar_programa(fonte), 'windows',
                                          otimizar=nivel > 0, nivel=nivel)
                        exe = Path(pasta) / f'erro_{indice}_{nivel}.exe'
                        exe.write_bytes(imagem)
                        resultado = subprocess.run(
                            [str(exe)], input='invalido\n',
                            cwd=pasta, capture_output=True, text=True,
                            encoding='utf-8', errors='replace', timeout=15)
                        self.assertEqual(resultado.returncode, 1, resultado.stderr)
                        self.assertIn(trecho.lower(), resultado.stdout.lower())


if __name__ == '__main__':
    unittest.main()
