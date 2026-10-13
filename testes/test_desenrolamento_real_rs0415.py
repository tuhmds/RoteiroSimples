"""RS 0.41.5: desenrolador e exceções executados pelo Windows AMD64 real.

Cada chamada nativa roda em subprocesso: uma falha de pilha/CONTEXT causa
falha do teste, não um skip. Só Windows x64 indisponível permite ignorar.
Metadados são extraídos do PE realmente publicado pelo backend.
"""
import ctypes
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import unittest

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

ARQUIVOS = """inicio {
    seja atual: texto[32]
    seja dados: bytes[8]
    seja estado = 0
    seja recurso: arquivo
    copie(atual, "ABCDE")
    grave_arquivo("arquivo.rsd", atual)
    carregue_arquivo("arquivo.rsd", atual)
    adicione_byte(dados, 67)
    grave_trecho("arquivo.rsd", dados, 2, estado)
    carregue_trecho("arquivo.rsd", dados, 2, 1, estado)
    abra_arquivo("arquivo.rsd", recurso, "alteracao", estado)
    feche_arquivo(recurso, estado)
    publique_arquivo("arquivo.rsd", "final.rsd", estado)
    escreva(estado)
}"""
LISTAS = """inicio {
    seja primeira: lista[inteiro]
    seja segunda: lista[inteiro]
    adicione(primeira, 17)
    mova(segunda, primeira)
    escreva(segunda[0])
    libere(segunda)
}"""
ENTRADA = """inicio {
    seja numero = 0
    seja linha: texto[32]
    leia(numero)
    leia(linha)
    escreva(numero)
    escreva(linha)
}"""


def fonte_funcao(capacidade):
    return f"""funcao processamento(numero: inteiro) -> inteiro {{
        seja dados: bytes[{capacidade}]
        adicione_byte(dados, 31)
        retorne numero + dados[0]
    }}
    inicio {{
        escreva(processamento(11))
    }}"""


WINDOWS_X64 = (sys.platform == 'win32' and ctypes.sizeof(ctypes.c_void_p) == 8
               and platform.machine().lower() in ('amd64', 'x86_64'))


@unittest.skipUnless(WINDOWS_X64, 'Ensaio exige Windows AMD64 real.')
class TestesDesenrolamentoRealRS0415(unittest.TestCase):
    def ensaio(self, acao, fonte):
        ambiente = os.environ.copy()
        ambiente['PYTHONIOENCODING'] = 'utf-8'
        resultado = subprocess.run(
            [sys.executable, str(Path(__file__).resolve()), '--ensaio'],
            input=json.dumps({'acao': acao, 'fonte': fonte}),
            text=True, encoding='utf-8', errors='replace', capture_output=True,
            cwd=RAIZ, env=ambiente, timeout=45)
        self.assertEqual(resultado.returncode, 0,
                         f'{acao}: {resultado.stdout}\n{resultado.stderr}')
        return json.loads(resultado.stdout)

    def test_windows_percorre_todas_fronteiras_e_familias_de_auxiliares(self):
        nomes = set()
        alocacoes = set()
        total = 0
        for familia, fonte in (('arquivos', ARQUIVOS), ('listas', LISTAS),
                               ('entrada', ENTRADA)):
            with self.subTest(familia=familia):
                resultado = self.ensaio('estados', fonte)
                nomes.update(resultado['nomes'])
                alocacoes.update(map(tuple, resultado['alocacoes']))
                total += resultado['estados']
        obrigatorios = {
            'rs_inicio_principal', 'rs_verificar_arquivo_regular',
            'rs_arquivo_gravar', 'rs_arquivo_carregar',
            'rs_abrir_caminho_verificado', 'rs_abrir_recurso',
            'rs_fechar_recurso', 'rs_sincronizar_recurso',
            'rs_bloquear_recurso', 'rs_recurso_gravar', 'rs_recurso_ler',
            'rs_publicar_arquivo', 'rs_trecho_gravar', 'rs_trecho_carregar',
            'rs_lista_alocar', 'rs_lista_desalocar',
            'rs_lista_liberar_descritor', 'rs_lista_mover_descritor',
            'rs_lista_acrescentar', 'imprimir_inteiro', 'ler_inteiro',
            'entrada_proximo_byte', 'ler_buffer_texto',
        }
        self.assertTrue(obrigatorios <= nomes, obrigatorios - nomes)
        self.assertTrue({(1, 0), (2, 0)} <= alocacoes)
        self.assertGreater(total, 200)

    def test_funcoes_reais_cobrem_quadros_pequenos_sondados_e_alloc_large_32(self):
        classes = set()
        for capacidade in (8, 7000, 600000):
            with self.subTest(capacidade=capacidade):
                resultado = self.ensaio('estados', fonte_funcao(capacidade))
                self.assertIn('funcao_processamento', resultado['nomes'])
                classes.update(map(tuple, resultado['alocacoes']))
        self.assertTrue({(1, 0), (1, 1)} <= classes)

    def test_excecoes_int3_reais_percorrem_auxiliar_e_chamador(self):
        total = 0
        for familia, fonte in (('arquivos', ARQUIVOS), ('listas', LISTAS),
                               ('entrada', ENTRADA),
                               ('funcao_sondada', fonte_funcao(7000))):
            with self.subTest(familia=familia):
                resultado = self.ensaio('excecoes', fonte)
                self.assertIn('rs_inicio_principal', resultado['excecoes'])
                self.assertEqual(resultado['quadros'],
                                 2 * len(resultado['excecoes']))
                total += len(resultado['excecoes'])
        self.assertGreater(total, 25)

    def test_metadado_corrompido_nao_produz_falsa_aprovacao(self):
        resultado = self.ensaio('negativo', fonte_funcao(8))
        self.assertTrue(resultado['corrupcao_detectada'])

    def test_retorno_real_preserva_registradores_e_pilha_da_funcao_rs(self):
        for capacidade in (8, 7000, 600000):
            with self.subTest(capacidade=capacidade):
                resultado = self.ensaio('retorno', fonte_funcao(capacidade))
                self.assertEqual(resultado['retornos'], ['funcao_processamento'])

    def test_retorno_real_preserva_auxiliares_de_listas(self):
        resultado = self.ensaio('retorno', LISTAS)
        self.assertEqual(set(resultado['retornos']), {
            'rs_lista_alocar', 'rs_lista_desalocar', 'rs_lista_acrescentar',
            'rs_lista_mover_descritor', 'rs_lista_liberar_descritor',
        })

    def test_sondagem_folha_retorna_sem_tabela_artificial(self):
        resultado = self.ensaio('sondagem', fonte_funcao(7000))
        self.assertGreaterEqual(resultado['quadros_intermediarios'], 1)
        self.assertEqual(resultado['retornos_folha'], 2)

    def test_impressao_zera_ponteiro_completo_em_pilha_envenenada(self):
        fonte = """funcao processamento(numero: inteiro) -> inteiro {
            seja linha: texto[32]
            copie(linha, "buffer")
            escreva("literal")
            escreva(linha)
            escreva(numero)
            retorne 42
        }
        inicio {
            escreva(processamento(11))
        }"""
        resultado = self.ensaio('impressao', fonte)
        self.assertTrue(resultado['sobreposta_nula'])
        self.assertGreaterEqual(resultado['escritas'], 6)


if __name__ == '__main__':
    if sys.argv[1:] == ['--ensaio']:
        from testes.ensaio_windows_rs0415 import executar_ensaio
        dados = json.loads(sys.stdin.read())
        print(json.dumps(executar_ensaio(dados['acao'], dados['fonte'])))
    else:
        unittest.main()
