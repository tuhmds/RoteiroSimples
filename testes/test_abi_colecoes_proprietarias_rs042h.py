"""Crescimento, identidade, descarte tipado e ABI das coleções no Windows."""
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

FONTE = '''tipo Documento {
    titulo: texto
    dados: bytes
}
tipo Catalogo {
    documentos: lista[Documento]
}
tipo Remocao {
    documentos: lista[Documento]
    escolhido: Documento
}
funcao criar_documento(numero: inteiro) -> Documento {
    seja documento: Documento
    copie(documento.titulo, "RS")
    adicione_byte(documento.dados, numero)
    retorne mova(documento)
}
funcao criar() -> lista[Documento] {
    seja documentos: lista[Documento]
    para numero de 0 ate 3 {
        adicione(documentos, criar_documento(numero))
    }
    retorne mova(documentos)
}
funcao ampliar(documentos: lista[Documento]) -> lista[Documento] {
    para numero de 4 ate 8 {
        adicione(documentos, criar_documento(numero))
    }
    retorne mova(documentos)
}
funcao efetuar(documentos: lista[Documento]) -> Remocao {
    documentos[2] = criar_documento(42)
    remova_ultimo(documentos)
    seja escolhido = retire(documentos, 3)
    seja remocao: Remocao
    mova(remocao.documentos, documentos)
    mova(remocao.escolhido, escolhido)
    retorne mova(remocao)
}
funcao consumir(remocao: Remocao) -> inteiro {
    retorne tamanho(remocao.documentos) + remocao.escolhido.dados[0]
}
funcao exercitar() -> inteiro {
    para numero de 0 ate 1 {
        seja origem: lista[Documento]
        seja destino: lista[Documento]
        adicione(origem, criar_documento(1))
        adicione(destino, criar_documento(2))
        mova(destino, origem)
        limpe_lista(destino)
        se numero == 0 {
            continue
        }
        pare
    }
    retorne 0
}
funcao aninhados() -> inteiro {
    seja catalogo: Catalogo
    para numero de 0 ate 3 {
        adicione(catalogo.documentos, criar_documento(numero))
    }
    seja catalogos: lista[Catalogo]
    adicione(catalogos, mova(catalogo))
    retorne tamanho(catalogos)
}
inicio {
    escreva(1)
}'''


@unittest.skipUnless(WINDOWS_X64, 'Ensaio exige Windows AMD64 real.')
class TestesAbiColecoesProprietariasRS042H(unittest.TestCase):
    def ensaio(self, acao):
        ambiente = os.environ.copy()
        ambiente['PYTHONIOENCODING'] = 'utf-8'
        resultado = subprocess.run([sys.executable, str(Path(__file__).resolve()), '--ensaio', acao],
                                  cwd=RAIZ, env=ambiente, capture_output=True, text=True,
                                  encoding='utf-8', errors='replace', timeout=40)
        self.assertEqual(resultado.returncode, 0, resultado.stdout + resultado.stderr)
        return json.loads(resultado.stdout)

    def test_crescimento_preserva_heaps_e_cada_dono_e_descartado_uma_vez(self):
        self.assertEqual(self.ensaio('propriedade'), {
            'alocacoes': 45, 'liberacoes': 45, 'ponteiros_preservados_no_crescimento': 8,
            'liberacoes_finais_verificadas': 17, 'resultado': 10,
            'inteiros_preservados': 8, 'vetoriais_preservados': 10,
        })

    def test_desenrola_novos_auxiliares_por_tipo(self):
        observado = self.ensaio('estados')
        for tipo in ('Documento', 'Catalogo'):
            for operacao in ('descartar_elemento', 'limpar', 'liberar', 'substituir', 'retirar'):
                self.assertIn(f'rs_colecao_{operacao}_{tipo}', observado['nomes'])

    def test_excecoes_reais_nos_novos_auxiliares(self):
        observado = self.ensaio('excecoes')
        self.assertEqual(observado['quadros'], 2 * len(observado['excecoes']))
        self.assertIn('rs_colecao_retirar_Documento', observado['excecoes'])
        self.assertIn('rs_colecao_liberar_Catalogo', observado['excecoes'])

    def test_falha_no_crescimento_nao_libera_ou_corrompe_armazenamento_antigo(self):
        ambiente = os.environ.copy()
        ambiente['PYTHONIOENCODING'] = 'utf-8'
        resultado = subprocess.run([sys.executable, str(Path(__file__).resolve()), '--ensaio', 'falha'],
                                  cwd=RAIZ, env=ambiente, capture_output=True, text=True,
                                  encoding='utf-8', errors='replace', timeout=40)
        self.assertEqual(resultado.returncode, 1, resultado.stdout + resultado.stderr)
        self.assertIn('reservar', resultado.stdout + resultado.stderr)
        observado = json.loads(resultado.stdout.split('ESTADO:')[-1])
        self.assertEqual(observado, {'tentativas': 12, 'liberacoes': 0, 'codigos': [0, 1, 2, 3]})


def executar_propriedade():
    from testes.ensaio_windows_rs0415 import Windows, PeCarregado, gerar_imagem, chamar_com_sentinelas
    windows = Windows()
    gerador, pe, _, _ = gerar_imagem(FONTE)
    contadores = (ct.c_uint64 * 258)()
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

    def examinar(ponteiro, quantidade):
        palavras = (ct.c_uint64 * (6 * quantidade)).from_address(ponteiro)
        codigos, donos = [], []
        for indice in range(quantidade):
            texto, ntexto, ctexto, dados, ndados, cdados = palavras[indice*6:indice*6+6]
            assert ntexto == 2 and ctexto >= 2 and ndados == 1 and cdados >= 1
            assert ct.string_at(texto, ntexto) == b'RS'
            codigos.append(ct.c_ubyte.from_address(dados).value)
            donos.append({texto, dados})
        assert len(set().union(*donos)) == quantidade * 2
        return codigos, donos

    try:
        with PeCarregado(windows, pe) as imagem:
            for nome, liberar in (('VirtualAlloc', False), ('VirtualFree', True)):
                celula = ct.c_uint64.from_address(imagem.importacoes[nome])
                celula.value = interceptar(celula.value, liberar)

            def chamar(nome, argumentos):
                return chamar_com_sentinelas(windows, imagem.base + 0x1000 + gerador.rotulos['funcao_' + nome],
                                             argumentos_pilha=argumentos)

            primeiro = (ct.c_uint64 * 3)()
            chamar('criar', [0, ct.addressof(primeiro) + 16])
            assert tuple(primeiro[:2]) == (4, 4)
            codigos, originais = examinar(primeiro[2], 4)
            assert codigos == [0, 1, 2, 3] and tuple(contadores[:2]) == (9, 0)
            segundo = (ct.c_uint64 * 3)()
            chamar('ampliar', [0, ct.addressof(segundo) + 16, *primeiro])
            assert tuple(segundo[:2]) == (16, 9) and segundo[2] != primeiro[2]
            codigos, ampliados = examinar(segundo[2], 9)
            assert codigos == list(range(9)) and ampliados[:4] == originais
            assert tuple(contadores[:2]) == (21, 2)
            assert not set(contadores[2:4]) & set().union(*originais)

            removido = (ct.c_uint64 * 9)()
            chamar('efetuar', [0, ct.addressof(removido) + 64, *segundo])
            cap_dados, ndados, dados, cap_texto, ntexto, texto, capacidade, quantidade, ponteiro = removido
            assert quantidade == 7 and capacidade == 16 and ponteiro == segundo[2]
            assert {texto, dados} == originais[3] and ct.c_ubyte.from_address(dados).value == 3
            codigos, restantes = examinar(ponteiro, 7)
            assert codigos == [0, 1, 42, 4, 5, 6, 7]
            assert tuple(contadores[:2]) == (23, 6)
            assert set(contadores[4:6]) == originais[2]
            assert set(contadores[6:8]) == ampliados[8]
            ativos = set().union(*restantes) | {texto, dados, ponteiro}
            resultado = chamar('consumir', [0, *removido])
            assert resultado == 10 and tuple(contadores[:2]) == (23, 23)
            assert set(contadores[8:25]) == ativos and len(ativos) == 17
            assert chamar('exercitar', [0]) == 0
            assert tuple(contadores[:2]) == (35, 35)
            assert chamar('aninhados', [0]) == 1
            assert tuple(contadores[:2]) == (45, 45)
            return {'alocacoes': int(contadores[0]), 'liberacoes': int(contadores[1]),
                    'ponteiros_preservados_no_crescimento': 8, 'liberacoes_finais_verificadas': 17,
                    'resultado': int(resultado), 'inteiros_preservados': 8, 'vetoriais_preservados': 10}
    finally:
        for endereco in reversed(rotinas):
            windows.nucleo.VirtualFree(endereco, 0, 0x8000)


def executar_falha():
    # Subprocesso isolado: a saída fatal realmente chama ExitProcess.
    # O stub nega só a primeira expansão, após criar quatro registros.
    from testes.ensaio_windows_rs0415 import Windows, PeCarregado, gerar_imagem, chamar_com_sentinelas
    windows = Windows()
    gerador, pe, _, _ = gerar_imagem(FONTE)
    with PeCarregado(windows, pe) as imagem:
        primeira = (ct.c_uint64 * 3)()
        alocar = ct.c_uint64.from_address(imagem.importacoes['VirtualAlloc'])
        liberar = ct.c_uint64.from_address(imagem.importacoes['VirtualFree'])
        sair = ct.c_uint64.from_address(imagem.importacoes['ExitProcess'])
        real_alocar = ct.WINFUNCTYPE(ct.c_void_p, ct.c_void_p, ct.c_size_t, ct.c_uint32, ct.c_uint32)(alocar.value)
        real_liberar = ct.WINFUNCTYPE(ct.c_int, ct.c_void_p, ct.c_size_t, ct.c_uint32)(liberar.value)
        real_sair = ct.WINFUNCTYPE(None, ct.c_uint32)(sair.value)
        obter = ct.WINFUNCTYPE(ct.c_void_p, ct.c_int32)(ct.c_uint64.from_address(imagem.importacoes['GetStdHandle']).value)
        contagem = [0, 0]
        @ct.WINFUNCTYPE(ct.c_void_p, ct.c_void_p, ct.c_size_t, ct.c_uint32, ct.c_uint32)
        def negar_expansao(endereco, tamanho, flags, protecao):
            contagem[0] += 1
            return None if tamanho >= 384 else real_alocar(endereco, tamanho, flags, protecao)
        @ct.WINFUNCTYPE(ct.c_int, ct.c_void_p, ct.c_size_t, ct.c_uint32)
        def contar_liberacao(endereco, tamanho, flags):
            contagem[1] += 1
            return real_liberar(endereco, tamanho, flags)
        @ct.WINFUNCTYPE(None, ct.c_uint32)
        def observar_saida(codigo):
            palavras = (ct.c_uint64 * 24).from_address(primeira[2])
            codigos = [ct.c_ubyte.from_address(palavras[indice * 6 + 3]).value for indice in range(4)]
            print('ESTADO:' + json.dumps({'tentativas': contagem[0], 'liberacoes': contagem[1], 'codigos': codigos}), flush=True)
            real_sair(codigo)
        alocar.value = ct.cast(negar_expansao, ct.c_void_p).value
        liberar.value = ct.cast(contar_liberacao, ct.c_void_p).value
        sair.value = ct.cast(observar_saida, ct.c_void_p).value
        entradas = {'Rbx': obter(-11), 'R12': obter(-12)}
        chamar_com_sentinelas(windows, imagem.base + 0x1000 + gerador.rotulos['funcao_criar'],
                             entradas=entradas, argumentos_pilha=[0, ct.addressof(primeira) + 16])
        segunda = (ct.c_uint64 * 3)()
        chamar_com_sentinelas(windows, imagem.base + 0x1000 + gerador.rotulos['funcao_ampliar'],
                             entradas=entradas, argumentos_pilha=[0, ct.addressof(segunda) + 16, *primeira])
        raise AssertionError('A expansão deveria falhar.')


if __name__ == '__main__':
    if len(sys.argv) == 3 and sys.argv[1] == '--ensaio':
        if sys.argv[2] == 'falha':
            executar_falha()
        elif sys.argv[2] == 'propriedade':
            resultado = executar_propriedade()
        else:
            from testes.ensaio_windows_rs0415 import executar_ensaio
            resultado = executar_ensaio(sys.argv[2], FONTE)
        print(json.dumps(resultado, ensure_ascii=False))
    else:
        unittest.main()
