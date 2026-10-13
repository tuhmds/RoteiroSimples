"""Leitura sem alocação, identidade, ABI e desenrolamento no Windows real."""
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
from testes.test_emprestimos_registros_rs042i import COMUM

FONTE = COMUM + '''funcao montar() -> lista[Documento] {
    seja documentos: lista[Documento]
    para numero de 0 ate 8 {
        adicione(documentos, criar(numero))
    }
    retorne mova(documentos)
}
funcao ler(documentos: emprestimo[lista[Documento]]) -> inteiro {
    seja soma = 0
    para indice de 0 ate tamanho(documentos) - 1 {
        soma = soma + consultar(empreste(documentos[indice]))
    }
    retorne soma
}
funcao encaminhar(documento: emprestimo[Documento]) -> inteiro {
    retorne consultar(documento)
}
funcao consumir(documentos: lista[Documento]) -> inteiro {
    retorne tamanho(documentos)
}
inicio {
    escreva(1)
}'''


@unittest.skipUnless(WINDOWS_X64, 'Ensaio exige Windows AMD64 real.')
class TestesAbiEmprestimosRegistrosRS042I(unittest.TestCase):
    def ensaio(self, acao):
        ambiente = os.environ.copy()
        ambiente['PYTHONIOENCODING'] = 'utf-8'
        resultado = subprocess.run([sys.executable, str(Path(__file__).resolve()), '--ensaio', acao],
            cwd=RAIZ, env=ambiente, capture_output=True, text=True, encoding='utf-8',
            errors='replace', timeout=40)
        self.assertEqual(resultado.returncode, 0, resultado.stdout + resultado.stderr)
        return json.loads(resultado.stdout)

    def test_leituras_preservam_memoria_sem_alocar_ou_liberar(self):
        self.assertEqual(self.ensaio('leitura'), {
            'consultas': 100, 'resultado': 144, 'ponteiros_preservados': 27,
            'alocacoes_na_leitura': 0, 'liberacoes_na_leitura': 0,
            'alocacoes_totais': 30, 'liberacoes_totais': 30,
            'inteiros_preservados': 8, 'vetoriais_preservados': 10,
        })

    def test_estados_de_desenrolamento_das_funcoes_com_vistas(self):
        observado = self.ensaio('estados')
        for nome in ('funcao_consultar', 'funcao_ler', 'funcao_encaminhar'):
            self.assertIn(nome, observado['nomes'])

    def test_excecoes_reais_em_funcoes_com_vistas(self):
        observado = self.ensaio('excecoes')
        self.assertEqual(observado['quadros'], 2 * len(observado['excecoes']))
        self.assertIn('funcao_ler', observado['excecoes'])


def executar_leitura():
    from testes.ensaio_windows_rs0415 import Windows, PeCarregado, gerar_imagem, chamar_com_sentinelas
    windows = Windows()
    gerador, pe, _, _ = gerar_imagem(FONTE)
    contadores = (ct.c_uint64 * 34)()
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
    try:
        with PeCarregado(windows, pe) as imagem:
            for nome, liberar in (('VirtualAlloc', False), ('VirtualFree', True)):
                celula = ct.c_uint64.from_address(imagem.importacoes[nome])
                celula.value = interceptar(celula.value, liberar)
            def chamar(nome, argumentos):
                return chamar_com_sentinelas(windows,
                    imagem.base + 0x1000 + gerador.rotulos['funcao_' + nome],
                    argumentos_pilha=argumentos)
            descritor = (ct.c_uint64 * 3)()
            chamar('montar', [0, ct.addressof(descritor) + 16])
            assert tuple(descritor[:2]) == (16, 9)
            assert tuple(contadores[:2]) == (30, 2)
            palavras = (ct.c_uint64 * 90).from_address(descritor[2])
            antes = bytes(palavras)
            ponteiros = {palavras[i*10 + campo] for i in range(9) for campo in (1, 4, 7)}
            assert len(ponteiros) == 27
            conteudos = {ponteiro: ct.string_at(ponteiro, palavras[i*10 + campo + 1])
                for i in range(9) for campo in (1, 4, 7)
                for ponteiro in (palavras[i*10 + campo],)}
            chamadas = 100
            # Negar efetivamente toda alocação durante as consultas: uma
            # tentativa inesperada encerra o subprocesso pelo erro nativo.
            real_alocador = ct.c_uint64.from_address(imagem.importacoes['VirtualAlloc']).value
            @ct.WINFUNCTYPE(ct.c_void_p, ct.c_void_p, ct.c_size_t, ct.c_uint32, ct.c_uint32)
            def negar_alocacao(endereco, tamanho, flags, protecao):
                contadores[0] += 1
                return None
            ct.c_uint64.from_address(imagem.importacoes['VirtualAlloc']).value = ct.cast(negar_alocacao, ct.c_void_p).value
            for _ in range(chamadas):
                assert chamar('ler', [0, ct.addressof(descritor) + 16]) == 144
            # Vista externa em disposição de parâmetro: três ponteiros de
            # descritores decrescentes e um código, sem possuir os buffers.
            registro = (ct.c_uint64 * 10)(*reversed(palavras[:10]))
            codigo = registro[9]
            titulo = ct.addressof(registro) + 64
            conteudo = ct.addressof(registro) + 40
            marcas = ct.addressof(registro) + 16
            assert chamar('encaminhar', [0, marcas, conteudo, titulo, codigo]) == 8
            assert tuple(contadores[:2]) == (30, 2)
            assert bytes(palavras) == antes and tuple(descritor[:2]) == (16, 9)
            for ponteiro, conteudo_original in conteudos.items():
                assert ct.string_at(ponteiro, len(conteudo_original)) == conteudo_original
            ct.c_uint64.from_address(imagem.importacoes['VirtualAlloc']).value = real_alocador
            vivos = ponteiros | {int(descritor[2])}
            assert chamar('consumir', [0, *descritor]) == 9
            assert tuple(contadores[:2]) == (30, 30)
            assert set(contadores[4:32]) == vivos and len(vivos) == 28
            return {'consultas': chamadas, 'resultado': 144,
                'ponteiros_preservados': len(ponteiros), 'alocacoes_na_leitura': 0,
                'liberacoes_na_leitura': 0, 'alocacoes_totais': 30,
                'liberacoes_totais': 30, 'inteiros_preservados': 8, 'vetoriais_preservados': 10}
    finally:
        for endereco in reversed(rotinas):
            windows.nucleo.VirtualFree(endereco, 0, 0x8000)


if __name__ == '__main__' and '--ensaio' in sys.argv:
    acao = sys.argv[-1]
    if acao == 'leitura':
        observado = executar_leitura()
    else:
        from testes.ensaio_windows_rs0415 import executar_ensaio
        observado = executar_ensaio(acao, FONTE)
    print(json.dumps(observado))
elif __name__ == '__main__':
    unittest.main()
