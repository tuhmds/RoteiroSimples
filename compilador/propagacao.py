"""O2 experimental: propagação local de constantes, sem eliminar efeitos observáveis."""
from dataclasses import replace
from .nos_ir import ProgramaIR, ExpressaoIR
from .otimizador import dobrar_constantes


def otimizar_expressao(expr, ambiente):
    """Reescreve na ordem de avaliação e invalida conhecimentos após chamada.

    Um ramo lógico comprovadamente dispensado não é percorrido: sua chamada
    não acontece. Quando o direito ainda pode executar, sua invalidação é
    conservada para as expressões e instruções seguintes.
    """
    if expr.operacao == 'var' and expr.valor in ambiente:
        return ExpressaoIR(expr.tipo, 'logico' if expr.tipo == 'logico' else 'numero',
                           ambiente[expr.valor], origem=expr.origem)
    if not expr.filhos:
        if expr.operacao == 'chamada':
            ambiente.clear()
        return expr
    if expr.operacao == 'logica':
        esquerdo = otimizar_expressao(expr.filhos[0], ambiente)
        reescrita = replace(expr, filhos=(esquerdo, expr.filhos[1]))
        reduzida = dobrar_constantes(reescrita)
        if reduzida.operacao == 'logico':
            return reduzida
        direito = otimizar_expressao(expr.filhos[1], ambiente)
        reescrita = replace(expr, filhos=(esquerdo, direito))
    else:
        reescrita = replace(expr, filhos=tuple(otimizar_expressao(f, ambiente)
                                              for f in expr.filhos))
    if expr.operacao == 'chamada':
        # Chamadas escalares atuais não alteram locais do chamador. Ainda
        # assim, não propagar suposições além desta fronteira de efeitos.
        ambiente.clear()
    return dobrar_constantes(reescrita)


def propagar_constantes_locais(programa: ProgramaIR):
    """Propaga apenas dentro de sequências retas; limpa estado em cada junção.

    Mantém todas as atribuições e operações potencialmente falhas: nenhuma
    expressão é removida ou movida. Laços/ramos nunca herdam suposições.
    """
    def bloco(instrucoes):
        ambiente = {}
        resultado = []
        for ins in instrucoes:
            op, args = ins.operacao, ins.argumentos
            if op == 'atribua':
                nome, expressao = args
                exp = otimizar_expressao(expressao, ambiente)
                resultado.append(replace(ins, argumentos=(nome, exp)))
                ambiente.pop(nome, None)
                if exp.operacao in ('numero', 'logico'):
                    ambiente[nome] = exp.valor
            elif op in ('imprima_num', 'retorne'):
                resultado.append(replace(ins, argumentos=(otimizar_expressao(args[0], ambiente),)))
                if op == 'retorne':
                    ambiente.clear()
            elif op == 'leia_int':
                ambiente.pop(args[0], None)
                resultado.append(ins)
            elif op == 'se':
                # Não propagamos estados através de condições e junções.
                resultado.append(replace(ins, argumentos=(args[0], bloco(args[1]), bloco(args[2]))))
                ambiente.clear()
            elif op == 'enquanto':
                resultado.append(replace(ins, argumentos=(args[0], bloco(args[1]))))
                ambiente.clear()
            elif op == 'para':
                resultado.append(replace(ins, argumentos=(*args[:4], bloco(args[4]))))
                ambiente.clear()
            else:
                resultado.append(ins)
        return tuple(resultado)

    return replace(programa, instrucoes=bloco(programa.instrucoes))
