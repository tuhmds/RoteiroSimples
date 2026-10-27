"""Invariantes da ABI de cópia de agregados nativos no AMD64."""
import struct
import unittest

from backend.x86_64 import _copiar_palavras, _copiar_para_retorno


class EmissorEspiao:
    def __init__(self):
        self.proxima_condicao = 7
        self.eventos = []

    def bytes(self, dados):
        self.eventos.append(("bytes", dados))

    def marcar(self, rotulo):
        self.eventos.append(("marcar", rotulo))

    def salto(self, rotulo, modo):
        self.eventos.append(("salto", rotulo, modo))


def contrato_copia(origem, destino, quantidade, rotulo, retorno=False, windows=False):
    prologo = [
        ("bytes", b"\x4C\x8D\x95" + struct.pack("<i", origem)),
    ]
    if retorno:
        prologo.append(
            ("bytes", b"\x4C\x8B\x5D" + bytes((80 if windows else 24,)))
        )
    else:
        prologo.append(
            ("bytes", b"\x4C\x8D\x9D" + struct.pack("<i", destino))
        )
    return prologo + [
        ("bytes", b"\xB9" + struct.pack("<I", quantidade)),
        ("marcar", rotulo),
        ("bytes", b"\x49\x8B\x02\x49\x89\x03"),
        ("bytes", b"\x49\x83\xEA\x08\x49\x83\xEB\x08"),
        ("bytes", b"\xFF\xC9"),
        ("salto", rotulo, "jnz"),
    ]


class TestesCopiaRegistrosAMD64(unittest.TestCase):
    def test_copia_local_preserva_instrucoes_e_rotulos(self):
        for quantidade in (1, 2, 16):
            with self.subTest(slots=quantidade):
                g = EmissorEspiao()
                _copiar_palavras(g, -8, -64, quantidade)
                self.assertEqual(g.eventos, contrato_copia(
                    -8, -64, quantidade, "copiar_composto_7"
                ))
                self.assertEqual(g.proxima_condicao, 8)

    def test_quantidade_invalida_nao_emite_laco_infinito(self):
        for quantidade in (0, -1):
            with self.subTest(quantidade=quantidade):
                g = EmissorEspiao()
                with self.assertRaisesRegex(ValueError, "quantidade positiva"):
                    _copiar_palavras(g, -8, -16, quantidade)
                self.assertEqual(g.proxima_condicao, 7)
                self.assertEqual(g.eventos, [])

                g = EmissorEspiao()
                with self.assertRaisesRegex(ValueError, "quantidade positiva"):
                    _copiar_para_retorno(g, -8, quantidade)
                self.assertEqual(g.proxima_condicao, 7)
                self.assertEqual(g.eventos, [])

    def test_contagem_fora_de_32_bits_nao_altera_gerador(self):
        for quantidade in (2**32, 2**64):
            for metodo in (
                lambda g: _copiar_palavras(g, -8, -16, quantidade),
                lambda g: _copiar_para_retorno(g, -8, quantidade),
            ):
                with self.subTest(quantidade=quantidade):
                    g = EmissorEspiao()
                    with self.assertRaisesRegex(ValueError, "32 bits"):
                        metodo(g)
                    self.assertEqual(g.proxima_condicao, 7)
                    self.assertEqual(g.eventos, [])

    def test_deslocamentos_invalidos_nao_geram_codigo_parcial(self):
        for origem, destino in ((2**31, -8), (-8, -(2**31)-1)):
            with self.subTest(origem=origem, destino=destino):
                g = EmissorEspiao()
                with self.assertRaises(struct.error):
                    _copiar_palavras(g, origem, destino, 3)
                self.assertEqual(g.proxima_condicao, 7)
                self.assertEqual(g.eventos, [])
        g = EmissorEspiao()
        with self.assertRaises(struct.error):
            _copiar_para_retorno(g, -(2**31)-1, 3)
        self.assertEqual(g.proxima_condicao, 7)
        self.assertEqual(g.eventos, [])

    def test_tipo_de_quantidade_invalido_nao_altera_gerador(self):
        for quantidade in (True, 2.5, "3", None):
            with self.subTest(quantidade=quantidade):
                g = EmissorEspiao()
                with self.assertRaisesRegex(ValueError, "quantidade positiva"):
                    _copiar_palavras(g, -8, -16, quantidade)
                self.assertEqual(g.proxima_condicao, 7)
                self.assertEqual(g.eventos, [])

    def test_destinos_identicos_nao_geram_instrucao(self):
        g = EmissorEspiao()
        _copiar_palavras(g, -24, -24, 3)
        self.assertEqual(g.eventos, [])
        self.assertEqual(g.proxima_condicao, 7)

    def test_copia_identica_valida_parametros_antes_de_ignorar(self):
        # A otimizacao de auto-copia nao pode esconder entradas invalidas.
        for quantidade in (0, -1, True, 2.5, "3", None, 2**32):
            with self.subTest(quantidade=quantidade):
                g = EmissorEspiao()
                with self.assertRaises(ValueError):
                    _copiar_palavras(g, -24, -24, quantidade)
                self.assertEqual(g.eventos, [])
                self.assertEqual(g.proxima_condicao, 7)

        for deslocamento in (2**31, -(2**31) - 1):
            with self.subTest(deslocamento=deslocamento):
                g = EmissorEspiao()
                with self.assertRaises(struct.error):
                    _copiar_palavras(g, deslocamento, deslocamento, 1)
                self.assertEqual(g.eventos, [])
                self.assertEqual(g.proxima_condicao, 7)

    def test_retorno_composto_preserva_abi_linux_windows(self):
        for windows in (False, True):
            for quantidade in (1, 2, 16):
                with self.subTest(windows=windows, slots=quantidade):
                    g = EmissorEspiao()
                    _copiar_para_retorno(g, -32, quantidade, windows)
                    self.assertEqual(g.eventos, contrato_copia(
                        -32, None, quantidade, "retornar_composto_7",
                        retorno=True, windows=windows,
                    ))
                    self.assertEqual(g.proxima_condicao, 8)


if __name__ == "__main__":
    unittest.main()
