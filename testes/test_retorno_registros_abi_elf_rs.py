"""Contrato experimental de retorno de registro no emissor ELF64 em RS.

O compilador escrito em RS emite um trecho de copia com ponteiro oculto.
O teste executa os bytes em uma imagem ELF independente no Linux.
A sintaxe publica de retorno de registro ainda nao e suportada aqui.
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
from compilador.modulos import carregar_fontes
from compilador.parser import analisar_programa

FERRAMENTA = RAIZ / "exemplos" / "ferramentas" / "testar_retorno_registros_elf_rs.rts"


def alvo_local():
    if sys.platform == "win32":
        return "windows"
    if sys.platform == "linux" and os.uname().machine == "x86_64":
        return "linux"
    raise unittest.SkipTest("Exige Windows ou Linux x86-64")


def imagem_elf(codigo):
    identificacao = b"\x7fELF\x02\x01\x01" + bytes(9)
    cabecalho = struct.pack(
        "<16sHHIQQQIHHHHHH", identificacao, 2, 62, 1,
        0x400078, 64, 0, 0, 64, 56, 1, 0, 0, 0,
    )
    tamanho = 120 + len(codigo)
    programa = struct.pack(
        "<IIQQQQQQ", 1, 5, 0, 0x400000, 0x400000,
        tamanho, tamanho, 4096,
    )
    assert len(cabecalho) == 64 and len(programa) == 56
    return cabecalho + programa + codigo


def executar_copia(trecho, por_referencia):
    # _start prepara dois slots de destino independentes e passa o
    # endereco do primeiro deles como argumento oculto do callee.
    entrada = bytearray(bytes.fromhex(
        "55 48 89 e5 48 81 ec 20 00 00 00"
        "48 8d 85 e8 ff ff ff"
        "50 e8 00 00 00 00"
        "48 81 c4 08 00 00 00"
        "48 8b bd e8 ff ff ff"
        "48 03 bd e0 ff ff ff"
        "b8 3c 00 00 00 0f 05"
    ))
    # Prologo: tres slots, para admitir a variante com referencia.
    funcao = bytearray(bytes.fromhex(
        "55 48 89 e5 48 81 ec 18 00 00 00"
    ))
    if por_referencia:
        funcao.extend(bytes.fromhex(
            "48 c7 85 f0 ff ff ff 28 00 00 00"
            "48 c7 85 e8 ff ff ff 02 00 00 00"
            "48 8d 8d f0 ff ff ff"
            "48 89 8d f8 ff ff ff"
        ))
    else:
        funcao.extend(bytes.fromhex(
            "48 c7 85 f8 ff ff ff 28 00 00 00"
            "48 c7 85 f0 ff ff ff 02 00 00 00"
        ))
    funcao.extend(trecho)
    funcao.extend(bytes.fromhex("c9 c3"))
    # O deslocamento relativo de call parte do byte seguinte ao imm32.
    call_imediato = 19
    deslocamento = len(entrada) - (call_imediato + 4)
    struct.pack_into("<i", entrada, call_imediato, deslocamento)
    return imagem_elf(bytes(entrada + funcao))


class TestesRetornoRegistrosABI(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.alvo = alvo_local()
        cls.pasta = tempfile.TemporaryDirectory(prefix="rs_retorno_elf_")
        programa = analisar_programa(carregar_fontes(FERRAMENTA).texto)
        cls.executaveis = []
        for nivel in (0, 8):
            imagem = compilar(
                programa, cls.alvo, nivel=nivel, otimizar=nivel > 0
            )
            destino = Path(cls.pasta.name) / (
                f"emissor_retorno_{nivel}" + (".exe" if cls.alvo == "windows" else "")
            )
            destino.write_bytes(imagem)
            if cls.alvo == "linux":
                destino.chmod(0o700)
            cls.executaveis.append(destino)

    @classmethod
    def tearDownClass(cls):
        if hasattr(cls, "pasta"):
            cls.pasta.cleanup()

    def test_transferencia_real_em_buffer_pertencente_ao_chamador(self):
        for nivel, emissor in zip((0, 8), self.executaveis):
            with self.subTest(nivel=nivel):
                with tempfile.TemporaryDirectory(prefix="rs_trecho_retorno_") as d:
                    raiz = Path(d)
                    processo = subprocess.run(
                        [str(emissor)], cwd=raiz, capture_output=True,
                        text=True, encoding="utf-8", errors="replace", timeout=30
                    )
                    self.assertEqual(
                        processo.returncode, 0, processo.stdout + processo.stderr
                    )
                    for por_referencia, nome in (
                        (False, "trecho_retorno_local.bin"),
                        (True, "trecho_retorno_referencia.bin"),
                    ):
                        with self.subTest(referencia=por_referencia):
                            trecho = (raiz / nome).read_bytes()
                            self.assertGreater(len(trecho), 30)
                            # ponteiro oculto em [rbp+16]; retorno em rax
                            self.assertTrue(trecho.startswith(bytes.fromhex(
                                "48 8b 95 10 00 00 00"
                            )))
                            self.assertTrue(trecho.endswith(bytes.fromhex("48 89 d0")))
                            if self.alvo == "linux":
                                arquivo = raiz / ("executar_ref" if por_referencia else "executar_local")
                                arquivo.write_bytes(executar_copia(trecho, por_referencia))
                                arquivo.chmod(0o700)
                                execucao = subprocess.run(
                                    [str(arquivo)], cwd=raiz, timeout=4,
                                    capture_output=True,
                                )
                                self.assertEqual(
                                    execucao.returncode, 42, execucao.stderr
                                )


if __name__ == "__main__":
    unittest.main()
