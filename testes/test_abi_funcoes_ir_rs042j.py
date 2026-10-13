"""ABI e desenrolamento do código realmente transformado pela IR O8."""
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))
from testes.test_abi_proprietarios_rs042a import WINDOWS_X64

FONTE = '''funcao incrementar(numero: inteiro) -> inteiro {
    seja constante = 6 * 7
    retorne numero + constante
}
funcao combinar(a: inteiro, b: inteiro, c: inteiro) -> inteiro {
    retorne incrementar(a) + incrementar(b) + c
}
funcao repetir(numero: inteiro) -> inteiro {
    se numero == 0 {
        retorne incrementar(1)
    }
    retorne repetir(numero - 1) + 1
}
inicio {
    escreva(combinar(1, 2, 3))
}'''


@unittest.skipUnless(WINDOWS_X64, 'Ensaio exige Windows AMD64 real.')
class TestesAbiFuncoesIRRS042J(unittest.TestCase):
    def ensaio(self, acao):
        ambiente = os.environ.copy()
        ambiente['PYTHONIOENCODING'] = 'utf-8'
        resultado = subprocess.run([sys.executable, str(Path(__file__).resolve()), '--ensaio', acao],
            cwd=RAIZ, env=ambiente, capture_output=True, encoding='utf-8', errors='replace', timeout=40)
        self.assertEqual(resultado.returncode, 0, resultado.stdout + resultado.stderr)
        return json.loads(resultado.stdout)

    def test_codigo_ir_preserva_gpr_xmm_e_pilha_em_chamadas_aninhadas(self):
        self.assertEqual(self.ensaio('normal'), {'resultados': [90, 68],
            'inteiros_preservados': 8, 'vetoriais_preservados': 10, 'nivel_ir': 2})

    def test_estados_de_desenrolamento_apos_transformar_corpos(self):
        resultado = self.ensaio('estados')
        for nome in ('funcao_incrementar', 'funcao_combinar', 'funcao_repetir'):
            self.assertIn(nome, resultado['nomes'])

    def test_excecoes_reais_apos_transformar_corpos(self):
        resultado = self.ensaio('excecoes')
        self.assertEqual(resultado['quadros'], 2 * len(resultado['excecoes']))
        self.assertIn('funcao_combinar', resultado['excecoes'])


def executar(acao):
    from backend.x86_64 import montar_codigo
    from compilador.ir import construir_ir, programa_para_backend
    from testes.ensaio_windows_rs0415 import (Windows, PeCarregado, gerar_imagem,
                                            chamar_com_sentinelas, executar_ensaio)
    def montar_transformado(programa, windows, *args, **kwargs):
        ir = construir_ir(programa, otimizar=True, nivel=8)
        return montar_codigo(programa_para_backend(ir), windows, *args, **kwargs)
    # O hospedeiro reutiliza o PE e os metadados realmente emitidos, sem
    # reconstruir UNWIND_INFO nem substituir o corpo por código artificial.
    with patch('backend.x86_64.montar_codigo', montar_transformado):
        if acao != 'normal':
            return executar_ensaio(acao, FONTE)
        windows = Windows()
        gerador, pe, _, _ = gerar_imagem(FONTE)
        with PeCarregado(windows, pe) as imagem:
            resultados = []
            for nome, argumentos in (('combinar', [0, 3, 2, 1]), ('repetir', [0, 25])):
                resultados.append(int(chamar_com_sentinelas(windows,
                    imagem.base + 0x1000 + gerador.rotulos['funcao_' + nome],
                    argumentos_pilha=argumentos)))
            return {'resultados': resultados, 'inteiros_preservados': 8,
                    'vetoriais_preservados': 10, 'nivel_ir': 2}


if __name__ == '__main__' and '--ensaio' in sys.argv:
    print(json.dumps(executar(sys.argv[-1])))
elif __name__ == '__main__':
    unittest.main()
