# Exercício 5 — Pool fixo de threads com fila concorrente

## Enunciado

Implementar um pool fixo de N threads que processa uma fila concorrente de tarefas CPU-bound (teste de primalidade ou Fibonacci iterativo), permitindo enfileirar tarefas pela entrada padrão, processando até EOF e finalizando o pool com sinalização apropriada. Provar que a fila é thread-safe e que nenhuma tarefa se perde.

## Arquivos

| Arquivo | Conteúdo |
|---|---|
| `pool_threads.py` | Fila concorrente, pool de threads, leitura da entrada, verificação e teste de estresse da fila |
| `gerar_tarefas.py` | Gera uma quantidade qualquer de tarefas aleatórias para usar como entrada |
| `tarefas.txt` | Entrada pequena de exemplo (inclui uma linha inválida de propósito) |

## Como executar

Linguagem: Python 3 (testado no 3.14). Não há dependências externas.

```bash
python pool_threads.py 4 < tarefas.txt
python gerar_tarefas.py 500 42 | python pool_threads.py 4 --silencioso
python pool_threads.py 8 --teste-fila --produtores 4 --itens 20000
```

Também dá para digitar as tarefas no terminal, uma por linha. Para enviar EOF, use `Ctrl+Z` e `Enter` no Windows ou `Ctrl+D` no Linux.

| Parâmetro | Significado | Padrão |
|---|---|---|
| `threads` (posicional) | Número de threads do pool (ou de consumidores no `--teste-fila`) | 4 |
| `--silencioso` | Não imprime o resultado de cada tarefa, só o resumo | desligado |
| `--teste-fila` | Roda o teste de estresse da fila em vez de ler tarefas | desligado |
| `--produtores` | Quantidade de produtores no teste de estresse | 4 |
| `--itens` | Itens gerados por produtor no teste de estresse | 50000 |

### Formato da entrada

Cada linha é uma tarefa:

```
primo 1000000007
fib 5000
97
```

- `primo N` testa se N é primo.
- `fib N` calcula o N-ésimo número de Fibonacci.
- Uma linha com apenas um número é tratada como `primo`.
- Linhas em branco são ignoradas. Linhas inválidas são avisadas na saída de erro e contadas como rejeitadas.

## Explicação do código

### `FilaConcorrente`

É a fila compartilhada entre as threads. Ela foi escrita à mão, sem usar `queue.Queue`, para deixar explícito como a sincronização acontece:

- Os itens ficam em um `deque`.
- Um único `threading.Condition`, construído sobre um `Lock`, protege todo o estado: os itens, a flag `_fechada` e os contadores `inseridos` e `removidos`.
- `colocar(item)` adquire a trava, insere o item, incrementa `inseridos` e chama `notify()` para acordar uma thread que esteja esperando. Se a fila já estiver fechada, lança um erro, então nenhuma tarefa é aceita depois do encerramento.
- `retirar()` adquire a trava e, enquanto a fila estiver vazia **e** aberta, chama `wait()`. O `wait()` solta a trava e bloqueia a thread sem consumir CPU, ou seja, não há espera ativa. O teste fica dentro de um `while` para lidar com acordares espúrios e com o caso de outra thread pegar o item primeiro. Quando a fila está vazia **e** fechada, devolve `None`, que é o sinal de fim para o worker.
- `fechar()` marca a fila como fechada e chama `notify_all()` para acordar **todas** as threads bloqueadas, para que elas percebam o encerramento.

Como toda leitura e escrita do estado acontece com a mesma trava adquirida, duas threads nunca mexem no `deque` ou nos contadores ao mesmo tempo.

### Tarefas CPU-bound

- `eh_primo(n)`: divisão por tentativa até a raiz de `n`, testando só números da forma 6k ± 1.
- `fibonacci(n)`: versão iterativa, com dois acumuladores.
- `Tarefa`: um `dataclass` imutável com `id`, `operacao` e `valor`. Os ids são sequenciais, começando em 1, e é por eles que o programa confere se alguma tarefa se perdeu.

### `PoolDeThreads`

- No construtor, cria N threads (`worker-0` até `worker-N-1`) e já as inicia. O número de threads é fixo durante toda a execução.
- Cada worker (`_executar`) fica em um laço: retira uma tarefa, executa, grava o resultado e repete. Quando `retirar()` devolve `None`, o worker sai do laço, registra quantas tarefas fez e termina.
- Os resultados ficam em um dicionário `resultados`, protegido por `_lock_resultados`. Antes de gravar, o worker verifica se aquele id já existe. Se existir, anota em `duplicadas`.
- A impressão usa outra trava (`_lock_saida`), para que as linhas de threads diferentes não se misturem no terminal.
- `encerrar()` fecha a fila e faz `join()` em todos os workers. Esse é o protocolo de encerramento: a fila fechada funciona como sinal, e os workers só param depois de esvaziá-la, então nenhuma tarefa que já estava na fila é abandonada.

### Fluxo principal (`main`)

1. Cria o pool.
2. `ler_tarefas` lê a entrada padrão linha a linha até EOF, valida cada linha com `interpretar` e submete as tarefas válidas. A thread principal atua como produtora enquanto os workers já estão consumindo.
3. No EOF, chama `pool.encerrar()`.
4. Imprime o resumo e chama `verificar`.

## Como o programa prova que funciona

### 1. Nenhuma tarefa perdida ou duplicada (`verificar`)

Ao fim de toda execução, estas asserções são checadas:

| Asserção | O que garante |
|---|---|
| `fila.inseridos == total` | Toda tarefa lida entrou na fila |
| `fila.removidos == total` | Toda tarefa que entrou foi retirada |
| `len(fila) == 0` | Não sobrou nada na fila |
| `not duplicadas` | Nenhuma tarefa foi processada duas vezes |
| `set(resultados) == {1, ..., total}` | Todos os ids aparecem nos resultados, sem faltar nenhum |
| `sum(por_worker) == total` | A soma do que cada worker declarou fazer bate com o total |
| Recalcula cada tarefa sem threads e compara | Os resultados não foram corrompidos |

Se qualquer uma falhar, o programa termina com `AssertionError` e uma mensagem dizendo o que deu errado.

### 2. A fila é thread-safe (`--teste-fila`)

O teste de estresse coloca P produtores e C consumidores usando a mesma fila ao mesmo tempo:

- Cada produtor insere pares `(produtor, i)` para `i` de 0 até `itens - 1`. Assim, cada item é único e sabemos de onde ele veio.
- `sys.setswitchinterval(1e-6)` força o interpretador a trocar de thread com muito mais frequência, aumentando a chance de aparecer uma condição de corrida se a fila tivesse algum erro.
- No final, o teste confere que:
  - a quantidade consumida é igual à produzida;
  - o conjunto de itens consumidos é exatamente o conjunto esperado, sem itens perdidos, repetidos ou desconhecidos;
  - para cada consumidor, os itens de um mesmo produtor chegaram em ordem crescente, ou seja, a ordem FIFO foi mantida.

## Resultados obtidos

### Entrada de exemplo (`tarefas.txt`, 3 threads)

```
linha 11 ignorada: 'isso nao e tarefa'
[worker-0] tarefa #1 primo(97) = primo (0.00 ms)
[worker-0] tarefa #4 fib(90) = 2880067194370816120 (0.00 ms)
[worker-0] tarefa #5 primo(600851475143) = nao primo (0.00 ms)
[worker-0] tarefa #6 fib(5000) = <1045 digitos> (0.29 ms)
[worker-0] tarefa #7 primo(2147483647) = primo (0.81 ms)
[worker-2] tarefa #2 primo(1000000007) = primo (0.55 ms)
[worker-1] tarefa #3 fib(10) = 55 (0.00 ms)
...
===== Resumo =====
Threads no pool: 3
Tarefas lidas: 12 (linhas rejeitadas: 1)
Inseridas na fila: 12 | Retiradas da fila: 12
Tarefas processadas: 12
  worker-0: 7 tarefas
  worker-1: 2 tarefas
  worker-2: 3 tarefas
Verificacao: OK - nenhuma tarefa perdida, nenhuma duplicada e todos os resultados conferem.
```

As tarefas terminam fora da ordem de chegada (a #3 depois da #7, por exemplo), o que mostra que várias threads estão processando ao mesmo tempo. Mesmo assim, todas as 12 foram processadas uma única vez.

### 500 tarefas aleatórias (4 threads)

```
Tarefas lidas: 500 (linhas rejeitadas: 0)
Inseridas na fila: 500 | Retiradas da fila: 500
Tarefas processadas: 500
  worker-0: 75 tarefas
  worker-1: 183 tarefas
  worker-2: 153 tarefas
  worker-3: 89 tarefas
Verificacao: OK - nenhuma tarefa perdida, nenhuma duplicada e todos os resultados conferem.
```

A divisão entre os workers não é igual porque cada um pega uma nova tarefa assim que termina a anterior. Quem pega tarefas mais rápidas acaba fazendo mais, e é assim que um pool deve se comportar.

### Teste de estresse da fila (4 produtores, 8 consumidores, 80.000 itens)

```
Produtores: 4 | Consumidores: 8 | Itens: 80000
  consumidor-0: 10048 itens
  consumidor-1: 10106 itens
  ...
  consumidor-7: 10546 itens
Tempo: 0.69 s
OK: todos os itens foram consumidos exatamente uma vez e a ordem FIFO foi preservada.
```

## Observação sobre o GIL

No CPython comum, o GIL impede que duas threads executem bytecode Python ao mesmo tempo. Por isso, este pool não deixa tarefas CPU-bound mais rápidas do que rodá-las em sequência. O objetivo do exercício, porém, é a parte de sincronização: fila compartilhada, bloqueio sem espera ativa, encerramento limpo e garantia de que nada se perde. Isso vale da mesma forma com ou sem GIL, porque as trocas de thread continuam acontecendo em momentos imprevisíveis. Em um Python sem GIL (free-threaded, disponível a partir do 3.13), o mesmo código roda em paralelo de verdade sem precisar de nenhuma mudança.

## Conclusão

- A fila usa uma única trava com variável de condição. Isso garante exclusão mútua e faz as threads bloquearem sem gastar CPU enquanto não há trabalho.
- O encerramento por fila fechada + `notify_all()` acorda todos os workers, e cada um só termina depois que a fila esvazia. Assim nenhuma tarefa enfileirada é perdida.
- As asserções ao final de cada execução e o teste de estresse com 80.000 itens mostram, na prática, que cada tarefa é processada exatamente uma vez e com o resultado correto.
