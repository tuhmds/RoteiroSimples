"""RS 0.27: importações, dependências, conflitos e execução nativa."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))
from compilador.modulos import carregar_fontes
from compilador.erros import ErroCompilacao


class TestesModulos(unittest.TestCase):
    def arquivo(self, pasta, nome, conteudo):
        destino = Path(pasta) / nome
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_text(conteudo, encoding='utf-8')
        return destino

    def compilar(self, principal, destino, *opcoes):
        return subprocess.run([sys.executable, str(RAIZ / 'compilar.py'),
                               str(principal), '--alvo',
                               'windows' if sys.platform == 'win32' else 'linux',
                               '-o', str(destino), *opcoes],
                              capture_output=True, text=True, encoding='utf-8',
                              errors='replace', timeout=20)

    def test_modulos_transitivos_repetidos_com_tipos_e_funcoes(self):
        with tempfile.TemporaryDirectory() as pasta:
            self.arquivo(pasta, 'modulos/valores.rts', """funcao taxa(n: inteiro) -> inteiro {
    retorne n + 5
}
""")
            self.arquivo(pasta, 'modulos/pedidos.rts', """importe "valores.rts"
tipo Pedido {
    preco: inteiro
    quantidade: inteiro
}
funcao calcular(p: Pedido) -> inteiro {
    retorne taxa(p.preco * p.quantidade)
}
""")
            principal = self.arquivo(pasta, 'principal.rts', """importe "modulos/pedidos.rts"
importe "modulos/valores.rts"
inicio {
    seja p: Pedido
    p.preco = 20
    p.quantidade = 3
    escreva(calcular(p))
}
""")
            fontes = carregar_fontes(principal)
            self.assertEqual(len(fontes.arquivos), 3)
            self.assertEqual(fontes.texto.count('funcao taxa'), 1)
            executavel = Path(pasta) / ('programa.exe' if sys.platform == 'win32' else 'programa')
            resultado = self.compilar(principal, executavel, '--mostrar-modulos')
            self.assertEqual(resultado.returncode, 0, resultado.stderr)
            self.assertEqual(resultado.stdout.count('Módulo:'), 3)
            if sys.platform == 'win32' or (sys.platform == 'linux' and os.uname().machine == 'x86_64'):
                execucao = subprocess.run([str(executavel)], capture_output=True,
                                          text=True, encoding='utf-8', timeout=10)
                self.assertEqual((execucao.returncode, execucao.stdout), (0, '65\n'))

    def test_matematica_de_um_modulo(self):
        with tempfile.TemporaryDirectory() as pasta:
            self.arquivo(pasta, 'mat.rts', """inclua matematica
funcao dobro(n: inteiro) -> inteiro {
    retorne multiplicar(n, 2)
}
""")
            principal = self.arquivo(pasta, 'principal.rts',
                    'importe "mat.rts"\ninicio {\n escreva(dobro(7))\n}\n')
            self.assertTrue(carregar_fontes(principal).texto.startswith('inclua matematica'))
            resultado = self.compilar(principal, Path(pasta) / 'programa')
            self.assertEqual(resultado.returncode, 0, resultado.stderr)

    def test_circulo_detectado(self):
        with tempfile.TemporaryDirectory() as pasta:
            self.arquivo(pasta, 'a.rts', 'importe "b.rts"\nfuncao a() -> inteiro {\n retorne 1\n}\n')
            self.arquivo(pasta, 'b.rts', 'importe "a.rts"\nfuncao b() -> inteiro {\n retorne 2\n}\n')
            principal = self.arquivo(pasta, 'principal.rts',
                                    'importe "a.rts"\ninicio {\n escreva(1)\n}\n')
            with self.assertRaisesRegex(ErroCompilacao, 'Importação circular'):
                carregar_fontes(principal)

    def test_fora_do_projeto_e_arquivo_ausente(self):
        with tempfile.TemporaryDirectory() as pasta:
            self.arquivo(pasta, 'externo.rts', 'funcao f() -> inteiro {\n retorne 1\n}\n')
            projeto = Path(pasta) / 'projeto'
            projeto.mkdir()
            principal = self.arquivo(projeto, 'principal.rts',
                                    'importe "../externo.rts"\ninicio {\n escreva(1)\n}\n')
            with self.assertRaisesRegex(ErroCompilacao, 'não pode sair'):
                carregar_fontes(principal)
            principal.write_text('importe "inexistente.rts"\ninicio {\n escreva(1)\n}\n')
            with self.assertRaisesRegex(ErroCompilacao, 'não encontrado'):
                carregar_fontes(principal)

    def test_importado_nao_pode_conter_inicio(self):
        with tempfile.TemporaryDirectory() as pasta:
            self.arquivo(pasta, 'segundo.rts', 'inicio {\n escreva(2)\n}\n')
            principal = self.arquivo(pasta, 'principal.rts',
                                    'importe "segundo.rts"\ninicio {\n escreva(1)\n}\n')
            with self.assertRaisesRegex(ErroCompilacao, 'não podem conter inicio'):
                carregar_fontes(principal)

    def test_conflicto_de_nomes_e_localizacao(self):
        with tempfile.TemporaryDirectory() as pasta:
            self.arquivo(pasta, 'a.rts', 'funcao igual() -> inteiro {\n retorne 1\n}\n')
            self.arquivo(pasta, 'b.rts', 'funcao igual() -> inteiro {\n retorne 2\n}\n')
            principal = self.arquivo(pasta, 'principal.rts',
                    'importe "a.rts"\nimporte "b.rts"\ninicio {\n escreva(1)\n}\n')
            resultado = self.compilar(principal, Path(pasta) / 'programa')
            self.assertNotEqual(resultado.returncode, 0)
            self.assertIn('b.rts:', resultado.stderr)
            self.arquivo(pasta, 'b.rts',
                'funcao erro() -> inteiro {\n retorne desconhecido\n}\n')
            resultado = self.compilar(principal, Path(pasta) / 'programa')
            self.assertNotEqual(resultado.returncode, 0)
            self.assertIn('b.rts:2', resultado.stderr)

    def test_fonte_sem_importacoes_inalterada(self):
        with tempfile.TemporaryDirectory() as pasta:
            original = '\n\n// Comentário\ninicio {\n\n escreva(42)\n}\n'
            principal = self.arquivo(pasta, 'principal.rts', original)
            fontes = carregar_fontes(principal)
            self.assertEqual(fontes.texto, original)
            self.assertEqual(fontes.origens[4].numero, 5)


if __name__ == '__main__':
    unittest.main()
