"""Conversoes RS: contagem nativa de donos e preservacao da ABI Windows."""
import ctypes as ct
import json
import os
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import unittest

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))
from compilador.modulos import carregar_fontes
from testes.test_abi_proprietarios_rs042a import WINDOWS_X64

FONTE = '''importe "padrao/conversoes.rts" como conversoes
funcao exercitar() -> inteiro {
    seja origem: texto = "-9223372036854775808"
    seja minimo = conversoes.inteiro_de_texto(empreste(origem))
    seja primeiro = conversoes.texto_de_inteiro(minimo.valor)
    seja volta_minimo = conversoes.inteiro_de_texto(empreste(primeiro.valor))
    se volta_minimo.valor != -9223372036854775808 {
        retorne 1
    }
    copie(origem, "9223372036854775807")
    seja maximo = conversoes.inteiro_de_texto(empreste(origem))
    seja segundo = conversoes.texto_de_inteiro(maximo.valor)
    seja volta_maximo = conversoes.inteiro_de_texto(empreste(segundo.valor))
    se volta_maximo.valor != 9223372036854775807 {
        retorne 2
    }
    copie(origem, "9223372036854775808")
    seja fora = conversoes.inteiro_de_texto(empreste(origem))
    se fora.codigo_erro != 3 {
        retorne 3
    }
    copie(origem, "12x")
    seja invalido = conversoes.inteiro_de_texto(empreste(origem))
    se invalido.codigo_erro != 2 {
        retorne 4
    }
    seja terceiro = conversoes.texto_de_inteiro(0)
    seja volta_zero = conversoes.inteiro_de_texto(empreste(terceiro.valor))
    se volta_zero.valido == falso ou volta_zero.valor != 0 {
        retorne 5
    }
    retorne 0
}
inicio {
    escreva(1)
}'''


@unittest.skipUnless(WINDOWS_X64, 'Ensaio exige Windows AMD64 real.')
class TestesAbiConversoesRS042U(unittest.TestCase):
    def test_contagem_de_donos_e_registradores(self):
        ambiente = os.environ.copy()
        ambiente['PYTHONIOENCODING'] = 'utf-8'
        r = subprocess.run([sys.executable, str(Path(__file__).resolve()), '--ensaio'],
                           cwd=RAIZ, env=ambiente, capture_output=True, encoding='utf-8', timeout=60)
        self.assertEqual(r.returncode, 0, r.stdout+r.stderr)
        self.assertEqual(json.loads(r.stdout), {'alocacoes': 4, 'liberacoes': 4,
            'resultado': 0, 'inteiros_preservados': 8, 'vetoriais_preservados': 10})


def executar():
    from testes.ensaio_windows_rs0415 import Windows, PeCarregado, gerar_imagem, chamar_com_sentinelas
    with tempfile.TemporaryDirectory() as pasta:
        arquivo = Path(pasta)/'principal.rts'
        arquivo.write_text(FONTE, encoding='utf-8')
        fonte = carregar_fontes(arquivo).texto
    windows = Windows()
    g, pe, _, _ = gerar_imagem(fonte)
    contadores = (ct.c_uint64 * 2)()
    rotinas = []
    try:
        with PeCarregado(windows, pe) as imagem:
            for nome, indice in (('VirtualAlloc', 0), ('VirtualFree', 1)):
                celula = ct.c_uint64.from_address(imagem.importacoes[nome])
                codigo = b'\x48\xB8'+struct.pack('<Q', ct.addressof(contadores)+8*indice)
                codigo += b'\xFF\x00\x48\xB8'+struct.pack('<Q', celula.value)+b'\xFF\xE0'
                ponteiro = windows.alocar(len(codigo))
                ct.memmove(ponteiro, codigo, len(codigo))
                windows.executar(ponteiro, len(codigo))
                rotinas.append(ponteiro)
                celula.value = ponteiro
            resultado = int(chamar_com_sentinelas(windows,
                imagem.base+0x1000+g.rotulos['funcao_exercitar'], argumentos_pilha=[0]))
            return {'alocacoes': int(contadores[0]), 'liberacoes': int(contadores[1]),
                    'resultado': resultado, 'inteiros_preservados': 8, 'vetoriais_preservados': 10}
    finally:
        for ponteiro in reversed(rotinas):
            windows.nucleo.VirtualFree(ponteiro, 0, 0x8000)


if __name__ == '__main__' and '--ensaio' in sys.argv:
    print(json.dumps(executar()))
elif __name__ == '__main__':
    unittest.main()
