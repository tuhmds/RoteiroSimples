"""Biblioteca Padrão RS 0.29 — testes end-to-end com executáveis nativos."""
from pathlib import Path
import os
import subprocess
import sys
import tempfile
import unittest

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))
from compilador.modulos import carregar_fontes
from compilador.erros import ErroCompilacao


class TestesBibliotecaPadrao(unittest.TestCase):
    def executar(self, fonte, esperado=None):
        if sys.platform not in ('linux', 'win32') or (
                sys.platform == 'linux' and os.uname().machine != 'x86_64'):
            raise unittest.SkipTest('Execução exige x86-64 Linux ou Windows.')
        with tempfile.TemporaryDirectory() as pasta:
            arquivo = Path(pasta) / 'principal.rts'
            arquivo.write_text(fonte, encoding='utf-8')
            executavel = Path(pasta) / ('programa.exe' if sys.platform == 'win32' else 'programa')
            alvo = 'windows' if sys.platform == 'win32' else 'linux'
            cmd = [sys.executable, str(RAIZ / 'compilar.py'), str(arquivo),
                   '--alvo', alvo, '-O', '8', '-o', str(executavel)]
            compilacao = subprocess.run(cmd, capture_output=True, text=True,
                                       encoding='utf-8', errors='replace', timeout=35)
            self.assertEqual(compilacao.returncode, 0, compilacao.stderr)
            programa = subprocess.run([str(executavel)], capture_output=True,
                                     text=True, encoding='utf-8', errors='replace', timeout=12)
            if esperado is not None:
                self.assertEqual((programa.returncode, programa.stdout), (0, esperado))
            return programa

    def test_exemplo_oficial(self):
        resultado = self.executar((RAIZ / 'exemplos/biblioteca_padrao.rts').read_text(encoding='utf-8'),
                                 'RS 0.29: Biblioteca Padrao\n25\n120\n6\n22\n4\n2\n-2\n8\n8\n')
        self.assertEqual(resultado.returncode, 0)

    def test_numeros(self):
        self.executar('''importe "padrao/numeros.rts" como n
inicio {
 escreva(n.menor(3, 8))
 escreva(n.maior(3, 8))
 escreva(n.absoluto(-19))
 escreva(n.sinal(-8))
 escreva(n.sinal(0))
 escreva(n.sinal(8))
 escreva(n.limitar(18, 0, 10))
 escreva(n.eh_par(-12))
 escreva(n.eh_impar(7))
 escreva(n.quadrado(11))
 escreva(n.multiplo_de(12, 4))
 escreva(n.multiplo_de(12, 0))
}''','3\n8\n19\n-1\n0\n1\n10\n1\n1\n121\n1\n0\n')

    def test_matematica(self):
        self.executar('''importe "padrao/matematica.rts" como m
inicio {
 escreva(m.potencia_natural(2, 10))
 escreva(m.potencia_natural(5, -1))
 escreva(m.fatorial(0))
 escreva(m.fatorial(5))
 escreva(m.fatorial(21))
 escreva(m.fibonacci(10))
 escreva(m.fibonacci(93))
 escreva(m.mdc(84, 30))
 escreva(m.mmc(12, 18))
 escreva(m.eh_primo(29))
 escreva(m.eh_primo(30))
 escreva(m.soma_digitos(12345))
 escreva(m.quantidade_digitos(0))
 escreva(m.quantidade_digitos(-123))
}''','1024\n0\n1\n120\n-1\n55\n-1\n6\n36\n1\n0\n15\n1\n3\n')

    def test_estatistica(self):
        self.executar('''importe "padrao/estatistica.rts" como estat
inicio {
 seja dados: lista[5]
 dados[0] = 8
 dados[1] = 3
 dados[2] = 8
 dados[3] = -2
 dados[4] = 5
 escreva(estat.soma_cinco(dados))
 escreva(estat.media_cinco(dados))
 escreva(estat.minimo_cinco(dados))
 escreva(estat.maximo_cinco(dados))
 escreva(estat.amplitude_cinco(dados))
 escreva(estat.contar_acima_cinco(dados, 5))
}''','22\n4\n-2\n8\n10\n2\n')

    def test_listas_copia_independente(self):
        self.executar('''importe "padrao/listas.rts" como l
inicio {
 seja dados: lista[5]
 dados[0] = 8
 dados[1] = 3
 dados[2] = 8
 dados[3] = -2
 dados[4] = 5
 escreva(l.buscar_cinco(dados, -2))
 escreva(l.buscar_cinco(dados, 111))
 escreva(l.contar_cinco(dados, 8))
 escreva(l.contem_cinco(dados, -2))
 escreva(l.crescente_cinco(dados))
 seja ordem: lista[5] = l.ordenar_cinco(dados)
 escreva(l.crescente_cinco(ordem))
 escreva(ordem[0])
 escreva(ordem[4])
 seja reverso: lista[5] = l.inverter_cinco(dados)
 escreva(reverso[0])
 escreva(reverso[4])
 seja trocado: lista[5] = l.substituir_cinco(dados, 8, 99)
 escreva(trocado[0])
 escreva(trocado[2])
 escreva(dados[0])
}''','3\n-1\n2\n1\n0\n1\n-2\n8\n5\n8\n99\n99\n8\n')

    def test_falha_nativa_por_transbordamento(self):
        resultado = self.executar('''importe "padrao/numeros.rts" como n
inicio {
 escreva(n.absoluto(-9223372036854775808))
}''')
        self.assertNotEqual(resultado.returncode, 0, 'Valor mínimo não pode passar silenciosamente.')

    def test_importacao_restrita_e_modulos_unicos(self):
        with tempfile.TemporaryDirectory() as pasta:
            arquivo = Path(pasta) / 'principal.rts'
            arquivo.write_text('''importe "padrao/numeros.rts" como a
importe "padrao/numeros.rts" como b
inicio {
 escreva(a.maior(2, 3))
 escreva(b.menor(2, 3))
}''', encoding='utf-8')
            fontes = carregar_fontes(arquivo)
            self.assertEqual(len(fontes.arquivos), 2)
            self.assertEqual(sum(p.name == 'numeros.rts' for p in fontes.arquivos), 1)
            arquivo.write_text('''importe "padrao/../../exemplos/ola.rts" como f
inicio {
 escreva(1)
}''', encoding='utf-8')
            with self.assertRaisesRegex(ErroCompilacao, 'inválido|não pode sair'):
                carregar_fontes(arquivo)


if __name__ == '__main__':
    unittest.main()
