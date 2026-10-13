"""Donos agregados: identidade, descarte e desenrolamento no Windows real."""
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

# Sete palavras: código, texto e subregistro com bytes. Cabem na área
# de argumentos do hospedeiro que também verifica GPR, XMM e RSP.
FONTE = '''tipo Dados {
    conteudo: bytes
}
tipo Documento {
    codigo: inteiro
    titulo: texto
    dados: Dados
}
funcao criar() -> Documento {
    seja documento: Documento
    documento.codigo = 17
    copie(documento.titulo, "Ação")
    adicione_byte(documento.dados.conteudo, 0)
    adicione_byte(documento.dados.conteudo, 255)
    retorne mova(documento)
}
funcao transportar(documento: Documento) -> Documento {
    retorne mova(documento)
}
funcao encaminhar(documento: Documento) -> Documento {
    retorne transportar(mova(documento))
}
funcao consumir(documento: Documento) -> inteiro {
    retorne documento.codigo + documento.dados.conteudo[1] + caracteres(documento.titulo)
}
funcao exercitar() -> inteiro {
    para indice de 0 ate 2 {
        seja documento = encaminhar(criar())
        se indice == 0 {
            continue
        }
        se indice == 2 {
            pare
        }
    }
    retorne 0
}
inicio {
    escreva(1)
}'''


@unittest.skipUnless(WINDOWS_X64, 'Ensaio exige Windows AMD64 real.')
class TestesAbiRegistrosFuncoesRS042F(unittest.TestCase):
    def ensaio(self, acao):
        ambiente = os.environ.copy()
        ambiente['PYTHONIOENCODING'] = 'utf-8'
        resultado = subprocess.run([sys.executable, str(Path(__file__).resolve()), '--ensaio', acao],
                                  cwd=RAIZ, env=ambiente, capture_output=True, text=True,
                                  encoding='utf-8', errors='replace', timeout=40)
        self.assertEqual(resultado.returncode, 0, resultado.stdout + resultado.stderr)
        return json.loads(resultado.stdout)

    def test_preserva_dois_heaps_e_descarta_cada_dono_uma_vez(self):
        self.assertEqual(self.ensaio('propriedade'), {
            'ponteiros_preservados': 2, 'alocacoes': 8, 'liberacoes': 8,
            'resultado': 276, 'inteiros_preservados': 8, 'vetoriais_preservados': 10,
        })

    def test_desenrola_estados_de_funcoes_com_agregados(self):
        observado = self.ensaio('estados')
        for nome in ('funcao_criar', 'funcao_transportar', 'funcao_encaminhar', 'funcao_consumir', 'funcao_exercitar'):
            self.assertIn(nome, observado['nomes'])
        self.assertGreater(observado['estados'], 20)

    def test_excecoes_reais_em_funcoes_com_agregados(self):
        observado = self.ensaio('excecoes')
        self.assertEqual(observado['quadros'], 2 * len(observado['excecoes']))
        self.assertIn('funcao_encaminhar', observado['excecoes'])


def executar_propriedade():
    from testes.ensaio_windows_rs0415 import Windows, PeCarregado, gerar_imagem, chamar_com_sentinelas
    windows = Windows()
    gerador, pe, _, _ = gerar_imagem(FONTE)
    # Guarda também cada ponteiro liberado: contar apenas o total não
    # distinguiria um descarte duplicado de outro dono não descartado.
    contadores = (ct.c_uint64 * 18)()
    rotinas = []

    def interceptar(endereco_real, liberar):
        contador = ct.addressof(contadores) + (8 if liberar else 0)
        codigo = b'\x48\xB8' + struct.pack('<Q', contador)
        if liberar:
            # r10 = índice; endereço da entrada = contador + 8 + índice*8.
            codigo += b'\x4C\x8B\x10\x4A\x89\x4C\xD0\x08'
        codigo += b'\xFF\x00\x48\xB8' + struct.pack('<Q', endereco_real) + b'\xFF\xE0'
        endereco = windows.alocar(len(codigo))
        ct.memmove(endereco, codigo, len(codigo))
        windows.executar(endereco, len(codigo))
        rotinas.append(endereco)
        return endereco

    try:
        with PeCarregado(windows, pe) as imagem:
            for nome, liberar in (('VirtualAlloc', False), ('VirtualFree', True)):
                celula = ct.c_uint64.from_address(imagem.importacoes[nome])
                celula.value = interceptar(celula.value, liberar)

            def chamar(nome, argumentos):
                return chamar_com_sentinelas(windows, imagem.base + 0x1000 + gerador.rotulos['funcao_' + nome],
                                             argumentos_pilha=argumentos)

            primeiro = (ct.c_uint64 * 7)()
            chamar('criar', [0, ct.addressof(primeiro) + 48])
            # Memória cresce em ordem inversa aos campos do registro.
            capacidade_bytes, comprimento_bytes, bytes_ptr, capacidade_texto, comprimento_texto, texto_ptr, codigo = primeiro
            assert codigo == 17 and comprimento_bytes == 2 and comprimento_texto == 6
            assert bytes_ptr != texto_ptr and bytes_ptr and texto_ptr
            assert ct.string_at(bytes_ptr, comprimento_bytes) == b'\0\xff'
            assert ct.string_at(texto_ptr, comprimento_texto) == 'Ação'.encode('utf-8')
            assert tuple(contadores[:2]) == (2, 0)
            segundo = (ct.c_uint64 * 7)()
            chamar('encaminhar', [0, ct.addressof(segundo) + 48, *primeiro])
            assert tuple(segundo) == tuple(primeiro), 'Transferência alterou palavras do agregado.'
            assert tuple(contadores[:2]) == (2, 0), 'Transporte alocou ou descartou.'
            resultado = chamar('consumir', [0, *segundo])
            assert resultado == 276
            assert tuple(contadores[:2]) == (2, 2)
            assert set(contadores[2:4]) == {bytes_ptr, texto_ptr}
            assert chamar('exercitar', [0]) == 0
            assert tuple(contadores[:2]) == (8, 8), 'Temporários ou escopos perderam donos.'
            return {'ponteiros_preservados': 2, 'alocacoes': int(contadores[0]),
                    'liberacoes': int(contadores[1]), 'resultado': int(resultado),
                    'inteiros_preservados': 8, 'vetoriais_preservados': 10}
    finally:
        for endereco in reversed(rotinas):
            windows.nucleo.VirtualFree(endereco, 0, 0x8000)


if __name__ == '__main__':
    if len(sys.argv) == 3 and sys.argv[1] == '--ensaio':
        acao = sys.argv[2]
        if acao == 'propriedade':
            resultado = executar_propriedade()
        else:
            from testes.ensaio_windows_rs0415 import executar_ensaio
            resultado = executar_ensaio(acao, FONTE)
        print(json.dumps(resultado, ensure_ascii=False))
    else:
        unittest.main()
