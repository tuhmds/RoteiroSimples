"""RS 0.19: o cache e compartilhado entre leituras nativas de tipos diferentes."""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))
from compilador.parser import analisar_programa
from compilador.ir import construir_ir
from compilador.efeitos import efeito_instrucao, listar_efeitos, efeitos_para_json
from backend import compilar


class TestesEntradaBufferizada(unittest.TestCase):
    def executar(self, fonte, entrada, nivel=6):
        if sys.platform not in ('linux', 'win32') or (sys.platform == 'linux' and os.uname().machine != 'x86_64'):
            self.skipTest('Requer x86-64 Linux ou Windows')
        alvo = 'windows' if sys.platform == 'win32' else 'linux'
        with tempfile.TemporaryDirectory() as pasta:
            exe = Path(pasta) / ('programa.exe' if alvo == 'windows' else 'programa')
            exe.write_bytes(compilar(analisar_programa(fonte), alvo, nivel=nivel))
            if alvo == 'linux':
                exe.chmod(0o755)
            return subprocess.run([str(exe)], input=entrada, capture_output=True, timeout=8)

    def test_alternar_leituras_inteiro_texto_lista(self):
        codigo = '''inicio {
            seja numero = 0
            seja palavra: texto[32]
            seja itens: lista[2]
            leia(numero)
            leia(palavra)
            leia(itens[1])
            escreva(numero)
            escreva(palavra)
            escreva(itens[1])
        }'''
        for nivel in (0, 3, 6):
            with self.subTest(nivel=nivel):
                r = self.executar(codigo, '17\nCoração 🌎\n-31\n'.encode(), nivel)
                self.assertEqual((r.returncode, r.stdout), (0, '17\nCoração 🌎\n-31\n'.encode()), r.stderr)

    def test_multiplos_blocos_cache_e_ordem(self):
        codigo = '''inicio {
            seja i = 0
            seja total = 0
            enquanto i < 400 {
                leia(i)
                total = total + i
                i = i + 1
            }
            escreva(total)
        }'''
        # Controlled reading loop; 400 lines, each equal to its loop iteration.
        entrada = ''.join(f'{i}\n' for i in range(400)).encode()
        r = self.executar(codigo, entrada)
        self.assertEqual((r.returncode, r.stdout), (0, b'79800\n'), r.stderr)

    def test_unicode_multibyte_dividido_entre_blocos(self):
        codigo = 'inicio {\n seja mensagem: texto[1100]\n leia(mensagem)\n escreva(tamanho(mensagem))\n}'
        r = self.executar(codigo, b'A' * 1023 + '\u00e9'.encode() + b'\n')
        self.assertEqual((r.returncode, r.stdout), (0, b'1025\n'), r.stderr)
        r = self.executar(codigo, b'A' * 1023 + b'\xc3\n')
        self.assertEqual(r.returncode, 1)
        self.assertIn(b'UTF-8', r.stdout + r.stderr)

    def test_entrada_numerica_invalida_apos_prefetch(self):
        codigo = 'inicio {\n seja x = 0\n leia(x)\n leia(x)\n escreva(x)\n}'
        for dados in (b'12\nabc\n', b'12\n9223372036854775808\n', b'12\n'):
            with self.subTest(dados=dados):
                r = self.executar(codigo, dados)
                self.assertEqual(r.returncode, 1)
                self.assertIn(b'Erro:', r.stdout + r.stderr)

    def test_texto_consecutivo_apos_1024_bytes(self):
        codigo = 'inicio {\n seja a: texto[1100]\n seja b: texto[16]\n leia(a)\n leia(b)\n escreva(tamanho(a))\n escreva(b)\n}'
        r = self.executar(codigo, b'x'*1020 + b'\nFim\n')
        self.assertEqual((r.returncode, r.stdout), (0, b'1020\nFim\n'), r.stderr)

    def test_efeitos_ir_memoria_e_es(self):
        codigo = '''inicio {
            seja lista_a: lista[2]
            seja msg: texto[16]
            seja n = 1
            lista_a[0] = n
            copie(msg,"ola")
            junte(msg,"!")
            escreva(lista_a[0])
            escreva(msg)
            leia(n)
            leia(msg)
        }'''
        ir = construir_ir(analisar_programa(codigo))
        efeitos = listar_efeitos(ir)
        por_tag = {}
        for e in efeitos:
            por_tag.setdefault(e['operacao'], []).append(e)
        self.assertIn('lista_a', por_tag['atribua_indice'][0]['escritas'])
        self.assertIn('lista_a', por_tag['imprima_num'][0]['leituras'])
        self.assertTrue(por_tag['imprima_num'][0]['pode_falhar'])
        self.assertIn('msg', por_tag['modifique_texto'][1]['leituras'])
        self.assertTrue(por_tag['leia_int'][0]['entrada'])
        self.assertTrue(por_tag['leia_texto'][0]['entrada'])
        self.assertTrue(por_tag['leia_texto'][0]['pode_falhar'])
        self.assertTrue(por_tag['imprima_texto'][0]['saida'])
        objeto = json.loads(efeitos_para_json(ir))
        self.assertEqual(len(objeto['instrucoes']), len(efeitos))

    def test_cli_exporta_efeitos_com_texto_e_listas(self):
        with tempfile.TemporaryDirectory() as pasta:
            raiz = Path(pasta)
            json_saida = raiz / 'efeitos.json'
            exe = raiz / 'teste.exe'
            args = [sys.executable, str(RAIZ / 'compilar.py'),
                    str(RAIZ / 'exemplos/entrada_bufferizada.rts'),
                    '--alvo', 'windows', '-O', '6', '--mostrar-efeitos',
                    '--salvar-efeitos', str(json_saida), '-o', str(exe)]
            p = subprocess.run(args, capture_output=True, text=True, timeout=15)
            self.assertEqual(p.returncode, 0, p.stderr)
            self.assertIn('leia_texto', p.stdout)
            self.assertTrue(exe.read_bytes().startswith(b'MZ'))
            data = json.loads(json_saida.read_text(encoding='utf-8'))
            self.assertTrue(any(e['entrada'] for e in data['instrucoes']))
            self.assertTrue(any(e['escritas'] == ['valores'] for e in data['instrucoes']))

    def test_ir_efeitos_dentro_de_lacos(self):
        codigo = 'inicio {\n seja i = 0\n enquanto i < 2 {\n i = i + 1\n escreva(i)\n }\n}'
        r = listar_efeitos(construir_ir(analisar_programa(codigo)))
        self.assertTrue(any('corpo' in e['caminho'] for e in r))
        self.assertTrue(any(e['saida'] for e in r))


if __name__ == '__main__':
    unittest.main()
