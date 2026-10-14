"""Processos reais, retomada em cada fase e atualizacoes coordenadas."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import os
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
from testes.test_cadastro_persistente_rs042m import codificar
from testes.test_utf8_rs042m import programa_modulo
from testes.test_valores_dinamicos_rs042a import alvo_nativo


def registros(numero):
    return ((7, 'Ação 🌱', bytes((numero + i) % 256 for i in range(6000))),)


def envelopar(geracao, corpo):
    prefixo = b'RSCN' + struct.pack('<IQII', 1, geracao, len(corpo), zlib.adler32(corpo))
    return prefixo + struct.pack('<II', zlib.adler32(prefixo), 0) + b'CONFIRMA' + corpo


def linha_processo(processo):
    with ThreadPoolExecutor(max_workers=1) as executor:
        leitura = executor.submit(processo.stdout.readline)
        try:
            return leitura.result(timeout=20)
        except BaseException:
            processo.kill()
            processo.communicate(timeout=10)
            raise


def interromper_fonte(fonte, ancora, ocorrencia=0, antes=False, parcial=None):
    # Instrumentar somente o corpo real da rotina de escrita carregada.
    import re
    inicio = re.search(r'^funcao \w*gravar_copia\b', fonte, re.M).start()
    fim = fonte.index('\nfuncao ', inicio + 1)
    corpo = fonte[inicio:fim]
    posicao = -1
    for _ in range(ocorrencia + 1):
        posicao = corpo.index(ancora, posicao + 1)
    if parcial:
        trecho = '''seja pedaco: bytes[4]
para indice_pedaco de 0 ate 3 {
    adicione_byte(pedaco, ''' + parcial + '''[indice_pedaco])
}
grave_em(recurso, pedaco, 32, estado)
'''
    else:
        trecho = ''
    trecho += 'escreva("PONTO")\nenquanto verdadeiro {\n}\n'
    deslocamento = posicao if antes or parcial else posicao + len(ancora)
    corpo = corpo[:deslocamento] + '\n' + trecho + corpo[deslocamento:]
    return fonte[:inicio] + corpo + fonte[fim:]


class TestesCadastroRetomadaRS042N(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pasta = tempfile.TemporaryDirectory(prefix='rs_retomada_')
        cls.addClassCleanup(cls.pasta.cleanup)
        cls.executaveis, cls.fontes = {}, {}
        for nome in ('inicializar', 'salvar', 'reabrir'):
            fonte = carregar_fontes(RAIZ/f'exemplos/dados_rs/cadastro_{nome}_rs042n.rts').texto
            cls.fontes[nome] = fonte
            programa = analisar_programa(fonte)
            for nivel in range(9):
                cls.executaveis[nome, nivel] = cls.construir(programa, f'{nome}_{nivel}', nivel)
            for alvo in ('windows', 'linux'):
                assert compilar(programa, alvo, nivel=8, otimizar=True)

    @classmethod
    def construir(cls, programa, nome, nivel=8):
        destino = Path(cls.pasta.name)/(nome + ('.exe' if alvo_nativo() == 'windows' else ''))
        destino.write_bytes(compilar(programa, alvo_nativo(), nivel=nivel, otimizar=nivel > 0))
        if alvo_nativo() == 'linux':
            destino.chmod(0o700)
        return destino

    @classmethod
    def executar(cls, nome, pasta, nivel=8, entrada=None):
        return subprocess.run([str(cls.executaveis[nome, nivel])], cwd=pasta, input=entrada,
            capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=25)

    @staticmethod
    def iniciar_processo(executavel, pasta):
        return subprocess.Popen([str(executavel)], cwd=pasta, stdin=subprocess.PIPE,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding='utf-8', errors='replace')

    @staticmethod
    def preparar(pasta):
        pasta = Path(pasta)
        (pasta/'cadastro_a.rsd').write_bytes(envelopar(3, codificar(registros(29))))
        (pasta/'cadastro_b.rsd').write_bytes(envelopar(2, codificar(registros(17))))

    def conferir_leitura(self, pasta, geracao, recuperado, numero=29, nivel=8):
        r = self.executar('reabrir', pasta, nivel)
        esperado = f'{geracao}\n{int(recuperado)}\n1\n7\nAção 🌱\n6000\n{numero}\n'
        self.assertEqual((r.returncode, r.stdout), (0, esperado), r.stderr)

    def test_inicializacao_gravacao_alternada_e_oraculo_nove_niveis(self):
        for nivel in range(9):
            with self.subTest(nivel=nivel), tempfile.TemporaryDirectory() as pasta:
                r = self.executar('inicializar', pasta, nivel)
                self.assertEqual((r.returncode, r.stdout), (0, '0\n1\n'), r.stderr)
                self.assertEqual((Path(pasta)/'cadastro_a.rsd').read_bytes(), envelopar(1, codificar(())))
                for numero, geracao, nome in ((17, 2, 'b'), (29, 3, 'a'), (99, 4, 'b')):
                    anterior = (Path(pasta)/f'cadastro_{"a" if nome == "b" else "b"}.rsd').read_bytes()
                    r = self.executar('salvar', pasta, nivel, f'{numero}\n')
                    self.assertEqual((r.returncode, r.stdout), (0, f'{geracao-1}\n0\n{geracao}\n'), r.stderr)
                    self.assertEqual((Path(pasta)/f'cadastro_{nome}.rsd').read_bytes(), envelopar(geracao, codificar(registros(numero))))
                    self.assertEqual((Path(pasta)/f'cadastro_{"a" if nome == "b" else "b"}.rsd').read_bytes(), anterior)
                    self.conferir_leitura(pasta, geracao, False, numero, nivel)

    def test_encerramento_forcado_em_todas_fases_da_rotina_real(self):
        fases = (
            ('antes_invalidar', 'grave_em ( recurso , bloco , 32 , estado )', 0, True, None, 3, False),
            ('invalidacao_parcial', 'grave_em ( recurso , bloco , 32 , estado )', 0, True, 'bloco', 3, True),
            ('apos_invalidar', 'grave_em ( recurso , bloco , 32 , estado )', 0, False, None, 3, True),
            ('apos_sync_invalidacao', 'sincronize_arquivo ( recurso , estado )', 0, False, None, 3, True),
            ('apos_cabecalho', 'grave_em ( recurso , bloco , 0 , estado )', 0, False, None, 3, True),
            ('apos_primeiro_bloco', 'grave_em ( recurso , bloco , posicao + 40 , estado )', 0, False, None, 3, True),
            ('apos_sync_dados', 'sincronize_arquivo ( recurso , estado )', 1, False, None, 3, True),
            ('confirmacao_parcial', 'grave_em ( recurso , confirmacao , 32 , estado )', 0, True, 'confirmacao', 3, True),
            ('apos_confirmar', 'grave_em ( recurso , confirmacao , 32 , estado )', 0, False, None, 4, False),
            ('apos_sync_confirmacao', 'sincronize_arquivo ( recurso , estado )', 2, False, None, 4, False),
            ('apos_fechar', 'feche_arquivo ( recurso , estado )', 0, False, None, 4, False),
        )
        for nivel in (0, 8):
            for nome, ancora, ocorrencia, antes, parcial, geracao, recuperado in fases:
                with self.subTest(nivel=nivel, fase=nome), tempfile.TemporaryDirectory() as pasta:
                    self.preparar(pasta)
                    preservado = (Path(pasta)/'cadastro_a.rsd').read_bytes()
                    fonte = interromper_fonte(self.fontes['salvar'], ancora, ocorrencia, antes, parcial)
                    executavel = self.construir(analisar_programa(fonte), f'falha_{nome}_{nivel}', nivel)
                    processo = self.iniciar_processo(executavel, pasta)
                    try:
                        self.assertEqual(linha_processo(processo), '3\n')
                        processo.stdin.write('99\n'); processo.stdin.flush()
                        self.assertEqual(linha_processo(processo), 'PONTO\n')
                        processo.kill()  # TerminateProcess / SIGKILL, sem limpeza RS
                        processo.communicate(timeout=10)
                        self.assertNotEqual(processo.returncode, 0)
                    finally:
                        if processo.poll() is None:
                            processo.kill(); processo.communicate(timeout=10)
                    self.assertEqual((Path(pasta)/'cadastro_a.rsd').read_bytes(), preservado)
                    self.conferir_leitura(pasta, geracao, recuperado, 99 if geracao == 4 else 29, nivel)
                    # Uma gravacao posterior recupera/reutiliza a copia inativa.
                    r = self.executar('salvar', pasta, nivel, '71\n')
                    self.assertEqual((r.returncode, r.stdout), (0, f'{geracao}\n0\n{geracao+1}\n'), r.stderr)
                    self.conferir_leitura(pasta, geracao+1, False, 71, nivel)

    def test_trava_estavel_coordena_leitores_gravadores_e_reinicio_do_dono(self):
        fonte = '''inicio {
    seja trava: arquivo
    seja estado = 0
    abra_arquivo("cadastro_trava.rsl", trava, "alteracao", estado)
    bloqueie_arquivo(trava, estado)
    escreva(estado)
    seja aguardar = 0
    leia(aguardar)
    feche_arquivo(trava, estado)
}'''
        dono = self.construir(analisar_programa(fonte), 'dono_trava')
        for encerrar in ('normal', 'forcado'):
            with self.subTest(encerrar=encerrar), tempfile.TemporaryDirectory() as pasta:
                self.preparar(pasta)
                processo = self.iniciar_processo(dono, pasta)
                try:
                    self.assertEqual(linha_processo(processo), '0\n')
                    identidade = (Path(pasta)/'cadastro_trava.rsl').stat().st_ino
                    for nome in ('reabrir', 'salvar', 'inicializar'):
                        r = self.executar(nome, pasta, entrada='4\n')
                        self.assertEqual(r.returncode, 3, r.stderr)
                        self.assertEqual(r.stdout.splitlines()[0], '40')
                    if encerrar == 'forcado':
                        processo.kill(); processo.communicate(timeout=10)
                    else:
                        processo.communicate(input='0\n', timeout=10)
                    self.conferir_leitura(pasta, 3, False)
                    self.assertEqual((Path(pasta)/'cadastro_trava.rsl').stat().st_ino, identidade)
                finally:
                    if processo.poll() is None:
                        processo.kill(); processo.communicate(timeout=10)

    def test_geracao_obsoleta_de_dois_processos_nao_perde_atualizacao(self):
        with tempfile.TemporaryDirectory() as pasta:
            self.preparar(pasta)
            lento = self.iniciar_processo(self.executaveis['salvar', 8], pasta)
            try:
                self.assertEqual(linha_processo(lento), '3\n')
                rapido = self.executar('salvar', pasta, entrada='61\n')
                self.assertEqual((rapido.returncode, rapido.stdout), (0, '3\n0\n4\n'), rapido.stderr)
                antes = {p.name:p.read_bytes() for p in Path(pasta).iterdir()}
                saida, erros = lento.communicate(input='91\n', timeout=15)
                self.assertEqual((lento.returncode, saida), (3, '46\n4\n'), erros)
                self.assertEqual({p.name:p.read_bytes() for p in Path(pasta).iterdir()}, antes)
                self.conferir_leitura(pasta, 4, False, 61)
            finally:
                if lento.poll() is None:
                    lento.kill(); lento.communicate(timeout=10)

    def test_corrupcao_e_copias_truncadas_retornam_ultima_geracao_valida(self):
        original = envelopar(3, codificar(registros(29)))
        gerador = random.Random(4215)
        casos = [original[:n] for n in (0, 1, 8, 24, 32, 39, 40, 43, len(original)-1)]
        for _ in range(24):
            dados = bytearray(original); posicao = gerador.randrange(40, len(dados)); dados[posicao] ^= 1
            casos.append(bytes(dados))
        for dados in casos:
            with self.subTest(tamanho=len(dados)), tempfile.TemporaryDirectory() as pasta:
                self.preparar(pasta)
                (Path(pasta)/'cadastro_a.rsd').write_bytes(dados)
                self.conferir_leitura(pasta, 2, True, 17)

    def test_recusa_ausencia_total_corrupcao_total_geracao_igual_e_versao_futura(self):
        casos = ((None, None, 44), (b'', b'', 45),
            (envelopar(3, codificar(())), envelopar(3, codificar(())), 48),
            (envelopar(3, codificar(())), b'RSCN'+struct.pack('<I', 2)+envelopar(2, codificar(()))[8:], 49))
        for esquerda, direita, codigo in casos:
            with self.subTest(codigo=codigo), tempfile.TemporaryDirectory() as pasta:
                for nome, dados in (('a',esquerda),('b',direita)):
                    if dados is not None:
                        (Path(pasta)/f'cadastro_{nome}.rsd').write_bytes(dados)
                r = self.executar('reabrir', pasta)
                self.assertEqual((r.returncode,r.stdout),(3,str(codigo)+'\n'),r.stderr)
                r = self.executar('salvar', pasta, entrada='0\n')
                self.assertEqual((r.returncode,r.stdout),(3,str(codigo)+'\n'),r.stderr)
                for nome,dados in (('a',esquerda),('b',direita)):
                    arquivo = Path(pasta)/f'cadastro_{nome}.rsd'
                    self.assertEqual(arquivo.exists(), dados is not None)
                    if dados is not None:
                        self.assertEqual(arquivo.read_bytes(),dados)

    def test_inicializacao_nao_sobrescreve_cadastro_ou_copias_invalidas(self):
        for dados in (b'', envelopar(1, codificar(()))):
            with tempfile.TemporaryDirectory() as pasta:
                (Path(pasta)/'cadastro_a.rsd').write_bytes(dados)
                r = self.executar('inicializar', pasta)
                self.assertEqual(r.returncode,3,r.stderr)
                self.assertEqual(r.stdout.splitlines()[0],'50')
                self.assertEqual((Path(pasta)/'cadastro_a.rsd').read_bytes(),dados)

    def test_copia_fisica_grande_e_envelope_com_integridade_recalculada(self):
        casos = [envelopar(3, codificar(registros(29))) + bytes(8388649),
                 envelopar(0, codificar(())), envelopar(9223372036854775808, codificar(())),
                 envelopar(3, b'RSCV'+bytes(20))]
        for dados in casos:
            with tempfile.TemporaryDirectory() as pasta:
                self.preparar(pasta)
                (Path(pasta)/'cadastro_a.rsd').write_bytes(dados)
                self.conferir_leitura(pasta,2,True,17)

    def test_geracao_maxima_recusa_avanco_sem_estouro(self):
        with tempfile.TemporaryDirectory() as pasta:
            (Path(pasta)/'cadastro_a.rsd').write_bytes(envelopar(9223372036854775807, codificar(())))
            r = self.executar('salvar', pasta, entrada='0\n')
            self.assertEqual((r.returncode,r.stdout),(3,'9223372036854775807\n47\n9223372036854775807\n'),r.stderr)
            self.assertFalse((Path(pasta)/'cadastro_b.rsd').exists())

    def test_sobras_de_copia_anterior_nao_entram_no_cadastro_reduzido(self):
        fonte = '''importe "padrao/cadastro_retomada.rts" como disco
importe "padrao/cadastro_variavel.rts" como cad
inicio {
    seja leitura = disco.carregar()
    seja vazio = cad.criar()
    seja resposta = disco.salvar(empreste(vazio), leitura.geracao)
    escreva(resposta.codigo_erro)
}'''
        executavel = self.construir(programa_modulo(fonte), 'reduzir')
        with tempfile.TemporaryDirectory() as pasta:
            self.preparar(pasta)
            antes = (Path(pasta)/'cadastro_b.rsd').read_bytes()
            r = subprocess.run([str(executavel)],cwd=pasta,capture_output=True,text=True,timeout=20)
            self.assertEqual((r.returncode,r.stdout),(0,'0\n'),r.stderr)
            depois = (Path(pasta)/'cadastro_b.rsd').read_bytes()
            self.assertEqual(depois[:64],envelopar(4,codificar(())))
            self.assertEqual(depois[64:],antes[64:])
            r = self.executar('reabrir',pasta)
            self.assertEqual((r.returncode,r.stdout),(0,'4\n0\n0\n'),r.stderr)

    def test_diretorios_e_falha_de_consulta_nao_sao_cadastro_vazio(self):
        with tempfile.TemporaryDirectory() as pasta:
            self.preparar(pasta)
            (Path(pasta)/'cadastro_b.rsd').unlink()
            (Path(pasta)/'cadastro_b.rsd').mkdir()
            r = self.executar('reabrir',pasta)
            self.assertEqual((r.returncode,r.stdout),(3,'41\n'),r.stderr)

    def test_senao_mesma_linha_preserva_origem_e_descarta_donos(self):
        fonte = '''inicio {
    se verdadeiro {
        seja dados: bytes
        adicione_byte(dados, 1)
    } senao {
        seja texto: texto
        copie(texto, "RS")
    }
    escreva(7)
}'''.replace('seja texto:','seja nome:').replace('copie(texto,','copie(nome,')
        programa = analisar_programa(fonte)
        descarte = programa.instrucoes[0][2][-1]
        self.assertEqual((descarte.origem.linha,descarte.origem.coluna),(5,5))
        executavel = self.construir(programa, 'origem_descarte')
        with tempfile.TemporaryDirectory() as pasta:
            r=subprocess.run([str(executavel)],cwd=pasta,capture_output=True,text=True,timeout=15)
            self.assertEqual((r.returncode,r.stdout),(0,'7\n'),r.stderr)


if __name__ == '__main__':
    unittest.main()
