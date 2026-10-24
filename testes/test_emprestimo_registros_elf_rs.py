"""Parametros emprestimo[Registro] (readonly) na ABI ELF64 em RS."""
import unittest
from testes import test_emissao_corpos_funcoes_elf_rs as base_corpos

ESQUEMA = (
    "tipo Endereco {\n rua: inteiro\n numero: inteiro\n}\n"
    "tipo Pessoa {\n id: inteiro\n endereco: Endereco\n ativo: inteiro\n}\n"
)


class TestesEmprestimoRegistroELFRS(unittest.TestCase):
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

    def test_emprestimo_e_reemprestimo_de_registros(self):
        casos = (
            (ESQUEMA +
             "funcao consultar(p: emprestimo[Pessoa]) -> inteiro {\n"
             " retorne p.id + p.endereco.numero + p.ativo\n}\n"
             "inicio {\n seja p: Pessoa\n p.id = 12\n"
             " p.endereco.numero = 5\n p.ativo = 3\n"
             " seja r = consultar(p)\n}", 20),
            (ESQUEMA +
             "funcao consultar(p: emprestimo[Pessoa]) -> inteiro {\n"
             " retorne p.endereco.rua + p.endereco.numero\n}\n"
             "funcao encaminhar(p: emprestimo[Pessoa]) -> inteiro {\n"
             " retorne consultar(p) + p.id\n}\n"
             "inicio {\n seja p: Pessoa\n p.id = 9\n"
             " p.endereco.rua = 8\n p.endereco.numero = 7\n"
             " seja r = encaminhar(p)\n}", 24),
            (ESQUEMA +
             "funcao consultar(a: inteiro, p: emprestimo[Pessoa], b: inteiro) -> inteiro {\n"
             " retorne a + p.endereco.numero + b\n}\n"
             "inicio {\n seja p: Pessoa\n p.endereco.numero = -3\n"
             " seja r = consultar(12, p, 5)\n}", 14),
            (ESQUEMA +
             "funcao consultar(p: emprestimo[Pessoa]) -> inteiro {\n"
             " retorne p.id\n}\n"
             "inicio {\n seja p: Pessoa\n p.id = 4\n"
             " seja r = consultar(p)\n"
             " p.id = r + 30\n"
             " r = p.id\n}", 34),
            (ESQUEMA +
             "funcao consultar(p: emprestimo[Pessoa]) -> inteiro {\n"
             " retorne p.id + p.endereco.rua\n}\n"
             "inicio { seja p: Pessoa\n seja r = consultar(p)\n}", 0),
        )
        for nivel in (0, 8):
            for fonte, esperado in casos:
                with self.subTest(nivel=nivel, esperado=esperado):
                    codigo, arquivo, status = self.gerar(fonte, nivel)
                    self.assertEqual(codigo, 0)
                    self.assertIsNotNone(arquivo)
                    if status is not None:
                        self.assertEqual(status, esperado)

    def test_bloqueio_mutacao_tipos_e_retorno_da_referencia(self):
        casos = (
            (18, ESQUEMA +
             "funcao alterar(p: emprestimo[Pessoa]) -> inteiro {\n"
             " p.id = 3\n retorne 0\n}\n"
             "inicio { seja p: Pessoa\n seja r = alterar(p)\n}"),
            (18, ESQUEMA +
             "funcao alterar(p: emprestimo[Pessoa]) -> inteiro {\n"
             " p.endereco.numero = 7\n retorne 0\n}\n"
             "inicio { seja p: Pessoa\n seja r = alterar(p)\n}"),
            (18, ESQUEMA +
             "funcao consultar(p: emprestimo[Pessoa]) -> inteiro {\n"
             " retorne p\n}\n"
             "inicio { seja p: Pessoa\n seja r = consultar(p)\n}"),
            (18, ESQUEMA +
             "funcao consultar(p: emprestimo[Pessoa]) -> inteiro {\n"
             " retorne p.id\n}\n"
             "inicio { seja p: Endereco\n seja r = consultar(p)\n}"),
            (18, ESQUEMA +
             "funcao consultar(p: emprestimo[Pessoa]) -> inteiro {\n"
             " retorne p.id\n}\n"
             "inicio { seja p: lista[Pessoa]\n seja r = consultar(p)\n}"),
            (2, ESQUEMA +
             "funcao consultar(p: emprestimo[Inexistente]) -> inteiro {\n"
             " retorne 0\n}\n"
             "inicio { seja p: Pessoa\n seja r = consultar(p)\n}"),
            (5, ESQUEMA +
             "funcao consultar(p: emprestimo[Pessoa]) -> inteiro {\n"
             " retorne p.endereco.desconhecido\n}\n"
             "inicio { seja p: Pessoa\n seja r = consultar(p)\n}"),
            (18, ESQUEMA +
             "funcao consultar(p: emprestimo[Pessoa]) -> inteiro {\n"
             " retorne p.endereco\n}\n"
             "inicio { seja p: Pessoa\n seja r = consultar(p)\n}"),
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
