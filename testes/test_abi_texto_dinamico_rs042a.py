"""Prova Windows real do descritor UTF-8, descartes, ABI e desenrolamento."""
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))
from testes.test_abi_proprietarios_rs042a import WINDOWS_X64, executar_ensaio

FONTE = '''funcao criar() -> texto {
    seja nome: texto = "ação😀"
    retorne mova(nome)
}
funcao transportar(nome: texto) -> texto {
    retorne mova(nome)
}
funcao encaminhar(nome: texto) -> texto {
    retorne transportar(mova(nome))
}
funcao consumir(nome: texto) -> inteiro {
    retorne tamanho(nome) + caracteres(nome)
}
funcao exercitar() -> inteiro {
    seja externo: texto = "x"
    para indice de 0 ate 9 {
        seja local: texto = "ação"
        se indice == 5 {
            continue
        }
        se indice == 8 {
            pare
        }
    }
    retorne 0
}
inicio {
    escreva(1)
}'''


@unittest.skipUnless(WINDOWS_X64, 'Ensaio exige Windows AMD64 real.')
class TestesAbiTextoDinamicoRS042A(unittest.TestCase):
    def subprocesso(self, acao):
        ambiente = os.environ.copy()
        ambiente['PYTHONIOENCODING'] = 'utf-8'
        r = subprocess.run([sys.executable, str(Path(__file__).resolve()), acao],
                           cwd=RAIZ, env=ambiente, capture_output=True, text=True,
                           encoding='utf-8', errors='replace', timeout=45)
        self.assertEqual(r.returncode, 0, r.stdout + '\n' + r.stderr)
        return json.loads(r.stdout)

    def test_mesmo_heap_sem_copia_descarte_unico_escopos_e_registradores(self):
        observado = self.subprocesso('--abi')
        self.assertEqual(observado, {
            'alocacoes': 11, 'liberacoes': 11, 'resultado_consumo': 15,
            'mesmo_ponteiro': True, 'conteudo': list('ação😀'.encode()),
            'quantidade': 10, 'capacidade': 16,
            'inteiros_preservados': 8, 'vetoriais_preservados': 10,
        })

    def test_windows_desenrola_os_novos_auxiliares_em_todas_fronteiras(self):
        observado = self.subprocesso('--estados')
        esperados = {'rs_valor_reservar', 'rs_valor_liberar_descritor', 'rs_valor_mover_descritor',
                     'rs_validar_utf8', 'rs_texto_modificar', 'rs_texto_igual', 'rs_texto_escrever',
                     'rs_texto_ler_linha', 'rs_arquivo_carregar_dinamico'}
        self.assertTrue(esperados <= set(observado['nomes']), esperados - set(observado['nomes']))
        self.assertGreater(observado['estados'], 100)

    def test_excecoes_reais_atravessam_texto_memoria_e_arquivos(self):
        observado = self.subprocesso('--excecoes')
        self.assertIn('rs_valor_reservar', observado['excecoes'])
        self.assertIn('rs_texto_ler_linha', observado['excecoes'])
        self.assertIn('rs_arquivo_carregar_dinamico', observado['excecoes'])
        self.assertEqual(observado['quadros'], 2 * len(observado['excecoes']))


if __name__ == '__main__':
    if sys.argv[1:] == ['--abi']:
        print(json.dumps(executar_ensaio(FONTE, list('ação😀'.encode()), 16, 15,
                                        elemento_bytes=True, descartes_escopos=10)))
    elif sys.argv[1:] in (['--estados'], ['--excecoes']):
        from testes.ensaio_windows_rs0415 import executar_ensaio as ensaiar_desenrolamento
        fonte = (RAIZ / 'exemplos/aplicacoes/documento_utf8_rs042a.rts').read_text(encoding='utf-8')
        print(json.dumps(ensaiar_desenrolamento(sys.argv[1][2:], fonte)))
    else:
        unittest.main()
