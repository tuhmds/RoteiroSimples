# RS-MEM: compressão reversível com expansão limitada

Biblioteca pública: `padrao/memoria_compacta.rts`.

A função `compactar(emprestimo[bytes]) -> resultado[bytes]`
faz duas passagens e escolhe um de dois formatos reversíveis:
- cabeçalho 0: cópia literal, quando RLE não reduziria os bytes;
- cabeçalho 1: pares [contagem 1..255, byte], quando compacta.

`expandir(emprestimo[bytes], limite) -> resultado[bytes]`
valida cabeçalhos, pares e comprimentos e recusa um corpo que possa
expandir acima do limite recebido. O tamanho máximo por chamada é
1 MiB nesta versão. Códigos de falha: 1 formato inválido; 2
expansão acima do limite; 3 limite de API excedido.

São preservados NUL, 255, dados arbitrários e sequência vazia.
O formato ainda não possui checksum, cabeçalho de tamanho original,
criptografia, suporte a streaming ou persistência versionada.
Não deve ser utilizado sozinho para documentos não confiáveis em disco.

**Esta biblioteca não compacta a RAM automaticamente.** A chamada
gera outro buffer e mantém o original enquanto o dono existir;
a aplicação precisa descartar o original após validar o resultado
para obter redução de memória. A codificação RLE pode consumir mais
CPU; só se aplica a dados com repetições longas. É uma etapa controlada
para estudar dados frios, não implementa swap, NUMA nem compressão
transparente do alocador.

Executa nativamente sem Python, com propriedade RS e testes
Windows/Linux O0/O4/O8.
