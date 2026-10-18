"""Testes do relatório estático: contagens não são confundidas com execução."""
import json
import subprocess
import sys
import tempfile
from pathlib import Path
import unittest

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))
from compilador.parser import analisar_programa
from verificacao.diagnostico_memoria import diagnosticar, formatar


class TestesDiagnosticoMemoria(unittest.TestCase):
    def test_contagem_nao_infere_execucoes(self):
        p = analisar_programa('''inicio {
            seja numeros: lista[]
            seja dados: bytes
            para i de 0 ate 9 {
                adicione(numeros, i)
                adicione_byte(dados, i)
            }
            libere(dados)
        }''')
        r = diagnosticar(p)
        self.assertEqual(r['contagens_sintaticas']['declaracao_dinamica'], 2)
        self.assertEqual(r['contagens_sintaticas']['crescimento_potencial'], 2)
        self.assertEqual(r['contagens_sintaticas']['liberacao_explicita'], 1)
        self.assertEqual(len(r['pontos_de_atencao']), 2)
        self.assertIn('sem medicao', r['escopo'])
        self.assertIn('ocorrencias_sintaticas', r['rotinas'][0])

    def test_lista_fixa_nao_conta_como_heap(self):
        r = diagnosticar(analisar_programa('''inicio {
            seja dados: lista[4]
            dados[0] = 1
            escreva(dados[0])
        }'''))
        self.assertNotIn('crescimento_potencial', r['contagens_sintaticas'])
        self.assertEqual(r['pontos_de_atencao'], [])
        self.assertIn('nenhuma contagem', formatar(r).lower())

    def test_funcoes_e_lacos_aninhados(self):
        r = diagnosticar(analisar_programa('''funcao criar() -> lista[inteiro] {
            seja numeros: lista[inteiro]
            enquanto tamanho(numeros) < 2 {
                adicione(numeros, 3)
            }
            retorne mova(numeros)
        }
        inicio {
            seja dados = criar()
            escreva(tamanho(dados))
        }'''))
        self.assertGreaterEqual(len(r['rotinas']), 2)
        self.assertEqual(len(r['pontos_de_atencao']), 1)
        self.assertNotEqual(r['pontos_de_atencao'][0]['escopo'], 'inicio')

    def test_cli_json_reproduzivel(self):
        with tempfile.TemporaryDirectory() as pasta:
            fonte = Path(pasta) / 'entrada.rts'
            saida = Path(pasta) / 'relatorio.json'
            fonte.write_text('inicio {\nseja dados: bytes\nadicione_byte(dados, 5)\n}\n',
                             encoding='utf-8')
            execucao = subprocess.run([sys.executable, '-m', 'verificacao.diagnostico_memoria',
                                      str(fonte), '--json', str(saida)],
                                      cwd=RAIZ, capture_output=True, text=True,
                                      encoding='utf-8', timeout=20)
            self.assertEqual(execucao.returncode, 0, execucao.stderr)
            relatorio = json.loads(saida.read_text(encoding='utf-8'))
            self.assertEqual(relatorio['contagens_sintaticas']['crescimento_potencial'], 1)
            self.assertIn('diagnóstico estático', execucao.stdout)

if __name__ == '__main__':
    unittest.main()
