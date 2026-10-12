"""RS 0.41.2: descrições verificáveis de prólogos e quadros Windows x64.

Testes estruturais PE e execução nativa em todos os níveis de otimização.
Não ativamos HIGH_ENTROPY_VA ou exceções estruturadas da RS.
"""
import os
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import unittest

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

from backend import compilar
from backend.x86_64 import montar_codigo
from backend.desenrolamento_windows import gerar_desenrolamentos
from compilador.parser import analisar_programa
from compilador.erros import ErroCompilacao


def campos_pe(imagem):
    inicio = struct.unpack_from('<I', imagem, 0x3c)[0]
    assert imagem[inicio:inicio+4] == b'PE\0\0'
    quantidade = struct.unpack_from('<H', imagem, inicio+6)[0]
    inicio_opt = inicio+24
    tamanho_opt = struct.unpack_from('<H', imagem, inicio+20)[0]
    excecao = struct.unpack_from('<II', imagem, inicio_opt+112+8*3)
    secoes = {}
    for i in range(quantidade):
        pos = inicio_opt+tamanho_opt + i*40
        nome,tamanho_virtual,virtual,raw_size,deslocamento = struct.unpack_from(
            '<8sIIII', imagem, pos)
        secoes[nome.rstrip(b'\0').decode('ascii')] = (
            virtual, tamanho_virtual, deslocamento, raw_size)
    return excecao, secoes


def localizar(imagem,secoes,rva,tamanho):
    for virtual,real,offset,_ in secoes.values():
        if virtual <= rva and rva+tamanho <= virtual+real:
            pos = offset+rva-virtual
            return imagem[pos:pos+tamanho]
    raise AssertionError(f'RVA inválida: {rva:#x}')


def exemplo_funcoes():
    return """funcao somar(a: inteiro, b: inteiro) -> inteiro {
        retorne a + b
    }
    funcao dobro(numero: inteiro) -> inteiro {
        retorne somar(numero, numero)
    }
    inicio {
        escreva(dobro(21))
    }"""


class TestesDesenrolamentoWindowsRS0412(unittest.TestCase):
    def test_descricao_semantica_de_quadros_e_prologos(self):
        programa=analisar_programa(exemplo_funcoes())
        emissor,mensagens=montar_codigo(programa,True)
        self.assertEqual(len(emissor.desenrolamentos),4)
        for d in emissor.desenrolamentos:
            if d['inicio'] == 'imprimir_inteiro':
                continue
            with self.subTest(nome=d['inicio']):
                inicio=emissor.rotulos[d['inicio']]
                fim=emissor.rotulos[d['fim']]
                fim_prologo=emissor.rotulos[d['fim_prologo']]
                self.assertTrue(0 <= inicio < fim_prologo < fim)
                self.assertEqual(emissor.codigo[inicio:inicio+15],
                                 bytes.fromhex('56 57 41 54 41 55 41 56 41 57 53 55 48 89 E5'))
                self.assertEqual(emissor.codigo[fim_prologo-7:fim_prologo][:3],
                                 b'\x48\x81\xEC')
                quadro,=struct.unpack_from('<I',emissor.codigo,fim_prologo-4)
                self.assertEqual(quadro,d['quadro'])
                self.assertLess(quadro,4096)
        tabela,dados=gerar_desenrolamentos(emissor,0x1000,0x9000)
        self.assertEqual(len(tabela),4*12)
        self.assertEqual(len(dados),3*28+8)

    def test_pe_registra_intervalos_nativos_sem_inventar_metadados(self):
        programa=analisar_programa(exemplo_funcoes())
        emissor,_=montar_codigo(programa,True)
        imagem=compilar(programa,'windows',otimizar=False,nivel=0)
        (rva_tabela,tamanho_tabela),secoes=campos_pe(imagem)
        self.assertIn('.pdata',secoes)
        self.assertIn('.xdata',secoes)
        self.assertEqual(rva_tabela,secoes['.pdata'][0])
        self.assertEqual(tamanho_tabela,48)
        tabela=localizar(imagem,secoes,rva_tabela,tamanho_tabela)
        ult=0
        cobertura=set()
        for pos in range(0,len(tabela),12):
            ini,fim,info=struct.unpack_from('<III',tabela,pos)
            self.assertGreaterEqual(ini,ult)
            self.assertGreater(fim,ini)
            ult=fim
            self.assertTrue(secoes['.xdata'][0]<=info
                            <secoes['.xdata'][0]+secoes['.xdata'][1])
            descriptor=localizar(imagem,secoes,info,8)
            cobertura.add(ini)
            if ini == 0x1000+emissor.rotulos['imprimir_inteiro']:
                self.assertEqual(descriptor, bytes((1,8,2,0,8,0xF2,1,0x70)))
                continue
            descriptor=localizar(imagem,secoes,info,28)
            self.assertEqual(descriptor[0],1)    # versão UNWIND_INFO
            self.assertEqual(descriptor[2],11)    # oito registradores, frame e alocacao
            self.assertEqual(descriptor[3]&15,5) # RBP como frame
            self.assertGreaterEqual(descriptor[1],12)
            self.assertEqual(descriptor[4],descriptor[1])  # após SUB
            self.assertEqual(descriptor[5]&15,1)  # UWOP_ALLOC_LARGE
            self.assertEqual(descriptor[8:26],
                             bytes((15,3,12,0x50,11,0x30,10,0xF0,8,0xE0,
                                    6,0xD0,4,0xC0,2,0x70,1,0x60)))
            quadro,=struct.unpack_from('<H',descriptor,6)
            self.assertGreater(quadro,0)
            self.assertLess(quadro*8,4096)
            cobertura.add(ini)
        self.assertEqual(cobertura,{
            0x1000+emissor.rotulos[desc['inicio']]
            for desc in emissor.desenrolamentos
        })

    def test_sondagem_nativa_gera_tabela_real_para_quadros_grandes(self):
        fonte="""inicio {
            seja dados: bytes[5000]
            adicione_byte(dados, 255)
            escreva(dados[0])
        }"""
        programa=analisar_programa(fonte)
        emissor,_=montar_codigo(programa,True)
        self.assertGreaterEqual(emissor.desenrolamentos[0]['quadro'],4096)
        self.assertTrue(emissor.exige_sondagem_pilha)
        self.assertIn('rs_sondar_pilha',emissor.rotulos)
        tabela,dados=gerar_desenrolamentos(emissor,0x1000,0x9000)
        self.assertEqual(len(tabela),24)
        self.assertEqual(len(dados),36)
        self.assertEqual(dados[2],11)
        pe=compilar(programa,'windows',otimizar=False,nivel=0)
        diretorio,secoes=campos_pe(pe)
        self.assertEqual(diretorio[1],24)
        self.assertIn('.pdata',secoes)
        self.assertIn('.xdata',secoes)

    def test_tamanho_grande_usa_alocacao_de_32_bits(self):
        fonte="""inicio {
            seja dados: bytes[600000]
            adicione_byte(dados, 7)
            escreva(dados[0])
        }"""
        emissor,_=montar_codigo(analisar_programa(fonte),True)
        tabela,infos=gerar_desenrolamentos(emissor,0x1000,0x9000)
        self.assertEqual(len(tabela),24)
        self.assertEqual(infos[2],12)  # UWOP_ALLOC_LARGE com 3 slots
        self.assertEqual(infos[5],0x11)  # opInfo=1, operacao=1
        tamanho,=struct.unpack_from('<I',infos,6)
        self.assertEqual(tamanho,emissor.desenrolamentos[0]['quadro'])


    def test_recusa_metadados_de_prologo_incorreto(self):
        programa=analisar_programa('inicio {\n escreva(12)\n}')
        emissor,_=montar_codigo(programa,True)
        emissor.codigo[0]=0x90
        with self.assertRaisesRegex(ErroCompilacao,'Prologo Windows mudou'):
            gerar_desenrolamentos(emissor,0x1000,0x9000)

    def test_programas_com_funcoes_e_arquivos_rodam_no_windows(self):
        if sys.platform!='win32':
            self.skipTest('Teste nativo depende de Windows.')
        fontes=[
            (exemplo_funcoes(),'42\n'),
            ("""funcao contar(numero: inteiro) -> inteiro {
                se numero <= 0 {
                    retorne 0
                }
                retorne contar(numero - 1) + 1
            }
            inicio {\n                escreva(contar(7))\n            }""",'7\n'),
            ("""inicio {
                seja arq: arquivo
                seja estado = 0
                abra_arquivo("arquivo_de_teste.rsd",arq,"alteracao",estado)
                escreva(estado)
                feche_arquivo(arq,estado)
                escreva(estado)
            }""",'0\n0\n'),
        ]
        with tempfile.TemporaryDirectory() as pasta:
            for i,(fonte,esperado) in enumerate(fontes):
                for nivel in (0,4,8):
                    with self.subTest(caso=i,nivel=nivel):
                        pe=compilar(analisar_programa(fonte),'windows',
                                   otimizar=nivel>0,nivel=nivel)
                        p=Path(pasta)/f'rs_{i}_{nivel}.exe'
                        p.write_bytes(pe)
                        r=subprocess.run([str(p)],cwd=pasta,
                                         capture_output=True,text=True,
                                         encoding='utf-8',errors='replace',
                                         timeout=15)
                        self.assertEqual((r.returncode,r.stdout),(0,esperado),
                                         r.stderr)


if __name__=='__main__':
    unittest.main()
