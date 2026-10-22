"""Executa um emissor ELF64 escrito em RS e verifica os binarios produzidos."""
import os
from pathlib import Path
import random
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

FERRAMENTA = RAIZ / "exemplos" / "ferramentas" / "compilador_elf_inicial_rs.rts"


def alvo_local():
    if sys.platform == "win32":
        return "windows"
    if sys.platform == "linux" and os.uname().machine == "x86_64":
        return "linux"
    raise unittest.SkipTest("Exige Linux x86-64 ou Windows x86-64")


def validar_elf(arquivo):
    dados = arquivo.read_bytes()
    assert dados[:16] == b"\x7fELF\x02\x01\x01" + bytes(9)
    cabecalho = struct.unpack_from("<HHIQQQIHHHHHH", dados, 16)
    assert cabecalho[0:3] == (2, 62, 1)
    assert cabecalho[3:6] == (0x400078, 64, 0)
    assert cabecalho[7:10] == (64, 56, 1)
    segmento = struct.unpack_from("<IIQQQQQQ", dados, 64)
    assert segmento == (1, 5, 0, 0x400000, 0x400000, len(dados), len(dados), 4096)
    assert dados[120:122] == bytes((72, 184))
    assert dados[-8:] == bytes((95, 184, 60, 0, 0, 0, 15, 5))
    assert len(dados) <= 120 + 30000 * 14 + 8
    return dados


class TestesEmissorELFMinimoRS(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pasta = tempfile.TemporaryDirectory(prefix="rs_emissor_elf_")
        cls.alvo = alvo_local()
        programa = analisar_programa(carregar_fontes(FERRAMENTA).texto)
        cls.ferramentas = {}
        for nivel in (0, 8):
            for alvo in ("windows", "linux"):
                imagem = compilar(programa, alvo, nivel=nivel, otimizar=nivel > 0)
                if alvo == cls.alvo:
                    destino = Path(cls.pasta.name) / (
                        "compilador_elf_" + str(nivel) + (".exe" if alvo == "windows" else "")
                    )
                    destino.write_bytes(imagem)
                    if alvo == "linux":
                        destino.chmod(0o700)
                    cls.ferramentas[nivel] = destino

    @classmethod
    def tearDownClass(cls):
        if hasattr(cls, "pasta"):
            cls.pasta.cleanup()

    def construir(self, fonte, nivel):
        with tempfile.TemporaryDirectory(prefix="rs_saida_elf_") as pasta:
            raiz = Path(pasta)
            (raiz / "expressao.rts").write_text(fonte, encoding="utf-8")
            processo = subprocess.run(
                [str(self.ferramentas[nivel])],
                cwd=raiz, capture_output=True, text=True, timeout=20,
                encoding="utf-8", errors="replace",
            )
            self.assertEqual(processo.returncode, 0, processo.stdout + processo.stderr)
            resposta = [int(x) for x in processo.stdout.splitlines()]
            self.assertIn(len(resposta), (2, 3))
            destino = raiz / "resultado_elf"
            if resposta[0] != 0:
                self.assertFalse(destino.exists())
                self.assertEqual(len(resposta), 2)
                return resposta, None, None
            self.assertEqual(len(resposta), 3)
            self.assertEqual(destino.stat().st_size, resposta[2])
            dados = validar_elf(destino)
            codigo_saida = None
            if self.alvo == "linux":
                destino.chmod(0o700)
                executado = subprocess.run([str(destino)], cwd=raiz, timeout=10)
                codigo_saida = executado.returncode
            return resposta, dados, codigo_saida

    def test_imagem_elf64_com_instrucao_real(self):
        for nivel in (0, 8):
            resposta, dados, saida = self.construir("2 + 3 * 4", nivel)
            self.assertEqual(resposta[0], 0)
            self.assertIn(bytes.fromhex("48 0f af c1"), dados)
            self.assertIn(bytes.fromhex("48 01 c8"), dados)
            if saida is not None:
                self.assertEqual(saida, 14)

    def test_executa_aritmetica_e_sinais(self):
        casos = {
            "0": 0,
            "255": 255,
            "256": 0,
            "1000000000": 1000000000 % 256,
            "1 + 2 * 3": 7,
            "(1 + 2) * 3": 9,
            "90 - 13 - 7": 70,
            "-2 + 3 * 4": 10,
            "5 * (-4)": (-20) % 256,
            "--4": 4,
            "-(-20)": 20,
            "10 + -2 * +7": (-4) % 256,
            "(" * 40 + "19" + ")" * 40: 19,
        }
        for nivel in (0, 8):
            for fonte, esperado in casos.items():
                with self.subTest(nivel=nivel, expressao=fonte):
                    resposta, _, saida = self.construir(fonte, nivel)
                    self.assertEqual(resposta[0], 0)
                    if saida is not None:
                        self.assertEqual(saida, esperado)

    def test_geracao_aleatoria_diferencial(self):
        sorteio = random.Random(42055)
        def criar(nivel):
            if nivel == 0:
                return str(sorteio.randrange(0, 50))
            esquerda = criar(nivel - 1)
            direita = criar(nivel - 1)
            operador = sorteio.choice(("+", "-", "*"))
            return "(" + esquerda + operador + direita + ")"
        for _ in range(12):
            expressao = criar(3)
            esperado = eval(expressao, {"__builtins__": {}}, {}) % 256
            for nivel in (0, 8):
                resposta, _, saida = self.construir(expressao, nivel)
                self.assertEqual(resposta[0], 0)
                if saida is not None:
                    self.assertEqual(saida, esperado)

    def test_rejeita_entrada_que_nao_suporta(self):
        casos = [
            ("", 1),
            ("1 +", 1),
            ("1 == 2", 1),
            ("1 @ 2", 1),
            ("variavel + 1", 2),
            ("1 / 2", 3),
            ("1 % 2", 3),
            ("1000000001", 4),
            ("9999999999999999999999999", 4),
        ]
        for nivel in (0, 8):
            for fonte, esperado in casos:
                with self.subTest(nivel=nivel, expressao=fonte):
                    resposta, dados, saida = self.construir(fonte, nivel)
                    self.assertEqual(resposta[0], esperado)
                    self.assertIsNone(dados)
                    self.assertIsNone(saida)


if __name__ == "__main__":
    unittest.main()
