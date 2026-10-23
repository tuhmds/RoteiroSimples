"""Regressões do primeiro diálogo gráfico nativo Windows.

Não executa MessageBoxW na CI: isso bloquearia uma sessão sem desktop.
A aparência e o clique são ensaios manuais documentados.
"""
import struct
import unittest

from backend import compilar
from compilador.erros import ErroCompilacao
from compilador.parser import analisar_programa
from compilador.estrategia import decidir_estrategia


def _programa(comando):
    return analisar_programa('inicio {\n    ' + comando + '\n}\n')


def _offset_rva(imagem, rva):
    cabecalho = struct.unpack_from('<I', imagem, 0x3c)[0]
    assert imagem[cabecalho:cabecalho + 4] == b'PE\x00\x00'
    coff = cabecalho + 4
    total = struct.unpack_from('<H', imagem, coff + 2)[0]
    opcionais = struct.unpack_from('<H', imagem, coff + 16)[0]
    secao = coff + 20 + opcionais
    for i in range(total):
        virtual, inicio, bruto, offset = struct.unpack_from(
            '<IIII', imagem, secao + i * 40 + 8)
        if inicio <= rva < inicio + max(virtual, bruto):
            return offset + rva - inicio
    raise AssertionError(f'RVA não mapeado: {rva:08x}')


def _texto_nul(imagem, offset):
    fim = imagem.index(b'\x00', offset)
    return imagem[offset:fim].decode('ascii')


def _bibliotecas(imagem):
    cabecalho = struct.unpack_from('<I', imagem, 0x3c)[0]
    opcionais = cabecalho + 24
    importacao, tamanho = struct.unpack_from('<II', imagem, opcionais + 112 + 8)
    nomes = []
    for indice in range(0, tamanho - 20, 20):
        descritor = struct.unpack_from('<IIIII', imagem, _offset_rva(imagem, importacao + indice))
        if not any(descritor):
            break
        ilt, _, _, dll, iat = descritor
        nome = _texto_nul(imagem, _offset_rva(imagem, dll))
        funcoes = []
        pos = _offset_rva(imagem, ilt)
        while True:
            entrada, = struct.unpack_from('<Q', imagem, pos)
            if not entrada:
                break
            assert entrada >> 63 == 0  # importação por nome, não ordinal
            funcoes.append(_texto_nul(imagem, _offset_rva(imagem, entrada) + 2))
            pos += 8
        nomes.append((nome, tuple(funcoes), iat))
    return nomes, tamanho


class TesteGraficosWindows(unittest.TestCase):
    def test_analisa_comando_e_registra_efeitos(self):
        programa = _programa('janela_mensagem("Título", "Ação 🌱")')
        self.assertEqual(programa.instrucoes[0][:], ('janela_mensagem', 'Título', 'Ação 🌱'))
        estrategia = decidir_estrategia(programa, nivel=8)
        self.assertEqual(estrategia.gerador, 'conservador')
        self.assertTrue(any('grafica' in x for x in estrategia.motivos))

    def test_gera_pe_com_duas_bibliotecas_e_iat_valido(self):
        programa = _programa('janela_mensagem("RoteiroSimples", "Olá, mundo 🌱!")')
        for nivel in (0, 8):
            imagem = compilar(programa, 'windows', otimizar=nivel > 0, nivel=nivel)
            bibliotecas, tamanho = _bibliotecas(imagem)
            self.assertEqual(tamanho, 60)
            self.assertEqual([x[0] for x in bibliotecas], ['KERNEL32.dll', 'USER32.dll'])
            self.assertIn('ExitProcess', bibliotecas[0][1])
            self.assertEqual(bibliotecas[1][1], ('MessageBoxW',))
            self.assertIn('RoteiroSimples'.encode('utf-16-le') + b'\x00\x00', imagem)
            self.assertIn('Olá, mundo 🌱!'.encode('utf-16-le') + b'\x00\x00', imagem)
            self.assertIn(b'\x31\xc9\x48\x8d\x15', imagem)  # HWND nulo, ponteiro do corpo
            self.assertIn(b'\x45\x31\xc9\xff\x15', imagem)  # MB_OK e chamada IAT

    def test_multiplas_chamadas_separadas_e_acentos(self):
        programa = analisar_programa(
            'inicio {\n'
            '  janela_mensagem("Primeira", "Ação 🌱")\n'
            '  janela_mensagem("Segunda", "Olá")\n'
            '}\n')
        imagem = compilar(programa, 'windows', otimizar=False, nivel=0)
        for valor in ('Primeira', 'Segunda', 'Ação 🌱', 'Olá'):
            self.assertIn(valor.encode('utf-16-le') + b'\x00\x00', imagem)

    def test_console_antigo_nao_importa_user32(self):
        imagem = compilar(_programa('escreva(42)'), 'windows', otimizar=False, nivel=0)
        bibliotecas, tamanho = _bibliotecas(imagem)
        self.assertEqual(tamanho, 40)
        self.assertEqual(len(bibliotecas), 1)
        self.assertEqual(bibliotecas[0][0], 'KERNEL32.dll')
        self.assertNotIn(b'USER32.dll', imagem)

    def test_linux_recusado_explicitamente(self):
        with self.assertRaisesRegex(ErroCompilacao, 'Windows'):
            compilar(_programa('janela_mensagem("Titulo", "Texto")'),
                     'linux', otimizar=False, nivel=0)

    def test_validacao_de_argumentos_e_texto(self):
        ruins = [
            'janela_mensagem("So titulo")',
            'janela_mensagem(7, "mensagem")',
            'janela_mensagem("", "mensagem")',
            'janela_mensagem("A", "B", "C")',
            r'janela_mensagem("A", "B\u0000C")',
            'janela_mensagem("A", "x" * 5)',
            'janela_mensagem("A", "' + 'z' * 4097 + '")',
        ]
        for comando in ruins:
            with self.subTest(comando=comando[:45]):
                with self.assertRaises(ErroCompilacao):
                    _programa(comando)

    def test_literal_vazio_aceito_para_corpo(self):
        imagem = compilar(_programa('janela_mensagem("Aviso", "")'),
                          'windows', otimizar=False, nivel=0)
        self.assertIn('Aviso'.encode('utf-16-le') + b'\x00\x00', imagem)


if __name__ == '__main__':
    unittest.main()
