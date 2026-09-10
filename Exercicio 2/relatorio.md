## Ex02 — Buffer circular produtor/consumidor (`ex02_buffer_circular.c`)

**Objetivo:** clássico produtor-consumidor com buffer limitado e coleta de métricas.

**Solução:** buffer circular de tamanho fixo protegido por um mutex e duas condições:
`cv_nao_cheio` (produtor espera quando o buffer enche) e `cv_nao_vazio` (consumidor
espera quando esvazia). Cada item leva o *timestamp* de produção, o que permite medir o
tempo médio de espera na fila; ao final imprime *throughput* e latência média.

**Encerramento:** o contador `produtores_ativos` chega a zero quando todos terminam; aí
um `broadcast` acorda os consumidores, que saem do laço ao ver fila vazia e nenhum
produtor ativo. Sem isso, os consumidores ficariam bloqueados para sempre.

**Detalhe:** o `while` (e não `if`) em volta do `pthread_cond_wait` protege contra
*spurious wakeups* — despertares sem que a condição tenha realmente mudado.