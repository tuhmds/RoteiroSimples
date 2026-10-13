"""Funções escalares na IR: tipos, efeitos, equivalência e erros nativos."""
from pathlib import Path
import random
import sys
import unittest

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))
from backend import compilar
from compilador.cfg import construir_cfg
from compilador.efeitos import efeito_expressao, efeito_instrucao, listar_efeitos
from compilador.erros import ErroCompilacao
from compilador.estrategia import decidir_estrategia
from compilador.ir import construir_ir, programa_para_backend, formatar_ir
from compilador.parser import analisar_programa
from testes.test_cobertura_intermediaria_rs040c import executar_cli
from testes.test_valores_dinamicos_rs042a import alvo_nativo, rodar

FONTE = '''funcao calcular(numero: inteiro) -> inteiro {
    seja fator = 3 + 4
    seja ajuste = 9 * 2
    retorne numero * fator + ajuste
}
inicio {
    escreva(calcular(6))
}'''


class TestesFuncoesIRRS042J(unittest.TestCase):
    def verificar(self, fonte, esperado, niveis=tuple(range(9)), erro=None):
        programa = analisar_programa(fonte)
        for nivel in niveis:
            with self.subTest(nivel=nivel):
                for alvo in ('windows', 'linux'):
                    imagem = compilar(programa, alvo, nivel=nivel, otimizar=nivel > 0)
                    if alvo == alvo_nativo():
                        resultado, _ = rodar(imagem)
                self.assertEqual(resultado.returncode, 1 if erro else 0, resultado.stdout + resultado.stderr)
                if erro:
                    self.assertIn(erro, resultado.stdout + resultado.stderr)
                    self.assertNotIn('INDEVIDO', resultado.stdout)
                else:
                    self.assertEqual(resultado.stdout, esperado)
        return programa

    def test_gerador_e_nivel_real_e_codigo_otimizado(self):
        programa = self.verificar(FONTE, '60\n')
        for nivel in range(9):
            estrategia = decidir_estrategia(programa, nivel, nivel > 0)
            self.assertEqual((estrategia.gerador, estrategia.nivel_ir), ('intermediario', min(nivel, 2)))
        for alvo in ('windows', 'linux'):
            self.assertNotEqual(compilar(programa, alvo, nivel=0, otimizar=False), compilar(programa, alvo, nivel=8))
        ir = construir_ir(programa, nivel=2)
        self.assertIn('numero:inteiro(7)', formatar_ir(ir))
        self.assertIn('numero:inteiro(18)', formatar_ir(ir))

    def test_ida_e_volta_preserva_assinaturas_recursao_e_origem(self):
        fonte = '''funcao repetir(numero: inteiro) -> inteiro {
    se numero == 0 {
        retorne 7
    }
    retorne repetir(numero - 1)
}
inicio {
    escreva(repetir(5))
}'''
        programa = analisar_programa(fonte)
        reconstruido = programa_para_backend(construir_ir(programa, otimizar=False))
        self.assertEqual(reconstruido.instrucoes, programa.instrucoes)
        original, novo = programa.funcoes['repetir'], reconstruido.funcoes['repetir']
        self.assertEqual((novo.parametros, novo.retorno, novo.recursiva),
                         (original.parametros, original.retorno, original.recursiva))
        self.assertEqual(novo.programa.instrucoes, original.programa.instrucoes)
        self.assertEqual(novo.programa.instrucoes[-1].origem, original.programa.instrucoes[-1].origem)
        self.assertEqual(novo.programa.instrucoes[-1][1].origem, original.programa.instrucoes[-1][1].origem)
        self.verificar(fonte, '7\n')

    def test_logicos_e_argumentos_avaliados_na_ordem_com_efeitos(self):
        fonte = '''funcao marcar(numero: inteiro) -> inteiro {
    escreva(numero)
    retorne numero
}
funcao maior(a: inteiro, b: inteiro) -> logico {
    retorne a > b
}
funcao combinar(a: inteiro, b: logico, c: inteiro) -> inteiro {
    se b {
        retorne a + c
    }
    retorne a - c
}
inicio {
    escreva(3 + combinar(marcar(10), maior(marcar(2), marcar(1)), marcar(7)))
}'''
        self.verificar(fonte, '10\n2\n1\n7\n20\n')

    def test_retornos_antecipados_lacos_pare_continue_e_sombreamento(self):
        fonte = '''funcao calcular(limite: inteiro) -> inteiro {
    seja total = 0
    para numero de 0 ate limite {
        se numero == 2 {
            continue
        }
        se numero == 6 {
            pare
        }
        seja fator = 1 + 2
        total = total + numero * fator
        se total > 100 {
            retorne total
        }
    }
    se total == 39 {
        seja total = 7
        escreva(total)
    }
    retorne total
}
inicio {
    escreva(calcular(20))
}'''
        self.verificar(fonte, '7\n39\n')

    def test_funcoes_mutuamente_recursivas_e_orcamento(self):
        fonte = '''funcao par(numero: inteiro) -> logico {
    se numero == 0 {
        retorne verdadeiro
    }
    retorne impar(numero - 1)
}
funcao impar(numero: inteiro) -> logico {
    se numero == 0 {
        retorne falso
    }
    retorne par(numero - 1)
}
inicio {
    escreva(par(42))
    escreva(impar(43))
}'''
        self.verificar(fonte, '1\n1\n')
        self.verificar(fonte.replace('par(42)', 'par(1000000)').replace('escreva(impar(43))', 'escreva("INDEVIDO")'),
                       '', niveis=(0, 2, 8), erro='limite seguro de pilha')

    def test_overflow_divisao_resto_e_ordem_da_falha(self):
        for expressao in ('9223372036854775807 + 1', '1 / 0', '-9223372036854775808 / -1',
                         '-9223372036854775808 % -1', '-(-9223372036854775808)'):
            fonte = 'funcao falhar() -> inteiro {\n escreva("ANTES")\n retorne ' + expressao + '\n}\ninicio {\n escreva(falhar())\n escreva("INDEVIDO")\n}'
            programa = analisar_programa(fonte)
            resultados = []
            for nivel in (0, 1, 2, 8):
                observado, _ = rodar(compilar(programa, alvo_nativo(), nivel=nivel, otimizar=nivel > 0))
                self.assertEqual(observado.returncode, 1)
                self.assertTrue(observado.stdout.startswith('ANTES\nErro:'))
                self.assertNotIn('INDEVIDO', observado.stdout)
                resultados.append((observado.returncode, observado.stdout, observado.stderr))
            self.assertTrue(all(r == resultados[0] for r in resultados))

    def test_minimo_inteiro_e_divisao_truncada_para_zero(self):
        fonte = '''funcao dividir(numero: inteiro) -> inteiro {
    retorne numero / 3
}
funcao resto(numero: inteiro) -> inteiro {
    retorne numero % 3
}
funcao minimo() -> inteiro {
    retorne -9223372036854775808
}
inicio {
    escreva(dividir(-8))
    escreva(resto(-8))
    escreva(minimo())
}'''
        self.verificar(fonte, '-2\n-2\n-9223372036854775808\n')

    def test_oraculo_aritmetico_independente_com_programas_gerados(self):
        gerador = random.Random(420100)
        for _ in range(12):
            a, b, c = [gerador.randint(-99, 99) for _ in range(3)]
            fator, ajuste = gerador.randint(1, 9), gerador.randint(1, 20)
            fonte = f'''funcao calcular(numero: inteiro, ajuste: inteiro) -> inteiro {{
    seja fator = {fator} + 2
    retorne numero * fator + ajuste
}}
funcao combinar(a: inteiro, b: inteiro, c: inteiro) -> inteiro {{
    retorne calcular(a, {ajuste}) + calcular(b, c)
}}
inicio {{
    escreva(combinar({a}, {b}, {c}))
}}'''
            esperado = a * (fator + 2) + ajuste + b * (fator + 2) + c
            self.verificar(fonte, str(esperado) + '\n', niveis=(0, 2, 8))

    def test_chamada_e_retorno_sao_barreiras_de_efeitos(self):
        ir = construir_ir(analisar_programa(FONTE), otimizar=False)
        chamada = ir.instrucoes[0].argumentos[0]
        efeito = efeito_expressao(chamada)
        self.assertTrue(efeito.desconhecido and efeito.pode_falhar and efeito.barreira_de_reordenacao)
        retorno = efeito_instrucao(ir.funcoes['calcular'].programa.instrucoes[-1])
        self.assertTrue(retorno.encerra and retorno.controle)
        self.assertTrue(any(item['caminho'].startswith('funcao:calcular') for item in listar_efeitos(ir)))

    def test_tipos_compostos_e_operacoes_desconhecidas_continuam_conservadores(self):
        for fonte in ('funcao medir(dados: bytes) -> inteiro {\n retorne tamanho(dados)\n}\ninicio {\n escreva(1)\n}',
                       'tipo Registro {\n numero: inteiro\n}\nfuncao medir(numero: inteiro) -> inteiro {\n retorne numero\n}\ninicio {\n escreva(medir(1))\n}'):
            programa = analisar_programa(fonte)
            self.assertEqual(decidir_estrategia(programa, 8).gerador, 'conservador')
            with self.assertRaisesRegex(ErroCompilacao, 'representação intermediária'):
                construir_ir(programa, nivel=8)

    def test_cli_mostra_corpos_ir_e_rejeita_ssa_indisponivel(self):
        retorno, existe = executar_cli(FONTE, ('-O', '8', '--mostrar-ir', '--mostrar-efeitos', '--mostrar-estrategia'))
        self.assertEqual(retorno.returncode, 0, retorno.stderr)
        self.assertTrue(existe)
        self.assertIn('funcao calcular:', retorno.stdout)
        self.assertIn('análises IR até o nível 2', retorno.stdout)
        retorno, existe = executar_cli(FONTE, ('-O', '8', '--mostrar-ssa'))
        self.assertEqual(retorno.returncode, 1)
        self.assertFalse(existe)
        self.assertNotIn('Traceback', retorno.stderr)
        with self.assertRaisesRegex(ValueError, 'CFG/SSA'):
            construir_cfg(construir_ir(analisar_programa(FONTE)))
        with self.assertRaisesRegex(ValueError, 'retornos de função'):
            construir_cfg(construir_ir(analisar_programa(FONTE)).funcoes['calcular'].programa)
