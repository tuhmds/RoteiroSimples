"""RS 0.41 — validação estrutural e dinâmica de ELF PIE e PE com ASLR.

Não depende de ferramentas externas (objdump, readelf ou PE viewers).
Lê os cabeçalhos diretamente com struct e executa binários nativos.
"""
import os
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import time
import unittest

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

from backend import compilar
from compilador.parser import analisar_programa


FONTE = """inicio {
    seja valor = 17
    para numero de 1 ate 5 {
        valor = valor + numero
    }
    escreva(valor)
}"""


def binario(alvo, nivel=8, fonte=FONTE):
    return compilar(analisar_programa(fonte), alvo,
                    otimizar=nivel > 0, nivel=nivel)


def ler_elf(imagem):
    cab = struct.unpack_from('<16sHHIQQQIHHHHHH', imagem)
    assert cab[0][:4] == b'\x7fELF'
    tipo, maquina, entrada, inicio_programas = cab[1], cab[2], cab[4], cab[5]
    tamanho, quantidade = cab[9], cab[10]
    programas = [
        struct.unpack_from('<IIQQQQQQ', imagem, inicio_programas + i * tamanho)
        for i in range(quantidade)
    ]
    return tipo, maquina, entrada, programas


def ler_pe(imagem):
    assert imagem[:2] == b'MZ'
    inicio_pe, = struct.unpack_from('<I', imagem, 0x3c)
    assert imagem[inicio_pe:inicio_pe+4] == b'PE\x00\x00'
    maquina, quantidade = struct.unpack_from('<HH', imagem, inicio_pe + 4)
    tamanho_opcional, caracteristicas = struct.unpack_from(
        '<HH', imagem, inicio_pe+20)
    inicio_opcional = inicio_pe+24
    assert struct.unpack_from('<H', imagem, inicio_opcional)[0] == 0x20b
    entrada, = struct.unpack_from('<I', imagem, inicio_opcional+16)
    base, = struct.unpack_from('<Q', imagem, inicio_opcional+24)
    tamanho_imagem, tamanho_cabecalho = struct.unpack_from(
        '<II', imagem, inicio_opcional+56)
    protecoes, = struct.unpack_from('<H', imagem, inicio_opcional+70)
    rva_reloc, tamanho_reloc = struct.unpack_from(
        '<II', imagem, inicio_opcional+112+8*5)
    inicio_secoes = inicio_opcional + tamanho_opcional
    secoes = {}
    for n in range(quantidade):
        pos = inicio_secoes + n*40
        nome, tamanho_virtual, rva, tamanho_bruto, offset = (
            struct.unpack_from('<8sIIII', imagem, pos))
        flags, = struct.unpack_from('<I', imagem, pos+36)
        secoes[nome.rstrip(b'\0').decode('ascii')] = {
            'rva': rva,
            'virtual': tamanho_virtual,
            'bruto': tamanho_bruto,
            'offset': offset,
            'flags': flags,
        }
    return {
        'maquina': maquina, 'quantidade': quantidade,
        'caracteristicas': caracteristicas,
        'entrada': entrada, 'base': base,
        'tamanho_imagem': tamanho_imagem, 'tamanho_cabecalho': tamanho_cabecalho,
        'protecoes': protecoes,
        'relocalizacoes': (rva_reloc, tamanho_reloc),
        'secoes': secoes,
    }


def trecho_rva(imagem, secoes, rva, quantidade):
    for s in secoes.values():
        if s['rva'] <= rva and rva+quantidade <= s['rva']+s['virtual']:
            posicao = s['offset'] + rva-s['rva']
            return imagem[posicao:posicao+quantidade]
    raise AssertionError(f'RVA fora das seções: {rva:#x}')


class TestesProtecoesExecutaveisRS041(unittest.TestCase):
    def test_linux_elf_pie_e_pilha_sem_permissao_de_execucao(self):
        for nivel in (0, 4, 8):
            with self.subTest(nivel=nivel):
                imagem = binario('linux', nivel)
                tipo, maquina, entrada, programas = ler_elf(imagem)
                self.assertEqual(tipo, 3)       # ET_DYN, posição independente
                self.assertEqual(maquina, 62)    # AMD64
                self.assertEqual(entrada, 0x100)
                self.assertIn(len(programas), (2, 3))
                carregavel = next(p for p in programas if p[0] == 1)
                pilha = next(p for p in programas if p[0] == 0x6474e551)
                self.assertEqual(carregavel[1], 5)     # leitura + execução
                self.assertEqual(carregavel[2:5], (0, 0, 0))
                self.assertEqual(carregavel[5], carregavel[6])
                if len(programas) == 2:
                    self.assertEqual(carregavel[5], len(imagem))
                else:
                    dados = next(p for p in programas if p[0] == 1 and p[1] == 4)
                    self.assertEqual(dados[2] + dados[5], len(imagem))
                    self.assertLess(carregavel[5], len(imagem))
                self.assertEqual(pilha[1], 6)         # leitura + escrita; sem X
                self.assertEqual((pilha[5], pilha[6]), (0, 0))

    def test_linux_dados_constantes_isolados_do_codigo(self):
        fonte = """inicio {
            escreva("Mensagem constante e segura")
            escreva("Outra mensagem na secao de leitura")
        }"""
        for nivel in (0, 4, 8):
            with self.subTest(nivel=nivel):
                imagem = binario('linux', nivel, fonte)
                tipo, maquina, entrada, programas = ler_elf(imagem)
                self.assertEqual(tipo, 3)
                cargas = [p for p in programas if p[0] == 1]
                self.assertEqual(len(cargas), 2)
                codigo, dados = cargas
                self.assertEqual(codigo[1], 5) # leitura e execução
                self.assertEqual(dados[1], 4) # somente leitura
                self.assertNotEqual(dados[1] & 1, 1)
                self.assertNotEqual(codigo[1] & 2, 2)
                self.assertEqual(dados[2], dados[3])
                self.assertEqual(dados[2] % 4096, 0)
                self.assertGreaterEqual(dados[2], codigo[5])
                self.assertEqual(dados[2] + dados[5], len(imagem))
                self.assertIn(b'Mensagem constante e segura',
                              imagem[dados[2]:dados[2] + dados[5]])
                self.assertFalse(any(p[1] & 2 and p[1] & 1 for p in cargas))

    def test_linux_mensagens_posicionadas_funcionam_em_todos_niveis(self):
        if sys.platform != 'linux' or os.uname().machine != 'x86_64':
            self.skipTest('Linux x86-64 necessário.')
        fonte = """inicio {
            escreva("Mensagem constante e segura")
            escreva("Outra mensagem na secao de leitura")
        }"""
        with tempfile.TemporaryDirectory() as pasta:
            for nivel in range(9):
                with self.subTest(nivel=nivel):
                    caminho = Path(pasta)/f'mensagem_{nivel}'
                    caminho.write_bytes(binario('linux', nivel, fonte))
                    caminho.chmod(0o700)
                    r = subprocess.run([str(caminho)], capture_output=True,
                                       text=True, encoding='utf-8', timeout=12)
                    self.assertEqual((r.returncode, r.stdout),
                                     (0, 'Mensagem constante e segura\n'
                                      'Outra mensagem na secao de leitura\n'),
                                     r.stderr)

    def test_linux_mapeia_dados_sem_execucao(self):
        if sys.platform != 'linux' or os.uname().machine != 'x86_64':
            self.skipTest('Exige Linux x86-64.')
        fonte = """inicio {
            seja resposta = 0
            leia(resposta)
            escreva("Dado constante isolado")
        }"""
        with tempfile.TemporaryDirectory() as pasta:
            programa = Path(pasta)/'aplicacao'
            programa.write_bytes(binario('linux', 8, fonte))
            programa.chmod(0o700)
            processo = subprocess.Popen([str(programa)], stdin=subprocess.PIPE,
                                        stdout=subprocess.PIPE,stderr=subprocess.PIPE,
                                        text=True,encoding='utf-8')
            try:
                regioes=[]
                for tentativa in range(40):
                    linhas=(Path('/proc')/str(processo.pid)/'maps').read_text().splitlines()
                    regioes=[l for l in linhas if l.endswith(str(programa))]
                    if len(regioes)>=2:
                        break
                    time.sleep(0.025)
                permissoes={l.split()[1] for l in regioes}
                self.assertIn('r-xp', permissoes, regioes)
                self.assertIn('r--p', permissoes, regioes)
                self.assertFalse(any('w' in p and 'x' in p for p in permissoes))
                resposta,erro=processo.communicate('1\n',timeout=10)
                self.assertEqual((processo.returncode,resposta),
                                 (0,'Dado constante isolado\n'),erro)
            finally:
                if processo.poll() is None:
                    processo.kill()
                    processo.communicate()

    def test_windows_pe_posicionavel_com_realocacao_em_uso(self):
        for nivel in (0, 4, 8):
            with self.subTest(nivel=nivel):
                imagem = binario('windows', nivel)
                pe = ler_pe(imagem)
                self.assertEqual(pe['maquina'], 0x8664)
                self.assertEqual(pe['quantidade'], 6)
                self.assertEqual(pe['caracteristicas'] & 1, 0)
                self.assertEqual(pe['protecoes'] & 0x140, 0x140)
                self.assertEqual(pe['protecoes'] & 0x20, 0)  # alta entropia ainda não liberada
                self.assertEqual(pe['base'], 0x140000000)
                self.assertEqual(set(pe['secoes']),
                                 {'.text', '.idata', '.rdata', '.reloc',
                                  '.pdata', '.xdata'})
                self.assertGreaterEqual(pe['tamanho_cabecalho'], 0x400)
                self.assertGreater(pe['tamanho_imagem'], pe['secoes']['.reloc']['rva'])
                self.assertEqual(pe['secoes']['.text']['flags'] & 0xA0000000,
                                 0x20000000)  # executável, não gravável
                self.assertEqual(pe['secoes']['.reloc']['flags'] & 0xA0000000, 0)
                entrada = pe['entrada']
                codigo = trecho_rva(imagem, pe['secoes'], entrada, 12)
                self.assertEqual(codigo[:2], b'\x48\xB8') # MOVABS RAX
                self.assertEqual(codigo[10:12], b'\xFF\xE0') # JMP RAX
                endereco_original, = struct.unpack_from('<Q', codigo, 2)
                self.assertEqual(endereco_original, pe['base'] + 0x1000)
                rva, tamanho = pe['relocalizacoes']
                self.assertEqual(rva, pe['secoes']['.reloc']['rva'])
                self.assertEqual(tamanho, 12)
                pagina, bloco, item, preenchimento = struct.unpack(
                    '<IIHH', trecho_rva(imagem, pe['secoes'], rva, tamanho))
                self.assertEqual(bloco, 12)
                self.assertEqual(pagina, (entrada+2) & ~0xfff)
                self.assertEqual(item, (10<<12) | ((entrada+2) & 0xfff))
                self.assertEqual(preenchimento, 0)
                # Simula o delta aplicado ao endereço de entrada:
                # se a imagem for movida, o salto deve alcançar .text.
                desvio = 0x356780000
                self.assertEqual(endereco_original + desvio,
                                 pe['base'] + desvio + 0x1000)

    def test_cabecalhos_diferem_do_formato_fixo_anterior(self):
        linux = binario('linux', 0)
        windows = binario('windows', 0)
        self.assertNotEqual(struct.unpack_from('<H', linux, 16)[0], 2)
        self.assertNotEqual(
            struct.unpack_from('<I', windows,
                               struct.unpack_from('<I',windows,0x3c)[0]+24+16)[0],
            0x1000,
        )

    def test_execucao_nativa_em_ambas_estrategias_e_nove_niveis(self):
        if sys.platform == 'linux' and os.uname().machine != 'x86_64':
            self.skipTest('Linux x86-64 obrigatório.')
        if sys.platform not in ('linux','win32'):
            self.skipTest('Windows ou Linux obrigatório.')
        alvo = 'windows' if sys.platform == 'win32' else 'linux'
        with tempfile.TemporaryDirectory() as pasta:
            for nivel in range(9):
                with self.subTest(nivel=nivel):
                    arquivo = Path(pasta)/(
                        f'programa_{nivel}.exe' if alvo=='windows'
                        else f'programa_{nivel}')
                    arquivo.write_bytes(binario(alvo,nivel))
                    if alvo == 'linux':
                        arquivo.chmod(0o700)
                    resultado = subprocess.run([str(arquivo)],
                                               capture_output=True, text=True,
                                               encoding='utf-8', timeout=12)
                    self.assertEqual((resultado.returncode,resultado.stdout),
                                     (0,'32\n'),resultado.stderr)

    def test_linux_endereco_de_carregamento_aleatorio_observavel(self):
        if sys.platform != 'linux' or os.uname().machine != 'x86_64':
            self.skipTest('Exige Linux x86-64.')
        arquivo_aleatoriedade = Path('/proc/sys/kernel/randomize_va_space')
        if not arquivo_aleatoriedade.is_file() or (
                arquivo_aleatoriedade.read_text().strip() == '0'):
            self.skipTest('Núcleo não informou ASLR habilitado.')
        programa = """inicio {
            seja valor = 0
            leia(valor)
            escreva(valor)
        }"""
        bases = []
        with tempfile.TemporaryDirectory() as pasta:
            caminho = Path(pasta)/'programa'
            caminho.write_bytes(binario('linux',8,programa))
            caminho.chmod(0o700)
            for _ in range(3):
                processo = subprocess.Popen([str(caminho)],stdin=subprocess.PIPE,
                                            stdout=subprocess.PIPE,stderr=subprocess.PIPE,
                                            text=True,encoding='utf-8')
                try:
                    linhas = []
                    for _ in range(25):
                        linhas = (Path('/proc')/str(processo.pid)/'maps').read_text().splitlines()
                        encontrados = [x for x in linhas if x.endswith(str(caminho))]
                        if encontrados:
                            break
                        time.sleep(0.015)
                    self.assertTrue(encontrados, 'Processo PIE não apareceu em /proc/maps')
                    self.assertTrue(any(x.split()[1] == 'r-xp' for x in encontrados))
                    endereco = int(encontrados[0].split('-')[0], 16)
                    bases.append(endereco)
                    pilha = [x for x in linhas if '[stack]' in x]
                    self.assertTrue(pilha)
                    self.assertNotIn('x',pilha[0].split()[1])
                    saida,erro = processo.communicate('31\n',timeout=10)
                    self.assertEqual((processo.returncode,saida),(0,'31\n'),erro)
                finally:
                    if processo.poll() is None:
                        processo.kill()
                        processo.communicate()
        self.assertGreater(len(set(bases)),1,
                           f'Não foi observada aleatorização em 3 processos: {bases!r}')


if __name__ == '__main__':
    unittest.main()
