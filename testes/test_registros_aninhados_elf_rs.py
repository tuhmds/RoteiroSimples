"""Registros aninhados em slots ELF64, incluindo listas e emprestimos."""
import unittest
from testes import test_emissao_corpos_funcoes_elf_rs as base_corpos

ESQUEMAS = (
    "tipo Coordenada {\n x: inteiro\n y: inteiro\n}\n"
    "tipo Local {\n id: inteiro\n posicao: Coordenada\n codigo: inteiro\n}\n"
)
ESQUEMAS_TRES = (
    ESQUEMAS +
    "tipo Entrada {\n local: Local\n versao: inteiro\n}\n"
)


class TestesRegistrosAninhadosELFRS(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        base_corpos.TestesCorposFuncoesELFRS.setUpClass()
        cls.gerador = base_corpos.TestesCorposFuncoesELFRS(
            "test_corpos_de_funcao_com_locais_se_e_retorno_antecipado"
        )

    @classmethod
    def tearDownClass(cls):
        base_corpos.TestesCorposFuncoesELFRS.tearDownClass()

    def gerar(self, fonte, nivel):
        return self.gerador.gerar(fonte, nivel)

    def test_leitura_e_atribuicao_em_subcampos(self):
        casos = (
            (ESQUEMAS +
             "funcao calcular() -> inteiro {\n"
             " seja lugar: Local\n"
             " lugar.id = 10\n"
             " lugar.posicao.x = 20\n"
             " lugar.posicao.y = -4\n"
             " lugar.codigo = 3\n"
             " retorne lugar.id + lugar.posicao.x + lugar.posicao.y + lugar.codigo\n"
             "}\n inicio { seja r = calcular() }", 29),
            (ESQUEMAS +
             "funcao calcular() -> inteiro {\n"
             " seja lugar: Local\n"
             " retorne lugar.posicao.y + lugar.codigo\n"
             "}\n inicio { seja r = calcular() }", 0),
            (ESQUEMAS_TRES +
             "funcao calcular() -> inteiro {\n"
             " seja entrada: Entrada\n"
             " entrada.local.id = 5\n"
             " entrada.local.posicao.y = 11\n"
             " entrada.versao = 2\n"
             " retorne entrada.local.id + entrada.local.posicao.y + entrada.versao\n"
             "}\n inicio { seja r = calcular() }", 18),
            (ESQUEMAS +
             "funcao calcular() -> inteiro {\n"
             " seja lugar: Local\n"
             " lugar.posicao.x = 1\n"
             " seja indice = 0\n"
             " enquanto indice < 7 {\n"
             " lugar.posicao.x = lugar.posicao.x + 2\n"
             " indice = indice + 1\n"
             " }\n retorne lugar.posicao.x\n"
             "}\n inicio { seja r = calcular() }", 15),
            (ESQUEMAS +
             "funcao calcular() -> inteiro {\n"
             " seja lugar: Local\n"
             " lugar.posicao.x = 9\n"
             " se lugar.posicao.x == 9 {\n"
             " seja lugar: Local\n"
             " lugar.posicao.x = 40\n"
             " }\n"
             " retorne lugar.posicao.x\n"
             "}\n inicio { seja r = calcular() }", 9),
        )
        for nivel in (0, 8):
            for fonte, esperado in casos:
                with self.subTest(nivel=nivel, esperado=esperado):
                    codigo, arquivo, status = self.gerar(fonte, nivel)
                    self.assertEqual(codigo, 0)
                    self.assertIsNotNone(arquivo)
                    if status is not None:
                        self.assertEqual(status, esperado)

    def test_listas_achatadas_e_indice(self):
        casos = (
            (ESQUEMAS +
             "funcao calcular() -> inteiro {\n"
             " seja registros: lista[Local]\n"
             " seja lugar: Local\n"
             " lugar.posicao.x = 11\n"
             " lugar.posicao.y = 7\n"
             " lugar.codigo = 3\n"
             " adicione(registros, lugar)\n"
             " lugar.posicao.y = 99\n"
             " registros[0].posicao.x = 14\n"
             " retorne registros[0].posicao.x + registros[0].posicao.y + registros[0].codigo\n"
             "}\n inicio { seja r = calcular() }", 24),
            (ESQUEMAS +
             "funcao calcular() -> inteiro {\n"
             " seja registros: lista[Local]\n"
             " seja lugar: Local\n"
             " seja indice = 0\n"
             " enquanto indice < 40 {\n"
             " lugar.id = indice\n"
             " lugar.posicao.x = indice + 2\n"
             " lugar.posicao.y = indice * 2\n"
             " adicione(registros, lugar)\n"
             " indice = indice + 1\n"
             " }\n"
             " registros[38].posicao.y = 25\n"
             " retorne registros[0].posicao.x + registros[38].posicao.y + registros[39].id + tamanho(registros)\n"
             "}\n inicio { seja r = calcular() }", 106),
            (ESQUEMAS +
             "funcao consultar(v: emprestimo[lista[Local]]) -> inteiro {\n"
             " retorne v[16].posicao.x + tamanho(v)\n"
             "}\n"
             "inicio {\n seja v: lista[Local]\n seja p: Local\n"
             " seja i = 0\n"
             " enquanto i < 17 {\n"
             " p.posicao.x = i\n"
             " adicione(v, p)\n i = i + 1\n }\n"
             " seja r = consultar(v)\n}", 33),
        )
        for nivel in (0, 8):
            for fonte, esperado in casos:
                with self.subTest(nivel=nivel, esperado=esperado):
                    codigo, arquivo, status = self.gerar(fonte, nivel)
                    self.assertEqual(codigo, 0)
                    self.assertIsNotNone(arquivo)
                    if status is not None:
                        self.assertEqual(status, esperado)

    def test_elemento_maior_que_64_bytes_cresce_antes_da_copia(self):
        esquema = (
            "tipo Parte {\n"
            " a: inteiro\n b: inteiro\n c: inteiro\n d: inteiro\n"
            " campo_e: inteiro\n f: inteiro\n g: inteiro\n h: inteiro\n}\n"
            "tipo Pacote {\n"
            " id: inteiro\n dados: Parte\n checksum: inteiro\n}\n"
        )
        fonte = (
            esquema +
            "funcao executar() -> inteiro {\n"
            " seja itens: lista[Pacote]\n"
            " seja p: Pacote\n"
            " seja i = 0\n"
            " enquanto i < 17 {\n"
            " p.id = i\n"
            " p.dados.a = i + 5\n"
            " p.dados.h = i + 25\n"
            " p.checksum = i * 2\n"
            " adicione(itens, p)\n"
            " i = i + 1\n"
            " }\n"
            " retorne itens[0].dados.a + itens[16].dados.h + itens[16].checksum + tamanho(itens)\n"
            "}\n inicio { seja r = executar() }"
        )
        # 10 campos de 8 bytes = 80 bytes: excede a reserva inicial de 64.
        # 5 + 41 + 32 + 17 = 95.
        for nivel in (0, 8):
            codigo, arquivo, status = self.gerar(fonte, nivel)
            self.assertEqual(codigo, 0)
            self.assertIsNotNone(arquivo)
            if status is not None:
                self.assertEqual(status, 95)

    def test_erros_caminho_e_esquema(self):
        casos = (
            (2, "tipo Local {\n posicao: Coordenada\n}\n"
             "tipo Coordenada {\n x: inteiro\n}\n"
             "funcao f() -> inteiro { retorne 0 }\n inicio { seja r = f() }"),
            (2, "tipo A {\n b: A\n}\n"
             "funcao f() -> inteiro { retorne 0 }\n inicio { seja r = f() }"),
            (5, ESQUEMAS +
             "funcao f() -> inteiro {\n"
             " seja x: Local\n"
             " retorne x.posicao.inexistente\n"
             "}\n inicio { seja r = f() }"),
            (18, ESQUEMAS +
             "funcao f() -> inteiro {\n"
             " seja x: Local\n"
             " retorne x.posicao\n"
             "}\n inicio { seja r = f() }"),
            (18, ESQUEMAS +
             "funcao f() -> inteiro {\n"
             " seja x: Local\n"
             " retorne x.id.invalido\n"
             "}\n inicio { seja r = f() }"),
            (18, ESQUEMAS +
             "funcao f() -> inteiro {\n"
             " seja x: Local\n"
             " x.posicao = 8\n"
             " retorne 0\n}\n inicio { seja r = f() }"),
            (18, ESQUEMAS +
             "funcao f() -> inteiro {\n"
             " seja x: Local\n"
             " seja v: lista[Local]\n"
             " adicione(v, x)\n"
             " retorne v[0].posicao\n"
             "}\n inicio { seja r = f() }"),
        )
        for nivel in (0, 8):
            for esperado, fonte in casos:
                with self.subTest(nivel=nivel, esperado=esperado):
                    codigo, arquivo, status = self.gerar(fonte, nivel)
                    self.assertEqual(codigo, esperado)
                    self.assertIsNone(arquivo)
                    self.assertIsNone(status)


if __name__ == "__main__":
    unittest.main()
