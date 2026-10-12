"""Diagnóstico TEMPORÁRIO de endereço e carregamento Windows."""
import ctypes
import os
import struct
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))
from backend import compilar
from compilador.parser import analisar_programa


class TesteDiagnosticoEntropiaTemporario(unittest.TestCase):
    def test_bases_e_sinais_alta_entropia(self):
        if sys.platform != 'win32':
            self.skipTest('Exige Windows')
        exemplos = {
            'numero': """inicio {
                seja sinal = 0
                leia(sinal)
                escreva(1)
            }""",
            'arquivo': """inicio {
                seja sinal = 0
                leia(sinal)
                seja arquivo_atual: arquivo
                seja estado = 0
                abra_arquivo("prova.rsd", arquivo_atual, "alteracao", estado)
                escreva(estado)
                feche_arquivo(arquivo_atual, estado)
                escreva(estado)
            }""",
            'funcao': """funcao dobro(valor: inteiro) -> inteiro {
                retorne valor * 2
            }
            inicio {
                seja sinal = 0
                leia(sinal)
                escreva(dobro(4))
            }""",
            'texto': """inicio {
                seja sinal = 0
                leia(sinal)
                seja atual: texto[30]
                copie(atual, "teste")
                escreva(atual)
            }""",
            'lista': """inicio {
                seja sinal = 0
                leia(sinal)
                seja lista_atual: lista[inteiro]
                adicione(lista_atual, 123)
                escreva(lista_atual[0])
                libere(lista_atual)
            }""",
        }
        psapi = ctypes.WinDLL('psapi', use_last_error=True)
        psapi.EnumProcessModules.argtypes = [
            ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p),
            ctypes.c_uint32, ctypes.POINTER(ctypes.c_uint32)]
        psapi.EnumProcessModules.restype = ctypes.c_int
        with tempfile.TemporaryDirectory() as pasta:
            for nome, fonte in exemplos.items():
                try:
                    binario=compilar(analisar_programa(fonte),'windows',
                                    otimizar=True,nivel=8)
                except Exception as exc:
                    print('ENTROPIA_ERRO_FONTE',nome,repr(exc),flush=True)
                    continue
                for flags in (0x140,0x160):
                    dados=bytearray(binario)
                    offs=struct.unpack_from('<I',dados,0x3c)[0]+24+70
                    struct.pack_into('<H',dados,offs,flags)
                    arq=Path(pasta)/f'{nome}_{flags}.exe'
                    arq.write_bytes(dados)
                    proc=subprocess.Popen([str(arq)],cwd=pasta,stdin=subprocess.PIPE,
                                         stdout=subprocess.PIPE,stderr=subprocess.PIPE,
                                         encoding='utf-8',text=True,
                                         errors='replace')
                    try:
                        time.sleep(0.10)
                        modulos=(ctypes.c_void_p*128)()
                        qtd=ctypes.c_uint32(0)
                        ok=psapi.EnumProcessModules(int(proc._handle),modulos,
                                                    ctypes.sizeof(modulos),
                                                    ctypes.byref(qtd))
                        base=hex(modulos[0]) if ok and qtd.value>=8 else 'indisponivel'
                        saida,erro=proc.communicate('5\n',timeout=8)
                        print('ENTROPIA',nome,hex(flags),'base',base,
                              'saida',repr(saida),'erro',repr(erro),
                              'codigo',hex(proc.returncode & 0xffffffff),
                              flush=True)
                    finally:
                        if proc.poll() is None:
                            proc.kill()
                            proc.communicate()
