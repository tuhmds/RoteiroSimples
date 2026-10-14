"""Windows AMD64 real: ABI, desenrolamento e falhas na retomada RS0.42N.

Toda execucao ctypes ocorre em subprocesso, inclusive os INT3 reais.
O oraculo Python de envelopes e registros independe do codigo RS emitido.
"""
import ctypes as ct
from contextlib import contextmanager
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
from testes import test_cadastro_retomada_rs042n as oraculo

codificar, envelopar, registros = oraculo.codificar, oraculo.envelopar, oraculo.registros


@contextmanager
def mudar_pasta(caminho):
    # contextlib.chdir so existe a partir do Python 3.11.
    anterior = Path.cwd()
    os.chdir(caminho)
    try:
        yield
    finally:
        os.chdir(anterior)

FONTE_CONSULTA = '''funcao consultar() -> inteiro {
    seja estado = 0
    consulte_arquivo("consulta.rsd", estado)
    retorne estado
}
inicio {
    escreva(1)
}'''

FONTE = '''importe "padrao/cadastro_retomada.rts" como disco
importe "padrao/cadastro_variavel.rts" como cad
funcao ler() -> inteiro {
    seja resposta = disco.carregar()
    retorne resposta.codigo_erro
}
funcao geracao() -> inteiro {
    seja resposta = disco.carregar()
    retorne resposta.geracao
}
funcao recuperado() -> inteiro {
    seja resposta = disco.carregar()
    se resposta.recuperado {
        retorne 1
    }
    retorne 0
}
funcao primeiro_byte(registro: emprestimo[cad.Registro]) -> inteiro {
    retorne registro.conteudo[0]
}
funcao conteudo() -> inteiro {
    seja resposta = disco.carregar()
    se resposta.valido == falso {
        retorne -1
    }
    se tamanho(resposta.valor.registros) != 1 {
        retorne -2
    }
    retorne primeiro_byte(empreste(resposta.valor.registros[0]))
}
funcao gravar() -> inteiro {
    seja cadastro = cad.criar()
    seja novo: cad.Registro
    novo.codigo = 7
    copie(novo.titulo, "Ação 🌱")
    para indice de 0 ate 5999 {
        adicione_byte(novo.conteudo, (99 + indice) % 256)
    }
    seja adicao = cad.adicionar(mova(cadastro), mova(novo))
    mova(cadastro, adicao.valor)
    seja resposta = disco.salvar(empreste(cadastro), 3)
    retorne resposta.codigo_erro
}
funcao obsoleto() -> inteiro {
    seja cadastro = cad.criar()
    seja resposta = disco.salvar(empreste(cadastro), 2)
    retorne resposta.codigo_erro
}
funcao inicializar() -> inteiro {
    seja resposta = disco.inicializar()
    retorne resposta.codigo_erro
}
inicio {
    escreva(1)
}'''


def fonte_reunida():
    from compilador.modulos import carregar_fontes
    with tempfile.TemporaryDirectory() as pasta:
        caminho = Path(pasta) / 'principal.rts'
        caminho.write_text(FONTE, encoding='utf-8')
        return carregar_fontes(caminho).texto


@unittest.skipUnless(WINDOWS_X64, 'Ensaio exige Windows AMD64 real.')
class TestesAbiRetomadaRS042N(unittest.TestCase):
    def ensaio(self, acao):
        ambiente = os.environ.copy()
        ambiente['PYTHONIOENCODING'] = 'utf-8'
        resposta = subprocess.run(
            [sys.executable, str(Path(__file__).resolve()), '--ensaio', acao],
            cwd=RAIZ, env=ambiente, capture_output=True, text=True,
            encoding='utf-8', errors='replace', timeout=90,
        )
        self.assertEqual(resposta.returncode, 0, resposta.stdout + resposta.stderr)
        return json.loads(resposta.stdout)

    def test_consulta_real_preserva_pilha_oito_inteiros_e_dez_vetoriais(self):
        observado = self.ensaio('consulta')
        self.assertEqual(observado['reais'], {'regular': 0, 'ausente': 1, 'diretorio': -1})
        self.assertEqual((observado['inteiros'], observado['vetoriais']), (8, 10))
        self.assertEqual(observado['chamadas'], 6)

    def test_consulta_recusa_erro_5_diretorio_e_ponto_de_reanalise(self):
        observado = self.ensaio('consulta_injetada')
        self.assertEqual(observado['retornos'], {'acesso_negado': -1, 'diretorio': -1, 'reanalise': -1})
        self.assertEqual(observado['consultas_erro'], 2)

    def test_desenrolamento_nativo_em_prologo_corpo_e_epilogo_da_consulta(self):
        observado = self.ensaio('estados')
        self.assertIn('rs_consultar_arquivo', observado['nomes'])
        self.assertGreater(observado['estados'], 10)

    def test_int3_real_desenrola_consulta_e_quadro_chamador(self):
        observado = self.ensaio('excecoes')
        self.assertIn('rs_consultar_arquivo', observado['excecoes'])
        self.assertEqual(observado['quadros'], 2 * len(observado['excecoes']))

    def test_falha_writefile_na_preparacao_retorna_43_e_preserva_geracao_antiga(self):
        observado = self.ensaio('escrita')
        self.assertEqual(set(observado['fases']), {'invalidacao', 'cabecalho', 'corpo_parcial'})
        for fase, resultado in observado['fases'].items():
            self.assertEqual((resultado['codigo'], resultado['geracao'], resultado['conteudo']), (43, 3, 29), fase)
            self.assertEqual(resultado['recuperado'], int(fase != 'invalidacao'))
        self.assertEqual(observado['alocacoes'], observado['liberacoes'])
        self.assertEqual(observado['vivos'], 0)

    def test_confirmacao_escrita_com_flush_final_falho_retorna_51_e_expoe_geracao_nova(self):
        observado = self.ensaio('confirmacao')
        self.assertEqual((observado['codigo'], observado['geracao'], observado['conteudo']), (51, 4, 99))
        self.assertEqual(observado['sincronizacoes'], 3)
        self.assertTrue(observado['confirmacao_escrita'])
        self.assertEqual(observado['alocacoes'], observado['liberacoes'])
        self.assertEqual(observado['vivos'], 0)

    def test_getlasterror_5_nao_vira_ausencia_nem_inicializa_cadastro(self):
        observado = self.ensaio('acesso_negado')
        self.assertEqual(observado['retornos'], {'ler': 41, 'gravar': 41, 'inicializar': 50})
        self.assertGreaterEqual(observado['consultas_erro'], 6)
        self.assertEqual(observado['escritas'], 0)
        self.assertEqual(observado['copias_criadas'], 0)
        self.assertEqual(observado['alocacoes'], observado['liberacoes'])
        self.assertEqual(observado['vivos'], 0)

    def test_carregar_gravar_e_retornos_antecipados_descartam_todos_os_donos(self):
        observado = self.ensaio('memoria')
        self.assertGreater(observado['alocacoes'], 100)
        self.assertEqual(observado['alocacoes'], observado['liberacoes'])
        self.assertEqual(observado['vivos'], 0)
        self.assertEqual(observado['casos'], 30)
        self.assertEqual((observado['inteiros'], observado['vetoriais']), (8, 10))


def importar_hospedeiro():
    from testes.ensaio_windows_rs0415 import Windows, PeCarregado, gerar_imagem, chamar_com_sentinelas
    return Windows, PeCarregado, gerar_imagem, chamar_com_sentinelas


def interceptar(imagem, nome, rotina):
    ct.c_uint64.from_address(imagem.importacoes[nome]).value = ct.cast(rotina, ct.c_void_p).value


def inteiro_assinado(valor):
    return ct.c_int64(valor).value


def executar_consulta(injetada=False):
    Windows, PeCarregado, gerar_imagem, chamar_com_sentinelas = importar_hospedeiro()
    windows = Windows()
    gerador, pe, _, _ = gerar_imagem(FONTE_CONSULTA)
    pasta_original = Path.cwd()
    observados = {}
    chamadas = 0
    consultas_erro = [0]
    tipo_atributos = ct.WINFUNCTYPE(ct.c_uint32, ct.c_char_p)
    tipo_erro = ct.WINFUNCTYPE(ct.c_uint32)
    atributos = [0]
    @tipo_atributos
    def consultar_atributos(caminho):
        return atributos[0]
    @tipo_erro
    def consultar_erro():
        consultas_erro[0] += 1
        return 5
    try:
        with tempfile.TemporaryDirectory() as pasta, mudar_pasta(pasta), PeCarregado(windows, pe) as imagem:
            caminho = ct.create_string_buffer(b'consulta.rsd')
            if injetada:
                interceptar(imagem, 'GetFileAttributesA', consultar_atributos)
                interceptar(imagem, 'GetLastError', consultar_erro)
                casos = (('acesso_negado', 0xFFFFFFFF, -1), ('diretorio', 0x10, -1), ('reanalise', 0x400, -1))
            else:
                casos = (('regular', 0, 0), ('ausente', 0, 1), ('diretorio', 0, -1))
            for nome, valor, esperado in casos:
                atributos[0] = valor
                if not injetada:
                    if nome == 'regular':
                        Path('consulta.rsd').write_bytes(b'RS')
                    elif nome == 'ausente':
                        Path('consulta.rsd').unlink()
                    else:
                        Path('consulta.rsd').mkdir()
                direto = chamar_com_sentinelas(windows, imagem.base + 0x1000 + gerador.rotulos['rs_consultar_arquivo'],
                    entradas={'Rdi': ct.addressof(caminho)})
                comando = chamar_com_sentinelas(windows, imagem.base + 0x1000 + gerador.rotulos['funcao_consultar'],
                    argumentos_pilha=[0])
                chamadas += 2
                assert inteiro_assinado(direto) == inteiro_assinado(comando) == esperado, (nome, direto, comando)
                observados[nome] = inteiro_assinado(direto)
    finally:
        os.chdir(pasta_original)
    return {'retornos' if injetada else 'reais': observados, 'consultas_erro': consultas_erro[0],
            'chamadas': chamadas, 'inteiros': 8, 'vetoriais': 10}


class ContagemMemoria:
    """Conta somente alocacoes do PE pela IAT, fora do hospedeiro ctypes."""
    def __init__(self, windows, imagem):
        self.vivos, self.erros = set(), []
        self.alocacoes = self.liberacoes = self.casos = 0
        tipo_alocar = ct.WINFUNCTYPE(ct.c_void_p, ct.c_void_p, ct.c_size_t, ct.c_uint32, ct.c_uint32)
        tipo_liberar = ct.WINFUNCTYPE(ct.c_int, ct.c_void_p, ct.c_size_t, ct.c_uint32)
        @tipo_alocar
        def alocar(endereco, tamanho, sinalizadores, protecao):
            ponteiro = windows.nucleo.VirtualAlloc(endereco, tamanho, sinalizadores, protecao)
            self.alocacoes += 1
            if not ponteiro or ponteiro in self.vivos:
                self.erros.append('Alocacao nula ou repetida.')
            self.vivos.add(ponteiro)
            return ponteiro
        @tipo_liberar
        def liberar(endereco, tamanho, sinalizadores):
            self.liberacoes += 1
            if endereco not in self.vivos:
                self.erros.append('Descarte sem dono ou repetido.')
            self.vivos.discard(endereco)
            resultado = windows.nucleo.VirtualFree(endereco, tamanho, sinalizadores)
            if not resultado:
                self.erros.append('VirtualFree recusou o descarte.')
            return resultado
        self.rotinas = (alocar, liberar)
        interceptar(imagem, 'VirtualAlloc', alocar)
        interceptar(imagem, 'VirtualFree', liberar)

    def conferir(self):
        self.casos += 1
        assert not self.erros and not self.vivos, (self.erros, self.vivos)
        assert self.alocacoes == self.liberacoes, (self.alocacoes, self.liberacoes)

    def resultado(self):
        return {'alocacoes': self.alocacoes, 'liberacoes': self.liberacoes,
                'vivos': len(self.vivos), 'casos': self.casos, 'inteiros': 8, 'vetoriais': 10}


def executar_protocolo(acao):
    Windows, PeCarregado, gerar_imagem, chamar_com_sentinelas = importar_hospedeiro()
    windows = Windows()
    gerador, pe, _, _ = gerar_imagem(fonte_reunida())
    transferencia = ct.WINFUNCTYPE(ct.c_int, ct.c_void_p, ct.c_void_p, ct.c_uint32, ct.POINTER(ct.c_uint32), ct.c_void_p)
    sincronizacao = ct.WINFUNCTYPE(ct.c_int, ct.c_void_p)
    consulta = ct.WINFUNCTYPE(ct.c_uint32, ct.c_char_p)
    ultimo_erro = ct.WINFUNCTYPE(ct.c_uint32)
    windows.nucleo.WriteFile.argtypes = transferencia._argtypes_
    windows.nucleo.WriteFile.restype = ct.c_int
    windows.nucleo.FlushFileBuffers.argtypes = sincronizacao._argtypes_
    windows.nucleo.FlushFileBuffers.restype = ct.c_int
    pasta_original = Path.cwd()
    fase = [None]
    escritas, sincronizacoes, consultas_erro = [0], [0], [0]
    confirmacao_escrita = [False]
    erros_chamada = []
    @transferencia
    def escrever(recurso, dados, tamanho, quantidade, sobreposta):
        escritas[0] += 1
        if sobreposta:
            erros_chamada.append('WriteFile recebeu lpOverlapped nao nulo.')
            quantidade[0] = 0
            return 0
        if ((fase[0] == 'invalidacao' and escritas[0] == 1) or
                (fase[0] == 'cabecalho' and escritas[0] == 2) or
                (fase[0] == 'corpo_parcial' and escritas[0] == 4) or fase[0] == 'acesso_negado'):
            quantidade[0] = 0
            return 0
        pedido = tamanho // 2 if fase[0] == 'corpo_parcial' and escritas[0] == 3 else tamanho
        resultado = windows.nucleo.WriteFile(recurso, dados, pedido, quantidade, sobreposta)
        if resultado and ct.string_at(dados, tamanho) == b'CONFIRMA' and quantidade[0] == 8:
            confirmacao_escrita[0] = True
        return resultado
    @sincronizacao
    def sincronizar(recurso):
        sincronizacoes[0] += 1
        if fase[0] == 'confirmacao' and sincronizacoes[0] == 3:
            return 0
        return windows.nucleo.FlushFileBuffers(recurso)
    @consulta
    def negar_consulta(caminho):
        return 0xFFFFFFFF
    @ultimo_erro
    def consultar_erro():
        consultas_erro[0] += 1
        return 5
    resultado = {}
    try:
        with PeCarregado(windows, pe) as imagem:
            contagem = ContagemMemoria(windows, imagem)
            interceptar(imagem, 'WriteFile', escrever)
            interceptar(imagem, 'FlushFileBuffers', sincronizar)
            def chamar(nome):
                retorno = chamar_com_sentinelas(windows,
                    imagem.base + 0x1000 + gerador.rotulos['funcao_' + nome], argumentos_pilha=[0])
                contagem.conferir()
                return inteiro_assinado(retorno)
            if acao == 'escrita':
                resultado['fases'] = {}
                for nome in ('invalidacao', 'cabecalho', 'corpo_parcial'):
                    with tempfile.TemporaryDirectory() as pasta, mudar_pasta(pasta):
                        oraculo.TestesCadastroRetomadaRS042N.preparar(pasta)
                        antiga = Path('cadastro_a.rsd').read_bytes()
                        fase[0], escritas[0], sincronizacoes[0] = nome, 0, 0
                        codigo = chamar('gravar')
                        assert codigo == 43, (nome, codigo, escritas)
                        assert escritas[0] == {'invalidacao': 1, 'cabecalho': 2, 'corpo_parcial': 4}[nome]
                        assert Path('cadastro_a.rsd').read_bytes() == antiga
                        assert not confirmacao_escrita[0]
                        if nome != 'invalidacao':
                            assert Path('cadastro_b.rsd').read_bytes()[32:40] == bytes(8)
                        if nome == 'corpo_parcial':
                            assert Path('cadastro_b.rsd').read_bytes()[40:2088] == codificar(registros(99))[:2048]
                        fase[0] = None
                        resultado['fases'][nome] = {'codigo': codigo, 'geracao': chamar('geracao'),
                            'conteudo': chamar('conteudo'), 'recuperado': chamar('recuperado')}
                        assert chamar('ler') == 0
            elif acao == 'confirmacao':
                with tempfile.TemporaryDirectory() as pasta, mudar_pasta(pasta):
                    oraculo.TestesCadastroRetomadaRS042N.preparar(pasta)
                    antiga = Path('cadastro_a.rsd').read_bytes()
                    fase[0] = 'confirmacao'
                    codigo = chamar('gravar')
                    assert codigo == 51, codigo
                    assert Path('cadastro_a.rsd').read_bytes() == antiga
                    assert Path('cadastro_b.rsd').read_bytes() == envelopar(4, codificar(registros(99)))
                    assert confirmacao_escrita[0] and sincronizacoes[0] == 3
                    fase[0] = None
                    resultado.update(codigo=codigo, geracao=chamar('geracao'), conteudo=chamar('conteudo'),
                        sincronizacoes=sincronizacoes[0], confirmacao_escrita=confirmacao_escrita[0])
                    assert chamar('ler') == 0 and chamar('recuperado') == 0
            elif acao == 'acesso_negado':
                interceptar(imagem, 'GetFileAttributesA', negar_consulta)
                interceptar(imagem, 'GetLastError', consultar_erro)
                with tempfile.TemporaryDirectory() as pasta, mudar_pasta(pasta):
                    fase[0] = 'acesso_negado'
                    resultado['retornos'] = {nome: chamar(nome) for nome in ('ler', 'gravar', 'inicializar')}
                    resultado.update(consultas_erro=consultas_erro[0], escritas=escritas[0],
                        copias_criadas=len(list(Path('.').glob('cadastro_?.rsd'))))
                    assert not list(Path('.').glob('cadastro_?.rsd'))
            elif acao == 'memoria':
                for _ in range(3):
                    with tempfile.TemporaryDirectory() as pasta, mudar_pasta(pasta):
                        assert chamar('ler') == 44
                        assert chamar('inicializar') == 0
                        assert chamar('ler') == 0
                        assert chamar('inicializar') == 50
                        oraculo.TestesCadastroRetomadaRS042N.preparar(pasta)
                        assert chamar('ler') == 0
                        assert chamar('obsoleto') == 46
                        assert chamar('gravar') == 0
                        assert chamar('geracao') == 4
                        Path('cadastro_a.rsd').write_bytes(b'RSCN')
                        Path('cadastro_b.rsd').write_bytes(b'RSCN')
                        assert chamar('ler') == 45
                        assert chamar('gravar') == 45
            else:
                raise AssertionError(f'Ensaio desconhecido: {acao}.')
            assert not erros_chamada, erros_chamada
            resultado.update(contagem.resultado())
    finally:
        os.chdir(pasta_original)
    return resultado


if __name__ == '__main__' and '--ensaio' in sys.argv:
    acao = sys.argv[-1]
    if acao in ('consulta', 'consulta_injetada'):
        observado = executar_consulta(acao == 'consulta_injetada')
    elif acao in ('estados', 'excecoes'):
        from testes.ensaio_windows_rs0415 import executar_ensaio
        observado = executar_ensaio(acao, FONTE_CONSULTA)
    else:
        observado = executar_protocolo(acao)
    print(json.dumps(observado))
elif __name__ == '__main__':
    unittest.main()
