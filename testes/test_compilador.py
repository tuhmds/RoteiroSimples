import subprocess
import struct
import sys
import tempfile
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))
from compilar import ErroCompilacao, compilar_linux, compilar_windows, ler_programa


class TestesCompilador(unittest.TestCase):
    def test_linux_executa_e_imprime_unicode(self):
        with tempfile.TemporaryDirectory() as pasta:
            binario = Path(pasta) / "saida"
            binario.write_bytes(compilar_linux(["Olá, mundo!\n", "Ação e coração\n"]))
            binario.chmod(0o755)
            execucao = subprocess.run([str(binario)], capture_output=True, text=True,
                                      check=True, encoding="utf-8")
            self.assertEqual(execucao.stdout, "Olá, mundo!\nAção e coração\n")

    def test_windows_estrutura_pe_e_importacoes(self):
        exe = compilar_windows(["Olá, mundo!\n"])
        self.assertEqual(exe[:2], b"MZ")
        deslocamento = struct.unpack_from("<I", exe, 0x3C)[0]
        self.assertEqual(exe[deslocamento:deslocamento+4], b"PE\x00\x00")
        self.assertEqual(struct.unpack_from("<H", exe, deslocamento+4)[0], 0x8664)
        for item in [b"KERNEL32.dll", b"WriteFile", b"ExitProcess", b"GetStdHandle"]:
            self.assertIn(item, exe)

    def test_ler_programa_valido(self):
        self.assertEqual(ler_programa(RAIZ / "exemplos" / "ola.rts"),
                         ["Olá, mundo!\n", "O RoteiroSimples está funcionando!\n"])

    def test_erro_instrucao_desconhecida(self):
        with tempfile.TemporaryDirectory() as pasta:
            fonte = Path(pasta) / "erro.rts"
            fonte.write_text('início {\n    printe("Oi")\n}\n', encoding="utf-8")
            with self.assertRaisesRegex(ErroCompilacao, "Linha 2"):
                ler_programa(fonte)

    def test_linguagem_unicode_escapado(self):
        with tempfile.TemporaryDirectory() as pasta:
            fonte = Path(pasta) / "unicode.rts"
            fonte.write_text('início {\n    escreva("Um\\nDois")\n}\n', encoding="utf-8")
            self.assertEqual(ler_programa(fonte), ["Um\nDois\n"])

    def test_arquivo_precisa_ter_inicio(self):
        with tempfile.TemporaryDirectory() as pasta:
            fonte = Path(pasta) / "erro.rts"
            fonte.write_text('escreva("Olá")\n', encoding="utf-8")
            with self.assertRaisesRegex(ErroCompilacao, "começar"):
                ler_programa(fonte)


if __name__ == "__main__":
    unittest.main()
