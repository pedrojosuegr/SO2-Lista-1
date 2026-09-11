# Relatório — Pipeline Concorrente em Java (Captura → Processamento → Gravação)

## 1. Objetivo

Implementar uma linha de processamento (*pipeline*) com **três threads** — **Captura**,
**Processamento** e **Gravação** — conectadas por **duas filas limitadas (bounded
queues)**, protegidas manualmente por **mutex + variável de condição**. O pipeline
processa **N** itens e finaliza com um protocolo de **encerramento limpo (poison
pill)**, demonstrando **ausência de deadlock** e **ausência de perda de itens**.

## 2. Arquitetura da solução

```
                 fila1                        fila2
  [Captura] ───────────────▶ [Processamento] ───────────────▶ [Gravação]
   produz N itens      (capacidade limitada)      processa      (capacidade limitada)      grava
   + poison pill                                 e repassa                              e consome
                                                  poison pill                            poison pill
```

| Classe             | Papel                                                              |
|---------------------|---------------------------------------------------------------------|
| `Item`              | Dado que trafega no pipeline; também define o sentinela `POISON_PILL` |
| `BoundedQueue<T>`   | Fila limitada thread-safe (mutex + `Condition`), sem uso de `BlockingQueue` pronta |
| `CaptureStage`      | Gera N itens e os publica na fila 1; ao final, publica o poison pill |
| `ProcessingStage`   | Consome da fila 1, transforma o item, publica na fila 2; repassa o poison pill |
| `RecordingStage`    | Consome da fila 2 e "grava" o item final; encerra ao ver o poison pill |
| `Pipeline`          | `main`: monta filas/threads, executa, valida e imprime o relatório |

### 2.1 Fila limitada com mutex + condição

Em vez de usar `java.util.concurrent.BlockingQueue`, a fila é implementada manualmente
com `ReentrantLock` (mutex) e duas `Condition` — o padrão clássico de monitor:

```java
public void put(T item) throws InterruptedException {
    lock.lock();
    try {
        while (buffer.size() == capacity) {
            notFull.await();       // dorme liberando o mutex até haver espaço
        }
        buffer.addLast(item);
        notEmpty.signalAll();      // acorda quem espera para consumir
    } finally {
        lock.unlock();
    }
}

public T take() throws InterruptedException {
    lock.lock();
    try {
        while (buffer.isEmpty()) {
            notEmpty.await();       // dorme liberando o mutex até haver item
        }
        T item = buffer.removeFirst();
        notFull.signalAll();        // acorda quem espera para produzir
        return item;
    } finally {
        lock.unlock();
    }
}
```

Pontos de projeto relevantes:

- **`while` em vez de `if`** ao redor do `await()`: protege contra *spurious wakeups*
  e contra reavaliação incorreta da condição.
- **`signalAll()` em vez de `signal()`**: elimina o risco de *lost wakeup* mesmo que,
  no futuro, mais de um produtor/consumidor passe a operar na mesma fila.
- Cada operação (`put`/`take`) adquire **apenas o lock da própria fila**, nunca dois
  locks ao mesmo tempo — propriedade central para o argumento de ausência de
  deadlock (seção 4).

### 2.2 Protocolo de encerramento limpo (poison pill)

`Item.POISON_PILL` é um item sentinela (`id == -1`). Fluxo de encerramento:

1. **Captura** produz os N itens e, só então, publica o `POISON_PILL` na fila 1.
2. **Processamento** consome normalmente até receber o `POISON_PILL`; quando isso
   ocorre, ele o **repassa** para a fila 2 (sem processá-lo como dado) e termina.
3. **Gravação** consome normalmente até receber o `POISON_PILL`; como é o último
   estágio, apenas termina (não há para quem repassar).

Isso garante que todo item de dado real seja consumido pelo estágio seguinte
**antes** do sinal de término chegar, sem necessidade de `Thread.stop()`,
`interrupt()` forçado ou temporizadores arbitrários.

## 3. Como compilar e executar

O projeto vem em duas formas equivalentes (mesma lógica, mesmos arquivos-fonte):

**a) Multi-arquivo** (`src/pipeline/*.java`, um arquivo por classe):

```bash
javac -d out src/pipeline/*.java
java -cp out pipeline.Pipeline [N] [capacidadeDaFila] [timeoutJoinMs]

# exemplo:
java -cp out pipeline.Pipeline 20 5 10000
```

**b) Arquivo único** (`PipelineApp.java`, todas as classes como *nested static
classes* dentro de uma única classe com o `main`) — mais simples de rodar:

```bash
# opção 1: compilar e rodar
javac PipelineApp.java
java PipelineApp [N] [capacidade] [timeoutMs]

# opção 2: rodar direto sem compilar manualmente (Java 11+, "source-launch")
java PipelineApp.java [N] [capacidade] [timeoutMs]

# exemplo:
java PipelineApp.java 20 5 10000
```

Em ambos os casos, `N` (itens), `capacidade` (tamanho de cada fila) e
`timeoutMs` (timeout do `join`) são opcionais — os padrões são 20, 5 e 10000.

## 4. Evidência e argumento de ausência de deadlock

**Argumento estrutural.** Deadlock clássico exige, entre outras condições, **espera
circular** (*circular wait*) entre threads que seguram um recurso e esperam por
outro. Neste projeto:

- Existem apenas dois locks (um por `BoundedQueue`).
- Nenhuma thread jamais adquire os dois locks simultaneamente: `ProcessingStage`
  chama `input.take()` (adquire e libera o lock da fila 1) e, **depois**, chama
  `output.put()` (adquire e libera o lock da fila 2) — nunca os dois ao mesmo tempo.
- Sem posse simultânea de dois recursos por uma mesma thread, **não há espera
  circular possível** entre as duas filas. Logo, deadlock está descartado por
  construção, independentemente da ordem de escalonamento do SO.

**Evidência empírica.** O `main` usa `Thread.join(timeoutMs)`: se qualquer thread
ficasse presa, `isAlive()` continuaria `true` após o timeout e o programa reportaria
falha em vez de travar. Testes realizados:

| Cenário                                   | N     | Capacidade da fila | Resultado      |
|--------------------------------------------|-------|---------------------|----------------|
| Caso normal                                 | 20    | 5                   | sucesso        |
| Caso mínimo                                 | 1     | 3                   | sucesso        |
| Alta contenção (fila quase sempre cheia/vazia) | 2000  | 1                   | sucesso        |
| Repetição de estabilidade (15 execuções seguidas) | 300 (cada) | 3           | 15/15 sucesso |

O cenário de capacidade 1 é o mais adverso: cada `put`/`take` força a fila a
alternar constantemente entre cheia e vazia, maximizando o número de vezes que as
threads efetivamente aguardam em `await()`/`signalAll()`. Mesmo assim, as três
threads sempre terminam.

Trecho real de log (`N=20`, capacidade 5), mostrando as três threads operando
concorrentemente e o encerramento em cascata do poison pill:

```
[Captura      ] item   1 capturado  (fila=1)
[Processamento] item   1 processado (fila_in=0, fila_out=0)
[Captura      ] item   2 capturado  (fila=1)
...
[Captura      ] poison pill enviado. Encerrando.
[Processamento] item  20 processado (fila_in=1, fila_out=1)
[Gravação     ] item  19 gravado    (fila=0)
[Processamento] poison pill recebido e repassado. Encerrando.
[Gravação     ] item  20 gravado    (fila=1)
[Gravação     ] poison pill recebido. Encerrando.

================ RELATÓRIO ================
Itens solicitados (N):           20
Itens capturados:                20
Itens processados:                20
Itens gravados:                   20
Tempo total de execução:          314 ms
Todas as threads terminaram:      true  (ausência de deadlock)
Contagens batem em todos estágios: true  (ausência de perda)
Todos os IDs 1..20 foram gravados: true
=============================================

SUCESSO: pipeline concluído, sem deadlock e sem perda de itens.
```

## 5. Evidência e argumento de ausência de perda de itens

**Argumento estrutural.**

- `BoundedQueue.put()` só retorna depois de efetivamente inserir o item no buffer;
  se a fila está cheia, a thread **bloqueia** em `notFull.await()` em vez de
  descartar o item. Não existe caminho de código que descarte um item silenciosamente.
- `BoundedQueue.take()` só remove um item que de fato está no buffer (dentro da
  seção crítica protegida pelo lock), então não há leitura duplicada nem "furo" na
  sequência.
- O poison pill nunca é contado como item de dado (`isPoisonPill()` é checado antes
  de qualquer contagem), então não contamina as métricas de N itens.

**Evidência empírica (tripla verificação, feita em `Pipeline.main`):**

1. Três contadores atômicos independentes (`AtomicInteger`) — um por estágio —
   devem todos ser exatamente igual a **N** ao final.
2. Um `BitSet` marca o **id** de cada item efetivamente gravado; ao final,
   `recordedIds.cardinality() == N` confirma que **todos os ids de 1 a N** (nem a
   mais, nem a menos, sem duplicatas) passaram pelo pipeline inteiro.
3. Execução repetida (15×, N=300, capacidade=3) sem nenhuma falha, incluindo o
   cenário de alta contenção (N=2000, capacidade=1).

Essas três checagens, tomadas em conjunto, descartam tanto perda quanto duplicação
de itens.

## 6. Conclusão

O pipeline atende a todos os requisitos do enunciado:

- Três threads (captura, processamento, gravação).
- Duas filas limitadas conectando os estágios, protegidas por mutex
  (`ReentrantLock`) + variável de condição (`Condition`), implementadas manualmente.
- Processamento de N itens configurável via argumento de linha de comando.
- Encerramento limpo via protocolo de poison pill, repassado estágio a estágio.
- Ausência de deadlock, garantida estruturalmente (nenhuma thread retém dois
  locks simultaneamente) e confirmada empiricamente (`join` com timeout + testes de
  estresse).
- Ausência de perda de itens, garantida estruturalmente (fila bloqueante sem
  descarte) e confirmada empiricamente (contadores + verificação de IDs via `BitSet`).
