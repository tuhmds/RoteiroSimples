"""Windows real: ABI, descartes, excecoes e falhas de persistencia injetadas."""
import ctypes as ct
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))
from testes.test_abi_proprietarios_rs042a import WINDOWS_X64
from testes.test_cadastro_persistente_rs042m import codificar, corrigir_integridade

FONTE = '''importe "padrao/cadastro_variavel.rts" como cad
importe "padrao/cadastro_arquivo.rts" como disco
funcao converter() -> inteiro {
    seja nome: texto
    copie(nome, "Ação 🌱")
    seja dados: bytes
    seja volta: texto
    seja estado = 0
    codifique_utf8(dados, nome, estado)
    decodifique_utf8(volta, dados, estado)
    adicione_byte(dados, 255)
    decodifique_utf8(volta, dados, estado)
    retorne estado * 100 + tamanho(volta)
}
funcao analisar(dados: emprestimo[bytes]) -> inteiro {
    seja resposta = cad.desserializar(dados)
    se resposta.valido == falso {
        retorne resposta.codigo_erro
    }
    retorne tamanho(resposta.valor.registros)
}
funcao gravar() -> inteiro {
    seja cadastro = cad.criar()
    seja novo: cad.Registro
    novo.codigo = 1
    copie(novo.titulo, "Ação")
    para indice de 0 ate 4999 {
        adicione_byte(novo.conteudo, indice % 256)
    }
    seja adicao = cad.adicionar(mova(cadastro), mova(novo))
    mova(cadastro, adicao.valor)
    seja resposta = disco.salvar(empreste(cadastro))
    retorne resposta.codigo_erro
}
funcao ler() -> inteiro {
    seja resposta = disco.carregar()
    retorne resposta.codigo_erro
}
inicio {
    escreva(1)
}'''


def fonte_reunida():
    # O hospedeiro de ensaios aceita fonte pronta, nao importacoes.
    from compilador.modulos import carregar_fontes
    with tempfile.TemporaryDirectory() as pasta:
        caminho = Path(pasta)/'principal.rts'
        caminho.write_text(FONTE, encoding='utf-8')
        return carregar_fontes(caminho).texto


@unittest.skipUnless(WINDOWS_X64, 'Ensaio exige Windows AMD64 real.')
class TestesAbiCadastroRS042M(unittest.TestCase):
    def ensaio(self, acao):
        ambiente = os.environ.copy(); ambiente['PYTHONIOENCODING'] = 'utf-8'
        r = subprocess.run([sys.executable, str(Path(__file__).resolve()), '--ensaio', acao],
            cwd=RAIZ, env=ambiente, capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=45)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        return json.loads(r.stdout)

    def test_descarte_integral_validacao_parcial_conversoes_e_registradores(self):
        observado = self.ensaio('memoria')
        self.assertGreater(observado['alocacoes'], 100)
        self.assertEqual(observado['alocacoes'], observado['liberacoes'])
        self.assertEqual(observado['vivos'], 0)
        self.assertEqual(observado['casos'], 50)
        self.assertEqual((observado['inteiros'], observado['vetoriais']), (8, 10))

    def test_desenrolamento_real_dos_dois_auxiliares_utf8(self):
        observado = self.ensaio('estados')
        self.assertTrue({'rs_converter_utf8', 'rs_validar_utf8_recuperavel'} <= set(observado['nomes']))

    def test_excecoes_reais_nas_conversoes_utf8(self):
        observado = self.ensaio('excecoes')
        self.assertTrue({'rs_converter_utf8', 'rs_validar_utf8_recuperavel'} <= set(observado['excecoes']))
        self.assertEqual(observado['quadros'], 2 * len(observado['excecoes']))

    def test_escrita_parcial_sync_fechamento_publicacao_e_leitura_falham_com_codigo(self):
        observado = self.ensaio('arquivos')
        self.assertEqual(observado, {'WriteFile': 31, 'FlushFileBuffers': 32,
            'CloseHandle': 33, 'MoveFileExA': 34, 'ReadFile': 31})


def executar_memoria():
    from testes.ensaio_windows_rs0415 import Windows, PeCarregado, gerar_imagem, chamar_com_sentinelas
    windows = Windows()
    g, pe, _, _ = gerar_imagem(fonte_reunida())
    vivos, erros = set(), []
    contadores = [0, 0]
    @ct.WINFUNCTYPE(ct.c_void_p, ct.c_void_p, ct.c_size_t, ct.c_uint32, ct.c_uint32)
    def alocar(endereco, tamanho, flags, protecao):
        ponteiro = windows.nucleo.VirtualAlloc(endereco, tamanho, flags, protecao)
        contadores[0] += 1
        if not ponteiro or ponteiro in vivos:
            erros.append('Alocacao nula ou repetida.')
        vivos.add(ponteiro)
        return ponteiro
    @ct.WINFUNCTYPE(ct.c_int, ct.c_void_p, ct.c_size_t, ct.c_uint32)
    def liberar(endereco, tamanho, flags):
        contadores[1] += 1
        if endereco not in vivos:
            erros.append('Descarte sem dono ou repetido.')
        vivos.discard(endereco)
        return windows.nucleo.VirtualFree(endereco, tamanho, flags)
    correto = codificar()
    incompleto = corrigir_integridade(correto[:-1])
    duplicado = codificar(((1, 'Um', b'\xff'), (1, 'Dois', b'\0')))
    invalido = bytearray(codificar(((1, 'Um', b'\xff'), (2, 'Dois', b'\0'))))
    invalido[24 + 16 + 2 + 1 + 16] = 255
    invalido = corrigir_integridade(invalido)
    with PeCarregado(windows, pe) as imagem:
        for nome, callback in (('VirtualAlloc', alocar), ('VirtualFree', liberar)):
            ct.c_uint64.from_address(imagem.importacoes[nome]).value = ct.cast(callback, ct.c_void_p).value
        def chamar(nome, argumentos):
            return chamar_com_sentinelas(windows, imagem.base + 0x1000 + g.rotulos['funcao_' + nome], argumentos_pilha=argumentos)
        for _ in range(10):
            assert chamar('converter', [0]) == 111
            assert not vivos and not erros, (vivos, erros)
            for dados, esperado in ((correto, 2), (incompleto, 17), (duplicado, 20), (invalido, 21)):
                buffer = ct.create_string_buffer(dados)
                descritor = (ct.c_uint64 * 3)(len(dados), len(dados), ct.addressof(buffer))
                assert chamar('analisar', [0, ct.addressof(descritor) + 16]) == esperado
                assert not vivos and not erros, (vivos, erros)
                assert buffer.raw[:len(dados)] == dados
    return {'alocacoes': contadores[0], 'liberacoes': contadores[1], 'vivos': len(vivos),
            'casos': 50, 'inteiros': 8, 'vetoriais': 10}


def executar_arquivos():
    from testes.ensaio_windows_rs0415 import Windows, PeCarregado, gerar_imagem, chamar_com_sentinelas
    windows = Windows()
    g, pe, _, _ = gerar_imagem(fonte_reunida())
    transferencia = ct.WINFUNCTYPE(ct.c_int, ct.c_void_p, ct.c_void_p, ct.c_uint32, ct.POINTER(ct.c_uint32), ct.c_void_p)
    fechamento = ct.WINFUNCTYPE(ct.c_int, ct.c_void_p)
    publicacao = ct.WINFUNCTYPE(ct.c_int, ct.c_char_p, ct.c_char_p, ct.c_uint32)
    windows.nucleo.WriteFile.argtypes = transferencia._argtypes_; windows.nucleo.WriteFile.restype = ct.c_int
    windows.nucleo.CloseHandle.argtypes = [ct.c_void_p]; windows.nucleo.CloseHandle.restype = ct.c_int
    original_pasta = Path.cwd()
    observado = {}
    try:
        for nome, codigo in (('WriteFile', 31), ('FlushFileBuffers', 32), ('CloseHandle', 33), ('MoveFileExA', 34), ('ReadFile', 31)):
            chamadas = [0]
            def transferir(recurso, dados, tamanho, quantidade, sobreposta):
                chamadas[0] += 1
                if nome == 'WriteFile' and chamadas[0] == 1:
                    return windows.nucleo.WriteFile(recurso, dados, tamanho // 2, quantidade, sobreposta)
                quantidade[0] = 0
                return 0
            def fechar(recurso):
                chamadas[0] += 1
                if nome == 'CloseHandle':
                    assert windows.nucleo.CloseHandle(recurso)
                return 0
            def publicar(origem, destino, flags):
                chamadas[0] += 1
                return 0
            callback = (transferencia(transferir) if nome in ('WriteFile', 'ReadFile') else
                        publicacao(publicar) if nome == 'MoveFileExA' else fechamento(fechar))
            with tempfile.TemporaryDirectory() as pasta, PeCarregado(windows, pe) as imagem:
                os.chdir(pasta)
                anterior = codificar() if nome == 'ReadFile' else b'anterior'
                Path('cadastro.rsd').write_bytes(anterior)
                ct.c_uint64.from_address(imagem.importacoes[nome]).value = ct.cast(callback, ct.c_void_p).value
                funcao = 'ler' if nome == 'ReadFile' else 'gravar'
                retorno = chamar_com_sentinelas(windows, imagem.base + 0x1000 + g.rotulos['funcao_' + funcao], argumentos_pilha=[0])
                assert retorno == codigo and chamadas[0], (nome, retorno, chamadas)
                assert Path('cadastro.rsd').read_bytes() == anterior
                if nome == 'WriteFile':
                    assert Path('cadastro_provisorio.rsd').read_bytes() == codificar(((1, 'Ação', bytes(i % 256 for i in range(5000))),))[:2048]
                observado[nome] = retorno
                os.chdir(original_pasta)
    finally:
        os.chdir(original_pasta)
    return observado


if __name__ == '__main__' and '--ensaio' in sys.argv:
    acao = sys.argv[-1]
    if acao == 'memoria':
        observado = executar_memoria()
    elif acao == 'arquivos':
        observado = executar_arquivos()
    else:
        from testes.ensaio_windows_rs0415 import executar_ensaio
        observado = executar_ensaio(acao, fonte_reunida())
    print(json.dumps(observado))
elif __name__ == '__main__':
    unittest.main()
