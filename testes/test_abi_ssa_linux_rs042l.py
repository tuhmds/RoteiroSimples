"""Sentinelas de registradores e RSP no código ELF SSA, em processo isolado."""
import json
from pathlib import Path
import platform
import subprocess
import sys
import unittest

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))
LINUX_X64 = sys.platform == 'linux' and platform.machine().lower() in ('amd64', 'x86_64')


@unittest.skipUnless(LINUX_X64, 'Ensaio exige Linux x86-64 real.')
class TestesAbiSSALinuxRS042L(unittest.TestCase):
    def test_registradores_nao_volateis_e_rsp_em_chamadas_reais(self):
        r = subprocess.run([sys.executable, str(Path(__file__).resolve()), '--ensaio'],
                           cwd=RAIZ, capture_output=True, encoding='utf-8', timeout=30)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(json.loads(r.stdout), {'retorno': 162, 'registradores_preservados': 6, 'pilha_preservada': True})


def executar():
    import ctypes as ct
    import mmap
    import struct
    from backend.funcoes_ssa import montar_funcoes_ssa
    from backend.linux_elf import montar_elf
    from compilador.ir import construir_ir
    from compilador.parser import analisar_programa
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
    seja e = alterar(numero)
    retorne a + b + c + d + e + alterar(e)
}
inicio {
    escreva(calcular(2))
}'''
    g, mensagens = montar_funcoes_ssa(construir_ir(analisar_programa(fonte), nivel=3), False, 8)
    g.compactar_saltos_ssa()
    elf = montar_elf(g, mensagens)
    dados = (ct.c_uint64 * 9)()
    sentinelas = [0x1234500000000000 + i for i in range(6)]
    # O ELF usa endereços RIP-relativos; a função testada não chama o sistema.
    tamanho = ((len(elf) + 2048 + mmap.PAGESIZE - 1) // mmap.PAGESIZE) * mmap.PAGESIZE
    with mmap.mmap(-1, tamanho, prot=mmap.PROT_READ | mmap.PROT_WRITE) as memoria:
        base = ct.addressof(ct.c_char.from_buffer(memoria))
        wrapper = bytearray.fromhex('53 55 41 54 41 55 41 56 41 57 48 83 EC 08')
        for opcode, valor in zip(('48 BB', '48 BD', '49 BC', '49 BD', '49 BE', '49 BF'), sentinelas):
            wrapper += bytes.fromhex(opcode) + struct.pack('<Q', valor)
        wrapper += bytes.fromhex('49 BB') + struct.pack('<Q', ct.addressof(dados))
        wrapper += bytes.fromhex('49 89 63 38')  # RSP antes dos argumentos
        wrapper += bytes.fromhex('6A 02 6A 00')  # numero=2; orçamento inicial=0
        wrapper += bytes.fromhex('48 B8') + struct.pack('<Q', base + 0x100 + g.rotulos['funcao_calcular'])
        wrapper += bytes.fromhex('FF D0 48 83 C4 10')
        wrapper += bytes.fromhex('49 BB') + struct.pack('<Q', ct.addressof(dados))
        wrapper += bytes.fromhex('49 89 43 00')  # resultado, sem alterar RAX
        for n, opcode in enumerate(('49 89 5B', '49 89 6B', '4D 89 63', '4D 89 6B', '4D 89 73', '4D 89 7B')):
            wrapper += bytes.fromhex(opcode) + bytes((8 * (n + 1),))
        wrapper += bytes.fromhex('49 89 63 40 48 83 C4 08 41 5F 41 5E 41 5D 41 5C 5D 5B C3')
        endereco_wrapper = (len(elf) + 15) // 16 * 16
        memoria[:len(elf)] = elf
        memoria[endereco_wrapper:endereco_wrapper + len(wrapper)] = wrapper
        sistema = ct.CDLL(None, use_errno=True)
        sistema.mprotect.argtypes = (ct.c_void_p, ct.c_size_t, ct.c_int)
        sistema.mprotect.restype = ct.c_int
        if sistema.mprotect(base, tamanho, mmap.PROT_READ | mmap.PROT_EXEC) != 0:
            raise OSError(ct.get_errno(), 'Não foi possível preparar o código do ensaio Linux.')
        retorno = ct.CFUNCTYPE(ct.c_int64)(base + endereco_wrapper)()
        assert retorno == dados[0] == 162, list(dados)
        assert list(dados)[1:7] == sentinelas, list(dados)
        assert dados[7] == dados[8], list(dados)
    return {'retorno': retorno, 'registradores_preservados': 6, 'pilha_preservada': True}


if __name__ == '__main__' and '--ensaio' in sys.argv:
    print(json.dumps(executar()))
elif __name__ == '__main__':
    unittest.main()
