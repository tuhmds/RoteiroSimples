"""SSA e alocação nativa de funções: semântica, chamadas e limites."""
from dataclasses import replace
import json
from pathlib import Path
import random
import subprocess
import sys
import tempfile
import unittest

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))
from backend import compilar
from backend.funcoes_ssa import construir_backend_funcoes_ssa, montar_funcoes_ssa
from compilador.estrategia import decidir_estrategia
from compilador.ir import construir_ir
from compilador.nos_ir import ExpressaoIR, InstrucaoIR
from compilador.parser import analisar_programa
from compilador.ssa import InstrucaoSSA
from compilador.ssa_funcoes import construir_ssa_programa
from testes.test_valores_dinamicos_rs042a import alvo_nativo, rodar


def levantar(fonte, nivel=0):
    return construir_ir(analisar_programa(fonte), nivel=nivel, otimizar=nivel > 0)


def fonte_grande(quantidade=270):
    return ('funcao grande(' + ', '.join(f'p{n}: inteiro' for n in range(quantidade)) +
            ') -> inteiro {\n retorne ' + ' + '.join(f'p{n}' for n in range(quantidade)) +
            '\n}\ninicio {\n escreva(grande(' + ', '.join(['1'] * quantidade) + '))\n}')


class TestesSSAFuncoesRS042L(unittest.TestCase):
    def executar(self, fonte, esperado, niveis=tuple(range(9)), entrada=None):
        programa = analisar_programa(fonte)
        for nivel in niveis:
            with self.subTest(nivel=nivel):
                for alvo in ('windows', 'linux'):
                    imagem = compilar(programa, alvo, nivel=nivel, otimizar=nivel > 0)
                    if alvo == alvo_nativo():
                        r, _ = rodar(imagem, entrada=entrada)
                self.assertEqual((r.returncode, r.stdout, r.stderr), (0, esperado, ''))
        return programa

    def test_parametros_no_primeiro_laco_e_phi_da_entrada(self):
        ir = levantar('''funcao contar(numero: inteiro, limite: inteiro) -> inteiro {
    enquanto numero < limite {
        numero = numero + 1
    }
    retorne numero
}
inicio {
    escreva(contar(1, 7))
}''')
        s = construir_ssa_programa(ir).funcoes['contar']
        self.assertTrue(s.validar())
        entrada = s.blocos[s.cfg.entrada]
        self.assertEqual([i.destino for i in entrada.instrucoes], ['numero@0', 'limite@0'])
        cond = next(b for b in s.blocos.values() if b.papel == 'enquanto:condicao')
        self.assertEqual(cond.phis['numero'].entradas[s.cfg.entrada], 'numero@0')
        self.executar('''funcao contar(numero: inteiro, limite: inteiro) -> inteiro {
    enquanto numero < limite {
        numero = numero + 1
    }
    retorne numero
}
inicio {
    escreva(contar(1, 7))
}''', '7\n')

    def test_tipos_logicos_parametros_e_retornos_sem_atribuicao_local(self):
        fonte = '''funcao inverter(valor: logico) -> logico {
    retorne valor == falso
}
funcao escolher(valor: logico, numero: inteiro) -> inteiro {
    se valor {
        retorne numero
    }
    retorne 0
}
inicio {
    escreva(escolher(inverter(falso), 17))
    escreva(inverter(verdadeiro))
}'''
        self.executar(fonte, '17\n0\n')
        s = construir_ssa_programa(levantar(fonte)).funcoes['inverter']
        self.assertEqual(s.tipos['valor'], 'logico')

    def test_ssa_preserva_origem_e_nao_cria_versoes_inalcancaveis(self):
        fonte = 'funcao valor(numero: inteiro) -> inteiro {\n retorne numero\n escreva(numero + 99)\n}\ninicio {\n escreva(valor(7))\n}'
        ir = levantar(fonte)
        s = construir_ssa_programa(ir).funcoes['valor']
        ret = next(b.instrucoes[0] for b in s.blocos.values() if b.papel == 'retorne')
        self.assertEqual(ret.origem, ir.funcoes['valor'].programa.instrucoes[0].origem)
        self.assertTrue(all(not b.instrucoes for b in s.blocos.values() if not b.alcancavel))
        self.executar(fonte, '7\n')

    def test_incremento_temporario_so_atualiza_contador_apos_teste(self):
        s = construir_ssa_programa(levantar('''funcao contar(limite: inteiro) -> inteiro {
    seja soma = 0
    para numero de 0 ate limite {
        soma = soma + numero
    }
    retorne soma
}
inicio {
    escreva(contar(3))
}''')).funcoes['contar']
        inc = next(b for b in s.blocos.values() if b.papel == 'para:incremento')
        grav = next(b for b in s.blocos.values() if b.papel == 'para:gravar_incremento')
        self.assertTrue(inc.instrucoes[0].destino.startswith('__rs_incremento_'))
        self.assertEqual(grav.instrucoes[0].usos, (inc.instrucoes[0].destino,))
        self.assertIn('numero@', grav.instrucoes[0].destino)
        self.assertTrue(s.validar())

    def test_o3_propaga_constante_de_ramos_sem_avaliar_chamada(self):
        fonte = '''funcao escolher(numero: inteiro) -> inteiro {
    seja valor = 0
    se numero > 0 {
        valor = 7
    } senao {
        valor = 7
    }
    retorne valor + 3
}
inicio {
    escreva(escolher(-1))
}'''
        ir2, ir3 = levantar(fonte, 2), levantar(fonte, 3)
        self.assertEqual(ir2.funcoes['escolher'].programa.instrucoes[-1].argumentos[0].operacao, 'bin')
        self.assertEqual(ir3.funcoes['escolher'].programa.instrucoes[-1].argumentos[0].valor, 10)
        self.assertEqual(ir3.instrucoes[0].argumentos[0].operacao, 'chamada')
        self.executar(fonte, '10\n')

    def test_alocacao_por_funcao_e_valores_vivos_apos_chamadas(self):
        fonte = '''funcao alterar(numero: inteiro) -> inteiro {
    seja a = numero + 1
    seja b = numero + 2
    seja c = numero + 3
    retorne a + b + c
}
funcao calcular(numero: inteiro) -> inteiro {
    seja a = numero + 10
    seja b = numero + 20
    seja c = numero + 30
    seja d = numero + 40
    seja resultado_e = alterar(numero)
    retorne a + b + c + d + resultado_e + alterar(resultado_e)
}
inicio {
    seja a = 99
    escreva(calcular(2))
    escreva(a)
}'''
        self.executar(fonte, '162\n99\n')
        plano = construir_backend_funcoes_ssa(levantar(fonte, 3), coalescer=True)
        aloc = plano.alocacoes['calcular']
        self.assertGreater(aloc.vagas_pilha, 0)
        self.assertEqual({l.indice for l in aloc.locais.values() if l.classe == 'reg'}, {'r13', 'r14', 'r15'})
        for nome, ssa in plano.programa.funcoes.items():
            aloc = plano.alocacoes[nome]
            for valor, vizinhos in aloc.interferencias.items():
                self.assertTrue(all(aloc.locais[valor] != aloc.locais[outro] for outro in vizinhos))

    def test_argumentos_aninhados_avaliados_na_ordem_com_pilha_pendente(self):
        fonte = '''funcao marcar(numero: inteiro) -> inteiro {
    escreva(numero)
    retorne numero
}
funcao somar(a: inteiro, b: inteiro, c: inteiro) -> inteiro {
    retorne a + b + c
}
inicio {
    escreva(100 + somar(marcar(1), somar(marcar(2), marcar(3), marcar(4)), marcar(5)))
}'''
        self.executar(fonte, '1\n2\n3\n4\n5\n115\n')

    def test_aridade_par_impar_grande_e_ordem_dos_argumentos(self):
        for n in (0, 1, 2, 5, 16, 17):
            parametros = ', '.join(f'p{i}: inteiro' for i in range(n))
            valor = ' + '.join(f'p{i} * {i + 1}' for i in range(n)) or '7'
            argumentos = ', '.join(str(i + 1) for i in range(n))
            fonte = f'funcao valor({parametros}) -> inteiro {{\n retorne {valor}\n}}\ninicio {{\n escreva(valor({argumentos}))\n}}'
            self.executar(fonte, str(sum(i * i for i in range(1, n + 1)) if n else 7) + '\n')

    def test_quadros_com_muitas_vagas_e_sondagem_de_paginas(self):
        fonte = fonte_grande()
        ir = levantar(fonte, 3)
        plano = construir_backend_funcoes_ssa(ir)
        self.assertGreater(plano.alocacoes['grande'].vagas_pilha, 256)
        gerador, _ = montar_funcoes_ssa(ir, True, 8)
        self.assertGreaterEqual(gerador.quadros_funcoes['grande'], 4096)
        self.assertTrue(gerador.exige_sondagem_pilha)
        self.executar(fonte, '270\n', niveis=(0, 3, 4, 8))

    def test_guardas_de_falha_em_argumentos_nao_sao_eliminadas(self):
        for expr in ('1 / 0', '9223372036854775807 + 1', '-9223372036854775808 % -1'):
            fonte = 'funcao ignorar(a: inteiro) -> inteiro {\n retorne 7\n}\ninicio {\n escreva("ANTES")\n escreva(ignorar(' + expr + '))\n escreva("INDEVIDO")\n}'
            resultados = []
            for nivel in range(9):
                r, _ = rodar(compilar(analisar_programa(fonte), alvo_nativo(), nivel=nivel, otimizar=nivel > 0))
                self.assertEqual(r.returncode, 1)
                self.assertTrue((r.stdout + r.stderr).startswith('ANTES\nErro:'))
                self.assertNotIn('INDEVIDO', r.stdout)
                resultados.append((r.returncode, r.stdout, r.stderr))
            self.assertTrue(all(r == resultados[0] for r in resultados))

    def test_validador_rejeita_leitura_antes_da_definicao_no_mesmo_bloco(self):
        s = construir_ssa_programa(levantar('funcao valor(numero: inteiro) -> inteiro {\n retorne numero\n}\ninicio {\n escreva(valor(7))\n}')).funcoes['valor']
        entrada = s.blocos[s.cfg.entrada]
        fonte = ExpressaoIR('inteiro', 'var', 'numero@0')
        entrada.instrucoes.insert(0, InstrucaoSSA('imprima_num', None, (fonte,), ('numero@0',)))
        with self.assertRaisesRegex(ValueError, 'antes da definição'):
            s.validar()

    def test_validador_rejeita_uso_oculto_e_assinatura_incompativel(self):
        fonte = 'funcao valor(numero: inteiro) -> inteiro {\n retorne numero\n}\ninicio {\n seja n = 7\n escreva(valor(n))\n}'
        programa = construir_ssa_programa(levantar(fonte))
        instr = next(b for b in programa.principal.blocos.values() if b.papel == 'imprima_num')
        instr.instrucoes[0] = replace(instr.instrucoes[0], usos=())
        with self.assertRaisesRegex(ValueError, 'Usos SSA incompatíveis'):
            programa.validar()
        ir = levantar(fonte)
        chamada = ir.instrucoes[-1].argumentos[0]
        ir = replace(ir, instrucoes=(*ir.instrucoes[:-1], InstrucaoIR('imprima_num', (replace(chamada, filhos=()),))))
        with self.assertRaisesRegex(ValueError, 'assinatura'):
            construir_ssa_programa(ir)

    def test_cli_exporta_todas_funcoes_e_alocacao_real(self):
        with tempfile.TemporaryDirectory() as pasta:
            pasta = Path(pasta)
            dados, executavel = pasta / 'ssa.json', pasta / 'a.exe'
            r = subprocess.run([sys.executable, str(RAIZ / 'compilar.py'), str(RAIZ / 'exemplos/fluxo_funcoes_rs042k.rts'),
                                '-O', '8', '--mostrar-ssa', '--salvar-ssa', str(dados), '--mostrar-alocacao',
                                '--mostrar-copias-phi', '--mostrar-estrategia', '-o', str(executavel)],
                               capture_output=True, encoding='utf-8', timeout=15)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertIn('nativo com alocação SSA', r.stdout)
            self.assertIn('r13', r.stdout)
            self.assertIn('funcao somar:', r.stdout)
            j = json.loads(dados.read_text(encoding='utf-8'))
            self.assertEqual(j['versao'], 'RS 0.42O')
            self.assertEqual(set(j['funcoes']), {'somar', 'parcela'})
            self.assertEqual(j['funcoes']['parcela']['parametros'], [['numero', 'inteiro']])
            self.assertTrue(executavel.exists())

    def test_oraculo_independente_com_valores_vivos_e_chamadas(self):
        gerador = random.Random(420120)
        for _ in range(16):
            valor, ajuste, multiplicador = gerador.randint(-30, 30), gerador.randint(1, 8), gerador.randint(1, 5)
            fonte = f'''funcao parcela(numero: inteiro) -> inteiro {{
    se numero > 0 {{
        retorne numero * {multiplicador}
    }}
    retorne numero - {ajuste}
}}
funcao calcular(numero: inteiro) -> inteiro {{
    seja a = numero + 1
    seja b = numero + 2
    seja c = numero + 3
    seja d = numero + 4
    seja resultado = parcela(numero)
    retorne a + b + c + d + resultado + parcela(resultado)
}}
inicio {{
    escreva(calcular({valor}))
}}'''
            primeiro = valor * multiplicador if valor > 0 else valor - ajuste
            segundo = primeiro * multiplicador if primeiro > 0 else primeiro - ajuste
            esperado = 4 * valor + 10 + primeiro + segundo
            self.executar(fonte, str(esperado) + '\n')
