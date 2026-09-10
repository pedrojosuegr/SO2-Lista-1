# Relatório: Corrida de Cavalos com Threads

## 1. Objetivo

Simular uma corrida em que **cada cavalo é uma thread** independente, avançando em
passos aleatórios até cruzar a linha de chegada. O programa deve:

- pedir uma aposta ao usuário antes da largada;
- iniciar todas as threads em uma **largada sincronizada**;
- atualizar um placar compartilhado com **exclusão mútua**;
- ao final, anunciar o vencedor e informar se a aposta foi correta;
- garantir que **empates sejam resolvidos de forma determinística**;
- garantir que **não haja condição de corrida** ao registrar o primeiro colocado.

## 2. Estrutura geral do código

O arquivo `corrida.py` contém:

- **classe `Horse(threading.Thread)`**: cada instância é um cavalo/thread;
- **estruturas compartilhadas**: placar (`scoreboard`), registro de chegada
  (`finish_registry`) e seus respectivos locks;
- **`threading.Barrier`**: mecanismo de sincronização da largada;
- **`main()`**: lê a aposta, cria as threads, acompanha a corrida e exibe o resultado.

## 3. Largada sincronizada — `threading.Barrier`

```python
start_barrier = threading.Barrier(NUM_HORSES)
...
def run(self):
    self.start_barrier.wait()
    # corrida começa aqui
```

Uma `Barrier` é criada com o número exato de threads participantes (`NUM_HORSES`).
Cada thread, ao iniciar, chama `wait()` e **fica bloqueada** até que todas as
outras também cheguem a esse ponto. Só quando a última thread chama `wait()`,
a barreira libera **todas simultaneamente**. Isso evita o problema de um cavalo
começar a correr antes dos outros, mesmo que o sistema operacional escalone as
threads em momentos ligeiramente diferentes após o `.start()`.

## 4. Exclusão mútua no placar — `scoreboard_lock`

```python
with self.scoreboard_lock:
    self.position = min(self.position + step, self.finish_line)
    self.scoreboard[self.horse_id] = self.position
    crossed = self.position >= self.finish_line
```

O dicionário `scoreboard` é lido pela thread principal (para desenhar o placar
na tela) e escrito por todas as 6 threads dos cavalos ao mesmo tempo. Sem um
lock, duas threads poderiam escrever no dicionário simultaneamente e corromper
seu estado interno (condição de corrida clássica em estruturas mutáveis do
Python quando múltiplas operações não são atômicas). O `with self.scoreboard_lock:`
garante que cada atualização de posição seja uma **seção crítica atômica**.

## 5. Registro do primeiro colocado sem condição de corrida

Esta é a parte mais delicada do exercício. A solução:

```python
with self.finish_lock:
    arrival_order = len(self.finish_registry)
    self.finish_registry.append((arrival_order, self.horse_id, self.horse_name))
```

Pontos importantes:

- **Por que não há condição de corrida:** a leitura de `len(self.finish_registry)`
  e o `append()` subsequente acontecem dentro da mesma seção protegida por
  `finish_lock`. Isso significa que, mesmo que dois ou mais cavalos cruzem a
  linha de chegada "ao mesmo tempo" (em instantes de relógio muito próximos),
  o sistema operacional só permite que **uma thread por vez** execute esse
  bloco. Não existe cenário em que duas threads leiam o mesmo `len()` e
  gravem na mesma posição, nem cenário em que uma leitura fique "no meio" de
  uma escrita de outra thread.

- **Por que o empate é resolvido de forma determinística:** a ordem de chegada
  não é decidida por comparação de posições (`position`) nem por timestamps
  (que poderiam empatar por causa da resolução limitada do relógio). Ela é
  decidida pela **ordem de obtenção do lock**, e essa ordem é registrada de
  forma explícita e imutável em `arrival_order` no momento em que a thread
  entra na seção crítica. Ou seja, a primeira thread a conseguir o lock
  recebe `arrival_order = 0`, a segunda recebe `1`, e assim por diante — não
  há ambiguidade nem possibilidade de duas threads receberem o mesmo valor,
  pois a atribuição do índice acontece dentro do mesmo bloco protegido que
  faz o `append`.

- Ao final, a lista é ordenada por `arrival_order`:

  ```python
  finish_registry.sort(key=lambda entry: entry[0])
  ```

  Essa é a regra determinística de desempate: quem obteve o lock primeiro
  chegou primeiro. Como o próprio lock impede qualquer sobreposição, essa
  regra é sempre aplicável e nunca ambígua.

## 6. Fluxo da thread de cada cavalo (`Horse.run`)

1. Aguarda todos os cavalos ficarem prontos (`start_barrier.wait()`).
2. Em loop: sorteia um passo aleatório (`random.randint(1, 3)`), simula o
   tempo de corrida com `time.sleep(random.uniform(0.01, 0.05))` e atualiza sua
   posição no placar compartilhado (protegido por lock).
3. Quando a posição atinge ou ultrapassa `FINISH_LINE`, registra sua chegada
   na lista compartilhada (protegida por outro lock) e encerra a thread.

## 7. Thread principal (`main`)

1. Lê a aposta do usuário (`ler_aposta()`), validando a entrada.
2. Cria as estruturas compartilhadas e a barreira.
3. Cria e inicia as 6 threads `Horse`.
4. Enquanto houver threads vivas, redesenha o placar periodicamente
   (lendo o `scoreboard` sob o mesmo lock usado para escrevê-lo).
5. Aguarda todas as threads terminarem (`join()`).
6. Ordena `finish_registry` por `arrival_order`, exibe a colocação de todos
   os cavalos, anuncia o vencedor e informa se a aposta foi certeira.

## 8. Por que dois locks separados?

Foram usados **dois locks distintos** (`scoreboard_lock` e `finish_lock`) em
vez de um único lock global:

- `scoreboard_lock` protege atualizações de posição, que acontecem com alta
  frequência durante toda a corrida (a cada passo de cada cavalo).
- `finish_lock` protege apenas o registro de chegada, que acontece **uma
  única vez por cavalo**, no final de sua execução.

Separar os locks reduz a contenção: uma thread não precisa esperar pelo lock
de chegada só para atualizar sua posição no meio da corrida, e vice-versa.
Isso não afeta a corretude (cada lock protege sua própria seção crítica de
forma independente), apenas melhora o desempenho.

## 9. Testes realizados

O script foi executado múltiplas vezes de forma automatizada (fornecendo a
aposta via entrada padrão) para verificar:

- ausência de *deadlocks* ou travamentos;
- que a lista de chegada sempre contém exatamente 6 entradas, uma por
  cavalo, sem duplicidade nem omissão;
- que o vencedor anunciado corresponde sempre ao primeiro `arrival_order`;
- que o resultado da aposta (acerto/erro) é reportado corretamente.

Todas as execuções finalizaram corretamente, sem exceções relacionadas a
concorrência.

## 10. Como executar

```bash
python3 corrida.py
```

O programa pede o número do cavalo em que você deseja apostar (0 a 5),
executa a corrida com atualização do placar em tempo real no terminal e,
ao final, exibe a ordem de chegada completa e se sua aposta foi vencedora.
