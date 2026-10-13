"""Provas Windows reais dos bytes proprietários e rotinas compartilhadas."""
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))
from testes.test_abi_proprietarios_rs042a import WINDOWS_X64, executar_ensaio

FONTE = '''funcao criar() -> bytes {
    seja dados: bytes
    adicione_byte(dados, 0)
    adicione_byte(dados, 255)
    adicione_byte(dados, 192)
    adicione_byte(dados, 128)
    retorne mova(dados)
}
funcao transportar(dados: bytes) -> bytes {
    retorne mova(dados)
}
funcao encaminhar(dados: bytes) -> bytes {
    retorne transportar(mova(dados))
}
funcao consumir(dados: bytes) -> inteiro {
    retorne dados[1] + tamanho(dados)
}
funcao exercitar() -> inteiro {
    seja externo: bytes
    adicione_byte(externo, 255)
    para indice de 0 ate 9 {
        seja local: bytes
        adicione_byte(local, indice)
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
class TestesAbiBytesDinamicosRS042A(unittest.TestCase):
    def subprocesso(self, acao):
        ambiente = os.environ.copy()
        ambiente['PYTHONIOENCODING'] = 'utf-8'
        r = subprocess.run([sys.executable, str(Path(__file__).resolve()), acao],
                           cwd=RAIZ, env=ambiente, capture_output=True, text=True,
                           encoding='utf-8', errors='replace', timeout=45)
        self.assertEqual(r.returncode, 0, r.stdout + '\n' + r.stderr)
        return json.loads(r.stdout)

    def test_movimentacao_sem_copia_descarte_unico_e_preservacao_de_registradores(self):
        self.assertEqual(self.subprocesso('--abi'), {
            'alocacoes': 11, 'liberacoes': 11, 'resultado_consumo': 259,
            'mesmo_ponteiro': True, 'conteudo': [0, 255, 192, 128],
            'quantidade': 4, 'capacidade': 4,
            'inteiros_preservados': 8, 'vetoriais_preservados': 10,
        })

    def test_desenrolamento_windows_nas_fronteiras_dos_auxiliares(self):
        observado = self.subprocesso('--estados')
        esperados = {'rs_valor_reservar', 'rs_valor_liberar_descritor', 'rs_valor_mover_descritor',
                     'rs_sequencia_modificar', 'rs_arquivo_carregar_dinamico'}
        self.assertTrue(esperados <= set(observado['nomes']), esperados - set(observado['nomes']))
        self.assertGreater(observado['estados'], 70)
        self.assertNotIn('rs_validar_utf8', observado['nomes'])

    def test_excecoes_reais_atravessam_memoria_copias_e_arquivos_binarios(self):
        observado = self.subprocesso('--excecoes')
        self.assertIn('rs_sequencia_modificar', observado['excecoes'])
        self.assertIn('rs_arquivo_carregar_dinamico', observado['excecoes'])
        self.assertEqual(observado['quadros'], 2 * len(observado['excecoes']))


if __name__ == '__main__':
    if sys.argv[1:] == ['--abi']:
        print(json.dumps(executar_ensaio(FONTE, [0, 255, 192, 128], 4, 259,
                                        elemento_bytes=True, descartes_escopos=10)))
    elif sys.argv[1:] in (['--estados'], ['--excecoes']):
        from compilador.modulos import carregar_fontes
        from testes.ensaio_windows_rs0415 import executar_ensaio as ensaiar_desenrolamento
        fonte = carregar_fontes(RAIZ / 'exemplos/aplicacoes/arquivo_binario_rs042a.rts').texto
        print(json.dumps(ensaiar_desenrolamento(sys.argv[1][2:], fonte)))
    else:
        unittest.main()
