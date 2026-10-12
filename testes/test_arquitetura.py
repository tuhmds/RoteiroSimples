"""Verificações da arquitetura modular RS 0.9 (Windows e Linux)."""
import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))
from compilador.ast import Programa
from compilador.erros import ErroCompilacao
from compilador.ir import construir_ir, formatar_ir
from compilador.lexico import tokens
from compilador.otimizador import dobrar_constantes
from compilador.parser import analisar_programa
from compilador.semantica import ContextoSemantico
from compilador.tipos import tipo_expressao
from backend import compilar
from backend.windows_pe import montar_pe
from backend.linux_elf import montar_elf
from sintaxe import analisar_programa as analisar_legado
from codigo_nativo import compilar as compilar_legado
from ir import construir_ir as construir_ir_legado


class TestesArquitetura(unittest.TestCase):
    def test_apis_legadas(self):
        self.assertIs(analisar_legado, analisar_programa)
        self.assertIs(compilar_legado, compilar)
        self.assertIs(construir_ir_legado, construir_ir)
        self.assertIsInstance(analisar_programa('inicio {\n escreva(1)\n}'), Programa)
        self.assertTrue(callable(montar_elf) and callable(montar_pe))

    def test_tokenizador_e_semantica(self):
        self.assertEqual(tokens('escreva("Você está bem?") // comentário', 1),
                         ['escreva', '(', '"Você está bem?"', ')'])
        with self.assertRaisesRegex(ErroCompilacao, 'sem acentos'):
            tokens('início {', 1)
        contexto = ContextoSemantico()
        contexto.registrar('vida', 'inteiro', 1)
        expr, tipo = contexto.expressao_tipada(['vida', '+', '1'], 2, 'inteiro')
        self.assertEqual(tipo, 'inteiro')
        self.assertEqual(tipo_expressao(expr, contexto.tipos, 2), 'inteiro')
        with self.assertRaises(ErroCompilacao):
            contexto.expressao_tipada(['verdadeiro'], 3, 'inteiro')

    def test_otimizador_foi_separado(self):
        programa = analisar_programa('inicio {\n escreva(2 * 3 + 4)\n}')
        otimizado = construir_ir(programa, otimizar=True)
        normal = construir_ir(programa, otimizar=False)
        self.assertTrue(callable(dobrar_constantes))
        self.assertEqual(otimizado.instrucoes[0].argumentos[0].valor, 10)
        self.assertEqual(normal.instrucoes[0].argumentos[0].operacao, 'bin')
        self.assertIn('IR v1', formatar_ir(otimizado))

    def test_36_binarios_identicos_a_rs08(self):
        fixture = json.loads((RAIZ / 'testes/fixtures/rs08_binarios.json').read_text(encoding='utf-8'))
        self.assertEqual(len(fixture), 9)
        contador = 0
        for arq, esperados in fixture.items():
            fonte = (RAIZ / 'exemplos' / arq).read_text(encoding='utf-8-sig')
            programa = analisar_programa(fonte)
            for configuracao, hash_esperado in esperados.items():
                with self.subTest(arquivo=arq, configuracao=configuracao):
                    alvo, nivel = configuracao.split('/')
                    binario = compilar(programa, alvo, otimizar=(nivel == 'O1'))
                    self.assertEqual(hashlib.sha256(binario).hexdigest(), hash_esperado)
                    contador += 1
        self.assertEqual(contador, 36)

    def test_cli_e_ir_windows(self):
        with tempfile.TemporaryDirectory() as pasta:
            destino = Path(pasta) / 'test.exe'
            processo = subprocess.run(
                [sys.executable, str(RAIZ / 'compilar.py'),
                 str(RAIZ / 'exemplos/arquitetura.rts'),
                 '--alvo', 'windows', '-O', '1', '--mostrar-ir',
                 '-o', str(destino)],
                capture_output=True, text=True, timeout=15,
            )
            self.assertEqual(processo.returncode, 0, processo.stderr)
            self.assertTrue(destino.read_bytes().startswith(b'MZ'))
            self.assertIn('IR v1', processo.stdout)


if __name__ == '__main__':
    unittest.main()
