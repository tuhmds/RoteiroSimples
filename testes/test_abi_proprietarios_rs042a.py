"""RS 0.42A.1 — identidade, descarte e ABI reais de proprietários no Windows.

O hospedeiro de teste carrega o PE emitido em um subprocesso e chama suas
funções reais. Sentinelas cobrem oito registradores inteiros, dez vetoriais
não voláteis e RSP. Contadores nativos observam alocação/desalocação pela IAT.
"""
import ctypes as ct
import json
import os
from pathlib import Path
import platform
import struct
import subprocess
import sys
import unittest

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

FONTE = """funcao criar() -> lista[inteiro] {
    seja dados: lista[inteiro]
    adicione(dados, 17)
    adicione(dados, 23)
    retorne mova(dados)
}
funcao transportar(dados: lista[inteiro]) -> lista[inteiro] {
    retorne mova(dados)
}
funcao encaminhar(dados: lista[inteiro]) -> lista[inteiro] {
    retorne transportar(mova(dados))
}
funcao consumir(dados: lista[inteiro]) -> inteiro {
    retorne dados[0] + tamanho(dados)
}
inicio {
    escreva(1)
}"""

WINDOWS_X64 = (sys.platform == 'win32' and ct.sizeof(ct.c_void_p) == 8
               and platform.machine().lower() in ('amd64', 'x86_64'))


@unittest.skipUnless(WINDOWS_X64, 'Ensaio exige Windows AMD64 real.')
class TestesAbiProprietariosRS042A(unittest.TestCase):
    def test_transfere_heap_sem_copia_e_descarta_uma_vez_preservando_abi(self):
        ambiente = os.environ.copy()
        ambiente['PYTHONIOENCODING'] = 'utf-8'
        resultado = subprocess.run(
            [sys.executable, str(Path(__file__).resolve()), '--ensaio'],
            cwd=RAIZ, env=ambiente, capture_output=True, text=True,
            encoding='utf-8', errors='replace', timeout=30)
        self.assertEqual(resultado.returncode, 0,
                         resultado.stdout + '\n' + resultado.stderr)
        observado = json.loads(resultado.stdout)
        self.assertEqual(observado, {
            'alocacoes': 1, 'liberacoes': 1, 'resultado_consumo': 19,
            'mesmo_ponteiro': True, 'conteudo': [17, 23],
            'quantidade': 2, 'capacidade': 4,
            'inteiros_preservados': 8, 'vetoriais_preservados': 10,
        })


def executar_ensaio(fonte=FONTE, conteudo_esperado=None, capacidade_esperada=4,
                    resultado_esperado=19, elemento_bytes=False, descartes_escopos=0):
    from testes.ensaio_windows_rs0415 import (
        Windows, PeCarregado, gerar_imagem, chamar_com_sentinelas,
    )
    windows = Windows()
    g, pe, _, _ = gerar_imagem(fonte)
    if conteudo_esperado is None:
        conteudo_esperado = [17, 23]
    quantidade_esperada = len(conteudo_esperado)
    contadores = (ct.c_uint64 * 3)()  # alocações, liberações, último ponteiro liberado
    rotinas = []

    def contar_e_encaminhar(endereco_real, liberar):
        contador = ct.addressof(contadores) + (8 if liberar else 0)
        # Rotina folha: só altera RAX e encaminha os mesmos argumentos
        # ao sistema. Nenhum alocador ou desalocador alternativo é usado.
        codigo = b'\x48\xB8' + struct.pack('<Q', contador) + b'\xFF\x00'
        if liberar:
            codigo += b'\x48\x89\x48\x08'
        codigo += b'\x48\xB8' + struct.pack('<Q', endereco_real) + b'\xFF\xE0'
        endereco = windows.alocar(len(codigo))
        ct.memmove(endereco, codigo, len(codigo))
        windows.executar(endereco, len(codigo))
        rotinas.append(endereco)
        return endereco

    try:
        with PeCarregado(windows, pe) as imagem:
            for nome, liberar in (('VirtualAlloc', False), ('VirtualFree', True)):
                celula = ct.c_uint64.from_address(imagem.importacoes[nome])
                celula.value = contar_e_encaminhar(celula.value, liberar)
            primeiro = (ct.c_uint64 * 3)()
            chamar_com_sentinelas(windows, imagem.base + 0x1000 + g.rotulos['funcao_criar'],
                                 argumentos_pilha=[0, ct.addressof(primeiro) + 16])
            capacidade, quantidade, ponteiro = primeiro
            assert (capacidade, quantidade) == (capacidade_esperada, quantidade_esperada)
            assert ponteiro and tuple(contadores[:2]) == (1, 0)
            unidade = ct.c_ubyte if elemento_bytes else ct.c_uint64
            conteudo = list((unidade * quantidade_esperada).from_address(ponteiro))
            assert conteudo == conteudo_esperado
            segundo = (ct.c_uint64 * 3)()
            chamar_com_sentinelas(
                windows, imagem.base + 0x1000 + g.rotulos['funcao_encaminhar'],
                argumentos_pilha=[0, ct.addressof(segundo) + 16,
                                  capacidade, quantidade, ponteiro])
            assert tuple(segundo) == tuple(primeiro)
            assert tuple(contadores[:2]) == (1, 0), 'Transferência alocou ou descartou o heap.'
            resultado = chamar_com_sentinelas(
                windows, imagem.base + 0x1000 + g.rotulos['funcao_consumir'],
                argumentos_pilha=[0, capacidade, quantidade, ponteiro])
            assert resultado == resultado_esperado
            assert tuple(contadores) == (1, 1, ponteiro), 'Descarte incorreto do parâmetro proprietário.'
            if descartes_escopos:
                retorno = chamar_com_sentinelas(windows, imagem.base + 0x1000 + g.rotulos['funcao_exercitar'], argumentos_pilha=[0])
                assert retorno == 0
                assert tuple(contadores[:2]) == (1 + descartes_escopos, 1 + descartes_escopos), 'Escopos deixaram donos sem descarte ou descartaram duas vezes.'
            return {
                'alocacoes': int(contadores[0]), 'liberacoes': int(contadores[1]),
                'resultado_consumo': int(resultado), 'mesmo_ponteiro': segundo[2] == ponteiro,
                'conteudo': conteudo, 'quantidade': int(quantidade),
                'capacidade': int(capacidade), 'inteiros_preservados': 8,
                'vetoriais_preservados': 10,
            }
    finally:
        for endereco in reversed(rotinas):
            windows.nucleo.VirtualFree(endereco, 0, 0x8000)


if __name__ == '__main__':
    if sys.argv[1:] == ['--ensaio']:
        print(json.dumps(executar_ensaio(), ensure_ascii=False))
    else:
        unittest.main()
