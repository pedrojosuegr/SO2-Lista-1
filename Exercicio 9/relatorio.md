# Relatório — Simulação de Corrida de Revezamento com Barreira (Java)

## 1. Enunciado

Modelar uma corrida de revezamento em que **K threads** representam uma equipe, e
todas precisam alcançar uma **barreira** para liberar a próxima "perna" da prova.
Usar `pthread_barrier_t` (ou implementar uma barreira com mutex/condvar) e registrar
quantas rodadas são concluídas por minuto sob diferentes tamanhos de equipe.

Como Java não possui `pthread_barrier_t` (esse é um recurso da API POSIX de C), a
barreira foi implementada manualmente com `ReentrantLock` (mutex) e `Condition`
(variável de condição) — o par de primitivas equivalente em Java ao `mutex`/`condvar`
citado no enunciado.

## 2. Modelagem

| Conceito da prova | Equivalente no código |
|---|---|
| Equipe de revezamento | Um grupo de `K` objetos `Thread` |
| Corredor da equipe | Uma `Thread` individual |
| "Perna" da prova | Um bloco de trabalho simulado (`Thread.sleep` com duração aleatória) executado por cada thread antes de chamar a barreira |
| Barreira que libera a próxima perna | `RelayBarrier.await()` — só retorna quando as K threads chamaram `await()` |
| Bastão passado adiante | A liberação simultânea de todas as threads pela última a chegar (a "última perna" da rodada) |

### 2.1 `RelayBarrier` — a barreira (mutex + condvar)

A classe implementa uma barreira **cíclica** (reutilizável) do zero:

- Um `ReentrantLock` protege um contador `count` de quantas threads ainda faltam
  chegar nesta rodada.
- Cada thread que chama `await()` decrementa `count`.
- Se a thread **não** for a última a chegar, ela dorme em um `Condition.await()`,
  liberando o lock, até ser acordada.
- Se a thread **for** a última (`count == 0`), ela executa uma ação opcional
  (`barrierAction`, usada aqui para contar a rodada concluída), reinicia o contador
  para a próxima geração e chama `signalAll()`, acordando todas as outras threads de
  uma vez — exatamente o comportamento de `pthread_barrier_wait()`.
- Um número de **geração** evita a condição de corrida clássica de barreiras
  cíclicas (uma thread lenta acordar já numa rodada seguinte por engano).

Esse é o comportamento que `pthread_barrier_t` oferece nativamente em C; em Java,
como não existe esse tipo na biblioteca padrão, ele foi reconstruído manualmente com
`Lock`/`Condition` (a alternativa que o próprio enunciado permite).

### 2.2 `RelayRace` — a simulação

Para cada tamanho de equipe `K` testado:

1. Cria-se uma `RelayBarrier` para `K` partes.
2. Sobem-se `K` threads. Cada uma, em loop, executa:
   - `Thread.sleep(tempo aleatório entre 10 e 40 ms)` — simula o tempo de corrida
     daquele atleta na perna atual;
   - `barrier.await()` — espera o resto da equipe terminar a perna.
3. A cada vez que a barreira "fecha" (todas as K threads chegaram), um contador
   atômico de rodadas é incrementado. Ao atingir **150 rodadas**, a simulação
   termina.
4. Mede-se o tempo total decorrido (`System.nanoTime()`) e calcula-se:

   `rodadas_por_minuto = (rodadas_concluídas / tempo_decorrido_s) * 60`

## 3. Como executar

```bash
javac RelayBarrier.java RelayRace.java
java RelayRace
```

## 4. Resultados obtidos

Execução real no ambiente de testes (150 rodadas por tamanho de equipe, perna
simulada entre 10 e 40 ms por thread):

| K (threads na equipe) | Rodadas concluídas | Tempo total (s) | Rodadas/minuto |
|---:|---:|---:|---:|
| 2  | 150 | 4.71 | 1911.8 |
| 4  | 150 | 5.19 | 1735.7 |
| 8  | 150 | 5.59 | 1610.5 |
| 16 | 150 | 5.80 | 1551.3 |
| 32 | 150 | 5.96 | 1510.8 |
| 64 | 150 | 6.03 | 1491.3 |

## 5. Análise

O throughput (rodadas por minuto) **cai conforme o tamanho da equipe (K) aumenta**,
apesar de todas as threads simularem o mesmo intervalo de tempo por perna (10–40 ms).
Isso acontece por dois motivos combinados, típicos de sincronização por barreira:

1. **Efeito do "corredor mais lento" (straggler effect):** numa barreira, a rodada só
   termina quando a **última** thread chega. Como o tempo de cada perna é sorteado
   aleatoriamente, quanto mais threads existem, maior a chance de que pelo menos uma
   delas sorteie um tempo próximo do máximo (40 ms) naquela rodada — isso é
   estatística de valores extremos (o máximo de K amostras aleatórias cresce com K).
   Ou seja, equipes maiores são, em média, "tão rápidas quanto seu atleta mais
   lento da rodada".
2. **Overhead de sincronização:** com mais threads competindo pelo mesmo
   `ReentrantLock`/`Condition`, o custo de contenção (lock, troca de contexto,
   `signalAll` acordando dezenas de threads) também cresce, ainda que seja um
   efeito secundário comparado ao straggler effect.

Em suma, a barreira garante a corretude (nenhuma equipe "passa o bastão" antes que
todos cheguem), mas o próprio ato de esperar pelo mais lento é o que limita o ganho
de desempenho ao aumentar o número de corredores — um comportamento análogo ao de
barreiras de sincronização em computação paralela real (ex.: MPI_Barrier, OpenMP
`#pragma omp barrier`).

## 6. Arquivos entregues

- `RelayBarrier.java` — implementação da barreira com mutex (`ReentrantLock`) e
  variável de condição (`Condition`).
- `RelayRace.java` — simulação da corrida de revezamento e coleta das métricas de
  rodadas por minuto para diferentes tamanhos de equipe.
