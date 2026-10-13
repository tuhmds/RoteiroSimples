"""Oráculo de valores/donos, reprodução e redução de programas gerados."""
from dataclasses import replace
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))
from verificacao.casos_gerados import gerar_caso, montar_caso, Operacao, reduzir_caso
from verificacao.campanha import avaliar, salvar_falha


class TestesCampanhaRS042J(unittest.TestCase):
    def test_modelo_conhecido_de_ordem_movimento_e_arquivo(self):
        operacoes = (
            Operacao('adicionar', 0, 1, 0, False),
            Operacao('adicionar', 0, 256, 0, False),
            Operacao('retirar', 0, 0, 0, True),
            Operacao('mover', 1, 0, 0, False),
            Operacao('arquivo', 0, 258, 0, False),
        )
        caso = montar_caso(0, operacoes)
        self.assertEqual(caso.saida, '1\n7\n0\n2\n7\n771\n0\n7\n1\n771\n1\n7\n1\n7\n-1\n3\n0\n255\n2\n1\n7\n-1\n')
        self.assertEqual(caso.arquivos, {'dados.bin': b'\0\xff\x02'})
        for nivel in (0, 8):
            self.assertEqual(avaliar(caso, nivel)['classe'], 'aprovado')

    def test_programas_gerados_validam_donos_conteudo_e_arquivos_nativos(self):
        acoes = set()
        for semente in range(42010, 42018):
            caso = gerar_caso(semente, 40)
            acoes.update(op.acao for op in caso.operacoes)
            self.assertEqual(caso, gerar_caso(semente, 40))
            for nivel in (0, 8):
                with self.subTest(semente=semente, nivel=nivel):
                    resultado = avaliar(caso, nivel)
                    self.assertEqual(resultado['classe'], 'aprovado', resultado)
        self.assertEqual(acoes, {'adicionar', 'substituir', 'retirar', 'remover', 'limpar', 'mover', 'liberar', 'arquivo'})

    def test_oraculo_detecta_saida_e_arquivo_divergentes(self):
        caso = montar_caso(0, (Operacao('arquivo', 0, 258, 0, False),))
        self.assertEqual(avaliar(replace(caso, saida='SAIDA INCORRETA\n'), 8)['classe'], 'saida_divergente')
        self.assertEqual(avaliar(replace(caso, arquivos={'dados.bin': b'errado'}), 8)['classe'], 'arquivos_divergentes')

    def test_reducao_reproduz_defeito_injetado_no_emissor_do_programa(self):
        caso = gerar_caso(42010, 40)
        def defeito(novo):
            # Simula a geração da forma de gravação que a RS ainda rejeita.
            fonte = re.sub(r'grave_arquivo\("dados.bin", para_gravar_(\d+)\)',
                           r'grave_arquivo("dados.bin", documento_\1.dados)', novo.fonte)
            return replace(novo, fonte=fonte)
        resultado = avaliar(defeito(caso), 0)
        self.assertEqual(resultado['classe'], 'compilacao:ErroCompilacao')
        reduzido = reduzir_caso(caso, lambda novo: avaliar(defeito(novo), 0)['classe'] == resultado['classe'])
        self.assertEqual(len(reduzido.operacoes), 1)
        self.assertEqual(reduzido.operacoes[0].acao, 'arquivo')
        self.assertEqual(avaliar(defeito(reduzido), 0)['classe'], resultado['classe'])
        self.assertEqual(avaliar(reduzido, 0)['classe'], 'aprovado')

    def test_campanha_e_reproducao_json_na_linha_de_comando(self):
        with tempfile.TemporaryDirectory() as pasta:
            caminho = Path(pasta)
            executado = subprocess.run([sys.executable, '-m', 'verificacao.campanha', '--casos', '2',
                '--passos', '9', '--saida', str(caminho)], cwd=RAIZ, capture_output=True,
                encoding='utf-8', errors='replace', timeout=40)
            self.assertEqual(executado.returncode, 0, executado.stderr)
            resumo = json.loads((caminho / 'resumo.json').read_text(encoding='utf-8'))
            self.assertEqual((resumo['casos'], resumo['execucoes']), (2, 4))
            caso = gerar_caso(42010, 9)
            salvar_falha(caminho, caso, 8, {'classe': 'aprovado'}, reduzir=False)
            reproduzido = subprocess.run([sys.executable, '-m', 'verificacao.campanha',
                '--reproduzir', str(caminho / 'falha_42010_O8.json'), '--saida', str(caminho / 'reproducao')],
                cwd=RAIZ, capture_output=True, encoding='utf-8', errors='replace', timeout=40)
            self.assertEqual(reproduzido.returncode, 0, reproduzido.stderr)
            repetido = json.loads((caminho / 'reproducao/resumo.json').read_text(encoding='utf-8'))
            self.assertEqual((repetido['casos'], repetido['execucoes']), (1, 1))
            self.assertEqual(repetido['resultados'][0]['sha256'], resumo['resultados'][1]['sha256'])

    def test_uso_inativo_gerado_e_rejeitado_com_saida_controlada(self):
        caso = gerar_caso(42010, 9)
        fonte = caso.fonte.rsplit('}', 1)[0] + 'libere(primeira)\nescreva(tamanho(primeira))\n}\n'
        for nivel in (0, 8):
            resultado = avaliar(replace(caso, fonte=fonte), nivel)
            self.assertEqual(resultado['classe'], 'execucao:1')
            self.assertIn('liberacao', resultado['saida'])

    def test_argumentos_invalidos_da_campanha_nao_executam_programas(self):
        resultado = subprocess.run([sys.executable, '-m', 'verificacao.campanha', '--niveis', '9'],
            cwd=RAIZ, capture_output=True, encoding='utf-8', errors='replace', timeout=10)
        self.assertEqual(resultado.returncode, 1)
        self.assertNotIn('Traceback', resultado.stderr)
