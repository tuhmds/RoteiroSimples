"""Donos de texto: identidade no crescimento, descarte único e ABI Windows."""
import ctypes as ct
import json
import os
from pathlib import Path
import struct
import subprocess
import sys
import unittest

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))
from testes.test_abi_proprietarios_rs042a import WINDOWS_X64

FONTE = '''funcao texto_novo() -> texto {
    seja nome: texto = "RS"
    retorne mova(nome)
}
funcao criar() -> lista[texto] {
    seja nomes: lista[texto]
    para indice de 0 ate 3 {
        adicione(nomes, texto_novo())
    }
    retorne mova(nomes)
}
funcao ampliar(nomes: lista[texto]) -> lista[texto] {
    para indice de 4 ate 8 {
        adicione(nomes, texto_novo())
    }
    retorne mova(nomes)
}
funcao medir(nome: emprestimo[texto]) -> inteiro {
    retorne caracteres(nome)
}
funcao consumir(nomes: lista[texto]) -> inteiro {
    seja total = 0
    para indice de 0 ate tamanho(nomes) - 1 {
        total = total + medir(empreste(nomes[indice]))
    }
    retorne total
}
funcao exercitar() -> inteiro {
    seja origem: lista[texto]
    para indice de 0 ate 8 {
        adicione(origem, texto_novo())
    }
    origem[2] = texto_novo()
    seja escolhido = retire(origem, 3)
    remova_ultimo(origem)
    seja destino: lista[texto]
    adicione(destino, texto_novo())
    mova(destino, origem)
    limpe_lista(destino)
    adicione(destino, mova(escolhido))
    retorne tamanho(destino) + medir(empreste(destino[0]))
}
inicio {
    escreva(1)
}'''


@unittest.skipUnless(WINDOWS_X64, 'Ensaio exige Windows AMD64 real.')
class TestesAbiListaTextosRS042T(unittest.TestCase):
    def ensaio(self, acao):
        ambiente = os.environ.copy()
        ambiente['PYTHONIOENCODING'] = 'utf-8'
        r = subprocess.run([sys.executable, str(Path(__file__).resolve()), '--ensaio', acao],
                           cwd=RAIZ, env=ambiente, capture_output=True, encoding='utf-8', timeout=60)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        return json.loads(r.stdout)

    def test_identidade_descarte_unico_registradores_e_rsp(self):
        self.assertEqual(self.ensaio('propriedade'), {'alocacoes': 27, 'liberacoes': 27,
            'ponteiros_preservados': 4, 'resultado': 18, 'exercicio': 3,
            'inteiros_preservados': 8, 'vetoriais_preservados': 10})

    def test_desenrolamento_dos_auxiliares_de_lista_texto(self):
        r = self.ensaio('estados')
        for operacao in ('descartar_elemento', 'limpar', 'liberar', 'substituir', 'retirar'):
            self.assertIn('rs_colecao_' + operacao + '___rs_texto_utf8', r['nomes'])

    def test_excecoes_reais_em_donos_e_vistas_temporarias(self):
        r = self.ensaio('excecoes')
        self.assertEqual(r['quadros'], 2 * len(r['excecoes']))
        self.assertIn('rs_colecao_retirar___rs_texto_utf8', r['excecoes'])


def executar(acao):
    from testes.ensaio_windows_rs0415 import Windows, PeCarregado, gerar_imagem, chamar_com_sentinelas, executar_ensaio
    if acao != 'propriedade':
        return executar_ensaio(acao, FONTE)
    windows = Windows()
    g, pe, _, _ = gerar_imagem(FONTE)
    contadores = (ct.c_uint64 * 2)()
    rotinas = []

    def interceptar(endereco, liberar):
        codigo = b'\x48\xB8' + struct.pack('<Q', ct.addressof(contadores) + (8 if liberar else 0))
        codigo += b'\xFF\x00\x48\xB8' + struct.pack('<Q', endereco) + b'\xFF\xE0'
        ponteiro = windows.alocar(len(codigo))
        ct.memmove(ponteiro, codigo, len(codigo))
        windows.executar(ponteiro, len(codigo))
        rotinas.append(ponteiro)
        return ponteiro

    def examinar(ponteiro, quantidade):
        descritores = (ct.c_uint64 * (3 * quantidade)).from_address(ponteiro)
        donos = []
        for indice in range(quantidade):
            texto, tamanho, capacidade = descritores[3 * indice:3 * indice + 3]
            assert tamanho == 2 and capacidade >= 2
            assert ct.string_at(texto, tamanho) == b'RS'
            donos.append(texto)
        assert len(set(donos)) == quantidade
        return donos

    try:
        with PeCarregado(windows, pe) as imagem:
            for nome, liberar in (('VirtualAlloc', False), ('VirtualFree', True)):
                celula = ct.c_uint64.from_address(imagem.importacoes[nome])
                celula.value = interceptar(celula.value, liberar)

            def chamar(nome, argumentos):
                return int(chamar_com_sentinelas(windows,
                    imagem.base + 0x1000 + g.rotulos['funcao_' + nome], argumentos_pilha=argumentos))

            primeiro = (ct.c_uint64 * 3)()
            chamar('criar', [0, ct.addressof(primeiro) + 16])
            assert tuple(primeiro[:2]) == (4, 4)
            originais = examinar(primeiro[2], 4)
            assert tuple(contadores) == (5, 0)
            segundo = (ct.c_uint64 * 3)()
            chamar('ampliar', [0, ct.addressof(segundo) + 16, *primeiro])
            assert tuple(segundo[:2]) == (16, 9)
            ampliados = examinar(segundo[2], 9)
            assert ampliados[:4] == originais
            assert tuple(contadores) == (12, 2)
            resultado = chamar('consumir', [0, *segundo])
            assert resultado == 18 and tuple(contadores) == (12, 12)
            exercicio = chamar('exercitar', [0])
            assert exercicio == 3 and tuple(contadores) == (27, 27)
            return {'alocacoes': int(contadores[0]), 'liberacoes': int(contadores[1]),
                    'ponteiros_preservados': 4, 'resultado': resultado, 'exercicio': exercicio,
                    'inteiros_preservados': 8, 'vetoriais_preservados': 10}
    finally:
        for endereco in reversed(rotinas):
            windows.nucleo.VirtualFree(endereco, 0, 0x8000)


if __name__ == '__main__' and '--ensaio' in sys.argv:
    print(json.dumps(executar(sys.argv[-1])))
elif __name__ == '__main__':
    unittest.main()
