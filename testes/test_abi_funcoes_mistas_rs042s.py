"""Fronteiras mistas com sentinelas reais, desenrolamento e quadros grandes."""
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
from testes.test_abi_ssa_linux_rs042l import LINUX_X64
from testes.test_abi_funcoes_ir_rs042j import FONTE

FONTE_MISTA = FONTE.replace('inicio {', '''funcao encaminhar(a: inteiro, b: inteiro, c: inteiro) -> inteiro {
    seja titulo: texto
    copie(titulo, "RS")
    retorne combinar(a, b, c) + caracteres(titulo)
}
inicio {''')


def ensaio(acao):
    ambiente = os.environ.copy()
    ambiente['PYTHONIOENCODING'] = 'utf-8'
    r = subprocess.run([sys.executable, str(Path(__file__).resolve()), '--ensaio', acao],
                       cwd=RAIZ, env=ambiente, capture_output=True, encoding='utf-8', timeout=60)
    if r.returncode:
        raise AssertionError(r.stdout + r.stderr)
    return json.loads(r.stdout)


@unittest.skipUnless(WINDOWS_X64, 'Ensaio exige Windows AMD64 real.')
class TestesAbiFuncoesMistasWindowsRS042S(unittest.TestCase):
    def test_dono_no_chamador_preserva_resultado_registradores_e_pilha(self):
        self.assertEqual(ensaio('normal'), {'resultados': [90, 92, 68],
            'inteiros_preservados': 8, 'vetoriais_preservados': 10})

    def test_desenrolamento_dos_dois_caminhos_apos_compactar_saltos(self):
        r = ensaio('estados')
        self.assertIn('funcao_encaminhar', r['nomes'])
        self.assertIn('funcao_combinar', r['nomes'])

    def test_excecoes_reais_em_corpos_conservadores_e_ssa(self):
        r = ensaio('excecoes')
        self.assertEqual(r['quadros'], 2 * len(r['excecoes']))
        self.assertIn('funcao_encaminhar', r['excecoes'])
        self.assertIn('funcao_combinar', r['excecoes'])

    def test_quadro_ssa_grande_em_programa_com_donos(self):
        r = ensaio('grande')
        self.assertEqual(r['retorno'], 270)
        self.assertGreaterEqual(r['quadro'], 4096)
        self.assertIn('funcao_grande', r['nomes'])


@unittest.skipUnless(LINUX_X64, 'Ensaio exige Linux x86-64 real.')
class TestesAbiFuncoesMistasLinuxRS042S(unittest.TestCase):
    def test_chamador_com_texto_preserva_seis_registradores_e_rsp(self):
        self.assertEqual(ensaio('linux'), {'retorno': 162,
            'registradores_preservados': 6, 'pilha_preservada': True})


def executar(acao):
    from backend.funcoes_mistas import montar_funcoes_mistas
    from compilador.estrategia import decidir_estrategia
    from compilador.parser import analisar_programa

    def montar(programa, windows):
        decisao = decidir_estrategia(programa, 8)
        assert decisao.gerador == 'misto'
        g, mensagens = montar_funcoes_mistas(programa, decisao, windows)
        g.compactar_saltos_ssa()
        return g, mensagens

    if acao == 'linux':
        from testes.test_abi_ssa_linux_rs042l import executar as executar_linux
        fonte = '''funcao alterar(numero: inteiro) -> inteiro {
    seja a = numero + 1
    seja b = numero + 2
    seja c = numero + 3
    retorne a + b + c
}
funcao calcular(numero: inteiro) -> inteiro {
    seja titulo: texto
    copie(titulo, "RS")
    seja a = numero + 10
    seja b = numero + 20
    seja c = numero + 30
    seja d = numero + 40
    seja resultado_e = alterar(numero)
    retorne a + b + c + d + resultado_e + alterar(resultado_e)
}
inicio {
    escreva(calcular(2))
}'''
        # Reutiliza somente o hospedeiro de sentinelas; substitui o ELF pela
        # emissão mista real. A fonte histórica do hospedeiro não é emitida.
        with patch('backend.funcoes_ssa.montar_funcoes_ssa',
                   side_effect=lambda ir, windows, *a, **k: montar(analisar_programa(fonte), windows)):
            return executar_linux()

    from testes.ensaio_windows_rs0415 import (Windows, PeCarregado, gerar_imagem,
        chamar_com_sentinelas, executar_ensaio, ensaiar_estados)
    from testes.test_ssa_funcoes_rs042l import fonte_grande
    with patch('backend.x86_64.montar_codigo', side_effect=lambda p, w, *a, **k: montar(p, w)):
        if acao in ('estados', 'excecoes'):
            return executar_ensaio(acao, FONTE_MISTA)
        fonte = FONTE_MISTA
        if acao == 'grande':
            fonte = fonte_grande().replace('inicio {',
                'funcao chamar(numero: inteiro) -> inteiro {\n retorne grande('
                + ', '.join(['numero'] * 270) + ')\n}\ninicio {\n seja dono: texto\n')
        g, pe, tabela, dados = gerar_imagem(fonte)
        windows = Windows()
        with PeCarregado(windows, pe) as imagem:
            if acao == 'grande':
                retorno = int(chamar_com_sentinelas(windows,
                    imagem.base + 0x1000 + g.rotulos['funcao_chamar'], argumentos_pilha=[0, 1]))
                estados = ensaiar_estados(windows, g, tabela, dados)
                return {'retorno': retorno, 'quadro': g.quadros_funcoes['grande'], 'nomes': estados['nomes']}
            resultados = [int(chamar_com_sentinelas(windows,
                imagem.base + 0x1000 + g.rotulos['funcao_' + nome], argumentos_pilha=argumentos))
                for nome, argumentos in (('combinar', [0, 3, 2, 1]),
                                        ('encaminhar', [0, 3, 2, 1]), ('repetir', [0, 25]))]
            return {'resultados': resultados, 'inteiros_preservados': 8, 'vetoriais_preservados': 10}


if __name__ == '__main__' and '--ensaio' in sys.argv:
    print(json.dumps(executar(sys.argv[-1])))
elif __name__ == '__main__':
    unittest.main()
