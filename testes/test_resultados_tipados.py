"""RS 0.30: resultados tipados e erros de domínio na Biblioteca Padrão."""
from pathlib import Path
import os
import subprocess
import sys
import tempfile
import unittest

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))
from compilador.modulos import carregar_fontes


class TestesResultadosTipados(unittest.TestCase):
    def compilar_executar(self, fonte, esperado=None, compila=True):
        if sys.platform not in ('linux', 'win32') or (
                sys.platform == 'linux' and os.uname().machine != 'x86_64'):
            raise unittest.SkipTest('Requer Windows ou Linux x86-64.')
        with tempfile.TemporaryDirectory() as pasta:
            arquivo = Path(pasta) / 'principal.rts'
            arquivo.write_text(fonte, encoding='utf-8')
            destino = Path(pasta) / ('programa.exe' if sys.platform == 'win32' else 'programa')
            alvo = 'windows' if sys.platform == 'win32' else 'linux'
            processo = subprocess.run(
                [sys.executable, str(RAIZ / 'compilar.py'), str(arquivo),
                 '--alvo', alvo, '-O', '8', '-o', str(destino)],
                capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=30)
            if not compila:
                self.assertNotEqual(processo.returncode, 0)
                self.assertIn('tipo', processo.stderr.lower())
                return processo
            self.assertEqual(processo.returncode, 0, processo.stderr)
            programa = subprocess.run(
                [str(destino)], capture_output=True, text=True,
                encoding='utf-8', errors='replace', timeout=15)
            self.assertEqual(programa.returncode, 0, programa.stderr + programa.stdout)
            if esperado is not None:
                self.assertEqual(programa.stdout, esperado)
            return programa

    def test_exemplo_oficial(self):
        self.compilar_executar((RAIZ / 'exemplos/resultados_tipados.rts').read_text(encoding='utf-8'),
            'RS 0.30: resultados tipados\nFalha de divisao detectada\n1\n9\n120\n1\n')

    def test_divisao_valida_zero_e_transbordamento(self):
        fonte = '''importe "padrao/matematica_segura.rts" como m
inicio {
    seja boa = m.dividir(16, 4)
    escreva(boa.valido)
    escreva(boa.valor)
    escreva(boa.codigo_erro)
    seja zero = m.dividir(7, 0)
    escreva(zero.valido)
    escreva(zero.valor)
    escreva(zero.codigo_erro)
    seja minimo = m.dividir(-9223372036854775808, -1)
    escreva(minimo.valido)
    escreva(minimo.codigo_erro)
    seja resto = m.resto(-9223372036854775808, -1)
    escreva(resto.codigo_erro)
    seja outro = m.resto(15, 4)
    escreva(outro.valor)
}'''
        self.compilar_executar(fonte, '1\n4\n0\n0\n0\n1\n0\n3\n3\n3\n')

    def test_fatorial_e_fibonacci_limites(self):
        fonte = '''importe "padrao/matematica_segura.rts" como s
inicio {
    escreva(s.fatorial(0).valor)
}'''
        # O acesso direto a campo de chamada ainda não está disponível;
        # a variável de resultado é intencional e demonstra análise de tipo.
        fonte = fonte.replace('escreva(s.fatorial(0).valor)', '''seja a = s.fatorial(0)
    seja b = s.fatorial(20)
    seja c = s.fatorial(21)
    seja d = s.fatorial(-1)
    seja resultado_e = s.fibonacci(10)
    seja f = s.fibonacci(92)
    seja g = s.fibonacci(93)
    escreva(a.valor)
    escreva(b.valor)
    escreva(c.codigo_erro)
    escreva(d.codigo_erro)
    escreva(resultado_e.valor)
    escreva(f.valor)
    escreva(g.codigo_erro)''')
        self.compilar_executar(fonte, '1\n2432902008176640000\n2\n2\n55\n7540113804746346429\n2\n')

    def test_raiz_quadrada_inteira_extremos(self):
        fonte='''importe "padrao/matematica_segura.rts" como s
inicio {
    seja a = s.raiz_quadrada_inteira(-1)
    seja b = s.raiz_quadrada_inteira(0)
    seja c = s.raiz_quadrada_inteira(15)
    seja d = s.raiz_quadrada_inteira(16)
    seja resultado_e = s.raiz_quadrada_inteira(9223372036854775807)
    escreva(a.codigo_erro)
    escreva(b.valor)
    escreva(c.valor)
    escreva(d.valor)
    escreva(resultado_e.valor)
}'''
        self.compilar_executar(fonte, '2\n0\n3\n4\n3037000499\n')

    def test_resultado_logico_e_intervalo(self):
        fonte='''importe "padrao/matematica_segura.rts" como s
importe "padrao/resultados.rts" como r
inicio {
    seja p = s.eh_primo(29)
    seja q = s.eh_primo(30)
    seja n = s.eh_primo(-3)
    escreva(p.valido)
    escreva(p.valor)
    escreva(q.valido)
    escreva(q.valor)
    escreva(n.valido)
    escreva(n.codigo_erro)
    escreva(r.logico_ou(n, verdadeiro))
    seja a = s.limitar(15, 0, 10)
    seja b = s.limitar(15, 20, 10)
    escreva(a.valor)
    escreva(b.codigo_erro)
}'''
        self.compilar_executar(fonte, '1\n1\n1\n0\n0\n2\n1\n10\n4\n')

    def test_dominio_mdc_mmc_potencia(self):
        fonte='''importe "padrao/matematica_segura.rts" como s
inicio {
    seja a = s.mdc(84, 30)
    seja b = s.mmc(12, 18)
    seja c = s.potencia_natural(2, 10)
    seja d = s.potencia_natural(3, -1)
    seja resultado_e = s.mdc(-1, 2)
    escreva(a.valor)
    escreva(b.valor)
    escreva(c.valor)
    escreva(d.codigo_erro)
    escreva(resultado_e.codigo_erro)
}'''
        self.compilar_executar(fonte,'6\n36\n1024\n2\n2\n')

    def test_resultado_inteiro_diferente_de_resultado_logico(self):
        codigo='''importe "padrao/resultados.rts" como r
inicio {
    seja a: r.ResultadoInteiro = r.sucesso_logico(verdadeiro)
    escreva(a.valor)
}'''
        self.compilar_executar(codigo, compila=False)

    def test_resultados_copiados_por_valor(self):
        codigo='''importe "padrao/resultados.rts" como r
inicio {
    seja a = r.sucesso_inteiro(42)
    seja b = a
    b.valor = 17
    escreva(a.valor)
    escreva(b.valor)
    escreva(r.inteiro_ou(r.falha_inteiro(2), 99))
}'''
        self.compilar_executar(codigo, '42\n17\n99\n')

    def test_importacao_compartilhada_nao_duplica(self):
        with tempfile.TemporaryDirectory() as pasta:
            arq = Path(pasta) / 'principal.rts'
            arq.write_text('''importe "padrao/resultados.rts" como r
importe "padrao/matematica_segura.rts" como m
inicio {
    seja a = m.fatorial(3)
    escreva(r.inteiro_ou(a, -1))
}''', encoding='utf-8')
            fontes = carregar_fontes(arq)
            nomes = [x.name for x in fontes.arquivos]
            self.assertEqual(nomes.count('resultados.rts'), 1)
            self.assertEqual(nomes.count('matematica_segura.rts'), 1)

if __name__ == '__main__':
    unittest.main()
