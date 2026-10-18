"""Orçamento RS-MEM: limites reais em processos filhos Linux."""
import os
import sys
from pathlib import Path
import subprocess
import tempfile
import unittest

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))


class TesteLimiteMemoria(unittest.TestCase):
    def test_validacoes_puras(self):
        if sys.platform != 'linux':
            self.skipTest('RLIMIT_AS é exclusivo do Linux.')
        from verificacao.execucao_limitada import validar_orcamento
        for limite in (-1, 0, 15, 65537):
            with self.subTest(limite=limite):
                with self.assertRaises(ValueError):
                    validar_orcamento(limite, 5)
        with self.assertRaises(ValueError):
            validar_orcamento(128, 0)

    @unittest.skipUnless(sys.platform == 'linux', 'Somente Linux')
    def test_aceita_programa_pequeno_e_reporta_status(self):
        from verificacao.execucao_limitada import executar
        saida = executar([sys.executable, '-c', 'print(345)'], 128)
        self.assertEqual(saida['codigo_saida'], 0)
        self.assertEqual(saida['saida_inicio'], '345\n')
        self.assertIn('NAO RSS', saida['tipo_limite'])
        self.assertFalse(saida['tempo_esgotado'])

    @unittest.skipUnless(sys.platform == 'linux', 'Somente Linux')
    def test_impede_reserva_acima_do_orcamento(self):
        from verificacao.execucao_limitada import executar
        codigo = 'import sys; b=bytearray(128*1024*1024); print(len(b))'
        resposta = executar([sys.executable, '-c', codigo], 64)
        self.assertNotEqual(resposta['codigo_saida'], 0)
        self.assertNotIn('134217728', resposta['saida_inicio'])

    @unittest.skipUnless(sys.platform == 'linux', 'Somente Linux')
    def test_timeout_mata_filho_sem_pendencia(self):
        from verificacao.execucao_limitada import executar
        codigo = 'import time; time.sleep(10)'
        resposta = executar([sys.executable, '-c', codigo], 128, timeout=0.05)
        self.assertTrue(resposta['tempo_esgotado'])

    @unittest.skipUnless(sys.platform == 'linux', 'Somente Linux')
    def test_elf_rs_real_executa_dentro_do_orcamento(self):
        from verificacao.execucao_limitada import executar
        from compilador.parser import analisar_programa
        from backend import compilar
        programa = analisar_programa("""inicio {
            seja dados: bytes
            para i de 0 ate 8191 {
                adicione_byte(dados, i % 256)
            }
            escreva(tamanho(dados))
            escreva(dados[8191])
        }""")
        with tempfile.TemporaryDirectory() as pasta:
            caminho = Path(pasta) / 'aplicativo_rs'
            caminho.write_bytes(compilar(programa, 'linux', nivel=8))
            caminho.chmod(0o755)
            relatorio = executar([str(caminho)], 128, timeout=15)
            self.assertEqual(relatorio['codigo_saida'], 0)
            self.assertEqual(relatorio['saida_inicio'], '8192\n255\n')

    @unittest.skipUnless(sys.platform == 'linux', 'Somente Linux')
    def test_cli_json_e_codigo_da_aplicacao(self):
        import json
        with tempfile.TemporaryDirectory() as pasta:
            arquivo = Path(pasta) / 'status.json'
            comando = [sys.executable, '-m', 'verificacao.execucao_limitada',
                       '--limite-mib', '128', '--json', str(arquivo), '--',
                       sys.executable, '-c', 'print(777)']
            resultado = subprocess.run(comando, cwd=RAIZ, capture_output=True,
                                      timeout=20)
            self.assertEqual(resultado.returncode, 0, resultado.stderr)
            relatorio = json.loads(arquivo.read_text(encoding='utf-8'))
            self.assertEqual(relatorio['codigo_saida'], 0)
            self.assertIn('777', relatorio['saida_inicio'])


if __name__ == '__main__':
    unittest.main()
