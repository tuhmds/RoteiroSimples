"""Arena reutilizável de bytes escritos em RS, sem ponteiros persistentes."""
import os
from pathlib import Path
import sys
import tempfile
import subprocess
import unittest

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))
from compilador.modulos import carregar_fontes
from compilador.parser import analisar_programa
from backend import compilar

EXEMPLO = RAIZ / 'exemplos/aplicacoes/arena_memoria_rs_mem.rts'

class TestesArenaRsMem(unittest.TestCase):
    def _executar(self, fonte, saida=None, falha=False):
        if sys.platform not in ('win32', 'linux') or (
                sys.platform == 'linux' and os.uname().machine != 'x86_64'):
            self.skipTest('Execução nativa exige Windows AMD64 ou Linux x86-64.')
        alvo = 'windows' if sys.platform == 'win32' else 'linux'
        with tempfile.TemporaryDirectory() as pasta:
            entrada = Path(pasta) / 'fonte.rts'
            entrada.write_text(fonte, encoding='utf-8')
            programa = analisar_programa(carregar_fontes(entrada).texto)
            for nivel in (0, 4, 8):
                with self.subTest(nivel=nivel):
                    codigo = compilar(programa, alvo, nivel=nivel, otimizar=nivel > 0)
                    arquivo = Path(pasta) / ('codigo.exe' if alvo == 'windows' else 'codigo')
                    arquivo.write_bytes(codigo)
                    if alvo == 'linux':
                        arquivo.chmod(0o755)
                    resposta = subprocess.run([str(arquivo)], cwd=pasta,
                                             capture_output=True, timeout=30)
                    if falha:
                        self.assertNotEqual(resposta.returncode, 0, resposta.stderr)
                    else:
                        self.assertEqual(resposta.returncode, 0, resposta.stderr)
                        self.assertEqual(resposta.stdout, saida)

    def test_exemplo_real_e_binarios_em_nove_niveis(self):
        fonte = EXEMPLO.read_text(encoding='utf-8')
        self._executar(fonte, b'256\n1024\n255\n0\n32\n40\n')

    def test_recuar_conserva_bytes_e_reutiliza_capacidade(self):
        fonte = '''importe "padrao/arenas.rts" como arenas
inicio {
    seja area = arenas.criar(32)
    para i de 0 ate 9 {
        seja nova = arenas.acrescentar(mova(area), i)
        mova(area, nova)
    }
    seja marcador = arenas.marca(empreste(area))
    para i de 0 ate 4 {
        seja nova = arenas.acrescentar(mova(area), i + 90)
        mova(area, nova)
    }
    escreva(arenas.tamanho(empreste(area)))
    seja anterior = arenas.recuar(mova(area), marcador)
    mova(area, anterior)
    escreva(arenas.tamanho(empreste(area)))
    seja fora = arenas.ler(empreste(area), 12)
    escreva(fora.valido)
    escreva(fora.codigo_erro)
    seja nova = arenas.acrescentar(mova(area), 201)
    mova(area, nova)
    escreva(arenas.tamanho(empreste(area)))
    seja lido = arenas.ler(empreste(area), 10)
    escreva(lido.valor)
    escreva(arenas.capacidade(empreste(area)))
}'''
        self._executar(fonte, b'15\n10\n0\n1\n11\n201\n32\n')

    def test_marcador_invalido_encerra_sem_permitir_acesso(self):
        fonte = '''importe "padrao/arenas.rts" como arenas
inicio {
    seja area = arenas.criar(16)
    seja alterada = arenas.recuar(mova(area), 99)
    escreva(arenas.tamanho(empreste(alterada)))
}'''
        self._executar(fonte, falha=True)

    def test_capacidade_pequena_cresce_e_reuso_logico_nao_abaixa_capacidade(self):
        fonte = '''importe "padrao/arenas.rts" como arenas
inicio {
    seja area = arenas.criar(1)
    para i de 0 ate 4095 {
        seja nova = arenas.acrescentar(mova(area), i % 256)
        mova(area, nova)
    }
    escreva(arenas.tamanho(empreste(area)))
    escreva(arenas.capacidade(empreste(area)))
    seja reiniciada = arenas.reiniciar(mova(area))
    mova(area, reiniciada)
    escreva(arenas.tamanho(empreste(area)))
    escreva(arenas.capacidade(empreste(area)))
    para i de 0 ate 15 {
        seja nova = arenas.acrescentar(mova(area), 100 + i)
        mova(area, nova)
    }
    escreva(arenas.tamanho(empreste(area)))
    seja x = arenas.ler(empreste(area), 15)
    escreva(x.valor)
}'''
        self._executar(fonte, b'4096\n4096\n0\n4096\n16\n115\n')

if __name__ == '__main__':
    unittest.main()
