"""RS 0.41.3 — validação real de sondagem e quadros Windows x64.

O teste dos bytes da rotina nativa acompanha verificações ELF/PE
existentes e exercita executáveis sem bibliotecas estrangeiras.
"""
import os
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import unittest

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(RAIZ))

from backend import compilar
from backend.x86_64 import montar_codigo
from backend.desenrolamento_windows import gerar_desenrolamentos
from compilador.parser import analisar_programa


def _fonte(capacidade):
    return f"""inicio {{
        seja memoria: bytes[{capacidade}]
        adicione_byte(memoria, 42)
        escreva(memoria[0])
    }}"""


def _pe_registro(imagem):
    offset, = struct.unpack_from('<I',imagem,0x3c)
    diretorio=offset+24+112+8*3
    rva, tamanho=struct.unpack_from('<II',imagem,diretorio)
    quantidade,=struct.unpack_from('<H',imagem,offset+6)
    i=offset+24+0xF0
    secoes={}
    for n in range(quantidade):
        p=i+n*40
        name,size,base,raw,off=struct.unpack_from('<8sIIII',imagem,p)
        secoes[name.rstrip(b'\0').decode()] = (size,base,raw,off)
    for size,base,raw,off in secoes.values():
        if base<=rva<base+size:
            return rva,tamanho,secoes,imagem[off+rva-base:off+rva-base+tamanho]
    raise AssertionError('Diretório de exceções PE ausente.')


class TestesSondagemWindowsRS0413(unittest.TestCase):
    def test_sondagem_usa_apenas_registradores_volateis(self):
        g,_=montar_codigo(analisar_programa(_fonte(5000)), True)
        self.assertTrue(g.exige_sondagem_pilha)
        inicio=g.rotulos['rs_sondar_pilha']
        fim=g.rotulos['rs_sondar_pilha_restante']
        self.assertEqual(g.codigo[inicio:inicio+8],
                         b'\x4C\x8D\x54\x24\x08\x49\x89\xC3')
        self.assertEqual(g.codigo[fim:fim+8],
                         b'\x4D\x29\xDA\x41\xF6\x02\x00\xC3')
        # Corpo conhecido não modifica RAX, RSP nem registradores
        # não voláteis. A rotina folha é deliberadamente simples.
        esperado=(
            b'\x4C\x8D\x54\x24\x08\x49\x89\xC3'
            b'\x49\x81\xFB\x00\x10\x00\x00'
        )
        self.assertEqual(g.codigo[inicio:inicio+len(esperado)],esperado)
        self.assertNotIn(b'\x48\x81\xEC',g.codigo[inicio:fim+8])

    def test_prologos_grandes_possuem_reserva_unica_descritivel(self):
        for tamanho in (4096, 4100, 600000):
            with self.subTest(capacidade=tamanho):
                programa=analisar_programa(_fonte(tamanho))
                g,_=montar_codigo(programa,True)
                quadro=g.desenrolamentos[0]['quadro']
                self.assertEqual(quadro % 16,8)
                self.assertGreaterEqual(quadro,4096)
                pos=g.rotulos['rs_fim_prologo_principal']
                codigo=g.codigo[pos-18:pos]
                self.assertEqual(codigo[:2],b'\x48\xB8')
                self.assertEqual(struct.unpack_from('<Q',codigo,2)[0],quadro)
                self.assertEqual(codigo[10],0xE8)
                self.assertEqual(codigo[15:],b'\x48\x29\xC4')
                tab,xdados=gerar_desenrolamentos(g,0x1000,0x9000)
                self.assertEqual(len(tab),12)
                self.assertEqual(len(xdados),16)
                self.assertEqual(xdados[1],pos-g.rotulos['rs_inicio_principal'])
                self.assertEqual(xdados[2], 6 if quadro>0xFFFF*8 else 5)
                self.assertEqual(xdados[5], 0x11 if quadro>0xFFFF*8 else 0x01)
                imagem=compilar(programa,'windows',otimizar=False,nivel=0)
                rva,qtd,secoes,tabela=_pe_registro(imagem)
                self.assertEqual(qtd,12)
                self.assertEqual(len(tabela),12)
                ini,fim,info=struct.unpack('<III',tabela)
                self.assertEqual(ini,0x1000+g.rotulos['rs_inicio_principal'])
                self.assertGreater(fim,ini)
                self.assertIn('.xdata',secoes)
                self.assertIn('.pdata',secoes)

    def test_funcao_com_quadro_grande_recebe_sua_propria_descricao(self):
        fonte="""funcao processamento(numero: inteiro) -> inteiro {
            seja dados: bytes[7000]
            adicione_byte(dados, 31)
            retorne numero + dados[0]
        }
        inicio {
            escreva(processamento(11))
        }"""
        g,_=montar_codigo(analisar_programa(fonte),True)
        self.assertEqual(len(g.desenrolamentos),2)
        nomes={x['inicio'] for x in g.desenrolamentos}
        self.assertEqual(nomes,{'rs_inicio_principal','funcao_processamento'})
        tab,xdados=gerar_desenrolamentos(g,0x1000,0x9000)
        self.assertEqual(len(tab),24)
        self.assertTrue(g.exige_sondagem_pilha)
        self.assertEqual(len(xdados),32)

    def test_execucao_real_quadros_grandes_nove_niveis(self):
        if sys.platform!='win32':
            self.skipTest('Somente Windows x64.')
        fontes=[
            (_fonte(5000),'42\n'),
            (_fonte(600000),'42\n'),
            ("""funcao processamento(numero: inteiro) -> inteiro {
                seja dados: bytes[7000]
                adicione_byte(dados, 31)
                retorne numero + dados[0]
            }
            inicio {
                escreva(processamento(11))
            }""",'42\n'),
        ]
        with tempfile.TemporaryDirectory() as pasta:
            for caso,(fonte,esperado) in enumerate(fontes):
                programa=analisar_programa(fonte)
                for nivel in range(9):
                    with self.subTest(caso=caso,nivel=nivel):
                        arq=Path(pasta)/f'caso_{caso}_{nivel}.exe'
                        arq.write_bytes(compilar(programa,'windows',
                                                otimizar=nivel>0,nivel=nivel))
                        proc=subprocess.run([str(arq)],cwd=pasta,
                                            capture_output=True,text=True,
                                            encoding='utf-8',errors='replace',
                                            timeout=20)
                        self.assertEqual((proc.returncode,proc.stdout),
                                         (0,esperado),proc.stderr)


if __name__=='__main__':
    unittest.main()
