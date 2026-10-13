"""Resultados proprietários: heaps, saídas por falha e ABI Windows real."""
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

FONTE = '''tipo Conteudo {
    dados: bytes
}
tipo Documento {
    titulo: texto
    conteudo: Conteudo
}
funcao criar() -> resultado[Documento] {
    seja documento: Documento
    copie(documento.titulo, "Ação")
    adicione_byte(documento.conteudo.dados, 0)
    adicione_byte(documento.conteudo.dados, 255)
    retorne sucesso[Documento](mova(documento))
}
funcao transportar(resposta: resultado[Documento]) -> resultado[Documento] {
    retorne mova(resposta)
}
funcao encaminhar(resposta: resultado[Documento]) -> resultado[Documento] {
    retorne transportar(mova(resposta))
}
funcao consumir(resposta: resultado[Documento]) -> inteiro {
    se resposta.valido == falso {
        retorne 0
    }
    retorne caracteres(resposta.valor.titulo) + resposta.valor.conteudo.dados[1]
}
funcao falhar() -> resultado[Documento] {
    retorne falha[Documento](0)
}
funcao falhar_depois() -> resultado[Documento] {
    seja local = criar()
    seja etapa = falha[texto](13)
    propague etapa
    retorne mova(local)
}
funcao reembalar() -> resultado[Documento] {
    seja resposta = criar()
    seja documento = mova(resposta.valor)
    retorne sucesso[Documento](mova(documento))
}
funcao exercitar() -> inteiro {
    para indice de 0 ate 2 {
        seja resposta = criar()
        se indice == 0 {
            continue
        }
        se indice == 2 {
            pare
        }
        seja documento = mova(resposta.valor)
        seja novo = sucesso[Documento](mova(documento))
    }
    retorne 0
}
inicio {
    escreva(1)
}'''


@unittest.skipUnless(WINDOWS_X64, 'Ensaio exige Windows AMD64 real.')
class TestesAbiResultadosProprietariosRS042G(unittest.TestCase):
    def ensaio(self, acao):
        ambiente = os.environ.copy()
        ambiente['PYTHONIOENCODING'] = 'utf-8'
        resultado = subprocess.run([sys.executable, str(Path(__file__).resolve()), '--ensaio', acao],
                                  cwd=RAIZ, env=ambiente, capture_output=True, text=True,
                                  encoding='utf-8', errors='replace', timeout=40)
        self.assertEqual(resultado.returncode, 0, resultado.stdout + resultado.stderr)
        return json.loads(resultado.stdout)

    def test_transporte_extracao_falha_e_escopos_preservam_donos_e_abi(self):
        self.assertEqual(self.ensaio('propriedade'), {
            'ponteiros_preservados': 2, 'alocacoes': 12, 'liberacoes': 12,
            'resultado': 259, 'falha_sem_alocacao': True, 'codigo_propagado': 13,
            'inteiros_preservados': 8, 'vetoriais_preservados': 10,
        })

    def test_desenrola_construtores_e_funcoes_com_resultados(self):
        observado = self.ensaio('estados')
        self.assertIn('funcao_falhar_depois', observado['nomes'])
        self.assertTrue(any('RsInternoGenerico_Sucesso_' in nome for nome in observado['nomes']))
        self.assertTrue(any('RsInternoGenerico_Falha_' in nome for nome in observado['nomes']))
        self.assertGreater(observado['estados'], 20)

    def test_excecoes_reais_em_construtores_e_funcoes_com_resultados(self):
        observado = self.ensaio('excecoes')
        self.assertEqual(observado['quadros'], 2 * len(observado['excecoes']))
        self.assertIn('funcao_falhar_depois', observado['excecoes'])
        self.assertTrue(any('RsInternoGenerico_Sucesso_' in nome for nome in observado['excecoes']))


def executar_propriedade():
    from testes.ensaio_windows_rs0415 import Windows, PeCarregado, gerar_imagem, chamar_com_sentinelas
    windows = Windows()
    gerador, pe, _, _ = gerar_imagem(FONTE)
    contadores = (ct.c_uint64 * 18)()
    rotinas = []

    def interceptar(endereco_real, liberar):
        contador = ct.addressof(contadores) + (8 if liberar else 0)
        codigo = b'\x48\xB8' + struct.pack('<Q', contador)
        if liberar:
            codigo += b'\x4C\x8B\x10\x4A\x89\x4C\xD0\x08'
        codigo += b'\xFF\x00\x48\xB8' + struct.pack('<Q', endereco_real) + b'\xFF\xE0'
        endereco = windows.alocar(len(codigo))
        ct.memmove(endereco, codigo, len(codigo))
        windows.executar(endereco, len(codigo))
        rotinas.append(endereco)
        return endereco

    def conferir_donos(resposta):
        codigo, cap_bytes, quantidade_bytes, bytes_ptr, cap_texto, quantidade_texto, texto_ptr, valido = resposta
        assert (codigo, valido, quantidade_bytes, quantidade_texto) == (0, 1, 2, 6)
        assert cap_bytes >= 2 and cap_texto >= 6
        assert bytes_ptr != texto_ptr and bytes_ptr and texto_ptr
        assert ct.string_at(bytes_ptr, 2) == b'\0\xff'
        assert ct.string_at(texto_ptr, 6) == 'Ação'.encode('utf-8')
        return {bytes_ptr, texto_ptr}

    try:
        with PeCarregado(windows, pe) as imagem:
            for nome, liberar in (('VirtualAlloc', False), ('VirtualFree', True)):
                celula = ct.c_uint64.from_address(imagem.importacoes[nome])
                celula.value = interceptar(celula.value, liberar)

            def chamar(nome, argumentos):
                return chamar_com_sentinelas(windows, imagem.base + 0x1000 + gerador.rotulos['funcao_' + nome],
                                             argumentos_pilha=argumentos)

            primeiro = (ct.c_uint64 * 8)()
            chamar('criar', [0, ct.addressof(primeiro) + 56])
            ponteiros = conferir_donos(primeiro)
            assert tuple(contadores[:2]) == (2, 0)
            segundo = (ct.c_uint64 * 8)()
            chamar('encaminhar', [0, ct.addressof(segundo) + 56, *primeiro])
            assert tuple(segundo) == tuple(primeiro)
            assert tuple(contadores[:2]) == (2, 0), 'Resultado copiou ou descartou conteúdo durante transporte.'
            resultado = chamar('consumir', [0, *segundo])
            assert resultado == 259 and tuple(contadores[:2]) == (2, 2)
            assert set(contadores[2:4]) == ponteiros

            falha = (ct.c_uint64 * 8)(*([0xABABABABABABABAB] * 8))
            chamar('falhar', [0, ct.addressof(falha) + 56])
            assert tuple(falha) == (2, 0, 0, 0, 0, 0, 0, 0), 'Falha deixou palavras não inicializadas.'
            assert tuple(contadores[:2]) == (2, 2), 'Construtor de falha alocou conteúdo.'
            chamar('encaminhar', [0, ct.addressof(segundo) + 56, *falha])
            assert tuple(segundo) == tuple(falha)
            assert chamar('consumir', [0, *segundo]) == 0
            assert tuple(contadores[:2]) == (2, 2)

            chamar('falhar_depois', [0, ct.addressof(falha) + 56])
            assert tuple(falha) == (13, 0, 0, 0, 0, 0, 0, 0)
            assert tuple(contadores[:2]) == (4, 4), 'Propagação perdeu os donos locais.'
            assert len(set(contadores[4:6])) == 2 and all(contadores[4:6])

            chamar('reembalar', [0, ct.addressof(segundo) + 56])
            ponteiros = conferir_donos(segundo)
            assert tuple(contadores[:2]) == (6, 4)
            assert chamar('consumir', [0, *segundo]) == 259
            assert tuple(contadores[:2]) == (6, 6)
            assert set(contadores[6:8]) == ponteiros
            assert chamar('exercitar', [0]) == 0
            assert tuple(contadores[:2]) == (12, 12)
            return {'ponteiros_preservados': 2, 'alocacoes': int(contadores[0]),
                    'liberacoes': int(contadores[1]), 'resultado': int(resultado),
                    'falha_sem_alocacao': True, 'codigo_propagado': int(falha[0]),
                    'inteiros_preservados': 8, 'vetoriais_preservados': 10}
    finally:
        for endereco in reversed(rotinas):
            windows.nucleo.VirtualFree(endereco, 0, 0x8000)


if __name__ == '__main__':
    if len(sys.argv) == 3 and sys.argv[1] == '--ensaio':
        if sys.argv[2] == 'propriedade':
            resultado = executar_propriedade()
        else:
            from testes.ensaio_windows_rs0415 import executar_ensaio
            resultado = executar_ensaio(sys.argv[2], FONTE)
        print(json.dumps(resultado, ensure_ascii=False))
    else:
        unittest.main()
