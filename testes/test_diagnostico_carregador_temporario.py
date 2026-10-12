"""Diagnóstico temporário: flags do carregador Windows x64."""
import sys, struct, subprocess, tempfile
from pathlib import Path
import unittest
from compilador.parser import analisar_programa
from backend import compilar

class DiagnosticoTemporario(unittest.TestCase):
    def test_flags_carregamento_windows(self):
        if sys.platform != 'win32':
            self.skipTest('Somente Windows')
        programas={
            'simples': 'inicio {\n escreva(123)\n}',
            'recurso': '''inicio {
                seja arq: arquivo
                seja estado = 0
                abra_arquivo("teste.bin", arq, "alteracao", estado)
                escreva(estado)
                feche_arquivo(arq, estado)
                escreva(estado)
            }''',
            'funcao': '''funcao somar(n: inteiro) -> inteiro {
                retorne n + 1
            }
            inicio { escreva(somar(4)) }''',
        }
        with tempfile.TemporaryDirectory() as pasta:
            for nome,fonte in programas.items():
                try:
                    original=compilar(analisar_programa(fonte),'windows',nivel=8)
                except Exception as exc:
                    print('DIAGNOSTICO ERRO',nome,exc,flush=True)
                    continue
                inicio_pe=struct.unpack_from('<I',original,0x3c)[0]
                campo=inicio_pe+24+70
                for op in (0x100,0x140,0x160,0x40,0):
                    dados=bytearray(original)
                    struct.pack_into('<H',dados,campo,op)
                    caminho=Path(pasta)/f'{nome}_{op}.exe'
                    caminho.write_bytes(dados)
                    r=subprocess.run([str(caminho)],cwd=pasta,capture_output=True,
                                     timeout=8,text=True,encoding='utf-8',
                                     errors='replace')
                    print('DIAGNOSTICO',nome,hex(op),hex(r.returncode&0xffffffff),
                          repr(r.stdout),repr(r.stderr),flush=True)
