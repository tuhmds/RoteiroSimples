"""Pool RS de blocos pequenos, reuso individual e geração anti-ABA."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))
from compilador.modulos import carregar_fontes
from compilador.parser import analisar_programa
from backend import compilar


class TestesPoolRsMem(unittest.TestCase):
    def _verificar(self, fonte, esperado):
        if sys.platform not in ('linux', 'win32') or (
                sys.platform == 'linux' and os.uname().machine != 'x86_64'):
            self.skipTest('Exige execução nativa Windows AMD64 ou Linux x86-64.')
        alvo = 'windows' if sys.platform == 'win32' else 'linux'
        with tempfile.TemporaryDirectory() as pasta:
            fonte_path = Path(pasta) / 'pool.rts'
            fonte_path.write_text(fonte, encoding='utf-8')
            programa = analisar_programa(carregar_fontes(fonte_path).texto)
            for nivel in (0, 4, 8):
                with self.subTest(alvo=alvo, nivel=nivel):
                    imagem = compilar(programa, alvo, nivel=nivel, otimizar=nivel > 0)
                    nome = Path(pasta) / ('pool.exe' if alvo == 'windows' else 'pool')
                    nome.write_bytes(imagem)
                    if alvo == 'linux':
                        nome.chmod(0o755)
                    execucao = subprocess.run([str(nome)], cwd=pasta,
                                               capture_output=True, timeout=30)
                    self.assertEqual(execucao.returncode, 0, execucao.stderr)
                    self.assertEqual(execucao.stdout, esperado)

    def test_exemplo_reusa_geracao_zerando_conteudo(self):
        exemplo = (RAIZ / 'exemplos/aplicacoes/pool_rs_mem.rts').read_text(
            encoding='utf-8')
        self._verificar(exemplo, b'239\n0\n2\n3\n0\n1\n')

    def test_pool_cheio_validacao_e_liberacao_dupla(self):
        fonte = '''importe "padrao/pools.rts" como pools
inicio {
    seja criado = pools.criar(64, 1)
    seja p = mova(criado.valor)
    seja a = pools.alocar(mova(p))
    mova(p, a)
    seja id = pools.ultimo(empreste(p))
    seja cheio = pools.alocar(mova(p))
    mova(p, cheio)
    escreva(pools.erro(empreste(p)))
    escreva(pools.ocupados(empreste(p)))
    seja invalido = pools.escrever(mova(p), id, 64, 10)
    mova(p, invalido)
    escreva(pools.erro(empreste(p)))
    seja salvo = pools.escrever(mova(p), id, 63, 255)
    mova(p, salvo)
    seja leitura = pools.ler(empreste(p), id, 63)
    escreva(leitura.valor)
    seja desfeito = pools.liberar(mova(p), id)
    mova(p, desfeito)
    seja repetido = pools.liberar(mova(p), id)
    mova(p, repetido)
    escreva(pools.erro(empreste(p)))
    escreva(pools.ocupados(empreste(p)))
}'''
        self._verificar(fonte, b'4\n1\n6\n255\n3\n0\n')

    def test_classes_incorretas_e_largura_invalidas(self):
        fonte = '''importe "padrao/pools.rts" como pools
inicio {
    seja a = pools.criar(17, 2)
    escreva(a.valido)
    escreva(a.codigo_erro)
    seja b = pools.criar(16, 0)
    escreva(b.valido)
    escreva(b.codigo_erro)
    seja c = pools.criar(256, 1)
    escreva(c.valido)
    escreva(c.codigo_erro)
}'''
        self._verificar(fonte, b'0\n1\n0\n2\n1\n0\n')

    def test_multiplos_slots_ordem_lifo_e_zeragem(self):
        fonte = '''importe "padrao/pools.rts" como pools
inicio {
    seja r = pools.criar(16, 4)
    seja p = mova(r.valor)
    seja a = pools.alocar(mova(p))
    mova(p, a)
    seja x = pools.ultimo(empreste(p))
    seja b = pools.alocar(mova(p))
    mova(p, b)
    seja y = pools.ultimo(empreste(p))
    seja escrito = pools.escrever(mova(p), y, 15, 123)
    mova(p, escrito)
    seja liberado = pools.liberar(mova(p), y)
    mova(p, liberado)
    seja novo = pools.alocar(mova(p))
    mova(p, novo)
    seja z = pools.ultimo(empreste(p))
    escreva(x.indice)
    escreva(y.indice)
    escreva(z.indice)
    escreva(z.versao)
    escreva(pools.ocupados(empreste(p)))
    seja valor = pools.ler(empreste(p), z, 15)
    escreva(valor.valor)
}'''
        self._verificar(fonte, b'0\n1\n1\n2\n2\n0\n')


if __name__ == '__main__':
    unittest.main()
