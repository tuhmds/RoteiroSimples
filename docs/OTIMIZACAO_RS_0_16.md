# RS 0.16 — Coalescência e compactação segura de saltos

## O que foi implementado

O novo nível `-O 6` parte da mesma SSA/CFG tipada do `-O 5` e conserva a verificação de estouro aritmético, a entrada via `leia` e o formato PE32+/ELF64.

1. **Afinidades `phi`:** o alocador identifica pares `destino, fonte` dos nós `phi`, conta quantas arestas preferem a cópia e, durante a coloração, dá preferência à localização física de vizinhos afins já alocados. O compartilhamento só é aceito quando os nós não se encontram no grafo de interferência. Se não houver registrador disponível, a preferência pode ser aplicada também aos slots da pilha.
2. **Movimentações de registradores:** cópias `reg <- reg` restantes são emitidas como uma instrução `mov` (3 bytes para `r13`/`r14`/`r15`), em vez de `mov rax,reg` seguido de `mov reg,rax`. As cópias paralelas e a quebra de ciclos preservam a mesma semântica.
3. **Branch relaxation `rel32 -> rel8`:** o backend anota saltos SSA candidatos, calcula as reduções em múltiplas passagens até atingir um ponto fixo, e então reescreve os bytes. Só encurta se o deslocamento final assinado couber em 8 bits; nunca encurta `call`, saltos de runtime ou referências externas. Ajusta rótulos e pendências relativas de quatro bytes. Usa os opcodes AMD64 curtos correspondentes, incluindo saltos condicionais. O cálculo é feito antes de resolver endereços no formato PE/ELF.

## Limitações e cuidados

- **Não é coalescência global perfeita** nem construção de SSA destruída em uma nova IR: é coloração com preferência de movimentos.
- A codificação encurtada afeta apenas branches locais com nomes `ssa_*`; rotinas de suporte continuam usando rel32.
- Os testes incluem ciclos de cópias, interferências de registradores, limites dos saltos, leitura, `pare`, `continue`, overflow e comparação entre backends em Linux/Windows.
- `-O 5` continua disponível para comparar comportamentos e usar como alternativa caso a nova otimização apresente regressão.
- Redução de bytes não equivale automaticamente a redução de tempo de CPU; a medição usa um microbenchmark com múltiplas repetições e mediana.

## Próximos passos

Adicionar perfil de uso de blocos, benchmarks de código pesado em memória, análise de custo de spills e melhoria do `leia` para entrada em blocos. Tipos compostos, ponteiros e `heap` ainda exigem especificação de propriedade e tempo de vida antes da implementação.
