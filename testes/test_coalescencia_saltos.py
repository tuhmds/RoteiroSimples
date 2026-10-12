"""RS 0.16: saltos rel8, coalescencia, equivalencia O5/O6 e erros nativos."""
import os
import random
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))
from backend import compilar
from tamanho_codigo import tamanho_codigo_elf
from backend.ssa_x86_64 import construir_backend_ssa, copias_paralelas
from backend.x86_64 import Gerador
from compilador.alocacao import Local
from compilador.ir import construir_ir
from compilador.parser import analisar_programa


class TesteRelaxacao(unittest.TestCase):
    def test_salto_curto_frente_e_atras(self):
        g = Gerador()
        g.ativar_saltos_curtos_ssa()
        g.marcar('ssa_inicio')
        g.salto('ssa_fim')
        g.bytes(b'\x90' * 9)
        g.marcar('ssa_fim')
        g.salto('ssa_inicio')
        self.assertEqual(g.compactar_saltos_ssa(), 2)
        self.assertEqual(bytes(g.codigo[:2]), b'\xeb\x09')
        self.assertEqual(bytes(g.codigo[-2:]), b'\xeb\xf3')
        self.assertEqual(g.pendencias, [])
        self.assertEqual(g.saltos_compactados, 2)

    def test_fronteira_rel8_positiva_e_negativa(self):
        for distancia, compacta in ((127, True), (128, False)):
            with self.subTest(frente=distancia):
                g = Gerador()
                g.ativar_saltos_curtos_ssa()
                g.salto('ssa_alvo')
                g.bytes(b'\x90' * distancia)
                g.marcar('ssa_alvo')
                self.assertEqual(g.compactar_saltos_ssa(), int(compacta))
        for espaco, compacta in ((126, True), (127, False)):
            with self.subTest(atras=espaco):
                g = Gerador()
                g.ativar_saltos_curtos_ssa()
                g.marcar('ssa_inicio')
                g.bytes(b'\x90' * espaco)
                g.salto('ssa_inicio')
                self.assertEqual(g.compactar_saltos_ssa(), int(compacta))

    def test_ponto_fixo_reduz_outro_salto(self):
        g = Gerador()
        g.ativar_saltos_curtos_ssa()
        g.salto('ssa_fim')
        g.bytes(b'\x90' * 9)
        g.salto('ssa_perto')
        g.marcar('ssa_perto')
        g.bytes(b'\x90' * 114)
        g.marcar('ssa_fim')
        # O primeiro salto so cabe depois de encolher o segundo.
        self.assertEqual(g.compactar_saltos_ssa(), 2)
        self.assertEqual(g.codigo[0], 0xeb)
        g.finalizar(0x100, {})

    def test_salto_condicional_e_relocacoes_que_permanecem(self):
        g = Gerador()
        g.ativar_saltos_curtos_ssa()
        g.marcar('ssa_inicio')
        g.salto('ssa_alvo', 'jz')
        g.chamada('funcao')
        g.relativo(b'\x48\x8d\x15', 'mensagem')
        g.marcar('ssa_alvo')
        g.bytes(b'\x90')
        g.marcar('funcao')
        g.bytes(b'\xc3')
        self.assertEqual(g.compactar_saltos_ssa(), 1)
        self.assertEqual(bytes(g.codigo[:2]), b'\x74\x0c')
        g.finalizar(0x100, {'mensagem': 0x200})
        self.assertEqual(g.codigo[g.rotulos['funcao']], 0xc3)
        self.assertEqual(len(g.pendencias), 2)
        self.assertEqual(g.codigo[2], 0xe8)

    def test_salto_longo_nao_cabe_e_nao_muda(self):
        g = Gerador()
        g.ativar_saltos_curtos_ssa()
        g.salto('ssa_longe')
        g.bytes(b'\x90' * 170)
        g.marcar('ssa_longe')
        g.bytes(b'\xc3')
        self.assertEqual(g.compactar_saltos_ssa(), 0)
        self.assertEqual(bytes(g.codigo[:1]), b'\xe9')
        g.finalizar(0x100, {})
        self.assertEqual(bytes(g.codigo[1:5]), (170).to_bytes(4, 'little', signed=True))

    def test_sem_mudar_backend_antigo(self):
        g = Gerador()
        g.salto('ssa_a')
        g.marcar('ssa_a')
        self.assertEqual(g.compactar_saltos_ssa(), 0)
        self.assertEqual(len(g.codigo), 5)

    def test_copias_diretas_e_ciclo(self):
        locais = {'a': Local('reg', 'r13'), 'b': Local('reg', 'r14'),
                  'c': Local('reg', 'r15')}
        g = Gerador()
        self.assertEqual(copias_paralelas(g, [('a', 'b')], locais,
                             Local('pilha', 0), False, diretas=True), 1)
        self.assertEqual(len(g.codigo), 3)
        g = Gerador()
        self.assertGreater(copias_paralelas(g, [('a', 'b'), ('b', 'a')], locais,
                              Local('pilha', 0), False, diretas=True), 2)

    def test_conserva_copias_phi_no_sem_conflitos(self):
        src = '''inicio {
 seja entrada = 0
 seja resultado = 1
 leia(entrada)
 se entrada > 0 {
   resultado = entrada + 2
 } senao {
   resultado = entrada - 2
 }
 escreva(resultado)
}'''
        ir = construir_ir(analisar_programa(src), nivel=3)
        ssa, aloc = construir_backend_ssa(ir, coalescer=True)
        ssa.validar()
        for v, conflitos in aloc.interferencias.items():
            for u in conflitos:
                self.assertNotEqual(aloc.locais[v], aloc.locais[u])


class TesteIntegracaoO6(unittest.TestCase):
    def executar(self, src, nivel, entrada='21\n'):
        alvo = 'windows' if sys.platform == 'win32' else 'linux'
        if sys.platform not in ('win32', 'linux'):
            self.skipTest('Windows ou Linux x86-64')
        if alvo == 'linux' and os.uname().machine != 'x86_64':
            self.skipTest('Linux x86-64')
        programa = analisar_programa(src)
        with tempfile.TemporaryDirectory() as temp:
            exe = Path(temp) / ('teste.exe' if alvo == 'windows' else 'teste')
            exe.write_bytes(compilar(programa, alvo, nivel=nivel))
            if alvo == 'linux':
                exe.chmod(0o755)
            resultado = subprocess.run([str(exe)], input=entrada, text=True,
                                       capture_output=True, timeout=10, encoding='utf-8')
        return (resultado.returncode, resultado.stdout, resultado.stderr)

    def test_exemplos_iguais_a_o5(self):
        for path in sorted((RAIZ / 'exemplos').glob('*.rts')):
            with self.subTest(exemplo=path.name):
                from compilador.modulos import carregar_fontes
                fonte = carregar_fontes(path).texto
                self.assertEqual(self.executar(fonte, 5), self.executar(fonte, 6))

    def test_erros_iguais_a_o5(self):
        fontes = (
            'inicio {\n seja n = 9223372036854775807\n escreva(n+1)\n}',
            'inicio {\n seja n = -9223372036854775808\n escreva(n-1)\n}',
            'inicio {\n seja n = 0\n escreva(17/n)\n}',
            'inicio {\n seja n = 5000000000\n escreva(n*n)\n}',
            'inicio {\n seja n = -9223372036854775808\n escreva(-n)\n}',
        )
        for src in fontes:
            with self.subTest(fonte=src[:65]):
                a, b = self.executar(src, 5), self.executar(src, 6)
                self.assertNotEqual(a[0], 0)
                self.assertEqual(a, b)

    def test_40_programas_aleatorios(self):
        rng = random.Random(1616)
        for n in range(40):
            fim = rng.randint(2, 30)
            passo = rng.randint(1, 7)
            divisor = rng.randint(2, 9)
            sinal = rng.choice(('+', '-'))
            codigo = f'''inicio {{
                seja acc = 0
                para i de 1 ate {fim} {{
                    se i % {divisor} == 0 {{
                        acc = acc + {passo}
                    }} senao {{
                        acc = acc {sinal} i
                    }}
                    se i == {fim-1} {{\n                        continue\n                    }}
                }}
                escreva(acc)
            }}'''
            with self.subTest(caso=n):
                self.assertEqual(self.executar(codigo, 5), self.executar(codigo, 6))

    def test_compilacao_deterministica_e_tamanho(self):
        fonte = (RAIZ/'exemplos'/'registradores.rts').read_text(encoding='utf-8')
        prog = analisar_programa(fonte)
        for alvo in ('linux', 'windows'):
            with self.subTest(alvo=alvo):
                a = compilar(prog, alvo, nivel=6)
                self.assertEqual(a, compilar(prog, alvo, nivel=6))
                if alvo == 'linux':
                    self.assertLess(tamanho_codigo_elf(a), tamanho_codigo_elf(compilar(prog, alvo, nivel=5)))


if __name__ == '__main__':
    unittest.main()
