# Relatório: Jantar dos Filósofos

## 1. Objetivo

Implementar o algoritmo clássico do **jantar dos filósofos**, com garfos
representados por mutexes (`threading.Lock`), propondo **duas soluções**
para evitar deadlock:

- **(a)** ordem global de aquisição dos garfos;
- **(b)** semáforo limitando a N-1 filósofos simultâneos;

e, em ambas, coletar **métricas por filósofo** (número de refeições, maior
tempo de espera) e ajustar a lógica para **mitigar starvation**.

## 2. Modelagem

- `Fork`: um garfo, contendo um `threading.Lock`.
- `Philosopher(threading.Thread)`: cada filósofo é uma thread com um garfo
  à esquerda e um à direita (mesa circular de `N = 5` filósofos e `N = 5`
  garfos).
- `FairnessGate`: mecanismo transversal de justiça, usado pelas duas
  soluções, para evitar que um filósofo monopolize as refeições.

O ciclo de cada filósofo é: **pensar → ficar faminto → (portão de
justiça) → pegar os dois garfos → comer → devolver os garfos → repetir**.

## 3. O problema original (por que ele trava)

Na versão ingênua, cada filósofo pega primeiro o garfo à esquerda e depois
o da direita. Se **todos os 5** pegarem o garfo da esquerda ao mesmo
tempo, cada um fica esperando o garfo da direita, que está na mão do
vizinho — uma **espera circular** perfeita, e nenhum consegue avançar:
deadlock. As duas soluções abaixo eliminam essa espera circular por
caminhos diferentes.

## 4. Solução (a) — Ordem global de aquisição

```python
first, second = sorted((self.left_fork, self.right_fork), key=lambda f: f.id)
first.lock.acquire()
second.lock.acquire()
```

Em vez de "esquerda depois direita", cada filósofo sempre pega **o garfo
de menor índice primeiro**, independentemente de ser seu garfo esquerdo ou
direito. Como todos os filósofos obedecem à mesma ordem total (0 < 1 < 2
< 3 < 4), é **impossível** formar um ciclo de espera: o filósofo 4 (que
usa os garfos 4 e 0) precisa pegar o garfo 0 primeiro — o mesmo garfo que
o filósofo 0 também tenta pegar primeiro — quebrando exatamente o elo que
fechava o ciclo no cenário de deadlock. Essa é a clássica técnica de
**quebra de espera circular por hierarquia de recursos**.

**Vantagem:** simples, sem overhead de sincronização extra, sem
`sleep`/retry.
**Limitação:** por si só não impede starvation — um filósofo "rápido"
poderia, em tese, continuar conseguindo os garfos antes de um vizinho mais
lento repetidamente (mitigado pelo portão de justiça, seção 6).

## 5. Solução (b) — Semáforo limitando a N-1 filósofos

```python
room_semaphore = threading.Semaphore(N - 1)
...
room_semaphore.acquire()
self.left_fork.lock.acquire()
self.right_fork.lock.acquire()
...
# depois de comer e soltar os garfos:
room_semaphore.release()
```

Um semáforo contador é inicializado com `N - 1` (4, para 5 filósofos).
Isso significa que **no máximo 4 filósofos** podem estar simultaneamente
tentando pegar garfos; pelo menos um está obrigatoriamente "de fora"
(pensando ou esperando o semáforo). Com apenas 4 dos 5 concorrendo pelos
5 garfos, **sobra sempre pelo menos um garfo livre** para algum dos
concorrentes fechar seu par — não há como todos os concorrentes ficarem
mutuamente bloqueados, porque não é possível que 4 filósofos peguem 4
garfos distintos e todos os 4 fiquem esperando um 5º garfo que não está
sendo usado por ninguém de fora da disputa.

**Vantagem:** não exige nenhuma ordem especial de aquisição (pode manter
"esquerda depois direita"), fácil de entender.
**Limitação:** acrescenta uma sincronização extra (o semáforo) e, tal
qual a solução (a), não resolve starvation sozinho.

## 6. Mitigação de starvation — `FairnessGate`

Nenhuma das duas soluções acima garante, por si só, que todo filósofo
coma com frequência semelhante — ambas evitam **deadlock**, mas não
**starvation** (um filósofo indefinidamente preterido por vizinhos mais
"rápidos"). Para isso foi adicionado um portão comum às duas soluções:

```python
def _is_too_far_ahead(self, philosopher_id):
    my_meals = self.meals[philosopher_id]
    min_others = min(m for i, m in enumerate(self.meals) if i != philosopher_id)
    return my_meals - min_others >= FAIRNESS_MARGIN
```

Antes de tentar pegar os garfos, cada filósofo passa por
`FairnessGate.wait_turn()`. Se ele já comeu `FAIRNESS_MARGIN` refeições a
mais que o filósofo com **menos** refeições no momento (comparando contra
todos os outros, não só os famintos naquele instante), ele **cede a vez**
e fica bloqueado em um `Condition.wait(timeout=0.05)` — revalidado
periodicamente — até que os demais avancem em número de refeições.
Isso é o que se chama de **envelhecimento (aging)**: quanto mais um
filósofo fica para trás, mais prioridade implícita ele ganha, pois os
adiantados passam a ser barrados.

Importante: esse portão é **independente** do mecanismo de prevenção de
deadlock — ele só atrasa a entrada na disputa pelos garfos, nunda impede
que um filósofo who já está de posse de um garfo o solte incorretamente,
então não introduz nenhum novo risco de deadlock. E como o `wait()` usa
`timeout`, não há risco de bloqueio permanente por uma notificação
perdida.

### Evidência experimental

Um teste isolado (`FAIRNESS_MARGIN` desabilitado vs. ativo em 3), com um
filósofo artificialmente "ganancioso" (praticamente sem tempo de
"pensar"), mostrou o efeito do portão:

| Cenário                         | Refeições por filósofo   | Desvio (max−min) |
|----------------------------------|---------------------------|-------------------|
| Sem fairness gate                 | [86, 65, 66, 73, 60]      | 26                |
| Com fairness gate (margem = 3)    | [67, 64, 66, 67, 67]      | 3                 |

O filósofo ganancioso, que sem o portão comia visivelmente mais do que os
outros, passa a comer praticamente na mesma proporção que os demais
quando o portão está ativo.

## 7. Métricas coletadas

Para cada filósofo, o programa registra:

- **`meals`** — número de refeições concluídas durante a simulação;
- **`wait_times`** (lista) e **`max_wait`** — tempo entre "ficar faminto"
  (após pensar) e efetivamente conseguir os dois garfos; usado para
  calcular espera máxima e espera média.

Essas métricas são impressas ao final de cada simulação (`print_report`),
junto com o desvio entre o filósofo que mais comeu e o que menos comeu —
usado como indicador prático de ausência de starvation.

### Resultado de uma execução típica (5 filósofos, 6 segundos cada estratégia)

**Estratégia (a) — ordem global:**

| Filósofo | Refeições | Espera máx (ms) | Espera média (ms) |
|----------|-----------|------------------|--------------------|
| 0        | 93        | 66.57            | 14.76              |
| 1        | 94        | 57.43            | 13.46              |
| 2        | 94        | 66.37            | 15.24              |
| 3        | 94        | 59.05            | 12.33              |
| 4        | 94        | 94.89            | 14.31              |

Desvio entre refeições: **1**.

**Estratégia (b) — semáforo N-1:**

| Filósofo | Refeições | Espera máx (ms) | Espera média (ms) |
|----------|-----------|------------------|--------------------|
| 0        | 96        | 64.04            | 10.98              |
| 1        | 96        | 56.94            | 14.05              |
| 2        | 96        | 44.30            | 11.45              |
| 3        | 97        | 58.98            | 11.35              |
| 4        | 97        | 50.55            | 11.36              |

Desvio entre refeições: **1**.

Em ambas as estratégias, nenhuma thread travou (sem deadlock) e o desvio
de refeições entre filósofos ficou mínimo, confirmando que o
`FairnessGate` cumpre seu papel de mitigar starvation em conjunto com
qualquer uma das duas técnicas de prevenção de deadlock.

## 8. Como executar

```bash
python3 filosofos.py
```

O script roda automaticamente as duas estratégias em sequência (6
segundos cada, por padrão) e imprime a tabela de métricas de cada uma.
Os parâmetros `NUM_PHILOSOPHERS`, `FAIRNESS_MARGIN` e `SIM_DURATION`
podem ser ajustados no topo do arquivo.
