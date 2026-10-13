"""RS 0.42A: contrato único de valores, descritores e efeitos de transferência."""
from dataclasses import FrozenInstanceError
from pathlib import Path
import sys
import unittest

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

from compilador.ast import Programa
from compilador.contrato_efeitos import Efeitos, podem_trocar_de_ordem
from compilador.disposicao_tipos import palavras_tipo
from compilador.efeitos_programa import (
    efeito_expressao_arvore, efeito_instrucao_arvore, listar_efeitos_programa,
)
from compilador.estrategia import decidir_estrategia
from compilador.propriedade import (
    PALAVRAS_DESCRITOR, ESTADO_INATIVO, DESLOCAMENTO_PONTEIRO,
    DESLOCAMENTO_COMPRIMENTO, DESLOCAMENTO_CAPACIDADE,
    eh_proprietario, eh_emprestimo, classe_valor, contrato_valor,
)

DONO = ('lista_dinamica', 'inteiro')
EMPRESTIMO = ('lista_emprestada', 'inteiro')


class TestesPropriedadeRS042A(unittest.TestCase):
    def test_descritor_compartilhado_preserva_disposicao_atual(self):
        self.assertEqual(PALAVRAS_DESCRITOR, 3)
        self.assertEqual(ESTADO_INATIVO, -1)
        self.assertEqual((DESLOCAMENTO_PONTEIRO, DESLOCAMENTO_COMPRIMENTO,
                          DESLOCAMENTO_CAPACIDADE), (0, -8, -16))
        self.assertEqual(palavras_tipo(DONO, {}), PALAVRAS_DESCRITOR)
        self.assertEqual(contrato_valor(DONO).palavras, PALAVRAS_DESCRITOR)
        self.assertEqual(palavras_tipo(EMPRESTIMO, {}), 1)

    def test_dono_nao_e_copiavel_e_requer_descarte(self):
        for elemento in ('inteiro', 'logico', 'Registro'):
            tipo = ('lista_dinamica', elemento)
            self.assertTrue(eh_proprietario(tipo))
            self.assertFalse(eh_emprestimo(tipo))
            contrato = contrato_valor(tipo)
            self.assertEqual(contrato.classe, 'proprietario')
            self.assertFalse(contrato.pode_copiar)
            self.assertTrue(contrato.precisa_descartar)
            self.assertEqual(contrato.palavras, 3)

    def test_emprestimo_nao_duplica_propriedade_nem_requer_descarte(self):
        contrato = contrato_valor(EMPRESTIMO)
        self.assertTrue(eh_emprestimo(EMPRESTIMO))
        self.assertFalse(eh_proprietario(EMPRESTIMO))
        self.assertEqual(contrato.classe, 'emprestimo')
        self.assertFalse(contrato.pode_copiar)
        self.assertFalse(contrato.precisa_descartar)
        self.assertEqual(contrato.palavras, 1)

    def test_valores_fixos_continuam_copiaveis(self):
        registros = {'Registro': (('numero', 'inteiro'),
                                  ('texto', ('texto', 17)),
                                  ('bytes', ('bytes', 9)))}
        casos = [('inteiro', 1), ('logico', 1), (('texto', 17), 4),
                 (('bytes', 9), 3), (('lista', 'inteiro', 5), 5),
                 ('Registro', 8),
                 (('registro', 'Registro', registros['Registro']), 8)]
        for tipo, largura in casos:
            with self.subTest(tipo=tipo):
                contrato = contrato_valor(tipo, registros)
                self.assertEqual(contrato.classe, 'valor')
                self.assertTrue(contrato.pode_copiar)
                self.assertFalse(contrato.precisa_descartar)
                self.assertEqual(contrato.palavras, largura)
                self.assertEqual(contrato.palavras, palavras_tipo(tipo, registros))

    def test_arquivo_mantem_descarte_proprio_sem_movimentacao_dinamica(self):
        contrato = contrato_valor('arquivo')
        self.assertEqual(classe_valor('arquivo'), 'recurso')
        self.assertFalse(eh_proprietario('arquivo'))
        self.assertFalse(contrato.pode_copiar)
        self.assertTrue(contrato.precisa_descartar)
        self.assertEqual(contrato.palavras, 1)

    def test_contrato_imutavel_nao_anuncia_tipos_dinamicos_inexistentes(self):
        contrato = contrato_valor(DONO)
        with self.assertRaises(FrozenInstanceError):
            contrato.pode_copiar = True
        for tipo in (('texto_dinamico',), ('bytes_dinamicos',),
                     ('lista_dinamica',), ('lista_emprestada',)):
            with self.subTest(tipo=tipo):
                self.assertFalse(eh_proprietario(tipo))
                self.assertFalse(eh_emprestimo(tipo))
                with self.assertRaises(ValueError):
                    contrato_valor(tipo)

    def test_consultas_dinamicas_preservam_falha_e_ordem(self):
        outra_escrita = Efeitos(escritas=frozenset(('outra',)))
        for operacao in ('quantidade_lista_dinamica', 'capacidade_lista_dinamica',
                         'quantidade_lista_emprestada', 'capacidade_lista_emprestada',
                         'empreste_lista_dinamica'):
            with self.subTest(operacao=operacao):
                efeito = efeito_expressao_arvore((operacao, 'origem'))
                self.assertEqual(efeito.leituras, frozenset(('origem',)))
                self.assertTrue(efeito.pode_falhar)
                self.assertFalse(efeito.desconhecido)
                self.assertTrue(efeito.barreira_de_reordenacao)
                self.assertFalse(podem_trocar_de_ordem(efeito, outra_escrita))
                self.assertFalse(podem_trocar_de_ordem(outra_escrita, efeito))
        for operacao in ('tamanho_texto', 'tamanho_bytes'):
            efeito = efeito_expressao_arvore((operacao, 'fixo'))
            self.assertFalse(efeito.pode_falhar)

    def test_movimentacao_existente_marca_verificacao_e_descarte(self):
        efeito = efeito_instrucao_arvore(('mova_lista_dinamica', 'destino', 'origem'))
        self.assertTrue(efeito.pode_falhar)
        self.assertEqual(efeito.propriedade, ('receber:destino', 'mover:origem'))
        self.assertEqual(efeito.leituras, frozenset(('origem', 'destino')))
        self.assertEqual(efeito.escritas, frozenset(('origem', 'destino')))
        self.assertFalse(efeito.desconhecido)
        self.assertFalse(podem_trocar_de_ordem(efeito, Efeitos()))

    def test_receber_e_retornar_dono_sao_eventos_de_propriedade(self):
        movimento = ('mova_valor_dinamico', 'origem')
        efeito = efeito_expressao_arvore(movimento)
        self.assertEqual(efeito.propriedade, ('mover:origem',))
        self.assertTrue(efeito.pode_falhar)
        self.assertEqual(efeito.leituras, efeito.escritas)
        recebimento = efeito_instrucao_arvore(('receba_valor_dinamico', 'destino', movimento))
        self.assertEqual(recebimento.propriedade, ('receber:destino', 'mover:origem'))
        self.assertFalse(recebimento.desconhecido)
        self.assertTrue(recebimento.barreira_de_reordenacao)
        retorno = efeito_instrucao_arvore(('retorne', movimento))
        self.assertTrue(retorno.controle)
        self.assertTrue(retorno.encerra)
        self.assertEqual(retorno.propriedade, ('mover:origem',))

    def test_receber_resultado_de_chamada_mantem_barreira_interprocedural(self):
        efeito = efeito_instrucao_arvore(('receba_valor_dinamico', 'destino',
                    ('chamada', 'transformar', (('mova_valor_dinamico', 'origem'),))))
        self.assertTrue(efeito.pode_falhar)
        self.assertTrue(efeito.desconhecido)
        self.assertTrue(efeito.barreira_de_reordenacao)
        self.assertIn('mover:origem', efeito.propriedade)
        self.assertIn('receber:destino', efeito.propriedade)
        self.assertFalse(podem_trocar_de_ordem(efeito, Efeitos()))

    def test_novas_transferencias_seguem_gerador_conservador_em_nove_niveis(self):
        programa = Programa([
            ('crie_lista_dinamica', 'origem'),
            ('receba_valor_dinamico', 'destino', ('mova_valor_dinamico', 'origem')),
        ], {'origem': 0, 'destino': 3}, False, {'origem': DONO, 'destino': DONO})
        for nivel in range(9):
            for otimizar in (False, True):
                with self.subTest(nivel=nivel, otimizar=otimizar):
                    estrategia = decidir_estrategia(programa, nivel, otimizar)
                    self.assertEqual(estrategia.gerador, 'conservador')
                    self.assertFalse(estrategia.otimiza)
                    self.assertEqual(estrategia.nivel_ir, 0)
        recebimento = next(i for i in listar_efeitos_programa(programa)
                          if i['operacao'] == 'receba_valor_dinamico')
        self.assertTrue(recebimento['barreira_de_reordenacao'])
        self.assertFalse(recebimento['desconhecido'])


if __name__ == '__main__':
    unittest.main()
