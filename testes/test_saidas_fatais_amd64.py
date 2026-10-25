"""Contrato das saídas fatais do emissor AMD64.

Verifica a ordem dos rótulos, textos, alinhamento Win64 e encerramento.
Os testes end-to-end existentes exercitam a execução nativa desses rótulos.
"""
import unittest
from unittest.mock import patch

from backend.x86_64 import _emitir_erro_fatal


class GeradorEspiao:
    def __init__(self, eventos):
        self.eventos = eventos

    def marcar(self, nome):
        self.eventos.append(("marcar", nome))

    def bytes(self, conteudo):
        self.eventos.append(("bytes", conteudo))

    def relativo(self, instrucao, destino):
        self.eventos.append(("relativo", instrucao, destino))


class TestesSaidasFataisAMD64(unittest.TestCase):
    def verificar(self, windows):
        eventos = []
        gerador = GeradorEspiao(eventos)
        mensagens = {0: "mensagem preexistente"}

        def preparar(g):
            self.assertIs(g, gerador)
            eventos.append(("alinhar_win64",))

        def escrever(g, indice, mensagem, alvo, manipulador="saida"):
            self.assertIs(g, gerador)
            eventos.append(("escrever", indice, mensagem, alvo, manipulador))

        with patch("backend.x86_64.preparar_saida_fatal_windows", preparar), \
             patch("backend.x86_64.escreve_literal", escrever):
            _emitir_erro_fatal(gerador, mensagens, "erro_um", "Primeiro\n", windows)
            _emitir_erro_fatal(gerador, mensagens, "erro_dois", "Segundo\n", windows)

        self.assertEqual(
            mensagens, {0: "mensagem preexistente", 1: "Primeiro\n", 2: "Segundo\n"}
        )
        esperado = []
        for indice, rotulo, mensagem in (
            (1, "erro_um", "Primeiro\n"),
            (2, "erro_dois", "Segundo\n"),
        ):
            esperado.append(("marcar", rotulo))
            if windows:
                esperado.append(("alinhar_win64",))
            esperado.append((
                "escrever", indice, mensagem, windows,
                "saida" if windows else "erro",
            ))
            if windows:
                esperado.append(("bytes", b"\xB9\x01\x00\x00\x00"))
                esperado.append(("relativo", b"\xFF\x15", "ExitProcess"))
            else:
                esperado.append((
                    "bytes",
                    b"\xB8\x3C\x00\x00\x00\xBF\x01\x00\x00\x00\x0F\x05",
                ))
        self.assertEqual(eventos, esperado)

    def test_linux_saida_em_stderr_e_syscall_exit(self):
        self.verificar(windows=False)

    def test_windows_alinhamento_e_exitprocess(self):
        self.verificar(windows=True)


if __name__ == "__main__":
    unittest.main()
