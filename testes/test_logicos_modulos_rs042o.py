"""RS 0.42O: palavras lógicas são reservadas antes de reunir módulos."""
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from compilador.erros import ErroCompilacao
from compilador.modulos import carregar_fontes, apresentar_erro
from compilador.parser import analisar_programa


class TestesLogicosModulosRS042O(unittest.TestCase):
    def reunir(self, modulo, principal):
        with tempfile.TemporaryDirectory() as pasta:
            raiz = Path(pasta)
            (raiz / 'biblioteca.rts').write_text(modulo, encoding='utf-8')
            arquivo = raiz / 'principal.rts'
            arquivo.write_text(principal, encoding='utf-8')
            return carregar_fontes(arquivo)

    def test_operadores_em_modulos_e_argumentos_qualificados(self):
        fontes = self.reunir('''publico funcao conferir(valor: logico) -> logico {
 retorne nao falso e valor ou falso
}
privado funcao auxiliar() -> logico {
 retorne nao verdadeiro
}
''', '''importe "biblioteca.rts" como regras
inicio {
 escreva(regras.conferir(nao falso e verdadeiro) ou nao falso)
}
''')
        programa = analisar_programa(fontes.texto)
        conferir = next(funcao for funcao in programa.funcoes.values()
                        if funcao.nome.endswith('_conferir'))
        self.assertEqual(conferir.programa.instrucoes[0][1][0], 'logica')
        argumento = programa.instrucoes[0][1][2][2][0]
        self.assertEqual(argumento[0], 'logica')
        self.assertEqual(argumento[2][0], 'nao')

    def test_apelidos_logicos_sao_rejeitados(self):
        modulo = 'publico funcao conferir() -> logico {\n retorne verdadeiro\n}\n'
        for palavra in ('e', 'ou', 'nao'):
            with self.subTest(palavra=palavra):
                with self.assertRaisesRegex(ErroCompilacao, 'apelido.*reservado'):
                    self.reunir(modulo, f'importe "biblioteca.rts" como {palavra}\ninicio {{\n escreva(1)\n}}\n')

    def test_tipos_e_funcoes_logicos_nao_escapam_pela_renomeacao(self):
        for palavra in ('e', 'ou', 'nao'):
            for visibilidade in ('publico', 'privado'):
                for definicao in (f'funcao {palavra}() -> logico {{\n retorne verdadeiro\n}}\n',
                                  f'tipo {palavra} {{\n valor: inteiro\n}}\n'):
                    with self.subTest(palavra=palavra, visibilidade=visibilidade, definicao=definicao):
                        with self.assertRaisesRegex(ErroCompilacao, 'biblioteca.rts:1:.*reservada.*operador lógico'):
                            self.reunir(visibilidade + ' ' + definicao,
                                        'importe "biblioteca.rts" como regras\ninicio {\n escreva(1)\n}\n')

    def test_erro_do_operando_logico_preserva_arquivo_e_linha_originais(self):
        fontes = self.reunir('''publico funcao conferir(valor: logico) -> logico {
 retorne falso e 1
}
''', 'importe "biblioteca.rts" como regras\ninicio {\n escreva(1)\n}\n')
        with self.assertRaises(ErroCompilacao) as contexto:
            analisar_programa(fontes.texto)
        mensagem, origem, _ = apresentar_erro(contexto.exception, fontes.origens)
        self.assertEqual(origem.caminho.name, 'biblioteca.rts')
        self.assertEqual(origem.numero, 2)
        self.assertIn('biblioteca.rts:2', mensagem)
        self.assertIn('operador e exige dois logicos', mensagem)


if __name__ == '__main__':
    unittest.main()
