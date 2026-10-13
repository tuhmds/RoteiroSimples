"""Cadastro RSCV: dois processos nativos, formato independente e rejeicoes."""
from pathlib import Path
import random
import struct
import subprocess
import sys
import tempfile
import unittest
import zlib

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))
from backend import compilar
from compilador.modulos import carregar_fontes
from compilador.parser import analisar_programa
from testes.test_utf8_rs042m import programa_modulo
from testes.test_valores_dinamicos_rs042a import alvo_nativo, rodar

REGISTROS = ((7, 'Ação 🌱', bytes(i % 256 for i in range(5000))),
             (9, 'Revisão concluída', bytes(i % 256 for i in range(257))))


def codificar(registros=REGISTROS, versao=1, reservado=0):
    corpo = b''.join(struct.pack('<QII', chave, len(titulo.encode()), len(dados)) + titulo.encode() + dados
                     for chave, titulo, dados in registros)
    return b'RSCV' + struct.pack('<IIIII', versao, len(registros), len(corpo), zlib.adler32(corpo), reservado) + corpo


def corrigir_integridade(dados):
    dados = bytearray(dados)
    struct.pack_into('<I', dados, 12, len(dados) - 24)
    struct.pack_into('<I', dados, 16, zlib.adler32(dados[24:]))
    return bytes(dados)


class TestesCadastroPersistenteRS042M(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pasta = tempfile.TemporaryDirectory(prefix='rs_cadastro_')
        cls.addClassCleanup(cls.pasta.cleanup)
        cls.executaveis = {}
        for nome in ('gravar', 'ler'):
            fonte = carregar_fontes(RAIZ / f'exemplos/dados_rs/cadastro_{nome}_rs042m.rts').texto
            p = analisar_programa(fonte)
            for nivel in range(9):
                imagem = compilar(p, alvo_nativo(), nivel=nivel, otimizar=nivel > 0)
                destino = Path(cls.pasta.name) / f'{nome}_{nivel}{".exe" if alvo_nativo() == "windows" else ""}'
                destino.write_bytes(imagem)
                if alvo_nativo() == 'linux':
                    destino.chmod(0o700)
                cls.executaveis[nome, nivel] = destino
            # Tambem construir o outro formato de executavel.
            for alvo in ('windows', 'linux'):
                assert compilar(p, alvo, nivel=8, otimizar=True)

    @classmethod
    def executar(cls, nome, pasta, nivel=8):
        return subprocess.run([str(cls.executaveis[nome, nivel])], cwd=pasta,
            capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=25)

    def rejeitar(self, dados, codigo, niveis=(0, 8)):
        with tempfile.TemporaryDirectory() as pasta:
            arquivo = Path(pasta) / 'cadastro.rsd'
            arquivo.write_bytes(dados)
            for nivel in niveis:
                r = self.executar('ler', pasta, nivel)
                self.assertEqual((r.returncode, r.stdout), (3, str(codigo) + '\n'), r.stderr)
                self.assertEqual(arquivo.read_bytes(), dados)

    def test_crud_gravacao_reabertura_e_oraculo_nove_niveis(self):
        for nivel in range(9):
            with self.subTest(nivel=nivel), tempfile.TemporaryDirectory() as pasta:
                r = self.executar('gravar', pasta, nivel)
                self.assertEqual((r.returncode, r.stdout), (0, '1\n5343\n2\n'), r.stderr)
                self.assertEqual((Path(pasta)/'cadastro.rsd').read_bytes(), codificar())
                self.assertFalse((Path(pasta)/'cadastro_provisorio.rsd').exists())
                r = self.executar('ler', pasta, nivel)
                self.assertEqual((r.returncode, r.stdout), (0, '2\n7\nAção 🌱\n5000\n9\nRevisão concluída\n257\n1\n'), r.stderr)
                # Outra publicacao substitui o snapshot e deixa o mesmo formato.
                r = self.executar('gravar', pasta, nivel)
                self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
                self.assertEqual((Path(pasta)/'cadastro.rsd').read_bytes(), codificar())

    def test_formato_vazio_e_limites_validos(self):
        for registros in ((), ((1, 'X' * 1024, bytes(65536)),),
                          tuple((i + 1, 'X', b'') for i in range(1024)),
                          ((9223372036854775807, 'é', b'\0\xff'),)):
            with self.subTest(quantidade=len(registros)), tempfile.TemporaryDirectory() as pasta:
                (Path(pasta)/'cadastro.rsd').write_bytes(codificar(registros))
                r = self.executar('ler', pasta)
                self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
                self.assertEqual(r.stdout.splitlines()[0], str(len(registros)))

    def test_cabecalhos_tamanho_versao_contagem_e_integridade(self):
        for tamanho in (0, 1, 4, 8, 16, 23):
            self.rejeitar(codificar()[:tamanho], 10)
        for posicao, valor, codigo in ((0, 0, 11), (3, 0, 11), (4, 2, 12),
                                      (8, 1025, 14), (12, 1, 15), (16, 0, 16), (20, 1, 13)):
            dados = bytearray(codificar())
            struct.pack_into('<I', dados, posicao, valor)
            with self.subTest(posicao=posicao):
                self.rejeitar(bytes(dados), codigo)
        self.rejeitar(codificar()[:-1], 15)
        self.rejeitar(codificar() + b'\0', 15)
        dados = bytearray(codificar()); dados[-1] ^= 1
        self.rejeitar(bytes(dados), 16)

    def test_offsets_truncados_extra_contagem_e_campos_limitados(self):
        original = codificar(((1, 'RS', b'\0\xff'),))
        for tamanho in (24, 25, 39, 40, 41, 42, 43):
            self.rejeitar(corrigir_integridade(original[:tamanho]), 17)
        self.rejeitar(corrigir_integridade(original + b'\0'), 17)
        for posicao, valor, codigo in ((8, 0, 17), (8, 2, 17), (32, 0, 18),
                                      (32, 1025, 18), (36, 65537, 18)):
            dados = bytearray(original); struct.pack_into('<I', dados, posicao, valor)
            self.rejeitar(corrigir_integridade(dados), codigo)

    def test_identificadores_invalidos_duplicados_e_utf8_com_checksum_valido(self):
        for chave in (0, 9223372036854775808, 18446744073709551615):
            dados = bytearray(codificar(((1, 'RS', b''),)))
            struct.pack_into('<Q', dados, 24, chave)
            self.rejeitar(corrigir_integridade(dados), 19)
        self.rejeitar(codificar(((1, 'Um', b'\xff'), (1, 'Dois', b'\0'))), 20)
        for titulo in (b'\xff', b'\xc0\x80', b'\xed\xa0\x80', b'\xf4\x90\x80\x80', b'\xe2\x82'):
            corpo = struct.pack('<QII', 1, len(titulo), 0) + titulo
            dados = b'RSCV' + struct.pack('<IIIII', 1, 1, len(corpo), zlib.adler32(corpo), 0) + corpo
            self.rejeitar(dados, 21)

    def test_mutacoes_geradas_rejeitadas_sem_reescrever_arquivo(self):
        rng = random.Random(4214)
        original = codificar()
        for _ in range(48):
            dados = bytearray(original)
            posicao = rng.randrange(24, len(dados))
            dados[posicao] ^= rng.randrange(1, 256)
            self.rejeitar(bytes(dados), 16, niveis=(8,))

    def test_limite_global_na_leitura_sem_aceitar_arquivo_maior(self):
        self.rejeitar(bytes(8388609), 14, niveis=(8,))

    def test_arquivo_ausente_e_diretorio_retornam_erro(self):
        with tempfile.TemporaryDirectory() as pasta:
            for criar in (False, True):
                if criar:
                    (Path(pasta)/'cadastro.rsd').mkdir()
                r = self.executar('ler', pasta)
                self.assertEqual((r.returncode, r.stdout), (3, '30\n'), r.stderr)

    def test_provisorio_existente_nao_sobrescreve_snapshot(self):
        with tempfile.TemporaryDirectory() as pasta:
            antigo = b'anterior'
            (Path(pasta)/'cadastro.rsd').write_bytes(antigo)
            (Path(pasta)/'cadastro_provisorio.rsd').write_bytes(b'pendente')
            r = self.executar('gravar', pasta)
            self.assertEqual((r.returncode, r.stdout), (3, '1\n30\n'), r.stderr)
            self.assertEqual((Path(pasta)/'cadastro.rsd').read_bytes(), antigo)
            self.assertEqual((Path(pasta)/'cadastro_provisorio.rsd').read_bytes(), b'pendente')

    def test_publicacao_rejeitada_conserva_provisorio_para_recuperacao(self):
        with tempfile.TemporaryDirectory() as pasta:
            destino = Path(pasta)/'cadastro.rsd'; destino.mkdir()
            (destino/'preservado').write_bytes(b'anterior')
            r = self.executar('gravar', pasta)
            self.assertEqual((r.returncode, r.stdout), (3, '1\n34\n'), r.stderr)
            self.assertEqual((destino/'preservado').read_bytes(), b'anterior')
            self.assertEqual((Path(pasta)/'cadastro_provisorio.rsd').read_bytes(), codificar())

    @unittest.skipUnless(sys.platform == 'linux', 'Limite de arquivo exige Linux.')
    def test_escrita_parcial_real_preserva_snapshot_anterior_linux(self):
        import resource
        import signal
        def limitar():
            signal.signal(signal.SIGXFSZ, signal.SIG_IGN)
            resource.setrlimit(resource.RLIMIT_FSIZE, (1024, 1024))
        with tempfile.TemporaryDirectory() as pasta:
            (Path(pasta)/'cadastro.rsd').write_bytes(b'anterior')
            r = subprocess.run([str(self.executaveis['gravar', 8])], cwd=pasta,
                preexec_fn=limitar, capture_output=True, text=True, encoding='utf-8', timeout=25)
            self.assertEqual((r.returncode, r.stdout), (3, '1\n31\n'), r.stderr)
            self.assertEqual((Path(pasta)/'cadastro.rsd').read_bytes(), b'anterior')
            self.assertEqual((Path(pasta)/'cadastro_provisorio.rsd').read_bytes(), codificar()[:1024])

    def test_crud_rejeitado_devolve_cadastro_sem_perder_registros(self):
        fonte = '''importe "padrao/cadastro_variavel.rts" como cad
funcao registro(chave: inteiro, nome: texto[8]) -> cad.Registro {
    seja novo: cad.Registro
    novo.codigo = chave
    copie(novo.titulo, nome)
    retorne mova(novo)
}
inicio {
    seja cadastro = cad.criar()
    seja nome: texto[8]
    copie(nome, "Primeiro")
    seja adicao = cad.adicionar(mova(cadastro), registro(1, nome))
    mova(cadastro, adicao.valor)
    seja duplicado = cad.adicionar(mova(cadastro), registro(1, nome))
    escreva(duplicado.codigo_erro)
    mova(cadastro, duplicado.valor)
    seja negativo = cad.adicionar(mova(cadastro), registro(-1, nome))
    escreva(negativo.codigo_erro)
    mova(cadastro, negativo.valor)
    seja vazio: texto[8]
    seja sem_nome = cad.adicionar(mova(cadastro), registro(2, vazio))
    escreva(sem_nome.codigo_erro)
    mova(cadastro, sem_nome.valor)
    seja ausente = cad.alterar(mova(cadastro), registro(9, nome))
    escreva(ausente.codigo_erro)
    mova(cadastro, ausente.valor)
    seja remocao = cad.remover(mova(cadastro), 9)
    escreva(remocao.codigo_erro)
    mova(cadastro, remocao.valor)
    escreva(tamanho(cadastro.registros))
    escreva(cad.localizar(empreste(cadastro), 1))
}'''
        programa = programa_modulo(fonte)
        for nivel in (0, 8):
            r, _ = rodar(compilar(programa, alvo_nativo(), nivel=nivel, otimizar=nivel > 0))
            self.assertEqual((r.returncode, r.stdout), (0, '5\n1\n2\n6\n6\n1\n0\n'), r.stderr)

    def test_serializacao_revalida_registros_publicos_antes_de_abrir_arquivo(self):
        for preparar, codigo in (( 'novo.codigo = 0', 1),
                ('copie(novo.titulo, "")', 2),
                ('para indice de 0 ate 1024 {\n junte(novo.titulo, "X")\n}', 2),
                ('para indice de 0 ate 65536 {\n adicione_byte(novo.conteudo, 0)\n}', 3),
                ('', 5)):
            fonte = '''importe "padrao/cadastro_variavel.rts" como cad
importe "padrao/cadastro_arquivo.rts" como disco
inicio {
    seja cadastro = cad.criar()
    seja novo: cad.Registro
    novo.codigo = 1
    copie(novo.titulo, "X")
''' + preparar + '''
    adicione(cadastro.registros, mova(novo))
'''
            if codigo == 5:
                fonte += '''    seja outro: cad.Registro
    outro.codigo = 1
    copie(outro.titulo, "Y")
    adicione(cadastro.registros, mova(outro))
'''
            fonte += '''    seja resposta = disco.salvar(empreste(cadastro))
    escreva(resposta.codigo_erro)
}'''
            p = programa_modulo(fonte)
            r, arquivos = rodar(compilar(p, alvo_nativo(), nivel=8, otimizar=True),
                antes=lambda p: (p/'cadastro.rsd').write_bytes(b'anterior'))
            self.assertEqual((r.returncode, r.stdout), (0, str(codigo)+'\n'), r.stderr)
            self.assertEqual(arquivos, {'cadastro.rsd': b'anterior'})

    def test_serializacao_limita_contagem_e_tamanho_total_antes_de_gravar(self):
        for quantidade, carga, codigo in ((1025, 0, 4), (128, 65536, 14)):
            fonte = '''importe "padrao/cadastro_variavel.rts" como cad
importe "padrao/cadastro_arquivo.rts" como disco
inicio {
    seja cadastro = cad.criar()
    para indice de 1 ate ''' + str(quantidade) + ''' {
        seja novo: cad.Registro
        novo.codigo = indice
        copie(novo.titulo, "X")
        para byte de 1 ate ''' + str(carga) + ''' {
            adicione_byte(novo.conteudo, 0)
        }
        adicione(cadastro.registros, mova(novo))
    }
    seja resposta = disco.salvar(empreste(cadastro))
    escreva(resposta.codigo_erro)
}'''
            p = programa_modulo(fonte)
            r, arquivos = rodar(compilar(p, alvo_nativo(), nivel=8, otimizar=True),
                antes=lambda p: (p/'cadastro.rsd').write_bytes(b'anterior'))
            self.assertEqual((r.returncode, r.stdout), (0, str(codigo) + '\n'), r.stderr)
            self.assertEqual(arquivos, {'cadastro.rsd': b'anterior'})


if __name__ == '__main__':
    unittest.main()
