"""RS 0.25: dados compostos por valor e retornos nativos."""
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

def executar(fonte):
    if sys.platform not in ('win32', 'linux') or (sys.platform == 'linux' and os.uname().machine != 'x86_64'):
        raise unittest.SkipTest('Requer Windows ou Linux x86-64')
    alvo = 'windows' if sys.platform == 'win32' else 'linux'
    with tempfile.TemporaryDirectory() as pasta:
        arquivo = Path(pasta) / ('teste.exe' if alvo == 'windows' else 'teste')
        arquivo.write_bytes(compilar(analisar_programa(fonte), alvo, nivel=8))
        if alvo == 'linux':
            arquivo.chmod(0o755)
        return subprocess.run([str(arquivo)], capture_output=True, encoding='utf-8', errors='replace', timeout=10)

class TestesCompostos(unittest.TestCase):
    def test_argumentos_listas_e_textos_copia_independente(self):
        codigo = """funcao calcular(itens: lista[3], frase: texto[16]) -> inteiro {
            itens[0] = itens[0] + 5
            junte(frase, "!")
            retorne itens[0] + tamanho(frase)
        }
        inicio {
            seja valores: lista[3]
            valores[0] = 10
            seja mensagem: texto[16]
            copie(mensagem, "Oi")
            escreva(calcular(valores, mensagem))
            escreva(valores[0])
            escreva(mensagem)
        }"""
        r=executar(codigo)
        self.assertEqual((r.returncode,r.stdout),(0,'18\n10\nOi\n'))

    def test_retornos_registro_lista_texto(self):
        codigo="""tipo Produto {
            preco: inteiro
            quantidade: inteiro
        }
        funcao criar(preco: inteiro) -> Produto {
            seja p: Produto
            p.preco = preco
            p.quantidade = 3
            retorne p
        }
        funcao replicar(p: Produto) -> Produto {
            retorne p
        }
        funcao numeros() -> lista[3] {
            seja x: lista[3]
            x[0] = 9
            x[2] = 40
            retorne x
        }
        funcao mensagem() -> texto[20] {
            seja t: texto[20]
            copie(t, "ação")
            retorne t
        }
        inicio {
            seja p: Produto = criar(10)
            seja q: Produto = replicar(p)
            escreva(q.preco)
            escreva(q.quantidade)
            seja dados: lista[3] = numeros()
            escreva(dados[0] + dados[2])
            seja msg: texto[20] = mensagem()
            escreva(msg)
        }"""
        r=executar(codigo)
        self.assertEqual((r.returncode,r.stdout),(0,'10\n3\n49\nação\n'))

    def test_retorno_encadeado(self):
        codigo="""tipo Ponto {
            x: inteiro
        }
        funcao origem() -> Ponto {
            seja p: Ponto
            p.x = 42
            retorne p
        }
        funcao intermediaria() -> Ponto {
            retorne origem()
        }
        inicio {
            seja resposta: Ponto = intermediaria()
            escreva(resposta.x)
        }"""
        r=executar(codigo)
        self.assertEqual((r.returncode,r.stdout),(0,'42\n'))

    def test_copia_composta_local(self):
        codigo="""inicio {
            seja a: lista[2]
            a[0] = 3
            seja b: lista[2] = a
            b[0] = 22
            escreva(a[0])
            escreva(b[0])
            seja t: texto[12]
            copie(t, "Oi")
            seja u = t
            junte(u, "!")
            escreva(t)
            escreva(u)
        }"""
        r=executar(codigo)
        self.assertEqual((r.returncode,r.stdout),(0,'3\n22\nOi\nOi!\n'))

    def test_capacidades_incompativeis(self):
        codigo="""funcao teste(x: texto[12]) -> inteiro {
            retorne tamanho(x)
        }
        inicio {
            seja frase: texto[16]
            escreva(teste(frase))
        }"""
        with self.assertRaises(ErroCompilacao):
            analisar_programa(codigo)

    def test_limites_preservados_em_funcao(self):
        codigo="""funcao consulta(valores: lista[2]) -> inteiro {
            retorne valores[2]
        }
        inicio {
            seja a: lista[2]
            escreva(consulta(a))
        }"""
        r=executar(codigo)
        self.assertNotEqual(r.returncode,0)
        self.assertIn('Erro',r.stdout+r.stderr)

if __name__=='__main__':
    unittest.main()
