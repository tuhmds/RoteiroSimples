"""RS 0.10: AST localizável, CFG, diagnósticos e preservação dos binários."""
import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

from compilador.ast import NoExpressao, NoInstrucao, PosicaoFonte
from compilador.cfg import construir_cfg
from compilador.erros import ErroCompilacao
from compilador.ir import construir_ir
from compilador.lexico import tokens
from compilador.parser import analisar_programa
from backend import compilar


class TestesCFG(unittest.TestCase):
    def grafo(self, fonte, otimizar=True):
        ir = construir_ir(analisar_programa(fonte), otimizar=otimizar)
        return construir_cfg(ir)

    def test_tokens_sao_strings_com_linha_coluna(self):
        x = tokens('   seja preco = 10 // comentário com acentos', 7)
        self.assertEqual(x, ['seja', 'preco', '=', '10'])
        self.assertEqual([t.origem for t in x], [PosicaoFonte(7, 4), PosicaoFonte(7, 9),
                                                 PosicaoFonte(7, 15), PosicaoFonte(7, 17)])
        self.assertEqual(tokens('escreva("coração")', 1)[2], '"coração"')

    def test_ast_posicoes_de_comandos_aninhados(self):
        texto = '''inicio {
    seja n = 3
    se n > 0 {
        escreva(n * 2)
    } senao {
        escreva("Não")
    }
}'''
        p = analisar_programa(texto)
        atribuicao, decisao = p.instrucoes
        self.assertIsInstance(atribuicao, NoInstrucao)
        self.assertEqual(atribuicao.origem, PosicaoFonte(2, 5))
        self.assertEqual(decisao.origem, PosicaoFonte(3, 5))
        self.assertEqual(decisao[2][0].origem, PosicaoFonte(4, 9))
        self.assertEqual(decisao[3][0].origem, PosicaoFonte(6, 9))
        self.assertIsInstance(decisao[1], NoExpressao)
        self.assertEqual(decisao[1].origem, PosicaoFonte(3, 10))
        self.assertEqual(decisao[2][0][1].origem, PosicaoFonte(4, 19))

    def test_ir_mantem_origem_apos_dobrar_constante(self):
        p = analisar_programa('inicio {\n    escreva((2 + 3) * 4)\n}')
        ir = construir_ir(p, otimizar=True)
        self.assertEqual(ir.instrucoes[0].origem, PosicaoFonte(2, 5))
        valor = ir.instrucoes[0].argumentos[0]
        self.assertEqual((valor.valor, valor.origem), (20, PosicaoFonte(2, 21)))

    def test_parser_reporta_coluna_exata(self):
        with self.assertRaisesRegex(ErroCompilacao, 'Linha 2, coluna 5'):
            analisar_programa('inicio {\n    print(1)\n}')
        with self.assertRaisesRegex(ErroCompilacao, 'Linha 2, coluna 13'):
            analisar_programa('inicio {\n    escreva(sem_variavel)\n}')
        with self.assertRaisesRegex(ErroCompilacao, 'Linha 2, coluna 5'):
            analisar_programa('inicio {\n    início {\n}')

    def test_cfg_se_tem_dois_caminhos_e_juncao(self):
        g = self.grafo('''inicio {
    seja a = 3
    se a > 2 {
        escreva(1)
    } senao {
        escreva(2)
    }
    escreva(3)
}''')
        decisoes = [b for b in g.blocos.values() if b.papel == 'se:condicao']
        self.assertEqual(len(decisoes), 1)
        self.assertEqual({a.motivo for a in decisoes[0].saidas}, {'verdadeiro', 'falso'})
        self.assertEqual(len(g.inalcancaveis()), 0)
        self.assertTrue(g.validar())
        self.assertIn('digraph RoteiroSimples', g.para_dot())
        self.assertEqual(decisoes[0].origem, PosicaoFonte(3, 5))

    def test_cfg_enquanto_pare_continue(self):
        g = self.grafo('''inicio {
    seja i = 0
    enquanto i < 5 {
        i = i + 1
        se i == 2 {
            continue
        }
        se i == 4 {
            pare
        }
        escreva(i)
    }
}''')
        cond = next(b for b in g.blocos.values() if b.papel == 'enquanto:condicao')
        self.assertEqual(len(cond.saidas), 2)
        self.assertTrue(any(a.destino == cond.id and a.motivo == 'continue'
                            for b in g.blocos.values() for a in b.saidas))
        self.assertTrue(any(a.motivo == 'pare'
                            for b in g.blocos.values() for a in b.saidas))
        self.assertEqual(g.inalcancaveis(), set())

    def test_cfg_para_continue_vai_ao_incremento(self):
        g = self.grafo('''inicio {
    para i de 1 ate 5 {
        continue
    }
}''')
        c = next(b for b in g.blocos.values() if b.papel == 'continue')
        passo = next(b for b in g.blocos.values() if b.papel == 'para:incremento')
        self.assertEqual(c.saidas[0].destino, passo.id)
        self.assertEqual(c.saidas[0].motivo, 'continue')
        self.assertEqual(g.inalcancaveis(), set())

    def test_cfg_lacos_aninhados_pare_mais_interno(self):
        g = self.grafo('''inicio {
    para i de 1 ate 3 {
        enquanto i < 3 {
            pare
        }
        escreva(i)
    }
}''')
        pare = next(b for b in g.blocos.values() if b.papel == 'pare')
        destino = g.blocos[pare.saidas[0].destino]
        self.assertEqual(destino.papel, 'imprima_num')

    def test_cfg_detecta_codigo_inalcancavel_sem_omitir(self):
        g = self.grafo('''inicio {
    enquanto 1 {
        pare
        escreva("não alcançado")
    }
}''')
        invisiveis = {g.blocos[n].papel for n in g.inalcancaveis()}
        self.assertIn('texto', invisiveis)
        self.assertIn('style="dashed"', g.para_dot())

    def test_cfg_e_so_analise_nao_muda_binarios(self):
        fixture = json.loads((RAIZ/'testes/fixtures/rs0415_binarios_08.json').read_text(encoding='utf-8'))
        contador = 0
        for nome, esperados in fixture.items():
            p = analisar_programa((RAIZ/'exemplos'/nome).read_text(encoding='utf-8-sig'))
            for config, hash_esperado in esperados.items():
                alvo, opt = config.split('/')
                use_opt = opt == 'O1'
                cfg = construir_cfg(construir_ir(p, otimizar=use_opt))
                self.assertTrue(cfg.validar())
                dados = compilar(p, alvo, otimizar=use_opt)
                self.assertEqual(hashlib.sha256(dados).hexdigest(), hash_esperado,
                                 (nome, config))
                contador += 1
        self.assertEqual(contador, 36)

    def test_cli_exibe_cfg_e_salva_dot(self):
        with tempfile.TemporaryDirectory() as d:
            pasta = Path(d)
            arquivo = pasta/'a.dot'
            saida = pasta/'a'
            result = subprocess.run([sys.executable, str(RAIZ/'compilar.py'),
                                     str(RAIZ/'exemplos/arquitetura.rts'),
                                     '--alvo', 'linux', '--mostrar-ast', '--mostrar-cfg',
                                     '--salvar-cfg', str(arquivo), '-o', str(saida)],
                                    capture_output=True, text=True, timeout=10)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn('RS CFG v1', result.stdout)
            self.assertIn('RS AST v2', result.stdout)
            self.assertIn('digraph RoteiroSimples', arquivo.read_text(encoding='utf-8'))
            self.assertTrue(saida.read_bytes().startswith(b'\x7fELF'))

    def test_cli_seta_erro_com_acento_em_texto(self):
        with tempfile.TemporaryDirectory() as d:
            pasta = Path(d)
            fonte = pasta/'erro.rts'
            fonte.write_text('inicio {\n    escreva(nao_existe) // comentário\n}', encoding='utf-8')
            r = subprocess.run([sys.executable,str(RAIZ/'compilar.py'),str(fonte),
                                '--alvo','linux','-o',str(pasta/'erro')],
                               capture_output=True,text=True,timeout=10)
            self.assertEqual(r.returncode, 1)
            self.assertIn('Linha 2, coluna 13',r.stderr)
            self.assertIn('            ^',r.stderr)


if __name__ == '__main__':
    unittest.main()
