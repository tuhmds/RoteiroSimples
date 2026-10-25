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
                self.assertEqual(g.proxima_condicao, 8)
                self.assertEqual(len(g.eventos), 2)

                g = EmissorEspiao()
                with self.assertRaisesRegex(ValueError, "quantidade positiva"):
                    _copiar_para_retorno(g, -8, quantidade)
                self.assertEqual(g.proxima_condicao, 8)
                self.assertEqual(len(g.eventos), 2)

    def test_destinos_identicos_nao_geram_instrucao(self):
        g = EmissorEspiao()
        _copiar_palavras(g, -24, -24, 3)
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
