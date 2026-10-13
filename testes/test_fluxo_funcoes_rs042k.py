"""Fluxo por função: saídas reais, parâmetros, efeitos e execução nativa."""
from dataclasses import replace
import hashlib
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
from compilador.cfg import construir_cfg, construir_cfg_funcao, construir_cfg_programa
from compilador.efeitos import efeito_expressao, efeitos_para_json, resumir_funcoes
from compilador.erros import ErroCompilacao
from compilador.fluxo_dados import analisar_fluxo
from compilador.fluxo_funcoes import analisar_fluxo_programa
from compilador.ir import construir_ir
from compilador.memory_ssa import construir_memory_ssa
from compilador.nos_ir import ExpressaoIR, InstrucaoIR
from compilador.parser import analisar_programa
from compilador.ssa import construir_ssa
from testes.test_valores_dinamicos_rs042a import alvo_nativo, rodar


FONTE = '''funcao escolher(numero: inteiro, limite: inteiro) -> inteiro {
    se numero > limite {
        retorne numero
        escreva("INDEVIDO")
    } senao {
        retorne limite
    }
    escreva("TAMBEM_INDEVIDO")
}
inicio {
    escreva(escolher(4, 7))
}'''


def levantar(fonte):
    return construir_ir(analisar_programa(fonte), otimizar=False, nivel=0)


class TestesFluxoFuncoesRS042K(unittest.TestCase):
    def test_parametros_definidos_na_entrada_e_retorno_usa_valores(self):
        fluxo = analisar_fluxo_programa(levantar(FONTE)).funcoes['escolher']
        nomes = {'numero', 'limite'}
        self.assertEqual(fluxo.definicoes[fluxo.cfg.entrada], nomes)
        self.assertEqual(fluxo.vivos_saida[fluxo.cfg.entrada], nomes)
        self.assertEqual(fluxo.vivos_entrada[fluxo.cfg.entrada], set())
        self.assertTrue(all(not fluxo.sem_definicao[b] for b in fluxo.cfg.alcancaveis()))
        retornos = [b for b in fluxo.cfg.blocos.values() if b.papel == 'retorne']
        self.assertEqual(len(retornos), 2)
        self.assertEqual(set.union(*(fluxo.usos[b.id] for b in retornos)), nomes)
        for b in retornos:
            self.assertEqual([(a.motivo, a.destino) for a in b.saidas], [('retorne', fluxo.cfg.saida)])
            self.assertEqual(fluxo.vivos_saida[b.id], set())
            self.assertEqual(fluxo.garantidas_entrada[b.id], nomes)

    def test_codigo_apos_retornos_inalcancavel_e_sem_efeitos_no_resumo(self):
        ir = levantar(FONTE)
        fluxo = analisar_fluxo_programa(ir)
        funcao = fluxo.funcoes['escolher']
        mortos = funcao.cfg.inalcancaveis()
        self.assertEqual(len(mortos), 2)
        self.assertTrue(all(funcao.cfg.blocos[b].papel == 'texto' for b in mortos))
        self.assertTrue(all(not funcao.entradas_def[b] and not funcao.garantidas_entrada[b] for b in mortos))
        self.assertFalse(fluxo.resumos['escolher'].saida)
        self.assertFalse(fluxo.resumos['escolher'].desconhecido)
        self.assertIn('inacessivel', fluxo.formatar())

    def test_retornos_em_lacos_nao_passam_pelo_incremento(self):
        ir = levantar('''funcao buscar(limite: inteiro) -> inteiro {
    para numero de 0 ate limite {
        se numero == 2 {
            continue
        }
        enquanto numero > 3 {
            retorne numero
        }
        se numero == 3 {
            pare
        }
    }
    retorne limite
}
inicio {
    escreva(buscar(8))
}''')
        grafo = construir_cfg_funcao(ir.funcoes['buscar'])
        inc = next(b.id for b in grafo.blocos.values() if b.papel == 'para:incremento')
        continuar = next(b for b in grafo.blocos.values() if b.papel == 'continue')
        parar = next(b for b in grafo.blocos.values() if b.papel == 'pare')
        self.assertEqual(continuar.saidas[0].destino, inc)
        self.assertEqual(grafo.blocos[parar.saidas[0].destino].papel, 'retorne')
        self.assertTrue(all(b.saidas[0].destino == grafo.saida
                            for b in grafo.blocos.values() if b.papel == 'retorne'))
        self.assertFalse(any(analisar_fluxo(grafo).sem_definicao.values()))

    def test_atribuicao_de_parametro_chega_ao_retorno(self):
        ir = levantar('''funcao ajustar(numero: inteiro) -> inteiro {
    se numero > 0 {
        numero = 2
    } senao {
        numero = 3
    }
    retorne numero
}
inicio {
    escreva(ajustar(7))
}''')
        fluxo = analisar_fluxo_programa(ir).funcoes['ajustar']
        ret = next(b.id for b in fluxo.cfg.blocos.values() if b.papel == 'retorne')
        self.assertEqual(len(fluxo.phi_candidatos[ret]['numero']), 2)
        self.assertNotIn(f'{fluxo.cfg.entrada}:numero', fluxo.entradas_def[ret])
        self.assertIn('numero', fluxo.garantidas_entrada[ret])

    def test_estouro_do_incremento_sai_sem_gravar_contador(self):
        for inicial, passo in ((9223372036854775807, 1), (-9223372036854775808, -1)):
            fonte = f'''funcao contar() -> inteiro {{
    seja total = 0
    para numero de {inicial} ate {inicial} passo {passo} {{
        total = total + 1
    }}
    retorne total
}}
inicio {{
    escreva(contar())
}}'''
            ir = levantar(fonte)
            fluxo = analisar_fluxo_programa(ir).funcoes['contar']
            inc = next(b for b in fluxo.cfg.blocos.values() if b.papel == 'para:incremento')
            self.assertEqual(fluxo.definicoes[inc.id], set())
            self.assertEqual([a.motivo for a in inc.saidas], ['proximo', 'estouro_incremento'])
            self.assertEqual(fluxo.cfg.blocos[inc.saidas[1].destino].papel, 'retorne')
            gravacao = fluxo.cfg.blocos[inc.saidas[0].destino]
            self.assertEqual(gravacao.papel, 'para:gravar_incremento')
            self.assertEqual(fluxo.definicoes[gravacao.id], {'numero'})
            for nivel in range(9):
                r, _ = rodar(compilar(analisar_programa(fonte), alvo_nativo(), nivel=nivel, otimizar=nivel > 0))
                self.assertEqual((r.returncode, r.stdout, r.stderr), (0, '1\n', ''))

    def test_entrada_no_inicio_e_ordem_das_falhas_preservadas(self):
        fonte = '''funcao dividir(numero: inteiro) -> inteiro {
    escreva("ANTES")
    retorne 10 / numero
}
inicio {
    seja numero = 0
    leia(numero)
    escreva(dividir(numero))
    escreva("DEPOIS")
}'''
        for entrada, sucesso in (('2\n', True), ('0\n', False), ('invalido\n', False)):
            resultados = []
            for nivel in range(9):
                programa = analisar_programa(fonte)
                analisar_fluxo_programa(construir_ir(programa, nivel=nivel, otimizar=nivel > 0))
                r, _ = rodar(compilar(programa, alvo_nativo(), nivel=nivel, otimizar=nivel > 0), entrada=entrada)
                resultados.append((r.returncode, r.stdout, r.stderr))
                self.assertEqual(r.returncode, 0 if sucesso else 1)
                if sucesso:
                    self.assertEqual(r.stdout, 'ANTES\n5\nDEPOIS\n')
                else:
                    self.assertIn('Erro:', r.stdout + r.stderr)
                    self.assertNotIn('DEPOIS', r.stdout)
            self.assertTrue(all(r == resultados[0] for r in resultados))

    def test_retorno_antecipado_exclui_definicao_da_juncao(self):
        ir = levantar('''funcao ajustar(numero: inteiro) -> inteiro {
    seja valor = 10
    se numero > 0 {
        valor = 99
        retorne valor
    }
    retorne valor
}
inicio {
    escreva(ajustar(0))
}''')
        fluxo = analisar_fluxo_programa(ir).funcoes['ajustar']
        retornos = [b.id for b in fluxo.cfg.blocos.values() if b.papel == 'retorne']
        self.assertEqual(len(retornos), 2)
        self.assertTrue(all(len([d for d in fluxo.entradas_def[b] if d.endswith(':valor')]) == 1 for b in retornos))
        self.assertTrue(all('valor' not in fluxo.phi_candidatos.get(b, {}) for b in retornos))

    def test_definicao_possivel_em_um_ramo_nao_e_garantida(self):
        # IR sintetizada: o parser normalmente inicializa toda declaração.
        ir = levantar('''inicio {
    seja condicao = 1
    seja valor = 10
    se condicao {
        valor = 20
    }
    escreva(valor)
}''')
        ir = replace(ir, instrucoes=(ir.instrucoes[0], *ir.instrucoes[2:]))
        fluxo = analisar_fluxo(construir_cfg(ir))
        leitura = next(b.id for b in fluxo.cfg.blocos.values() if b.papel == 'imprima_num')
        self.assertTrue(any(d.endswith(':valor') for d in fluxo.entradas_def[leitura]))
        self.assertIn('valor', fluxo.sem_definicao[leitura])
        self.assertNotIn('valor', fluxo.garantidas_entrada[leitura])

    def test_parametro_garantido_mesmo_com_retroaresta(self):
        fluxo = analisar_fluxo_programa(levantar('''funcao repetir(numero: inteiro) -> inteiro {
    enquanto numero < 4 {
        numero = numero + 1
    }
    retorne numero
}
inicio {
    escreva(repetir(0))
}''')).funcoes['repetir']
        cond = next(b.id for b in fluxo.cfg.blocos.values() if b.papel == 'enquanto:condicao')
        self.assertEqual(len(fluxo.phi_candidatos[cond]['numero']), 2)
        self.assertIn('numero', fluxo.garantidas_entrada[cond])
        self.assertFalse(any(fluxo.sem_definicao.values()))

    def test_nomes_iguais_e_sombreamento_ficam_em_escopos_separados(self):
        ir = levantar('''funcao primeira(numero: inteiro) -> inteiro {
    se numero > 0 {
        seja numero = 30
        escreva(numero)
    }
    retorne numero
}
funcao segunda(numero: inteiro) -> inteiro {
    retorne numero
}
inicio {
    seja numero = 10
    escreva(primeira(numero) + segunda(numero))
}''')
        fluxo = analisar_fluxo_programa(ir)
        self.assertFalse(any(v for f in [fluxo.principal, *fluxo.funcoes.values()] for v in f.sem_definicao.values()))
        defs = set.union(*fluxo.funcoes['primeira'].definicoes.values())
        self.assertEqual(len(defs), 2)
        self.assertEqual(set.union(*fluxo.funcoes['segunda'].definicoes.values()), {'numero'})
        self.assertEqual(set.union(*fluxo.principal.definicoes.values()), {'numero'})

    def test_efeitos_transitivos_de_entrada_saida_e_falha_na_ir(self):
        ir = levantar('''funcao ler() -> inteiro {
    seja numero = 0
    escreva(numero)
    retorne 10 / numero
}
funcao meio() -> inteiro {
    retorne ler()
}
funcao externo() -> inteiro {
    retorne meio()
}
inicio {
    escreva(externo())
}''')
        # Leitura em função ainda não faz parte da sintaxe aceita. A análise
        # da IR deve conservar esse efeito, caso receba o nó explicitamente.
        f = ir.funcoes['ler']
        corpo = replace(f.programa, instrucoes=(f.programa.instrucoes[0],
            InstrucaoIR('leia_int', ('numero',)), *f.programa.instrucoes[1:]))
        ir = replace(ir, funcoes={**ir.funcoes, 'ler': replace(f, programa=corpo)})
        resumos = resumir_funcoes(ir)
        for e in resumos.values():
            self.assertTrue(e.entrada and e.saida and e.pode_falhar and e.controle)
            self.assertFalse(e.desconhecido or e.encerra or e.leituras or e.escritas)
        chamada = ir.instrucoes[0].argumentos[0]
        e = efeito_expressao(chamada, resumos)
        self.assertTrue(e.entrada and e.saida and e.barreira_de_reordenacao)
        self.assertFalse(e.encerra)

    def test_recursao_mutua_resolve_efeitos_por_ponto_fixo(self):
        ir = levantar('''funcao primeira(numero: inteiro) -> inteiro {
    se numero == 0 {
        retorne 0
    }
    retorne segunda(numero - 1)
}
funcao segunda(numero: inteiro) -> inteiro {
    escreva(numero)
    retorne primeira(numero)
}
inicio {
    escreva(primeira(3))
}''')
        fluxo = analisar_fluxo_programa(ir)
        self.assertEqual(fluxo.recursivas, {'primeira': True, 'segunda': True})
        for e in fluxo.resumos.values():
            self.assertTrue(e.saida and e.pode_falhar and e.barreira_de_reordenacao)
            self.assertFalse(e.desconhecido or e.encerra)
        self.assertEqual(fluxo.funcoes['primeira'].cfg.chamadas, ('segunda',))

    def test_limite_de_pilha_conservado_em_recursao_mutua(self):
        fonte = '''funcao primeira(numero: inteiro) -> inteiro {
    se numero == 0 {
        retorne 7
    }
    retorne segunda(numero - 1)
}
funcao segunda(numero: inteiro) -> inteiro {
    retorne primeira(numero)
}
inicio {
    escreva(primeira(1000000))
    escreva("INDEVIDO")
}'''
        resultados = []
        for nivel in range(9):
            programa = analisar_programa(fonte)
            fluxo = analisar_fluxo_programa(construir_ir(programa, nivel=nivel, otimizar=nivel > 0))
            self.assertTrue(all(e.pode_falhar for e in fluxo.resumos.values()))
            r, _ = rodar(compilar(programa, alvo_nativo(), nivel=nivel, otimizar=nivel > 0))
            self.assertEqual(r.returncode, 1)
            self.assertIn('limite seguro de pilha', r.stdout + r.stderr)
            self.assertNotIn('INDEVIDO', r.stdout)
            resultados.append((r.returncode, r.stdout, r.stderr))
        self.assertTrue(all(r == resultados[0] for r in resultados))

    def test_chamada_constante_conserva_risco_de_pilha(self):
        ir = levantar('''funcao constante() -> inteiro {
    retorne 7
}
inicio {
    escreva(constante())
}''')
        resumos = resumir_funcoes(ir)
        self.assertFalse(resumos['constante'].pode_falhar)
        e = efeito_expressao(ir.instrucoes[0].argumentos[0], resumos)
        self.assertTrue(e.pode_falhar and e.controle and e.barreira_de_reordenacao)
        self.assertFalse(e.desconhecido or e.encerra)

    def test_chamada_sem_corpo_e_operacao_nova_sao_desconhecidas(self):
        ir = levantar('funcao valor() -> inteiro {\n retorne 7\n}\ninicio {\n escreva(valor())\n}')
        f = ir.funcoes['valor']
        chamada = ExpressaoIR('inteiro', 'chamada', 'externa')
        corpo = replace(f.programa, instrucoes=(InstrucaoIR('nova_operacao', ()),
                                               InstrucaoIR('retorne', (chamada,))))
        ir = replace(ir, funcoes={'valor': replace(f, programa=corpo)})
        e = resumir_funcoes(ir)['valor']
        self.assertTrue(e.desconhecido and e.pode_falhar and e.controle)

    def test_chamada_inalcancavel_nao_contamina_dependencias(self):
        ir = levantar('''funcao efeito() -> inteiro {
    escreva(99)
    retorne 1
}
funcao valor() -> inteiro {
    retorne 7
    escreva(efeito())
}
inicio {
    escreva(valor())
}''')
        fluxo = analisar_fluxo_programa(ir)
        self.assertEqual(fluxo.funcoes['valor'].cfg.chamadas, ())
        self.assertFalse(fluxo.resumos['valor'].saida)
        self.assertTrue(fluxo.resumos['efeito'].saida)

    def test_cfg_funcao_rejeita_saida_sem_retorno_e_tipo_incompativel(self):
        f = levantar(FONTE).funcoes['escolher']
        with self.assertRaisesRegex(ValueError, 'sem retornar'):
            construir_cfg_funcao(replace(f, programa=replace(f.programa, instrucoes=())))
        with self.assertRaisesRegex(ValueError, 'Retorno incompatível'):
            construir_cfg_funcao(replace(f, retorno='logico'))
        with self.assertRaisesRegex(ValueError, 'Parâmetros incompatíveis'):
            construir_cfg_funcao(replace(f, parametros=(('ausente', 'inteiro'),)))
        with self.assertRaisesRegex(ValueError, 'contrato escalar'):
            construir_cfg_funcao(replace(f, retorno='bytes'))

    def test_ssa_e_memoria_versionada_rejeitam_grafos_com_funcoes(self):
        ir = levantar(FONTE)
        grafos = construir_cfg_programa(ir)
        for grafo in (grafos.principal, grafos.funcoes['escolher']):
            with self.assertRaisesRegex(ValueError, 'ainda não'):
                construir_ssa(grafo)
            with self.assertRaisesRegex(ValueError, 'ainda não'):
                construir_memory_ssa(ir, grafo)
        with self.assertRaisesRegex(ValueError, 'ainda não'):
            construir_memory_ssa(ir.funcoes['escolher'].programa, grafos.funcoes['escolher'])

    def test_json_e_dot_cobrem_todas_funcoes_com_ids_distintos(self):
        ir = levantar(FONTE)
        fluxo = analisar_fluxo_programa(ir)
        self.assertEqual(fluxo.para_json(), analisar_fluxo_programa(ir).para_json())
        dados = json.loads(fluxo.para_json())
        self.assertEqual(dados['versao'], 'RS 0.42K')
        self.assertEqual(dados['principal']['chamadas'], ['escolher'])
        f = dados['funcoes']['escolher']
        self.assertEqual(f['parametros'], [['numero', 'inteiro'], ['limite', 'inteiro']])
        self.assertEqual(f['tipo_retorno'], 'inteiro')
        self.assertTrue(any(b.get('efeitos', {}).get('encerra') for b in f['blocos'] if b['papel'] == 'retorne'))
        efeitos = json.loads(efeitos_para_json(ir))
        self.assertFalse(efeitos['funcoes']['escolher']['desconhecido'])
        dot = fluxo.grafos.para_dot()
        self.assertIn('"g0_b0"', dot)
        self.assertIn('"g1_b0"', dot)
        self.assertIn('style="dashed"', dot)

    def test_analise_preserva_binarios_o0_a_o8(self):
        programa = analisar_programa(FONTE)
        for nivel in range(9):
            for alvo in ('windows', 'linux'):
                antes = compilar(programa, alvo, nivel=nivel, otimizar=nivel > 0)
                ir = construir_ir(programa, nivel=nivel, otimizar=nivel > 0)
                analisar_fluxo_programa(ir).para_json()
                construir_cfg_programa(ir).para_dot()
                depois = compilar(programa, alvo, nivel=nivel, otimizar=nivel > 0)
                self.assertEqual(hashlib.sha256(antes).digest(), hashlib.sha256(depois).digest())
            resultado, _ = rodar(compilar(programa, alvo_nativo(), nivel=nivel, otimizar=nivel > 0))
            self.assertEqual((resultado.returncode, resultado.stdout, resultado.stderr), (0, '7\n', ''))

    def test_cli_exporta_fluxo_cfg_e_conserva_bloqueio_ssa(self):
        with tempfile.TemporaryDirectory() as pasta:
            pasta = Path(pasta)
            fonte, saida, fluxo, dot = [pasta / n for n in ('a.rts', 'a.exe', 'fluxo.json', 'grafo.dot')]
            fonte.write_text(FONTE, encoding='utf-8')
            comando = [sys.executable, str(RAIZ / 'compilar.py'), str(fonte), '-O', '8', '-o', str(saida)]
            r = subprocess.run([*comando, '--mostrar-cfg', '--salvar-cfg', str(dot), '--mostrar-fluxo',
                                '--salvar-fluxo', str(fluxo), '--mostrar-efeitos'],
                               capture_output=True, encoding='utf-8', timeout=15)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertIn('funcao escolher:', r.stdout)
            self.assertEqual(json.loads(fluxo.read_text(encoding='utf-8'))['versao'], 'RS 0.42K')
            self.assertIn('cluster_1', dot.read_text(encoding='utf-8'))
            saida.unlink()
            for opcao in ('--mostrar-ssa', '--mostrar-alocacao', '--mostrar-memory-ssa', '--mostrar-copias-phi'):
                r = subprocess.run([*comando, opcao], capture_output=True, encoding='utf-8', timeout=15)
                self.assertEqual(r.returncode, 1, r.stderr)
                self.assertIn('ainda não', r.stderr)
                self.assertNotIn('Traceback', r.stderr)
                self.assertFalse(saida.exists())

    def test_programas_gerados_com_ramos_lacos_e_retornos_contra_oraculo(self):
        gerador = random.Random(420110)
        for _ in range(20):
            limite, corte, pular, fator = (gerador.randint(0, 25), gerador.randint(5, 40),
                                          gerador.randint(0, 8), gerador.randint(1, 5))
            esperado = 0
            for numero in range(limite + 1):
                if numero == pular:
                    continue
                esperado += numero * fator if numero % 2 == 0 else numero
                if esperado > corte:
                    break
            fonte = f'''funcao parcela(numero: inteiro) -> inteiro {{
    se numero % 2 == 0 {{
        retorne numero * {fator}
    }}
    retorne numero
}}
funcao somar(limite: inteiro, corte: inteiro) -> inteiro {{
    seja soma = 0
    para numero de 0 ate limite {{
        se numero == {pular} {{
            continue
        }}
        soma = soma + parcela(numero)
        se soma > corte {{
            retorne soma
        }}
    }}
    retorne soma
}}
inicio {{
    escreva(somar({limite}, {corte}))
}}'''
            programa = analisar_programa(fonte)
            for nivel in range(9):
                with self.subTest(limite=limite, corte=corte, nivel=nivel):
                    ir = construir_ir(programa, nivel=nivel, otimizar=nivel > 0)
                    fluxo = analisar_fluxo_programa(ir)
                    self.assertFalse(any(v for f in [fluxo.principal, *fluxo.funcoes.values()]
                                         for v in f.sem_definicao.values()))
                    r, _ = rodar(compilar(programa, alvo_nativo(), nivel=nivel, otimizar=nivel > 0))
                    self.assertEqual((r.returncode, r.stdout, r.stderr), (0, str(esperado) + '\n', ''))
