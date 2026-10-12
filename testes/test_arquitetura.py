"""Testes de compatibilidade da reorganização modular RS 0.9."""
import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

from backend import compilar as compilador_nativo
from backend.linux_elf import montar_elf
from backend.windows_pe import montar_pe
from compilador.ast import Programa
from compilador.erros import ErroCompilacao
from compilador.ir import construir_ir, formatar_ir
from compilador.lexico import tokens
from compilador.otimizador import dobrar_constantes
from compilador.parser import analisar_programa
from compilador.semantica import ContextoSemantico
from compilador.tipos import tipo_expressao
from codigo_nativo import compilar as compilar_legado
from ir import construir_ir as construir_ir_legado
from sintaxe import analisar_programa as analisar_legado


class TestesArquiteturaRS09(unittest.TestCase):
    def test_apis_legadas_continuam_equivalentes(self):
        self.assertIs(compilar_legado, compilador_nativo)
        self.assertIs(analisar_legado, analisar_programa)
        self.assertIs(construir_ir_legado, construir_ir)
        self.assertIs(Programa, type(analisar_programa('inicio {\n escreva(1)\n}')))
        self.assertTrue(callable(montar_elf) and callable(montar_pe))
        self.assertTrue(callable(dobrar_constantes))

    def test_lexico_preserva_acentos_dentro_de_string(self):
        self.assertEqual(tokens('escreva("Você está bem?") // comentário', 1),
                         ['escreva', '(', '"Você está bem?"', ')'])
        with self.assertRaisesRegex(ErroCompilacao, 'sem acentos'):
            tokens('início {', 1)

    def test_semantica_em_modulo_independente(self):
        semantica = ContextoSemantico()
        semantica.registrar('vida', 'inteiro', 1)
        expressao, tipo = semantica.expressao_tipada(['vida', '+', '1'], 2, 'inteiro')
        self.assertEqual((expressao[0], tipo), ('bin', 'inteiro'))
        self.assertEqual(tipo_expressao(expressao, semantica.tipos, 2), 'inteiro')
        with self.assertRaisesRegex(ErroCompilacao, 'tipo incompatível'):
            semantica.expressao_tipada(['verdadeiro'], 3, 'inteiro')

    def test_ir_isolada_do_backend(self):
        programa = analisar_programa('inicio {\n escreva(2 * 3 + 4)\n}')
        otimizada = construir_ir(programa, otimizar=True)
        normal = construir_ir(programa, otimizar=False)
        self.assertEqual(otimizada.instrucoes[0].argumentos[0].valor, 10)
        self.assertEqual(normal.instrucoes[0].argumentos[0].operacao, 'bin')
        self.assertIn('IR v1', formatar_ir(otimizada))

    def test_binarios_iguais_versao_041(self):
        """Confere novas assinaturas PE/ELF, mantendo originais historicas: 9 programas x 2 sistemas x 2 níveis de otimização."""
        fixture = json.loads((RAIZ / 'testes/fixtures/rs0412_binarios_08.json').read_text(encoding='utf-8'))
        self.assertEqual(len(fixture), 9)
        comparados = 0
        for arquivo, esperados in fixture.items():
            if arquivo in ('entrada.rts', 'tipos.rts'):
                continue  # RS 0.19 substitui explicitamente a rotina nativa de E/S.
            programa = analisar_programa((RAIZ / 'exemplos' / arquivo).read_text(encoding='utf-8-sig'))
            for config, digest in esperados.items():
                with self.subTest(arquivo=arquivo, config=config):
                    alvo, nivel = config.split('/')
                    binario = compilador_nativo(programa, alvo, otimizar=nivel == 'O1')
                    self.assertEqual(hashlib.sha256(binario).hexdigest(), digest)
                    comparados += 1
        self.assertEqual(comparados, 28)

    def test_cli_e_ir_tem_os_mesmos_comandos(self):
        with tempfile.TemporaryDirectory() as pasta:
            saida = Path(pasta) / 'exemplo.exe'
            processo = subprocess.run(
                [sys.executable, str(RAIZ / 'compilar.py'),
                 str(RAIZ / 'exemplos/otimizacao.rts'), '--alvo', 'windows',
                 '--mostrar-ir', '-O', '1', '-o', str(saida)],
                capture_output=True, text=True, timeout=15,
            )
            self.assertEqual(processo.returncode, 0, processo.stderr)
            self.assertIn('RS IR v1', processo.stdout)
            self.assertTrue(saida.read_bytes().startswith(b'MZ'))


if __name__ == '__main__':
    unittest.main()
