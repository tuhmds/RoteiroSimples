"""Balanço real de cada dono em sequências geradas de operações no Windows."""
import ctypes as ct
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))
from testes.test_abi_proprietarios_rs042a import WINDOWS_X64


@unittest.skipUnless(WINDOWS_X64, 'Ensaio exige Windows AMD64 real.')
class TestesAbiCampanhaRS042J(unittest.TestCase):
    def test_sequencias_geradas_liberam_cada_alocacao_sem_duplicar_donos(self):
        ambiente = os.environ.copy()
        ambiente['PYTHONIOENCODING'] = 'utf-8'
        resultado = subprocess.run([sys.executable, str(Path(__file__).resolve()), '--ensaio'],
            cwd=RAIZ, env=ambiente, capture_output=True, encoding='utf-8', errors='replace', timeout=40)
        self.assertEqual(resultado.returncode, 0, resultado.stdout + resultado.stderr)
        observado = json.loads(resultado.stdout)
        self.assertEqual(len(observado), 3)
        for caso in observado:
            self.assertGreater(caso['alocacoes'], 27)
            self.assertEqual(caso['alocacoes'], caso['liberacoes'])
            self.assertEqual((caso['ativos'], caso['erros']), (0, []))
            self.assertEqual(caso['passos'], 72)


def executar():
    from verificacao.casos_gerados import gerar_caso, montar_caso
    from testes.ensaio_windows_rs0415 import Windows, PeCarregado, gerar_imagem, chamar_com_sentinelas
    resultados = []
    for semente in (42010, 42011, 42012):
        # Arquivos são verificados na campanha portável. Aqui isolamos o
        # heap e descartamos operações de arquivo, sem escrever no repositório.
        original = gerar_caso(semente, 80)
        operacoes = tuple(op for op in original.operacoes if op.acao != 'arquivo')[:72]
        while len(operacoes) < 72:
            operacoes += (original.operacoes[0],)
        caso = montar_caso(semente, operacoes)
        fonte = caso.fonte.replace('inicio {', 'funcao exercitar() -> inteiro {', 1)
        fim = fonte.rfind('}')
        fonte = fonte[:fim] + 'retorne 0\n}\ninicio {\n escreva(1)\n}\n'
        windows = Windows()
        gerador, pe, _, _ = gerar_imagem(fonte)
        ativos, erros = set(), []
        contagem = [0, 0]
        with PeCarregado(windows, pe) as imagem:
            alocar = ct.c_uint64.from_address(imagem.importacoes['VirtualAlloc'])
            liberar = ct.c_uint64.from_address(imagem.importacoes['VirtualFree'])
            gravar = ct.c_uint64.from_address(imagem.importacoes['WriteFile'])
            real_alocar = ct.WINFUNCTYPE(ct.c_void_p, ct.c_void_p, ct.c_size_t, ct.c_uint32, ct.c_uint32)(alocar.value)
            real_liberar = ct.WINFUNCTYPE(ct.c_int, ct.c_void_p, ct.c_size_t, ct.c_uint32)(liberar.value)
            @ct.WINFUNCTYPE(ct.c_void_p, ct.c_void_p, ct.c_size_t, ct.c_uint32, ct.c_uint32)
            def rastrear_alocacao(endereco, tamanho, flags, protecao):
                ponteiro = real_alocar(endereco, tamanho, flags, protecao)
                if ponteiro:
                    if ponteiro in ativos:
                        erros.append('Dono já ativo na alocação.')
                    ativos.add(ponteiro)
                    contagem[0] += 1
                return ponteiro
            @ct.WINFUNCTYPE(ct.c_int, ct.c_void_p, ct.c_size_t, ct.c_uint32)
            def rastrear_liberacao(endereco, tamanho, flags):
                if endereco not in ativos:
                    erros.append('Liberação sem alocação ativa ou duplicada.')
                retorno = real_liberar(endereco, tamanho, flags)
                if retorno:
                    ativos.discard(endereco)
                    contagem[1] += 1
                else:
                    erros.append('Sistema rejeitou a liberação.')
                return retorno
            # Confirmar escrita completa sem despejar os milhares de valores
            # de diagnóstico. O conteúdo é conferido pelos testes portáveis.
            codigo = bytes.fromhex('45 89 01 B8 01 00 00 00 C3')
            endereco = windows.alocar(len(codigo))
            try:
                ct.memmove(endereco, codigo, len(codigo))
                windows.executar(endereco, len(codigo))
                alocar.value = ct.cast(rastrear_alocacao, ct.c_void_p).value
                liberar.value = ct.cast(rastrear_liberacao, ct.c_void_p).value
                gravar.value = endereco
                retorno = chamar_com_sentinelas(windows,
                    imagem.base + 0x1000 + gerador.rotulos['funcao_exercitar'], argumentos_pilha=[0])
                assert retorno == 0
                resultados.append({'semente': semente, 'passos': len(operacoes),
                    'alocacoes': contagem[0], 'liberacoes': contagem[1], 'ativos': len(ativos), 'erros': erros})
            finally:
                windows.nucleo.VirtualFree(endereco, 0, 0x8000)
    return resultados


if __name__ == '__main__' and '--ensaio' in sys.argv:
    print(json.dumps(executar()))
elif __name__ == '__main__':
    unittest.main()
