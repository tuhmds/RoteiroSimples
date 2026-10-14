"""Ausencia de arquivo e erro de acesso nao sao estados equivalentes."""
from pathlib import Path
import os
import sys
import unittest

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))
from backend import compilar
from compilador.efeitos_programa import efeito_instrucao_arvore
from compilador.erros import ErroCompilacao
from compilador.parser import analisar_programa
from testes.test_valores_dinamicos_rs042a import rodar, alvo_nativo

FONTE = '''inicio {
    seja estado = 0
    consulte_arquivo("arquivo.rsd", estado)
    escreva(estado)
}'''


class TestesConsultaArquivoRS042N(unittest.TestCase):
    def test_ausente_regular_e_diretorio_nove_niveis(self):
        programa = analisar_programa(FONTE)
        for nivel in range(9):
            imagem = compilar(programa, alvo_nativo(), nivel=nivel, otimizar=nivel > 0)
            for preparar, esperado in ((None, 1),
                (lambda p: (p/'arquivo.rsd').write_bytes(b'preservado'), 0),
                (lambda p: (p/'arquivo.rsd').mkdir(), -1)):
                r, arquivos = rodar(imagem, antes=preparar)
                self.assertEqual((r.returncode, r.stdout), (0, str(esperado)+'\n'), r.stderr)
                if esperado == 0:
                    self.assertEqual(arquivos, {'arquivo.rsd': b'preservado'})
        for alvo in ('windows', 'linux'):
            self.assertTrue(compilar(programa, alvo, nivel=8, otimizar=True))

    def test_rejeita_links_finais_inclusive_pendurados(self):
        def preparar(pasta):
            (pasta/'alvo').write_bytes(b'preservado')
            try:
                os.symlink('alvo', pasta/'arquivo.rsd')
            except OSError as erro:
                self.skipTest(f'Criacao de link simbolico indisponivel: {erro}')
        r, _ = rodar(compilar(analisar_programa(FONTE), alvo_nativo()), antes=preparar)
        self.assertEqual((r.returncode, r.stdout), (0, '-1\n'), r.stderr)

    def test_rejeita_sintaxe_caminhos_e_estado_incorretos(self):
        for comando in ('consulte_arquivo("arquivo.rsd")', 'consulte_arquivo("arquivo.rsd", estado, estado)',
                        'consulte_arquivo("../arquivo.rsd", estado)', 'consulte_arquivo("pasta/arquivo.rsd", estado)',
                        'consulte_arquivo("NUL", estado)', 'consulte_arquivo(nome, estado)',
                        'consulte_arquivo("arquivo.rsd", sinal)'):
            with self.subTest(comando=comando), self.assertRaises(ErroCompilacao):
                analisar_programa('inicio {\n seja estado = 0\n seja sinal = falso\n seja nome: texto[32]\n' + comando+'\n}')

    def test_efeitos_e_nome_reservado(self):
        efeito = efeito_instrucao_arvore(('consulte_arquivo', 'arquivo.rsd', 'estado'))
        self.assertEqual(efeito.escritas, frozenset(('estado',)))
        self.assertTrue(efeito.arquivos and efeito.pode_falhar)
        for fonte in ('inicio {\n seja consulte_arquivo = 1\n}',
                      'funcao consulte_arquivo() -> inteiro {\n retorne 1\n}\ninicio {\n escreva(1)\n}'):
            with self.assertRaises(ErroCompilacao):
                analisar_programa(fonte)


if __name__ == '__main__':
    unittest.main()
