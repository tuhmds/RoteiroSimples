"""RS 0.39: publicação por renomeação, caminhos validados e bloqueio.

Testes de integração em processos nativos Windows/Linux. Falhas entre etapas
são injetadas por encerramento determinístico do processo RS.
"""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(RAIZ))
from compilador.parser import analisar_programa
from compilador.erros import ErroCompilacao
from backend import compilar


def alvo():
    if sys.platform == 'win32':
        return 'windows'
    if sys.platform == 'linux' and os.uname().machine == 'x86_64':
        return 'linux'
    raise unittest.SkipTest('Requer Windows ou Linux x86-64.')


def construir(pasta,nome,fonte,nivel=8):
    programa = analisar_programa(fonte)
    destino = Path(pasta) / (nome + ('.exe' if alvo() == 'windows' else ''))
    destino.write_bytes(compilar(programa,alvo(),otimizar=nivel>0,nivel=nivel))
    if sys.platform!='win32':
        destino.chmod(0o700)
    return destino


def executar(programa,pasta):
    return subprocess.run([str(programa)],cwd=pasta,capture_output=True,
                          text=True,encoding='utf-8',errors='replace',timeout=18)


class TestesRS039(unittest.TestCase):
    def test_publicacao_renomeia_arquivo_fechado_e_substitui_completo(self):
        fonte = """inicio {
            seja arq: arquivo
            seja bloco: bytes[5]
            seja estado = 0
            abra_arquivo("provisorio.rsd", arq, "novo", estado)
            se estado != 0 {
                encerre(11)
            }
            adicione_byte(bloco, 82)
            adicione_byte(bloco, 83)
            adicione_byte(bloco, 0)
            adicione_byte(bloco, 255)
            grave_em(arq, bloco, 0, estado)
            se estado != 4 {
                encerre(12)
            }
            sincronize_arquivo(arq, estado)
            se estado != 0 {
                encerre(13)
            }
            feche_arquivo(arq, estado)
            se estado != 0 {
                encerre(14)
            }
            publique_arquivo("provisorio.rsd", "banco.rsd", estado)
            escreva(estado)
        }"""
        with tempfile.TemporaryDirectory() as pasta:
            for nivel in range(9):
                with self.subTest(nivel=nivel):
                    (Path(pasta)/'banco.rsd').write_bytes(b'ORIGINAL-SEM-CORRUPCAO')
                    dest=construir(pasta,f'publicar_{nivel}',fonte,nivel)
                    r=executar(dest,pasta)
                    self.assertEqual((r.returncode,r.stdout),(0,'0\n'),r.stderr)
                    self.assertEqual((Path(pasta)/'banco.rsd').read_bytes(),b'RS\x00\xff')
                    self.assertFalse((Path(pasta)/'provisorio.rsd').exists())

    def test_falha_injetada_antes_de_publicar_preserva_destino(self):
        fonte = """inicio {
            seja arq: arquivo
            seja bloco: bytes[8]
            seja estado = 0
            abra_arquivo("provisorio.rsd", arq, "novo", estado)
            se estado != 0 {
                encerre(2)
            }
            adicione_byte(bloco, 21)
            grave_em(arq, bloco, 0, estado)
            sincronize_arquivo(arq, estado)
            feche_arquivo(arq, estado)
            // Falha injetada: encerra antes da troca.
            encerre(99)
            publique_arquivo("provisorio.rsd","banco.rsd",estado)
        }"""
        with tempfile.TemporaryDirectory() as pasta:
            (Path(pasta)/'banco.rsd').write_bytes(b'VERSAO_ANTIGA')
            r=executar(construir(pasta,'falha_antes',fonte),pasta)
            self.assertEqual(r.returncode,99,r.stderr)
            self.assertEqual((Path(pasta)/'banco.rsd').read_bytes(),b'VERSAO_ANTIGA')
            self.assertEqual((Path(pasta)/'provisorio.rsd').read_bytes(),b'\x15')

    def test_falha_injetada_depois_da_publicacao_tem_nova_versao_completa(self):
        fonte = """inicio {
            seja arq: arquivo
            seja bloco: bytes[8]
            seja estado = 0
            abra_arquivo("provisorio.rsd",arq,"novo",estado)
            adicione_byte(bloco,1)
            adicione_byte(bloco,2)
            adicione_byte(bloco,3)
            grave_em(arq,bloco,0,estado)
            sincronize_arquivo(arq,estado)
            feche_arquivo(arq,estado)
            publique_arquivo("provisorio.rsd","banco.rsd",estado)
            se estado != 0 {
                encerre(7)
            }
            // Falha injetada: encerra imediatamente depois de publicar.
            encerre(98)
        }"""
        with tempfile.TemporaryDirectory() as pasta:
            (Path(pasta)/'banco.rsd').write_bytes(b'VERSAO_ANTIGA')
            r=executar(construir(pasta,'falha_depois',fonte),pasta)
            self.assertEqual(r.returncode,98,r.stderr)
            self.assertEqual((Path(pasta)/'banco.rsd').read_bytes(),b'\x01\x02\x03')

    def test_aplicacao_completa_republica_versao_sem_sobras(self):
        fonte = (RAIZ/'exemplos'/'aplicacoes'/'publicar_banco_rs039.rts').read_text(
            encoding='utf-8')
        with tempfile.TemporaryDirectory() as pasta:
            # Este exemplo importa modulo da biblioteca padrao; usar a
            # compilacao completa da CLI, que resolve as importacoes.
            origem = Path(pasta)/'publicacao_real.rts'
            origem.write_text(fonte, encoding='utf-8')
            programa = Path(pasta)/('publicacao_real.exe' if alvo() == 'windows'
                                    else 'publicacao_real')
            saida = subprocess.run([
                sys.executable, str(RAIZ/'compilar.py'), str(origem),
                '--alvo', alvo(), '-O', '8', '-o', str(programa)],
                capture_output=True, text=True, encoding='utf-8',
                errors='replace', timeout=45)
            self.assertEqual(saida.returncode,0,saida.stderr+saida.stdout)
            (Path(pasta)/'banco.rsd').write_bytes(b'VERSAO_ANTIGA_COM_MUITOS_BYTES')
            for passagem in range(2):
                with self.subTest(passagem=passagem):
                    r=executar(programa,pasta)
                    self.assertEqual((r.returncode,r.stdout),
                                     (0,'Nova versao publicada\n'),r.stderr)
                    self.assertEqual((Path(pasta)/'banco.rsd').read_bytes(),
                                     b'RSDB\x01\x64')
                    self.assertFalse((Path(pasta)/'rascunho.rsd').exists())

    def test_publicacao_origem_ausente_nao_destroi_destino(self):
        fonte = """inicio {
            seja estado = 0
            publique_arquivo("naoexiste.rsd","banco.rsd",estado)
            escreva(estado)
        }"""
        with tempfile.TemporaryDirectory() as pasta:
            (Path(pasta)/'banco.rsd').write_bytes(b'NAO_TOQUE')
            r=executar(construir(pasta,'ausente',fonte),pasta)
            self.assertEqual((r.returncode,r.stdout),(0,'-8\n'),r.stderr)
            self.assertEqual((Path(pasta)/'banco.rsd').read_bytes(),b'NAO_TOQUE')

    def test_nome_variavel_aceita_basename_normal(self):
        fonte = """inicio {
            seja nome: texto[40]
            copie(nome, "entregas_2026.rsd")
            seja arq: arquivo
            seja dado: bytes[5]
            seja estado = 0
            abra_arquivo(nome, arq, "novo", estado)
            escreva(estado)
            adicione_byte(dado, 19)
            grave_em(arq,dado,0,estado)
            escreva(estado)
            feche_arquivo(arq,estado)
            escreva(estado)
        }"""
        with tempfile.TemporaryDirectory() as pasta:
            for nivel in range(9):
                with self.subTest(nivel=nivel):
                    arquivo=Path(pasta)/'entregas_2026.rsd'
                    if arquivo.exists():arquivo.unlink()
                    r=executar(construir(pasta,f'nome_{nivel}',fonte,nivel),pasta)
                    self.assertEqual((r.returncode,r.stdout),(0,'0\n1\n0\n'),r.stderr)
                    self.assertEqual(arquivo.read_bytes(),b'\x13')

    def test_nome_variavel_bloqueia_travessia_barras_nul_e_vazio(self):
        casos=[
            'copie(nome, "../outro.bin")',
            'copie(nome, "sub/pasta.bin")',
            'copie(nome, "..")',
            'copie(nome, "-nao.bin")',
            'copie(nome, ".oculto")',
            'copie(nome, "nome:ads")',
            'copie(nome, "nome\\\\arquivo")',
            'limpe(nome)',
        ]
        with tempfile.TemporaryDirectory() as pasta:
            for idx,preparacao in enumerate(casos):
                with self.subTest(caso=preparacao):
                    fonte=f"""inicio {{
                        seja nome: texto[80]
                        {preparacao}
                        seja arq: arquivo
                        seja estado = 0
                        abra_arquivo(nome,arq,"novo",estado)
                        escreva(estado)
                    }}"""
                    r=executar(construir(pasta,f'invalido_{idx}',fonte),pasta)
                    self.assertEqual((r.returncode,r.stdout),(0,'-3\n'),r.stderr)
            self.assertFalse((Path(pasta)/'outro.bin').exists())
            self.assertFalse((Path(pasta)/'nome:ads').exists())

    def test_nome_variavel_rejeita_mais_de_240(self):
        longo = 'a'*241
        fonte=f"""inicio {{
            seja nome: texto[256]
            copie(nome,"{longo}")
            seja arq: arquivo
            seja estado = 0
            abra_arquivo(nome, arq,"novo",estado)
            escreva(estado)
        }}"""
        with tempfile.TemporaryDirectory() as pasta:
            r=executar(construir(pasta,'comprimento',fonte),pasta)
            self.assertEqual((r.returncode,r.stdout),(0,'-3\n'),r.stderr)

    def test_nomes_de_dispositivos_reservados_rejeitados_na_compilacao(self):
        for nome in ('CON', 'nul.rsd', 'PrN.txt', 'aux', 'COM1', 'lpt9.rsd'):
            with self.subTest(nome=nome):
                fonte=f"""inicio {{
                    seja arq: arquivo
                    seja estado = 0
                    abra_arquivo("{nome}", arq, "novo", estado)
                }}"""
                with self.assertRaises(ErroCompilacao):
                    analisar_programa(fonte)

    def test_nome_dinamico_de_dispositivo_reservado_no_windows(self):
        if alvo() != 'windows':
            self.skipTest('Dispositivos DOS são específicos do Windows.')
        with tempfile.TemporaryDirectory() as pasta:
            for indice,nome in enumerate(('NUL','con.rsd','COM1','lpt9.db','aux')):
                with self.subTest(nome=nome):
                    fonte=f"""inicio {{
                        seja caminho: texto[40]
                        copie(caminho, "{nome}")
                        seja arq: arquivo
                        seja estado = 0
                        abra_arquivo(caminho, arq, "novo", estado)
                        escreva(estado)
                    }}"""
                    r=executar(construir(pasta,f'device_{indice}',fonte),pasta)
                    self.assertEqual((r.returncode,r.stdout),(0,'-3\n'),r.stderr)

    def test_bloqueio_com_recurso_aberto_e_fechamento(self):
        fonte = """inicio {
            seja arq: arquivo
            seja estado = 0
            abra_arquivo("trava.rsd",arq,"alteracao",estado)
            escreva(estado)
            bloqueie_arquivo(arq,estado)
            escreva(estado)
            feche_arquivo(arq,estado)
            escreva(estado)
            bloqueie_arquivo(arq,estado)
            escreva(estado)
        }"""
        with tempfile.TemporaryDirectory() as pasta:
            r=executar(construir(pasta,'trava',fonte),pasta)
            self.assertEqual((r.returncode,r.stdout),(0,'0\n0\n0\n-3\n'),r.stderr)

    def test_exclusividade_de_abertura_no_windows(self):
        if alvo() != 'windows':
            self.skipTest('Compartilhamento exclusivo da API Windows.')
        fonte = """inicio {
            seja arq: arquivo
            seja estado = 0
            abra_arquivo("ocupado.rsd", arq, "alteracao", estado)
            escreva(estado)
        }"""
        with tempfile.TemporaryDirectory() as pasta:
            arquivo=Path(pasta)/'ocupado.rsd'
            arquivo.write_bytes(b'ORIGINAL')
            exe=construir(pasta,'ocupar',fonte)
            with arquivo.open('rb') as mantido:
                r=executar(exe,pasta)
                self.assertEqual((r.returncode,r.stdout),(0,'-1\n'),r.stderr)
            r=executar(exe,pasta)
            self.assertEqual((r.returncode,r.stdout),(0,'0\n'),r.stderr)
            self.assertEqual(arquivo.read_bytes(),b'ORIGINAL')

    def test_concorrencia_de_flock_no_linux(self):
        if alvo() != 'linux':
            self.skipTest('Bloqueio de flock Linux; Windows tem exclusão por abertura.')
        import fcntl
        fonte = """inicio {
            seja arq: arquivo
            seja estado = 0
            abra_arquivo("trava.rsd", arq, "alteracao",estado)
            escreva(estado)
            bloqueie_arquivo(arq,estado)
            escreva(estado)
            feche_arquivo(arq,estado)
        }"""
        with tempfile.TemporaryDirectory() as pasta:
            arquivo=Path(pasta)/'trava.rsd'
            arquivo.write_bytes(b't')
            prog=construir(pasta,'tentar',fonte)
            with arquivo.open('rb') as mantido:
                fcntl.flock(mantido, fcntl.LOCK_EX | fcntl.LOCK_NB)
                resultado=executar(prog,pasta)
                self.assertEqual((resultado.returncode,resultado.stdout),(0,'0\n-7\n'),resultado.stderr)
            resultado=executar(prog,pasta)
            self.assertEqual((resultado.returncode,resultado.stdout),(0,'0\n0\n'),resultado.stderr)

    def test_comandos_invalidos_rejeitados_estaticamente(self):
        fontes=[
            'inicio {\n seja estado=0\n publique_arquivo("x/a", "b", estado)\n}',
            'inicio {\n seja estado=0\n publique_arquivo("a","a",estado)\n}',
            'inicio {\n seja estado=0\n publique_arquivo("../a","b",estado)\n}',
            'inicio {\n seja estado=0\n publique_arquivo(".oculto","b",estado)\n}',
            'inicio {\n seja arq: arquivo\n seja estado=0\n bloqueie_arquivo(arq, arq)\n}',
            'inicio {\n seja arq: arquivo\n seja estado=0\n abra_arquivo(arq, arq, "novo", estado)\n}',
        ]
        for fonte in fontes:
            with self.subTest(fonte=fonte):
                with self.assertRaises(ErroCompilacao):
                    analisar_programa(fonte)


if __name__ == '__main__':
    unittest.main()
