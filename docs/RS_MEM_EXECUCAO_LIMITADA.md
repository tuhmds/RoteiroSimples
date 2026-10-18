# RS-MEM — execução com limite real de memória virtual (Linux)

CLI:
```bash
python -m verificacao.execucao_limitada --limite-mib 128 --timeout 15 --json relatorios/processo.json -- ./aplicativo-rs
```

O filho recebe `RLIMIT_AS` (limite de espaço de endereço virtual) antes
de executar o ELF. Uma tentativa de reservar acima do limite falha no
núcleo, sem requerer alterações no executável RS. O relatório inclui
código de saída, timeout, duração, trecho limitado de stdout/stderr e
`ru_maxrss` reportado pelo Linux para processos filhos.

**Atenção:** `RLIMIT_AS` não equivale a limitar RAM física residente,
não mede page faults individualmente, não impõe limite de CPU, não impede
sobresubscrição do sistema e não substitui cgroups. O pico RSS obtido por
`RUSAGE_CHILDREN` é o máximo de filhos já encerrados pelo supervisor
e pode incluir outros filhos se chamado repetidamente no mesmo processo.
Execute um comando por invocação da CLI para comparações mais claras.

O utilitário usa `preexec_fn` em processo filho Linux e é destinado ao
supervisor CLI *de thread única*. Não chamar em aplicações Python
multithread. Nenhuma modificação é feita em Windows: o modo não
é oferecido lá, pois restrições equivalentes requerem Windows Job Objects
e um caminho independente de criação de processo; não se simula segurança
de orçamento por monitoramento posterior.

Saídas do processo são encaminhadas a arquivos temporários, e somente os
primeiros 64 KiB de cada fluxo entram no relatório; evita que o
supervisor absorva uma saída potencialmente ilimitada em RAM.
Falhas de execução produzem status não zero; timeout mata o filho
e sinaliza código CLI 124. O limitador não garante segurança completa
contra subprocessos criados pelo aplicativo; para ambientes hostis,
combine contêiner/cgroup e isolamento de sistema.
