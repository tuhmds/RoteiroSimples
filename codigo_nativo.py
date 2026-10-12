"""API compatível, agora implementada em backend/."""
from backend.base import alinhar, Emissor
from backend.x86_64 import (Gerador, carregar_numero, deslocamento_variavel,
    expressao, escreve_literal, imprime_inteiro, percorrer_instrucoes,
    ler_inteiro, montar_codigo)
from backend.windows_pe import construir_importacoes, montar_pe
from backend.linux_elf import montar_elf
from backend import compilar
