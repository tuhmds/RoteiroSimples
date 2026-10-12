"""RS 0.28: importações qualificadas, visibilidade e tipos com nomes repetidos."""
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
from compilador.parser import analisar_programa
from backend import compilar


class TestesEspacosNomes(unittest.TestCase):
    def arquivo(self, raiz, nome, conteudo):
        arquivo = Path(raiz) / nome
        arquivo.parent.mkdir(parents=True, exist_ok=True)
        arquivo.write_text(conteudo, encoding='utf-8')
        return arquivo

    def preparar(self, raiz):
        self.arquivo(raiz, 'loja.rts', """publico tipo Pedido {
    valor: inteiro
}
privado funcao taxa(x: inteiro) -> inteiro {
    retorne x + 5
}
publico funcao calcular(p: Pedido) -> inteiro {
    retorne taxa(p.valor)
}
""")
        self.arquivo(raiz, 'servicos.rts', """publico tipo Pedido {
    valor: inteiro
}
publico funcao calcular(p: Pedido) -> inteiro {
    retorne p.valor * 2
}
""")

    def executar(self, raiz, fonte):
        main = self.arquivo(raiz, 'main.rts', fonte)
        programa = analisar_programa(carregar_fontes(main).texto)
        alvo = 'windows' if sys.platform == 'win32' else 'linux'
        if sys.platform not in ('linux', 'win32') or (
                sys.platform == 'linux' and os.uname().machine != 'x86_64'):
            raise unittest.SkipTest('Requer Windows ou Linux x86-64')
        exe = Path(raiz) / ('programa.exe' if alvo == 'windows' else 'programa')
        exe.write_bytes(compilar(programa, alvo, nivel=8))
        if alvo == 'linux':
            exe.chmod(0o755)
        return subprocess.run([str(exe)], capture_output=True, text=True,
                              encoding='utf-8', timeout=12)

    def test_tipos_e_funcoes_iguais_em_modulos_diferentes(self):
        with tempfile.TemporaryDirectory() as pasta:
            self.preparar(pasta)
            resultado = self.executar(pasta, """importe "loja.rts" como loja
importe "servicos.rts" como servicos
inicio {
    seja p: loja.Pedido
    p.valor = 12
    escreva(loja.calcular(p))
    seja q: servicos.Pedido
    q.valor = 12
    escreva(servicos.calcular(q))
}
""")
            self.assertEqual((resultado.returncode, resultado.stdout),
                             (0, '17\n24\n'))

    def test_privado_nao_pode_ser_importado(self):
        with tempfile.TemporaryDirectory() as pasta:
            self.preparar(pasta)
            main = self.arquivo(pasta, 'main.rts', """importe "loja.rts" como loja
inicio {
    escreva(loja.taxa(1))
}
""")
            with self.assertRaisesRegex(ErroCompilacao, 'privado'):
                carregar_fontes(main)

    def test_legado_sem_apelido_mantem_simbolos_publicos(self):
        with tempfile.TemporaryDirectory() as pasta:
            self.preparar(pasta)
            resultado = self.executar(pasta, """importe "loja.rts"
inicio {
    seja p: Pedido
    p.valor = 1
    escreva(calcular(p))
}
""")
            self.assertEqual((resultado.returncode, resultado.stdout), (0, '6\n'))

    def test_modulos_em_cadeia_e_simbolos_inexistentes(self):
        with tempfile.TemporaryDirectory() as pasta:
            self.preparar(pasta)
            self.arquivo(pasta, 'intermediario.rts', """importe "loja.rts" como loja
publico funcao dobrar(x: inteiro) -> inteiro {
    retorne loja.inexistente(x)
}
""")
            main = self.arquivo(pasta, 'main.rts', """importe "intermediario.rts" como interm
inicio {
    escreva(interm.dobrar(2))
}
""")
            with self.assertRaisesRegex(ErroCompilacao, 'não existe'):
                carregar_fontes(main)
            self.arquivo(pasta, 'intermediario.rts', """importe "loja.rts" como loja
publico funcao dobrar(x: inteiro) -> inteiro {
    seja p: loja.Pedido
    p.valor = x
    retorne loja.calcular(p) * 2
}
""")
            resultado = self.executar(pasta, main.read_text(encoding='utf-8'))
            self.assertEqual((resultado.returncode, resultado.stdout), (0, '14\n'))

    def test_conflito_de_apelidos_e_importacao_circular(self):
        with tempfile.TemporaryDirectory() as pasta:
            self.preparar(pasta)
            main = self.arquivo(pasta, 'main.rts', """importe "loja.rts" como a
importe "servicos.rts" como a
inicio {
    escreva(1)
}
""")
            with self.assertRaisesRegex(ErroCompilacao, 'apelido'):
                carregar_fontes(main)
            self.arquivo(pasta, 'a.rts', 'importe "b.rts" como b\npublico funcao a() -> inteiro {\n retorne 1\n}\n')
            self.arquivo(pasta, 'b.rts', 'importe "a.rts" como a\npublico funcao b() -> inteiro {\n retorne 1\n}\n')
            main = self.arquivo(pasta, 'main.rts', """importe "a.rts" como a
inicio {
    escreva(1)
}
""")
            with self.assertRaisesRegex(ErroCompilacao, 'circular'):
                carregar_fontes(main)

    def test_repeticao_de_modulo_e_diagnostico_original(self):
        with tempfile.TemporaryDirectory() as pasta:
            self.preparar(pasta)
            main = self.arquivo(pasta, 'main.rts', """importe "loja.rts" como uma
importe "loja.rts" como outra
inicio {
    seja p: uma.Pedido
    p.valor = 1
    escreva(outra.calcular(p))
}
""")
            fontes = carregar_fontes(main)
            self.assertEqual(len(fontes.arquivos), 2)
            resultado = self.executar(pasta, main.read_text(encoding='utf-8'))
            self.assertEqual((resultado.returncode, resultado.stdout), (0, '6\n'))
            main = self.arquivo(pasta, 'main.rts', """importe "loja.rts" como loja
inicio {
    escreva(loja.inexistente())
}
""")
            with self.assertRaisesRegex(ErroCompilacao, 'main.rts:3'):
                carregar_fontes(main)


if __name__ == '__main__':
    unittest.main()
