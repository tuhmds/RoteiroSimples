"""Ferramenta TEMPORÁRIA para localizar violação de acesso sob HIGH_ENTROPY_VA."""
import ctypes
import os
import struct
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backend import compilar
from compilador.parser import analisar_programa


class RegistroExcecao(ctypes.Structure):
    _fields_=[
        ('codigo',ctypes.c_uint32),('sinalizadores',ctypes.c_uint32),
        ('anterior',ctypes.c_void_p),('endereco',ctypes.c_void_p),
        ('total_parametros',ctypes.c_uint32),
        ('parametros',ctypes.c_uint64*15),
    ]


class InformacoesExcecao(ctypes.Structure):
    _fields_=[('registro',RegistroExcecao),('primeira_vez',ctypes.c_uint32)]


class EventoDepuracao(ctypes.Structure):
    _fields_=[('tipo',ctypes.c_uint32),('processo',ctypes.c_uint32),
             ('fluxo',ctypes.c_uint32),('alinhamento',ctypes.c_uint32),
             ('informacoes',ctypes.c_byte*200)]


class TesteDiagnosticoExcecao(unittest.TestCase):
    def test_encontrar_instrucao_que_falha(self):
        if sys.platform!='win32':
            self.skipTest('Somente Windows')
        fonte="""inicio {
            seja arq: arquivo
            seja estado = 0
            abra_arquivo("ponto.rsd", arq, "alteracao", estado)
            escreva(estado)
            feche_arquivo(arq, estado)
            escreva(estado)
        }"""
        k=ctypes.WinDLL('kernel32',use_last_error=True)
        ps=ctypes.WinDLL('psapi',use_last_error=True)
        k.WaitForDebugEvent.argtypes=[ctypes.POINTER(EventoDepuracao),ctypes.c_uint32]
        k.WaitForDebugEvent.restype=ctypes.c_int
        k.ContinueDebugEvent.argtypes=[ctypes.c_uint32,ctypes.c_uint32,ctypes.c_uint32]
        k.ContinueDebugEvent.restype=ctypes.c_int
        ps.EnumProcessModules.argtypes=[ctypes.c_void_p,ctypes.POINTER(ctypes.c_void_p),
                                      ctypes.c_uint32,ctypes.POINTER(ctypes.c_uint32)]
        ps.EnumProcessModules.restype=ctypes.c_int
        with tempfile.TemporaryDirectory() as pasta:
            exe=Path(pasta)/'diag.exe'
            blob=bytearray(compilar(analisar_programa(fonte),'windows',nivel=8))
            off=struct.unpack_from('<I',blob,0x3c)[0]+24+70
            struct.pack_into('<H',blob,off,0x160)
            exe.write_bytes(blob)
            p=subprocess.Popen([str(exe)],cwd=pasta,
                    creationflags=2,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
            try:
                for i in range(200):
                    ev=EventoDepuracao()
                    if not k.WaitForDebugEvent(ctypes.byref(ev),5000):
                        print('DEPURADOR TEMPO ESGOTADO',ctypes.get_last_error(),flush=True)
                        break
                    status=0x10002
                    if ev.tipo==1:
                        info=ctypes.cast(
                            ctypes.addressof(ev)+16,
                            ctypes.POINTER(InformacoesExcecao)).contents
                        codigo=info.registro.codigo
                        if codigo not in (0x80000003,0x4000001f):
                            mod=(ctypes.c_void_p*128)()
                            usados=ctypes.c_uint32()
                            ok=ps.EnumProcessModules(int(p._handle),mod,
                                  ctypes.sizeof(mod),ctypes.byref(usados))
                            base=mod[0] if ok and usados.value >= 8 else None
                            endereco=info.registro.endereco
                            print('EXCECAO_0411',
                                'codigo',hex(codigo),
                                'endereco',hex(endereco) if endereco else None,
                                'base',hex(base) if base else None,
                                'rva',hex(endereco-base) if base and endereco else None,
                                'primeira_vez',info.primeira_vez,
                                'parametros',[hex(info.registro.parametros[j])
                                            for j in range(min(info.registro.total_parametros,4))],
                                flush=True)
                            status=0x80010001
                    k.ContinueDebugEvent(ev.processo,ev.fluxo,status)
                    if ev.tipo==5:
                        print('DIAGNOSTICO_TERMINOU',i,flush=True)
                        break
                stdout,stderr=p.communicate(timeout=8)
                print('DIAGNOSTICO_SAIDA',repr(stdout),repr(stderr),
                      hex(p.returncode&0xffffffff),flush=True)
            finally:
                if p.poll() is None:
                    p.kill()
                    p.communicate()
