## Ex06 — Soma e histograma paralelos (`ex06_soma_histograma_paralelo.c`)

**Objetivo:** medir *speedup* (ganho de velocidade) ao paralelizar com P = 1, 2, 4, 8 threads.

**Solução:** padrão *map-reduce*. O vetor é dividido em blocos contíguos e cada thread
acumula em **sua própria** `soma_parcial` e `histograma_parcial`; a `main` faz a redução
depois do `join`.

**Por quê sem mutex:** como cada thread escreve só na sua estrutura, não há região crítica
durante o processamento — nenhuma trava é necessária. Um mutex por elemento destruiria o
desempenho e anularia o paralelismo.

**Uso:** `./ex06 numeros.txt` (arquivo com inteiros separados por espaço/quebra de linha).
O tempo é medido com `clock_gettime(CLOCK_MONOTONIC)`, que não é afetado por ajustes do
relógio do sistema.