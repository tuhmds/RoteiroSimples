"""RS 0.26: registros aninhados e chamadas com compostos diretos."""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))
from compilador.parser import analisar_programa
from compilador.erros import ErroCompilacao
from backend import compilar


def executar(codigo, nivel=8):
    if sys.platform not in ('win32', 'linux'):
        raise unittest.SkipTest('Requer Windows ou Linux')
    if sys.platform == 'linux' and os.uname().machine != 'x86_64':
        raise unittest.SkipTest('Requer Linux x86-64')
    alvo = 'windows' if sys.platform == 'win32' else 'linux'
    programa = analisar_programa(codigo)
    with tempfile.TemporaryDirectory() as pasta:
        arquivo = Path(pasta) / ('teste.exe' if alvo == 'windows' else 'teste')
        arquivo.write_bytes(compilar(programa, alvo, nivel=nivel))
        if alvo == 'linux':
            arquivo.chmod(0o755)
        return subprocess.run([str(arquivo)], capture_output=True,
                              encoding='utf-8', errors='replace', timeout=10)


TIPOS = """tipo Endereco {
    numero: inteiro
    logradouro: texto[24]
}
tipo Cliente {
    endereco: Endereco
    pontos: lista[3]
    ativo: logico
}
"""


class TestesRegistrosAninhados(unittest.TestCase):
    def test_campos_recursivos_lista_e_utf8(self):
        fonte = TIPOS + """inicio {
            seja cliente: Cliente
            cliente.endereco.numero = 42
            copie(cliente.endereco.logradouro, "Rua da Ação")
            cliente.pontos[0] = 10
            cliente.pontos[1] = 15
            cliente.ativo = verdadeiro
            escreva(cliente.endereco.numero)
            escreva(cliente.endereco.logradouro)
            escreva(cliente.pontos[0] + cliente.pontos[1])
            escreva(tamanho(cliente.endereco.logradouro))
        }"""
        r = executar(fonte)
        self.assertEqual((r.returncode, r.stdout), (0, '42\nRua da Ação\n25\n12\n'))

    def test_argumento_composto_direto_e_retorno_aninhado(self):
        fonte = TIPOS + """funcao criar(n: inteiro) -> Cliente {
            seja c: Cliente
            c.endereco.numero = n
            copie(c.endereco.logradouro, "Centro")
            c.pontos[1] = 8
            c.ativo = verdadeiro
            retorne c
        }
        funcao melhorar(c: Cliente) -> Cliente {
            c.endereco.numero = c.endereco.numero + 1
            c.pontos[1] = c.pontos[1] + 2
            retorne c
        }
        funcao somar(c: Cliente) -> inteiro {
            retorne c.endereco.numero + c.pontos[1]
        }
        inicio {
            escreva(somar(criar(30)))
            seja cliente: Cliente = melhorar(criar(30))
            escreva(cliente.endereco.numero)
            escreva(cliente.pontos[1])
            escreva(cliente.endereco.logradouro)
        }"""
        r = executar(fonte)
        self.assertEqual((r.returncode, r.stdout), (0, '38\n31\n10\nCentro\n'))

    def test_copia_integral_sem_alias(self):
        fonte = TIPOS + """inicio {
            seja a: Cliente
            a.endereco.numero = 7
            copie(a.endereco.logradouro, "Oi")
            a.pontos[0] = 13
            seja b: Cliente = a
            b.endereco.numero = 90
            junte(b.endereco.logradouro, "!")
            b.pontos[0] = 22
            escreva(a.endereco.numero)
            escreva(a.endereco.logradouro)
            escreva(a.pontos[0])
            escreva(b.endereco.numero)
            escreva(b.endereco.logradouro)
            escreva(b.pontos[0])
        }"""
        r = executar(fonte)
        self.assertEqual((r.returncode, r.stdout), (0, '7\nOi\n13\n90\nOi!\n22\n'))

    def test_limite_de_lista_aninhada(self):
        fonte = TIPOS + """inicio {
            seja c: Cliente
            escreva(c.pontos[3])
        }"""
        r = executar(fonte)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn('Erro', r.stdout + r.stderr)

    def test_tipos_aninhados_invalidos(self):
        fontes = (
            'tipo Coisa {\n filho: Coisa\n}\ninicio {\n escreva(1)\n}',
            'tipo Coisa {\n v: lista[0]\n}\ninicio {\n escreva(1)\n}',
            TIPOS + 'inicio {\n seja c: Cliente\n escreva(c.endereco.inexistente)\n}',
        )
        for codigo in fontes:
            with self.subTest(codigo=codigo):
                with self.assertRaises(ErroCompilacao):
                    analisar_programa(codigo)


if __name__ == '__main__':
    unittest.main()
