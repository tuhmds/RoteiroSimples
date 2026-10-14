"""Programas mistos: seleção, fronteiras de chamadas e oráculos nativos."""
import json
from pathlib import Path
import random
import tempfile
import unittest
from unittest.mock import patch

from backend import compilar
from backend.funcoes_mistas import preparar_funcoes_mistas
from backend.x86_64 import montar_codigo
from backend.windows_pe import montar_pe
from backend.linux_elf import montar_elf
from compilador.erros import ErroCompilacao
from compilador.estrategia import decidir_estrategia, descrever_estrategia
from compilador.funcoes_mistas import classificar_funcoes, construir_ir_funcoes
from compilador.medicao_compilacao import MedicaoCompilacao
from compilador.modulos import carregar_fontes
from compilador.parser import analisar_programa
from compilador.ssa_funcoes import construir_ssa_funcoes
from testes.test_cobertura_intermediaria_rs040c import executar_cli
from testes.test_valores_dinamicos_rs042a import alvo_nativo, rodar
from testes.test_emprestimos_registros_rs042i import COMUM

RAIZ = Path(__file__).resolve().parents[1]
ESCALAR = '''funcao calcular(numero: inteiro) -> inteiro {
    seja fator = 3 + 4
    seja ajuste = 9 * 2
    retorne numero * fator + ajuste
}
'''
MISTA = ESCALAR + '''funcao encaminhar(numero: inteiro) -> inteiro {
    seja titulo: texto
    copie(titulo, "RS")
    retorne calcular(numero) + caracteres(titulo)
}
inicio {
    seja valores: lista[]
    adicione(valores, encaminhar(6))
    escreva(valores[0])
}'''


class TestesFuncoesMistasRS042S(unittest.TestCase):
    def verificar(self, fonte, esperado=None, entrada=None, antes=None, erro=None):
        programa = analisar_programa(fonte)
        original = analisar_programa(fonte)
        referencia = None
        for nivel in range(9):
            with self.subTest(nivel=nivel):
                for alvo in ('windows', 'linux'):
                    imagem = compilar(programa, alvo, nivel=nivel, otimizar=nivel > 0)
                    if alvo == alvo_nativo():
                        resultado, arquivos = rodar(imagem, entrada, antes)
                observado = (resultado.returncode, resultado.stdout, resultado.stderr, arquivos)
                if referencia is None:
                    referencia = observado
                self.assertEqual(observado, referencia)
                if erro:
                    self.assertEqual(resultado.returncode, 1)
                    self.assertIn(erro, resultado.stdout + resultado.stderr)
                    self.assertNotIn('INDEVIDO', resultado.stdout)
                else:
                    self.assertEqual((resultado.returncode, resultado.stdout, resultado.stderr), (0, esperado, ''))
        self.assertEqual(programa, original, 'Compilar não pode alterar a AST compartilhada.')
        return programa

    def test_selecao_por_corpo_niveis_e_otimizacao_desativada(self):
        programa = analisar_programa(MISTA)
        for nivel in range(9):
            decisao = decidir_estrategia(programa, nivel, nivel > 0)
            self.assertEqual(decisao.gerador, 'misto' if nivel else 'conservador')
            funcoes = {f.nome: f for f in decisao.funcoes}
            self.assertTrue(funcoes['calcular'].elegivel)
            self.assertEqual(funcoes['calcular'].nivel_ir, min(nivel, 3))
            self.assertEqual(funcoes['calcular'].gerador,
                             'conservador' if not nivel else 'ssa' if nivel >= 4 else 'intermediario')
            self.assertFalse(funcoes['encaminhar'].elegivel)
            self.assertIn('variáveis locais', '; '.join(funcoes['encaminhar'].motivos))
            self.assertIn('encaminhar: conservador', descrever_estrategia(decisao))
        self.assertFalse(decidir_estrategia(programa, 8, False).otimiza)
        self.verificar(MISTA, '62\n')

    def test_recusa_transitiva_e_ciclos_elegiveis(self):
        fonte = MISTA.replace('inicio {', '''funcao depender(numero: inteiro) -> inteiro {
    retorne encaminhar(numero)
}
funcao acima(numero: inteiro) -> inteiro {
    retorne depender(numero)
}
funcao par(numero: inteiro) -> logico {
    se numero == 0 {
        retorne verdadeiro
    }
    retorne impar(numero - 1)
}
funcao impar(numero: inteiro) -> logico {
    se numero == 0 {
        retorne falso
    }
    retorne par(numero - 1)
}
inicio {''')
        programa = analisar_programa(fonte)
        motivos = classificar_funcoes(programa)
        self.assertIn('encaminhar', '; '.join(motivos['depender']))
        self.assertIn('depender', '; '.join(motivos['acima']))
        self.assertEqual(motivos['par'], ())
        self.assertEqual(motivos['impar'], ())
        grupo = construir_ir_funcoes(programa, ('calcular', 'par', 'impar'))
        self.assertTrue(construir_ssa_funcoes(grupo).validar())
        self.verificar(fonte.replace('escreva(valores[0])', 'escreva(par(24))\n escreva(impar(25))'), '1\n1\n')

    def test_grupo_incompleto_e_operacao_nova_sao_recusados(self):
        programa = analisar_programa(MISTA.replace('inicio {',
            'funcao outra(numero: inteiro) -> inteiro {\n retorne calcular(numero)\n}\ninicio {'))
        for nomes in (('outra',), ('encaminhar',), ('inexistente',), ('calcular', 'calcular')):
            with self.assertRaises(ErroCompilacao):
                construir_ir_funcoes(programa, nomes)
        programa.funcoes['calcular'].programa.instrucoes.insert(0, ('operacao_futura',))
        motivos = classificar_funcoes(programa)
        self.assertIn('operacao_futura', '; '.join(motivos['calcular']))
        self.assertIn('calcular', '; '.join(motivos['outra']))
        self.assertEqual(decidir_estrategia(programa, 8).gerador, 'conservador')
        programa = analisar_programa(MISTA)
        programa.funcoes['calcular'].programa.funcoes['interna'] = programa.funcoes['encaminhar']
        self.assertIn('aninhadas', '; '.join(classificar_funcoes(programa)['calcular']))

    def test_o0_preserva_bytes_e_corpos_conservadores_nao_sao_substituidos(self):
        programa = analisar_programa(MISTA)
        for windows in (True, False):
            g, mensagens = montar_codigo(programa, windows)
            esperado = montar_pe(g, mensagens) if windows else montar_elf(g, mensagens)
            self.assertEqual(compilar(programa, 'windows' if windows else 'linux', nivel=0, otimizar=False), esperado)
            legado, emissores, plano = preparar_funcoes_mistas(programa, decidir_estrategia(programa, 8), windows)
            self.assertIs(legado.funcoes['encaminhar'], programa.funcoes['encaminhar'])
            self.assertIs(legado.instrucoes, programa.instrucoes)
            self.assertIsNot(legado.funcoes['calcular'], programa.funcoes['calcular'])
            self.assertEqual(set(emissores), {'calcular'})
            self.assertIsNone(plano.programa.principal)

    def test_registros_colecoes_e_emprestimos_chamam_scalar(self):
        fonte = COMUM.replace('funcao criar', ESCALAR + 'funcao criar', 1).replace(
            'retorne documento.codigo +', 'retorne calcular(documento.codigo) +') + '''inicio {
    seja documentos: lista[Documento]
    para numero de 0 ate 200 {
        adicione(documentos, criar(numero))
    }
    seja soma = 0
    para indice de 0 ate tamanho(documentos) - 1 {
        soma = soma + consultar(empreste(documentos[indice]))
    }
    escreva(soma)
    seja retirado = retire(documentos, 2)
    escreva(consultar(empreste(retirado)))
    escreva(tamanho(documentos))
    limpe_lista(documentos)
    escreva(tamanho(documentos))
}'''
        esperado = sum((n * 7 + 18) + n + 7 + 1 for n in range(201))
        self.verificar(fonte, f'{esperado}\n42\n200\n0\n')

    def test_ordem_curto_circuito_e_donos_no_chamador(self):
        fonte = '''funcao marcar(numero: inteiro, valor: logico) -> logico {
    escreva(numero)
    retorne valor
}
funcao consultar(valor: logico) -> logico {
    seja texto_local: texto
    copie(texto_local, "RS")
    retorne marcar(1, valor) e marcar(2, verdadeiro)
}
inicio {
    seja valores: lista[logico]
    adicione(valores, consultar(falso))
    adicione(valores, consultar(verdadeiro))
    escreva(valores[0])
    escreva(valores[1])
}'''
        self.verificar(fonte, '1\n1\n2\n0\n1\n')

    def test_falhas_aritmeticas_e_argumentos_nao_usados(self):
        fonte = '''funcao ignorar(numero: inteiro) -> inteiro {
    retorne 7
}
funcao dividir(numero: inteiro, divisor: inteiro) -> inteiro {
    retorne ignorar(numero / divisor)
}
inicio {
    seja dono: texto
    copie(dono, "RS")
    escreva(dividir(1, 0))
    escreva("INDEVIDO")
}'''
        self.verificar(fonte, erro='zero')
        self.verificar(fonte.replace('dividir(1, 0)', 'dividir(-9223372036854775808, -1)'), erro='fora do limite')

    def test_entrada_e_arquivo_no_inicio_preservam_estado(self):
        fonte = ESCALAR + '''inicio {
    seja numero = 0
    leia(numero)
    seja dados: bytes
    adicione_byte(dados, calcular(numero))
    grave_arquivo("valor.rsd", dados)
    escreva(calcular(numero))
}'''
        programa = self.verificar(fonte, '60\n', entrada='6\n')
        resultado, arquivos = rodar(compilar(programa, alvo_nativo(), nivel=8), '6\n')
        self.assertEqual(arquivos, {'valor.rsd': bytes((60,))})

    def test_oraculo_gerado_com_lacos_chamadas_e_parametros_logicos(self):
        aleatorio = random.Random(420190)
        for _ in range(12):
            limite, fator, ajuste = aleatorio.randint(3, 20), aleatorio.randint(1, 9), aleatorio.randint(1, 40)
            fonte = f'''funcao parcela(numero: inteiro, incluir: logico) -> inteiro {{
    se incluir {{
        retorne numero * {fator} + {ajuste}
    }}
    retorne -numero
}}
funcao somar(limite: inteiro) -> inteiro {{
    seja total = 0
    para numero de 0 ate limite {{
        se numero == 2 {{
            continue
        }}
        total = total + parcela(numero, numero % 2 == 0)
    }}
    retorne total
}}
inicio {{
    seja valores: lista[]
    adicione(valores, somar({limite}))
    escreva(valores[0])
}}'''
            esperado = sum(n * fator + ajuste if n % 2 == 0 else -n
                           for n in range(limite + 1) if n != 2)
            self.verificar(fonte, f'{esperado}\n')

    def test_diagnostico_parcial_exporta_so_funcoes_elegiveis(self):
        with tempfile.TemporaryDirectory() as pasta:
            arquivo = Path(pasta) / 'ssa.json'
            resultado, existe = executar_cli(MISTA, ('-O', '8', '--mostrar-ir', '--mostrar-ssa',
                '--mostrar-alocacao', '--mostrar-estrategia', '--salvar-ssa', str(arquivo)))
            self.assertEqual(resultado.returncode, 0, resultado.stderr)
            self.assertTrue(existe)
            self.assertIn('IR parcial', resultado.stdout)
            dados = json.loads(arquivo.read_text(encoding='utf-8'))
            self.assertIsNone(dados['principal'])
            self.assertEqual(set(dados['funcoes']), {'calcular'})
        resultado, existe = executar_cli(MISTA, ('-O', '8', '--mostrar-fluxo'))
        self.assertEqual(resultado.returncode, 1)
        self.assertFalse(existe)
        self.assertIn('programa completo', resultado.stderr)
        resultado, existe = executar_cli(MISTA, ('-O', '0', '--mostrar-ssa'))
        self.assertEqual(resultado.returncode, 0, resultado.stderr)
        self.assertTrue(existe)

    def test_medidor_nao_altera_imagem_e_fecha_etapas_em_falha(self):
        programa = analisar_programa(MISTA)
        for alvo in ('windows', 'linux'):
            medidor = MedicaoCompilacao()
            self.assertEqual(compilar(programa, alvo, nivel=8, medidor=medidor), compilar(programa, alvo, nivel=8))
        with patch('backend.funcoes_mistas.alocar_registradores', side_effect=ValueError('falha injetada')):
            with self.assertRaisesRegex(ValueError, 'falha injetada'):
                compilar(programa, 'windows', nivel=8, medidor=medidor)
        self.assertEqual(medidor._pilha, [])

    def test_recursao_escalar_em_programa_misto_respeita_orcamento(self):
        fonte = '''funcao repetir(numero: inteiro) -> inteiro {
    retorne repetir(numero + 1)
}
inicio {
    seja dono: texto
    copie(dono, "RS")
    escreva(repetir(0))
    escreva("INDEVIDO")
}'''
        self.verificar(fonte, erro='pilha')

    def test_benchmarks_bibliotecas_tem_resultados_independentes(self):
        from testes.test_lexico_nativo_rs042c import referencia
        casos = (
            ('lexico_rs042s', 20000 * len(referencia(
                'inicio { seja numero = 17 se numero > 3 e nao falso { escreva(42) } }'))),
            ('colecoes_mistas_rs042s', 1000 * sum(243 * n + 128 for n in range(257))),
        )
        for nome, esperado in casos:
            programa = analisar_programa(carregar_fontes(RAIZ / 'benchmarks' / f'{nome}.rts').texto)
            for nivel in (0, 8):
                r, _ = rodar(compilar(programa, alvo_nativo(), nivel=nivel, otimizar=nivel > 0))
                self.assertEqual((r.returncode, r.stdout, r.stderr), (0, f'{esperado}\n', ''))

    def test_lexico_real_em_rs_confrontado_com_oraculo_python(self):
        from testes.test_lexico_nativo_rs042c import PROGRAMA, referencia
        programa = analisar_programa(carregar_fontes(PROGRAMA).texto)
        decisao = decidir_estrategia(programa, 8)
        self.assertEqual(decisao.gerador, 'misto')
        self.assertEqual(sum(f.elegivel for f in decisao.funcoes), 4)
        fonte = 'inicio {\n seja numero = 17\n se numero > 3 e nao falso { escreva("Ação 🌱") }\n}\n'
        tokens = referencia(fonte)
        esperado = str(len(tokens)) + '\n' + ''.join(str(v) + '\n' for t in tokens for v in t)
        for nivel in range(9):
            r, _ = rodar(compilar(programa, alvo_nativo(), nivel=nivel, otimizar=nivel > 0),
                         antes=lambda p: (p / 'codigo_fonte.rts').write_bytes(fonte.encode('utf-8')))
            self.assertEqual((r.returncode, r.stdout, r.stderr), (0, esperado, ''))


if __name__ == '__main__':
    unittest.main()
