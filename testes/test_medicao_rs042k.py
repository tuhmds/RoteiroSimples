"""Medições intercaladas com a execução real e rejeição de divergências."""
from unittest.mock import patch
import unittest

from benchmarks.medir import medir
from testes.test_valores_dinamicos_rs042a import alvo_nativo
from backend import compilar


class TestesMedicaoRS042K(unittest.TestCase):
    def test_intercalacao_reproduzivel_executa_todos_niveis_por_rodada(self):
        fonte = 'inicio {\n seja valores: lista[]\n adicione(valores, 7)\n escreva(valores[0])\n}'
        primeira = medir(fonte, alvo_nativo(), repeticoes=2, semente=42)
        segunda = medir(fonte, alvo_nativo(), repeticoes=2, semente=42)
        self.assertEqual(primeira['ordem_rodadas'], segunda['ordem_rodadas'])
        self.assertEqual(len(primeira['ordem_rodadas']), 3)
        self.assertTrue(all(sorted(ordem) == list(range(9)) for ordem in primeira['ordem_rodadas']))
        self.assertGreater(len({tuple(o) for o in primeira['ordem_rodadas']}), 1)
        self.assertTrue(all(len(r['tempos_ms']) == 2 for r in primeira['resultados']))
        self.assertTrue(all(r['resultado'] == (0, '7\n', '') for r in primeira['resultados']))
        self.assertEqual(len({r['sha256'] for r in primeira['resultados']}), 1)

    def test_binario_com_resultado_distinto_e_rejeitado(self):
        def defeito(programa, alvo, nivel, otimizar):
            # Executa binários reais: a medição deve rejeitar o nível alterado.
            if nivel == 8:
                from compilador.parser import analisar_programa
                programa = analisar_programa('inicio {\n escreva(8)\n}')
            return compilar(programa, alvo, nivel=nivel, otimizar=otimizar)
        with patch('benchmarks.medir.compilar', side_effect=defeito):
            with self.assertRaisesRegex(AssertionError, 'distintos entre os níveis'):
                medir('inicio {\n escreva(7)\n}', alvo_nativo(), repeticoes=2, niveis=(0, 8))

    def test_niveis_repetidos_sao_rejeitados_antes_de_compilar(self):
        with self.assertRaisesRegex(ValueError, 'distintos'):
            medir('inicio {\n escreva(7)\n}', alvo_nativo(), repeticoes=2, niveis=(8, 8))
