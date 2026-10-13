"""Medição real identifica os geradores, programas iguais e erros de execução."""
from pathlib import Path
import sys
import unittest

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))
from benchmarks.medir import medir
from testes.test_valores_dinamicos_rs042a import alvo_nativo
from testes.test_funcoes_ir_rs042j import FONTE


class TestesMedicaoRS042J(unittest.TestCase):
    def test_nove_niveis_registram_gerador_real_hashes_e_tempos(self):
        resultado = medir(FONTE, alvo_nativo(), repeticoes=2)
        linhas = resultado['resultados']
        self.assertEqual([r['nivel'] for r in linhas], list(range(9)))
        self.assertTrue(all(r['gerador'] == 'intermediario' for r in linhas))
        self.assertEqual([r['nivel_ir'] for r in linhas], [0, 1, 2, 2, 2, 2, 2, 2, 2])
        self.assertTrue(all(len(r['tempos_ms']) == 2 for r in linhas))
        self.assertTrue(all(r['resultado'] == (0, '60\n', '') for r in linhas))
        self.assertNotEqual(linhas[0]['sha256'], linhas[8]['sha256'])
        self.assertEqual(linhas[8]['mesmo_binario_que'], 2)

    def test_conservador_identifica_binarios_iguais_sem_prometer_otimizacao(self):
        fonte = 'inicio {\n seja valores: lista[]\n adicione(valores, 42)\n escreva(valores[0])\n}'
        linhas = medir(fonte, alvo_nativo(), repeticoes=2, niveis=(0, 8))['resultados']
        self.assertEqual([r['gerador'] for r in linhas], ['conservador', 'conservador'])
        self.assertEqual([r['nivel_ir'] for r in linhas], [0, 0])
        self.assertEqual(linhas[1]['mesmo_binario_que'], 0)
        self.assertEqual(linhas[0]['sha256'], linhas[1]['sha256'])

    def test_programa_que_falha_nao_produz_relatorio_de_desempenho_valido(self):
        with self.assertRaisesRegex(AssertionError, 'encerrou com erro'):
            medir('inicio {\n seja divisor = 0\n escreva(1 / divisor)\n}', alvo_nativo(), repeticoes=2, niveis=(0,))
