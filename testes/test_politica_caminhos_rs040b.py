"""RS 0.40B: todas as APIs evitam seguir um link no componente final.

Não testa confinamento de diretórios ancestrais: essa garantia ainda não
existe e requer diretório-base e política de resolução próprios.
"""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

from compilador.parser import analisar_programa
from backend import compilar
from backend.politica_caminhos import (SINALIZADORES_LINUX,
                                     ATRIBUTOS_WINDOWS_SEM_SEGUIR_LINK)


def plataforma():
    if sys.platform == 'win32':
        return 'windows'
    if sys.platform == 'linux' and os.uname().machine == 'x86_64':
        return 'linux'
    raise unittest.SkipTest('É necessário Windows ou Linux x86-64.')


def construir(codigo, destino, nivel):
    programa = analisar_programa(codigo)
    caminho = Path(destino) / ('programa.exe' if plataforma() == 'windows' else 'programa')
    caminho.write_bytes(compilar(programa, plataforma(), otimizar=nivel > 0, nivel=nivel))
    if sys.platform == 'linux':
        caminho.chmod(0o700)
    return caminho


def executar(executavel, pasta):
    return subprocess.run([str(executavel)], cwd=pasta, capture_output=True,
                          text=True, encoding='utf-8', errors='replace', timeout=15)


OPERACOES = {
    'gravacao_inteira': """inicio {
        seja buffer: texto[16]
        copie(buffer, "ALTERADO")
        grave_arquivo("referencia.rsd", buffer)
        escreva(123)
    }""",
    'leitura_inteira': """inicio {
        seja buffer: texto[32]
        carregue_arquivo("referencia.rsd", buffer)
        escreva(123)
    }""",
    'gravacao_posicional': """inicio {
        seja buffer: bytes[16]
        adicione_byte(buffer, 77)
        seja estado = 0
        grave_trecho("referencia.rsd", buffer, 0, estado)
        escreva(estado)
    }""",
    'leitura_posicional': """inicio {
        seja buffer: bytes[16]
        seja estado = 0
        carregue_trecho("referencia.rsd", buffer, 0, 8, estado)
        escreva(estado)
    }""",
    'recurso_alteracao': """inicio {
        seja arquivo_atual: arquivo
        seja estado = 0
        abra_arquivo("referencia.rsd", arquivo_atual, "alteracao", estado)
        escreva(estado)
        feche_arquivo(arquivo_atual, estado)
    }""",
    'recurso_leitura': """inicio {
        seja arquivo_atual: arquivo
        seja estado = 0
        abra_arquivo("referencia.rsd", arquivo_atual, "leitura", estado)
        escreva(estado)
        feche_arquivo(arquivo_atual, estado)
    }""",
}


class TestesPoliticaCaminhosRS040B(unittest.TestCase):
    def test_politica_linux_com_no_follow_e_close_on_exec(self):
        self.assertEqual(ATRIBUTOS_WINDOWS_SEM_SEGUIR_LINK, 0x00200080)
        for nome, sinais in SINALIZADORES_LINUX.items():
            with self.subTest(modo=nome):
                self.assertTrue(sinais & 0x20000)  # O_NOFOLLOW
                self.assertTrue(sinais & 0x80000)  # O_CLOEXEC

    def test_link_final_nao_altera_arquivo_externo(self):
        plataforma()
        with tempfile.TemporaryDirectory() as raiz:
            externo = Path(raiz)/'exterior'
            interno = Path(raiz)/'interno'
            externo.mkdir()
            interno.mkdir()
            alvo_externo = externo/'segredo.rsd'
            conteudo = b'DADOS_EXTERIORES_IMPORTANTES'
            alvo_externo.write_bytes(conteudo)
            referencia = interno/'referencia.rsd'
            try:
                referencia.symlink_to(alvo_externo)
            except (OSError, NotImplementedError) as exc:
                self.skipTest(f'Plataforma não permite criar symlink de teste: {exc}')
            for nome, codigo in OPERACOES.items():
                for nivel in (0, 8):
                    with self.subTest(operacao=nome, nivel=nivel):
                        exe = construir(codigo, interno, nivel)
                        r = executar(exe, interno)
                        if nome.endswith('inteira'):
                            self.assertNotEqual(r.returncode, 0,
                                                (nome, r.stdout, r.stderr))
                            self.assertNotIn('123', r.stdout)
                        else:
                            self.assertEqual(r.returncode, 0, r.stderr)
                            self.assertIn('-1', r.stdout)
                        self.assertEqual(alvo_externo.read_bytes(), conteudo)
                        self.assertTrue(referencia.is_symlink())
            # Um ataque por link para diretório não pode criar arquivo externo
            # como efeito das operações acima.
            self.assertEqual(list(externo.iterdir()), [alvo_externo])

    def test_arquivos_regulares_continuam_funcionando(self):
        fonte = """inicio {
            seja texto_atual: texto[20]
            seja bytes_atual: bytes[8]
            seja recurso: arquivo
            seja estado = 0
            copie(texto_atual, "COMUM")
            grave_arquivo("referencia.rsd", texto_atual)
            carregue_arquivo("referencia.rsd", texto_atual)
            escreva(texto_atual)
            adicione_byte(bytes_atual, 88)
            grave_trecho("referencia.rsd", bytes_atual, 2, estado)
            escreva(estado)
            carregue_trecho("referencia.rsd", bytes_atual, 2, 1, estado)
            escreva(estado)
            escreva(bytes_atual[0])
            abra_arquivo("referencia.rsd", recurso, "alteracao", estado)
            escreva(estado)
            feche_arquivo(recurso, estado)
            escreva(estado)
        }"""
        for nivel in (0, 4, 8):
            with self.subTest(nivel=nivel):
                with tempfile.TemporaryDirectory() as pasta:
                    exe = construir(fonte, pasta, nivel)
                    r = executar(exe, pasta)
                    self.assertEqual((r.returncode, r.stdout),
                                     (0, 'COMUM\n1\n1\n88\n0\n0\n'), r.stderr)
                    self.assertEqual((Path(pasta)/'referencia.rsd').read_bytes(), b'COXUM')

    def test_gravacao_inteira_ainda_trunca_um_arquivo_regular(self):
        fonte = """inicio {
            seja valor: texto[20]
            copie(valor, "Nova")
            grave_arquivo("referencia.rsd", valor)
            escreva(1)
        }"""
        for nivel in (0, 8):
            with self.subTest(nivel=nivel):
                with tempfile.TemporaryDirectory() as pasta:
                    (Path(pasta)/'referencia.rsd').write_bytes(b'VALOR_ANTIGO_LONGO')
                    r = executar(construir(fonte, pasta, nivel), pasta)
                    self.assertEqual((r.returncode, r.stdout), (0, '1\n'), r.stderr)
                    self.assertEqual((Path(pasta)/'referencia.rsd').read_bytes(), b'Nova')


if __name__ == '__main__':
    unittest.main()
