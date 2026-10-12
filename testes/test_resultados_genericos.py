"""RS 0.31: resultados genéricos especializados na compilação e propague."""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))
from compilador.modulos import carregar_fontes
from compilador.resultados_genericos import preparar_resultados_genericos
from compilador.parser import analisar_programa
from compilador.erros import ErroCompilacao
from backend import compilar


def executar(codigo):
    if sys.platform not in ('win32', 'linux') or (
            sys.platform == 'linux' and os.uname().machine != 'x86_64'):
        raise unittest.SkipTest('Requer Windows ou Linux x86-64')
    with tempfile.TemporaryDirectory() as pasta:
        origem = Path(pasta) / 'principal.rts'
        origem.write_text(codigo, encoding='utf-8')
        alvo = 'windows' if sys.platform == 'win32' else 'linux'
        destino = Path(pasta) / ('programa.exe' if alvo == 'windows' else 'programa')
        comando = [sys.executable, str(RAIZ / 'compilar.py'),
                   str(origem), '--alvo', alvo, '-O', '8', '-o', str(destino)]
        saida = subprocess.run(comando, capture_output=True, text=True,
                               encoding='utf-8', errors='replace', timeout=30)
        if saida.returncode:
            raise AssertionError(saida.stderr + saida.stdout)
        processo = subprocess.run([str(destino)], capture_output=True, text=True,
                                  encoding='utf-8', errors='replace', timeout=12)
        return processo


class TestesResultadosGenericos(unittest.TestCase):
    def test_resultado_inteiro_e_propagacao(self):
        fonte = """funcao dividir(a: inteiro, b: inteiro) -> resultado[inteiro] {
            se b == 0 {
                retorne falha[inteiro](1)
            }
            retorne sucesso[inteiro](a / b)
        }
        funcao calcular(n: inteiro) -> resultado[inteiro] {
            seja r: resultado[inteiro] = dividir(n, 2)
            propague r
            retorne sucesso[inteiro](r.valor + 1)
        }
        funcao outra(n: inteiro) -> resultado[inteiro] {
            seja r = calcular(n)
            propague r
            retorne sucesso[inteiro](r.valor * 3)
        }
        inicio {
            seja a = outra(10)
            seja b = dividir(10, 0)
            escreva(a.valido)
            escreva(a.valor)
            escreva(a.codigo_erro)
            escreva(b.valido)
            escreva(b.valor)
            escreva(b.codigo_erro)
        }"""
        r = executar(fonte)
        self.assertEqual((r.returncode,r.stdout),(0,'1\n18\n0\n0\n0\n1\n'))

    def test_falha_propagada_com_tipo_de_retorno_diferente(self):
        fonte="""funcao consultar(n: inteiro) -> resultado[inteiro] {
            se n < 0 {
                retorne falha[inteiro](8)
            }
            retorne sucesso[inteiro](n)
        }
        funcao validar(n: inteiro) -> resultado[logico] {
            seja x = consultar(n)
            propague x
            retorne sucesso[logico](x.valor > 3)
        }
        inicio {
            seja a = validar(5)
            seja b = validar(-2)
            escreva(a.valido)
            escreva(a.valor)
            escreva(b.valido)
            escreva(b.codigo_erro)
        }"""
        r=executar(fonte)
        self.assertEqual((r.returncode,r.stdout),(0,'1\n1\n0\n8\n'))

    def test_resultado_registro_proprio(self):
        fonte="""tipo Pessoa {
            idade: inteiro
            ativo: logico
        }
        funcao criar(n: inteiro) -> resultado[Pessoa] {
            se n < 0 {
                retorne falha[Pessoa](2)
            }
            seja pessoa: Pessoa
            pessoa.idade = n
            pessoa.ativo = verdadeiro
            retorne sucesso[Pessoa](pessoa)
        }
        inicio {
            seja a: resultado[Pessoa] = criar(17)
            seja b = criar(-1)
            escreva(a.valido)
            escreva(a.valor.idade)
            escreva(a.valor.ativo)
            escreva(b.valido)
            escreva(b.codigo_erro)
        }"""
        r=executar(fonte)
        self.assertEqual((r.returncode,r.stdout),(0,'1\n17\n1\n0\n2\n'))

    def test_resultado_texto_e_lista_copiados(self):
        fonte="""funcao criar_texto() -> resultado[texto[16]] {
            seja texto_local: texto[16]
            copie(texto_local, "Olá!")
            retorne sucesso[texto[16]](texto_local)
        }
        funcao criar_lista() -> resultado[lista[3]] {
            seja valores: lista[3]
            valores[0] = 5
            valores[1] = 8
            retorne sucesso[lista[3]](valores)
        }
        inicio {
            seja t = criar_texto()
            seja l = criar_lista()
            escreva(t.valido)
            escreva(t.valor)
            escreva(l.valor[0] + l.valor[1])
        }"""
        r=executar(fonte)
        self.assertEqual((r.returncode,r.stdout),(0,'1\nOlá!\n13\n'))

    def test_especializacoes_em_modulos(self):
        with tempfile.TemporaryDirectory() as pasta:
            base=Path(pasta)
            (base/'dados.rts').write_text("""publico tipo Cliente {
                codigo: inteiro
            }
            publico funcao consultar(valor: inteiro) -> resultado[Cliente] {
                seja c: Cliente
                c.codigo = valor
                retorne sucesso[Cliente](c)
            }
            """,encoding='utf-8')
            (base/'principal.rts').write_text("""importe "dados.rts" como dados
            inicio {
                seja pessoa: resultado[dados.Cliente] = dados.consultar(42)
                escreva(pessoa.valido)
                escreva(pessoa.valor.codigo)
            }
            """,encoding='utf-8')
            fontes=preparar_resultados_genericos(carregar_fontes(base/'principal.rts'))
            self.assertEqual(fontes.texto.count('tipo RsInternoGenerico_Resultado_'),1)
            programa=analisar_programa(fontes.texto)
            self.assertTrue(programa.funcoes)
            if sys.platform in ('win32','linux') and (sys.platform!='linux' or os.uname().machine=='x86_64'):
                alvo='windows' if sys.platform=='win32' else 'linux'
                binario=base/('programa.exe' if alvo=='windows' else 'programa')
                binario.write_bytes(compilar(programa,alvo,nivel=8))
                if alvo=='linux': binario.chmod(0o755)
                p=subprocess.run([str(binario)],capture_output=True,text=True,
                                 encoding='utf-8',timeout=10)
                self.assertEqual((p.returncode,p.stdout),(0,'1\n42\n'))

    def test_resultados_diferentes_nao_se_confundem(self):
        fonte="""inicio {
            seja a: resultado[inteiro] = sucesso[logico](verdadeiro)
            escreva(a.valido)
        }"""
        with tempfile.TemporaryDirectory() as pasta:
            arquivo=Path(pasta)/'principal.rts'
            arquivo.write_text(fonte,encoding='utf-8')
            expandido=preparar_resultados_genericos(carregar_fontes(arquivo))
            with self.assertRaises(ErroCompilacao):
                analisar_programa(expandido.texto)

    def test_propague_rejeitado_no_inicio(self):
        with tempfile.TemporaryDirectory() as pasta:
            arquivo=Path(pasta)/'principal.rts'
            arquivo.write_text('inicio {\n seja x = 1\n propague x\n}\n',encoding='utf-8')
            with self.assertRaisesRegex(ErroCompilacao,'propague exige função'):
                preparar_resultados_genericos(carregar_fontes(arquivo))

    def test_propague_rejeita_variavel_sem_resultado(self):
        fonte="""funcao calcular() -> resultado[inteiro] {
            seja x = 1
            propague x
            retorne sucesso[inteiro](2)
        }
        inicio {
            seja a = calcular()
            escreva(a.valor)
        }"""
        with tempfile.TemporaryDirectory() as pasta:
            arquivo=Path(pasta)/'principal.rts'
            arquivo.write_text(fonte,encoding='utf-8')
            expandido=preparar_resultados_genericos(carregar_fontes(arquivo))
            with self.assertRaises(ErroCompilacao):
                analisar_programa(expandido.texto)

    def test_codigo_de_erro_zero_normalizado(self):
        fonte="""inicio {
            seja r = falha[inteiro](0)
            escreva(r.valido)
            escreva(r.valor)
            escreva(r.codigo_erro)
        }"""
        r=executar(fonte)
        self.assertEqual((r.returncode,r.stdout),(0,'0\n0\n2\n'))


if __name__ == '__main__':
    unittest.main()
