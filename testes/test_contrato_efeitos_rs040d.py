"""RS 0.40D — contrato comum de efeitos, recursos e propriedade."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

from compilador.contrato_efeitos import Efeitos, podem_trocar_de_ordem
from compilador.efeitos import Efeitos as EfeitosDaIR
from compilador.efeitos_programa import (
    efeito_expressao_arvore, efeito_instrucao_arvore,
    efeitos_programa_para_json, listar_efeitos_programa,
)
from compilador.estrategia import decidir_estrategia
from compilador.ir import construir_ir
from compilador.memory_ssa import construir_memory_ssa
from compilador.parser import analisar_programa
from backend import compilar


def plataforma():
    if sys.platform == 'win32':
        return 'windows'
    if sys.platform == 'linux' and os.uname().machine == 'x86_64':
        return 'linux'
    raise unittest.SkipTest('Executáveis nativos requerem Linux ou Windows x86-64.')


def executar(programa, pasta, nivel):
    alvo = plataforma()
    destino = Path(pasta)/('nativo.exe' if alvo == 'windows' else 'nativo')
    destino.write_bytes(compilar(programa, alvo, otimizar=nivel > 0,
                                 nivel=nivel))
    if alvo == 'linux':
        destino.chmod(0o700)
    return subprocess.run([str(destino)], cwd=pasta, capture_output=True,
                          text=True, encoding='utf-8', errors='replace',
                          timeout=15)


class TestesContratoEfeitosRS040D(unittest.TestCase):
    def test_contrato_realmente_compartilhado_com_analise_anterior(self):
        self.assertIs(Efeitos, EfeitosDaIR)
        valor = Efeitos(leituras=frozenset(('a',)),
                        escritas=frozenset(('b',)))
        self.assertEqual(set(valor.para_dict()), {
            'leituras', 'escritas', 'entrada', 'saida', 'pode_falhar',
        })
        self.assertFalse(valor.barreira_de_reordenacao)
        self.assertEqual(valor.para_dict_completo()['propriedade'], [])

    def test_permutacao_exige_independencia_e_ausencia_de_risco(self):
        a = efeito_instrucao_arvore(('atribua', 'a', ('numero', 1)))
        b = efeito_instrucao_arvore(('atribua', 'b', ('numero', 2)))
        ler_a = efeito_instrucao_arvore(('atribua', 'b', ('var', 'a')))
        escrever_a = efeito_instrucao_arvore(('atribua', 'a', ('numero', 3)))
        self.assertTrue(podem_trocar_de_ordem(a, b))
        self.assertFalse(podem_trocar_de_ordem(a, ler_a))
        self.assertFalse(podem_trocar_de_ordem(ler_a, escrever_a))
        self.assertFalse(podem_trocar_de_ordem(a, a))
        ler_dado = efeito_instrucao_arvore(('imprima_num', ('var', 'a')))
        self.assertFalse(podem_trocar_de_ordem(a, ler_dado))
        falha = efeito_instrucao_arvore(
            ('atribua', 'b', ('bin', '/', ('numero', 1), ('numero', 0))))
        self.assertTrue(falha.pode_falhar)
        self.assertFalse(podem_trocar_de_ordem(a, falha))

    def test_operacao_desconhecida_eh_barreira(self):
        efeito = efeito_instrucao_arvore(('operacao_nova',))
        self.assertTrue(efeito.desconhecido)
        self.assertTrue(efeito.pode_falhar)
        self.assertFalse(podem_trocar_de_ordem(efeito, Efeitos()))
        expr = efeito_expressao_arvore(('expressao_nova',))
        self.assertTrue(expr.desconhecido)
        self.assertFalse(podem_trocar_de_ordem(Efeitos(), expr))

    def test_chamadas_nao_sao_consideradas_puras(self):
        expr = efeito_expressao_arvore(
            ('chamada', 'somar', (('var', 'a'), ('numero', 2))))
        self.assertIn('a', expr.leituras)
        self.assertTrue(expr.desconhecido)
        self.assertFalse(podem_trocar_de_ordem(expr, Efeitos()))

    def test_recursos_de_arquivo_com_propriedade(self):
        fonte = """inicio {
            seja arq: arquivo
            seja dados: bytes[3]
            seja estado = 0
            abra_arquivo("base.bin", arq, "alteracao", estado)
            bloqueie_arquivo(arq, estado)
            adicione_byte(dados, 12)
            grave_em(arq, dados, 0, estado)
            sincronize_arquivo(arq, estado)
            feche_arquivo(arq, estado)
            publique_arquivo("base.bin", "publicado.bin", estado)
        }"""
        programa = analisar_programa(fonte)
        self.assertEqual(decidir_estrategia(programa, 8).gerador,
                         'conservador')
        itens = listar_efeitos_programa(programa)
        por_operacao = {i['operacao']: i for i in itens}
        self.assertTrue(por_operacao['crie_recurso']['arquivos'])
        self.assertIn('declarar:arq',
                      por_operacao['crie_recurso']['propriedade'])
        self.assertIn('abrir:arq', por_operacao['abra_recurso']['propriedade'])
        self.assertIn('bloquear:arq',
                      por_operacao['bloqueie_recurso']['propriedade'])
        self.assertIn('fechar:arq',
                      por_operacao['feche_recurso']['propriedade'])
        self.assertTrue(por_operacao['grave_em']['arquivos'])
        self.assertTrue(por_operacao['sincronize_recurso']['pode_falhar'])
        self.assertTrue(por_operacao['publique_arquivo']['arquivos'])
        self.assertFalse(por_operacao['publique_arquivo']['desconhecido'])
        self.assertIn('estado', por_operacao['publique_arquivo']['escritas'])

    def test_listas_dinamicas_marcam_transferencia_e_liberacao(self):
        fonte = """inicio {
            seja primeira: lista[inteiro]
            seja segunda: lista[inteiro]
            adicione(primeira, 3)
            mova(segunda, primeira)
            remova_ultimo(segunda)
            libere(segunda)
        }"""
        programa = analisar_programa(fonte)
        itens = listar_efeitos_programa(programa)
        movimentos = [i for i in itens if i['operacao'] == 'mova_lista_dinamica']
        self.assertEqual(len(movimentos), 1)
        self.assertIn('mover:primeira', movimentos[0]['propriedade'])
        self.assertIn('receber:segunda', movimentos[0]['propriedade'])
        self.assertTrue(movimentos[0]['barreira_de_reordenacao'])
        self.assertIn('liberar:segunda', next(
            i for i in itens if i['operacao'] == 'libere_lista_dinamica'
        )['propriedade'])

    def test_analisa_corpos_de_funcoes_e_controle_aninhado(self):
        codigo = """funcao dobro(valor: inteiro) -> inteiro {
            se valor > 0 {
                retorne valor * 2
            } senao {
                retorne 0
            }
        }
        inicio {
            seja n = dobro(5)
            escreva(n)
        }"""
        itens = listar_efeitos_programa(analisar_programa(codigo))
        self.assertTrue(any(i['caminho'].startswith('funcao:dobro.')
                            for i in itens))
        chamada = next(i for i in itens if i['operacao'] == 'atribua')
        self.assertTrue(chamada['desconhecido'])
        retornos = [i for i in itens if i['operacao'] == 'retorne']
        self.assertEqual(len(retornos), 2)
        self.assertTrue(all(i['controle'] for i in retornos))

    def test_analise_antiga_de_memoria_continua_funcionando(self):
        fonte = """inicio {
            seja a: texto[12]
            copie(a, "RS")
            junte(a, "!")
            escreva(a)
        }"""
        ir = construir_ir(analisar_programa(fonte), nivel=6)
        mssa = construir_memory_ssa(ir)
        self.assertTrue(mssa.validar())
        self.assertIn('mem:a', mssa.regioes)
        original = json.loads(mssa.para_json())
        self.assertIn('blocos', original)
        self.assertEqual(original['versao'], 'RS 0.20')

    def test_json_deterministico_da_arvore_completa(self):
        codigo = """inicio {
            seja dados: bytes[3]
            adicione_byte(dados, 255)
            escreva(dados[0])
            encerre(4)
        }"""
        programa = analisar_programa(codigo)
        resultado = efeitos_programa_para_json(programa)
        self.assertEqual(resultado, efeitos_programa_para_json(programa))
        dados = json.loads(resultado)
        self.assertEqual(dados['versao'], 'RS 0.40D')
        self.assertTrue(any(i['operacao'] == 'adicione_byte'
                            for i in dados['instrucoes']))
        self.assertTrue(any(i['encerra'] for i in dados['instrucoes']))
        self.assertTrue(all('barreira_de_reordenacao' in i
                            for i in dados['instrucoes']))

    def test_cli_mostra_e_salva_sem_exigir_ir(self):
        codigo = """inicio {
            seja dados: bytes[3]
            adicione_byte(dados, 255)
            escreva(dados[0])
        }"""
        with tempfile.TemporaryDirectory() as pasta:
            origem = Path(pasta)/'exemplo.rts'
            origem.write_text(codigo, encoding='utf-8')
            relatorio = Path(pasta)/'efeitos.json'
            destino = Path(pasta)/('bin.exe' if plataforma() == 'windows'
                                   else 'bin')
            for nivel in (0, 4, 8):
                if destino.exists():
                    destino.unlink()
                r = subprocess.run([
                    sys.executable, str(RAIZ/'compilar.py'),
                    str(origem), '--alvo', plataforma(), '-O', str(nivel),
                    '--mostrar-efeitos-do-programa',
                    '--salvar-efeitos-do-programa', str(relatorio),
                    '-o', str(destino)],
                    capture_output=True, text=True, encoding='utf-8',
                    errors='replace', timeout=35)
                self.assertEqual(r.returncode, 0, r.stderr)
                self.assertIn('adicione_byte', r.stdout)
                self.assertIn('Efeitos e propriedade', r.stdout)
                self.assertTrue(destino.exists())
                obj = json.loads(relatorio.read_text(encoding='utf-8'))
                self.assertEqual(obj['versao'], 'RS 0.40D')
                self.assertTrue(any(i['operacao'] == 'adicione_byte'
                                    for i in obj['instrucoes']))

    def test_os_nove_niveis_preservam_execucao_nativa(self):
        codigo = """inicio {
            seja valores: bytes[3]
            adicione_byte(valores, 1)
            adicione_byte(valores, 250)
            escreva(valores[0])
            escreva(valores[1])
            encerre(6)
        }"""
        programa = analisar_programa(codigo)
        with tempfile.TemporaryDirectory() as pasta:
            for nivel in range(9):
                with self.subTest(nivel=nivel):
                    retorno = executar(programa, pasta, nivel)
                    self.assertEqual((retorno.returncode, retorno.stdout),
                                     (6, '1\n250\n'), retorno.stderr)


if __name__ == '__main__':
    unittest.main()
