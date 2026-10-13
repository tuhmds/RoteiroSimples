"""ABI e desenrolamento do código nativo SSA de funções, em processos isolados."""
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
from testes.test_abi_funcoes_ir_rs042j import FONTE


@unittest.skipUnless(WINDOWS_X64, 'Ensaio exige Windows AMD64 real.')
class TestesAbiFuncoesSSARS042L(unittest.TestCase):
    def ensaio(self, acao):
        ambiente = os.environ.copy()
        ambiente['PYTHONIOENCODING'] = 'utf-8'
        r = subprocess.run([sys.executable, str(Path(__file__).resolve()), '--ensaio', acao],
                           cwd=RAIZ, env=ambiente, capture_output=True, encoding='utf-8', timeout=60)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        return json.loads(r.stdout)

    def test_ssa_preserva_gpr_xmm_e_rsp_em_chamadas_aninhadas(self):
        self.assertEqual(self.ensaio('normal'), {'resultados': [90, 68],
                                              'inteiros_preservados': 8, 'vetoriais_preservados': 10})

    def test_desenrolamento_de_funcoes_ssa_com_saltos_compactados(self):
        r = self.ensaio('estados')
        for nome in ('funcao_incrementar', 'funcao_combinar', 'funcao_repetir'):
            self.assertIn(nome, r['nomes'])

    def test_excecoes_reais_em_corpos_ssa_e_chamadores(self):
        r = self.ensaio('excecoes')
        self.assertEqual(r['quadros'], 2 * len(r['excecoes']))
        self.assertIn('funcao_combinar', r['excecoes'])

    def test_sondagem_e_sentinelas_em_funcao_ssa_com_quadro_grande(self):
        r = self.ensaio('grande')
        self.assertEqual(r['retorno'], 270)
        self.assertGreaterEqual(r['quadro'], 4096)
        self.assertIn('funcao_grande', r['nomes'])


def executar(acao):
    from backend.funcoes_ssa import montar_funcoes_ssa
    from compilador.ir import construir_ir
    from testes.ensaio_windows_rs0415 import (Windows, PeCarregado, gerar_imagem,
                                            chamar_com_sentinelas, executar_ensaio, ensaiar_estados)
    from testes.test_ssa_funcoes_rs042l import fonte_grande
    def montar_transformado(programa, windows, *args, **kwargs):
        g, mensagens = montar_funcoes_ssa(construir_ir(programa, nivel=3), windows, 8)
        g.compactar_saltos_ssa()
        return g, mensagens
    with patch('backend.x86_64.montar_codigo', montar_transformado):
        if acao in ('estados', 'excecoes'):
            return executar_ensaio(acao, FONTE)
        windows = Windows()
        fonte = FONTE
        if acao == 'grande':
            # O wrapper de sentinelas recebe duas palavras. A função RS
            # monta a chamada grande com a convenção realmente emitida.
            fonte = fonte_grande().replace('inicio {', 'funcao chamar(numero: inteiro) -> inteiro {\n retorne grande('
                + ', '.join(['numero'] * 270) + ')\n}\ninicio {')
        gerador, pe, tabela, dados = gerar_imagem(fonte)
        with PeCarregado(windows, pe) as imagem:
            if acao == 'grande':
                retorno = int(chamar_com_sentinelas(windows,
                    imagem.base + 0x1000 + gerador.rotulos['funcao_chamar'], argumentos_pilha=[0, 1]))
                estados = ensaiar_estados(windows, gerador, tabela, dados)
                return {'retorno': retorno, 'quadro': gerador.quadros_funcoes['grande'], 'nomes': estados['nomes']}
            resultados = []
            for nome, argumentos in (('combinar', [0, 3, 2, 1]), ('repetir', [0, 25])):
                resultados.append(int(chamar_com_sentinelas(windows,
                    imagem.base + 0x1000 + gerador.rotulos['funcao_' + nome], argumentos_pilha=argumentos)))
            return {'resultados': resultados, 'inteiros_preservados': 8, 'vetoriais_preservados': 10}


if __name__ == '__main__' and '--ensaio' in sys.argv:
    print(json.dumps(executar(sys.argv[-1])))
elif __name__ == '__main__':
    unittest.main()
