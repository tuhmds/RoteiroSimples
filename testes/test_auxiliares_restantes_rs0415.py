"""RS 0.41.5 — contratos das auxiliares Windows restantes.

Os testes adulteram as instruções e os limites das descrições para conferir
que a tabela de exceções acompanha os bytes realmente emitidos.
"""
from pathlib import Path
import struct
import sys
import unittest

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

from backend.x86_64 import Gerador, montar_codigo
from backend.desenrolamento_windows import (
    gerar_desenrolamentos, registrar_quadro_empilhado,
    registrar_quadro_auxiliar, registrar_rotina_folha,
    emitir_prologo_auxiliar, emitir_epilogo_auxiliar,
)
from compilador.erros import ErroCompilacao
from compilador.parser import analisar_programa


FONTE = """inicio {
    seja atual: texto[32]
    seja dados: bytes[8]
    seja estado = 0
    seja recurso: arquivo
    seja primeira: lista[inteiro]
    seja segunda: lista[inteiro]
    copie(atual, "ABCDE")
    grave_arquivo("arquivo.rsd", atual)
    carregue_arquivo("arquivo.rsd", atual)
    adicione_byte(dados, 67)
    grave_trecho("arquivo.rsd", dados, 2, estado)
    carregue_trecho("arquivo.rsd", dados, 2, 1, estado)
    abra_arquivo("arquivo.rsd", recurso, "alteracao", estado)
    feche_arquivo(recurso, estado)
    publique_arquivo("arquivo.rsd", "final.rsd", estado)
    adicione(primeira, 17)
    mova(segunda, primeira)
    escreva(segunda[0])
    libere(segunda)
}"""


def _gerador():
    g = Gerador()
    g.desenrolamentos = []
    g.marcar('rotina')
    return g


def _informacao(g, nome):
    tabela, dados = gerar_desenrolamentos(g, 0x1000, 0xA000)
    inicio = 0x1000 + g.rotulos[nome]
    for pos in range(0, len(tabela), 12):
        atual, _, info = struct.unpack_from('<III', tabela, pos)
        if atual == inicio:
            return dados[info - 0xA000:]
    raise AssertionError(f'Descricao ausente: {nome}')


class TestesAuxiliaresRestantesRS0415(unittest.TestCase):
    def test_todas_as_familias_recebem_intervalos_reais(self):
        g, _ = montar_codigo(analisar_programa(FONTE), True)
        esperados = {
            'rs_lista_alocar', 'rs_lista_desalocar',
            'rs_lista_liberar_descritor', 'rs_lista_mover_descritor',
            'rs_lista_acrescentar', 'rs_verificar_arquivo_regular',
            'rs_arquivo_gravar', 'rs_arquivo_carregar',
            'rs_trecho_gravar', 'rs_trecho_carregar',
            'rs_abrir_caminho_verificado', 'rs_abrir_recurso',
            'rs_fechar_recurso', 'rs_sincronizar_recurso',
            'rs_bloquear_recurso', 'rs_recurso_gravar',
            'rs_recurso_ler', 'rs_publicar_arquivo',
        }
        auxiliares = {d['inicio'] for d in g.desenrolamentos
                      if d.get('prologo', '').startswith('auxiliar_')}
        self.assertTrue(esperados <= auxiliares, esperados - auxiliares)
        tabela, _ = gerar_desenrolamentos(g, 0x1000, 0xA000)
        intervalos = [struct.unpack_from('<III', tabela, i)
                      for i in range(0, len(tabela), 12)]
        self.assertEqual(len(intervalos), len(g.desenrolamentos))
        for atual, proximo in zip(intervalos, intervalos[1:]):
            self.assertLessEqual(atual[1], proximo[0])
        for inicio, fim, info in intervalos:
            self.assertLess(inicio, fim)
            self.assertEqual(info % 4, 0)

    def test_auxiliares_preservam_rdi_rsi_e_epilogo_reconhecido(self):
        g, _ = montar_codigo(analisar_programa(FONTE), True)
        for d in g.desenrolamentos:
            if d.get('prologo') != 'auxiliar_preservado':
                continue
            with self.subTest(nome=d['inicio']):
                inicio, fim = g.rotulos[d['inicio']], g.rotulos[d['fim']]
                self.assertEqual(g.codigo[inicio:inicio + 6],
                                 b'\x57\x56\x55\x48\x89\xE5')
                self.assertEqual(g.codigo[fim - 8:fim],
                                 b'\x48\x8D\x65\x00\x5D\x5E\x5F\xC3')
                info = _informacao(g, d['inicio'])
                self.assertEqual(info[3], 5)
                # Um ou dois slots para ALLOC; os quatro últimos são
                # SET_FPREG, PUSH RBP, PUSH RSI, PUSH RDI nesta ordem.
                inicio_codigos = 4 + (info[2] - 4) * 2
                self.assertEqual(info[inicio_codigos:inicio_codigos + 8],
                                 bytes((6, 3, 3, 0x50, 2, 0x60, 1, 0x70)))

    def test_novas_auxiliares_tem_reserva_fixa_e_retorno_unico(self):
        g, _ = montar_codigo(analisar_programa(FONTE), True)
        for nome in ('rs_lista_alocar', 'rs_lista_desalocar',
                     'rs_fechar_recurso', 'rs_sincronizar_recurso'):
            with self.subTest(nome=nome):
                d = next(d for d in g.desenrolamentos if d['inicio'] == nome)
                inicio, fim = g.rotulos[nome], g.rotulos[d['fim']]
                self.assertEqual(g.codigo[inicio:inicio + 4], b'\x48\x83\xEC\x28')
                self.assertEqual(g.codigo[fim - 5:fim], b'\x48\x83\xC4\x28\xC3')
                info = _informacao(g, nome)
                self.assertEqual(info[:6], bytes((1, 4, 1, 0, 4, 0x42)))

    def test_folha_real_nao_inventa_reservas(self):
        g = _gerador()
        g.bytes(b'\x31\xC0\xC3')
        registrar_rotina_folha(g, 'rotina')
        self.assertEqual(_informacao(g, 'rotina'), bytes((1, 0, 0, 0)))
        g.codigo[0] = 0x50
        with self.assertRaisesRegex(ErroCompilacao, 'folha'):
            gerar_desenrolamentos(g, 0x1000, 0xA000)

    def test_registro_recusa_mov_rsp_rbp_no_epilogo(self):
        g = _gerador()
        emitir_prologo_auxiliar(g, True, 32)
        g.bytes(b'\x90\x48\x89\xEC\x5D\x5E\x5F\xC3')
        with self.assertRaisesRegex(ErroCompilacao, 'Epilogo'):
            registrar_quadro_auxiliar(g, 'rotina')
        self.assertEqual(g.desenrolamentos, [])
        self.assertNotIn('rotina_fim_abi', g.rotulos)

    def test_publicacao_recusa_prologo_epilogo_e_intervalo_alterados(self):
        for alteracao in ('push', 'reserva', 'lea', 'pop', 'ret', 'limite'):
            with self.subTest(alteracao=alteracao):
                g = _gerador()
                emitir_prologo_auxiliar(g, True, 32)
                g.bytes(b'\x90')
                emitir_epilogo_auxiliar(g, True)
                registrar_quadro_auxiliar(g, 'rotina')
                fim = g.rotulos['rotina_fim_abi']
                posicoes = {'push': 0, 'reserva': 9, 'lea': fim - 7,
                            'pop': fim - 3, 'ret': fim - 1}
                if alteracao == 'limite':
                    g.rotulos['rotina_fim_abi'] -= 1
                else:
                    g.codigo[posicoes[alteracao]] = 0x90
                with self.assertRaises(ErroCompilacao):
                    gerar_desenrolamentos(g, 0x1000, 0xA000)

    def test_quadros_empilhados_descrevem_pushes_e_tamanhos_distintos(self):
        casos = [
            (('rdi',), 128, '57 48 81 EC 80 00 00 00', '48 81 C4 80 00 00 00 5F C3'),
            (('rsi',), 48, '56 48 83 EC 30', '48 83 C4 30 5E C3'),
            (('r13', 'r14', 'r15'), 64, '41 55 41 56 41 57 48 83 EC 40', '48 83 C4 40 41 5F 41 5E 41 5D C3'),
            (('r13', 'r14', 'r15', 'rsi'), 72, '41 55 41 56 41 57 56 48 83 EC 48', '48 83 C4 48 5E 41 5F 41 5E 41 5D C3'),
        ]
        for regs, quadro, prologo, epilogo in casos:
            with self.subTest(registradores=regs, quadro=quadro):
                g = _gerador()
                g.bytes(bytes.fromhex(prologo) + b'\x90' + bytes.fromhex(epilogo))
                registrar_quadro_empilhado(g, 'rotina', regs, quadro)
                info = _informacao(g, 'rotina')
                self.assertEqual(info[1], len(bytes.fromhex(prologo)))
                self.assertEqual(info[3], 0)
                self.assertEqual(info[2], len(regs) + 1)
                g.codigo[-2] = 0x90
                with self.assertRaisesRegex(ErroCompilacao, 'Epilogo'):
                    gerar_desenrolamentos(g, 0x1000, 0xA000)

    def test_imediato_negativo_nao_e_reserva_positiva(self):
        g = _gerador()
        g.bytes(bytes.fromhex('57 56 55 48 89 E5 48 83 EC 80 90 48 8D 65 00 5D 5E 5F C3'))
        with self.assertRaisesRegex(ErroCompilacao, 'negativo'):
            registrar_quadro_auxiliar(g, 'rotina')

    def test_push_nao_descrito_no_meio_do_prologo_e_rejeitado(self):
        fonte = """funcao dobrar(valor: inteiro) -> inteiro {
            retorne valor * 2
        }
        inicio {
            escreva(dobrar(21))
        }"""
        g, _ = montar_codigo(analisar_programa(fonte), True)
        inicio = g.rotulos['funcao_dobrar']
        g.codigo[inicio + 15] = 0x50
        with self.assertRaisesRegex(ErroCompilacao, 'profundidade'):
            gerar_desenrolamentos(g, 0x1000, 0xA000)

    def test_linux_mantem_prologo_e_epilogo_anteriores(self):
        g = _gerador()
        emitir_prologo_auxiliar(g, False, 96)
        emitir_epilogo_auxiliar(g, False)
        self.assertEqual(bytes(g.codigo), bytes.fromhex(
            '55 48 89 E5 48 83 EC 60 48 89 EC 5D C3'))
        g, _ = montar_codigo(analisar_programa(FONTE), False)
        self.assertEqual(g.desenrolamentos, [])


if __name__ == '__main__':
    unittest.main()
