"""Registros passados por valor: copia local na ABI ELF64 escrita em RS."""
import unittest
from testes import test_emissao_corpos_funcoes_elf_rs as base_corpos

ESQUEMAS = (
    "tipo Endereco {\n rua: inteiro\n numero: inteiro\n}\n"
    "tipo Pessoa {\n id: inteiro\n endereco: Endereco\n ativo: inteiro\n}\n"
)


class TestesParametrosRegistrosValorELFRS(unittest.TestCase):
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

    def test_copias_independentes_e_subcampos(self):
        casos = (
            (ESQUEMAS +
             "funcao mudar(p: Pessoa) -> inteiro {\n"
             " p.id = p.id + 40\n"
             " retorne p.id + p.endereco.numero\n}\n"
             "inicio {\n seja p: Pessoa\n p.id = 4\n"
             " p.endereco.numero = 7\n"
             " seja r = mudar(p) + p.id\n}", 55),
            (ESQUEMAS +
             "funcao mudar(p: Pessoa) -> inteiro {\n"
             " p.endereco.numero = 9\n"
             " retorne p.endereco.rua + p.endereco.numero + p.ativo\n}\n"
             "inicio {\n seja p: Pessoa\n p.endereco.rua = 20\n"
             " p.endereco.numero = 2\n p.ativo = 1\n"
             " seja r = mudar(p) + p.endereco.numero\n}", 32),
            (ESQUEMAS +
             "funcao combinar(a: inteiro, p: Pessoa, b: inteiro, q: Pessoa) -> inteiro {\n"
             " p.id = p.id + 5\n q.id = q.id + 7\n"
             " retorne a + p.id + q.id + b\n}\n"
             "inicio {\n seja p: Pessoa\n seja q: Pessoa\n"
             " p.id = 12\n q.id = 3\n"
             " seja r = combinar(2, p, 4, q) + p.id + q.id\n}", 48),
            (ESQUEMAS +
             "funcao ler(p: emprestimo[Pessoa]) -> inteiro {\n"
             " retorne p.id + p.endereco.numero\n}\n"
             "funcao encaminhar(p: Pessoa) -> inteiro {\n"
             " p.id = 15\n retorne ler(p)\n}\n"
             "inicio {\n seja p: Pessoa\n p.id = 4\n"
             " p.endereco.numero = 8\n seja r = encaminhar(p) + p.id\n}", 27),
            (ESQUEMAS +
             "funcao valor(p: Pessoa) -> inteiro {\n retorne p.id\n}\n"
             "funcao emprestar(p: emprestimo[Pessoa]) -> inteiro {\n"
             " retorne valor(p)\n}\n"
             "inicio {\n seja p: Pessoa\n p.id = 19\n"
             " seja r = emprestar(p)\n}", 19),
        )
        for nivel in (0, 8):
            for fonte, esperado in casos:
                with self.subTest(nivel=nivel, esperado=esperado):
                    codigo, arquivo, status = self.gerar(fonte, nivel)
                    self.assertEqual(codigo, 0)
                    self.assertIsNotNone(arquivo)
                    if status is not None:
                        self.assertEqual(status, esperado)

    def test_incompatibilidades_e_tipos_ausentes(self):
        casos = (
            (18, ESQUEMAS +
             "funcao usar(p: Pessoa) -> inteiro { retorne p.id }\n"
             "inicio { seja endereco: Endereco\n seja r = usar(endereco) }"),
            (18, ESQUEMAS +
             "funcao usar(p: Pessoa) -> inteiro { retorne p.id }\n"
             "inicio { seja r = usar(42) }"),
            (18, ESQUEMAS +
             "funcao usar(p: Pessoa) -> inteiro { retorne p.id }\n"
             "inicio { seja p: lista[Pessoa]\n seja r = usar(p) }"),
            (2, ESQUEMAS +
             "funcao usar(p: Fantasma) -> inteiro { retorne 0 }\n"
             "inicio { seja r = usar(1) }"),
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
