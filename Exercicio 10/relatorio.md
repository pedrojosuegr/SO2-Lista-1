# Exercício 10 — Deadlock, watchdog e ordem total de travamento

## Enunciado

Programar um cenário com múltiplos recursos e threads que, propositalmente, podem se bloquear por adquirir locks em ordens distintas. Criar uma thread "watchdog" que detecta ausência de progresso por T segundos e emite um relatório dos recursos e threads suspeitos. Em seguida, corrigir adotando uma ordem total de travamento e comparar os comportamentos.

## Arquivo

| Arquivo | Conteúdo |
|---|---|
| `deadlock_watchdog.py` | Recursos, threads trabalhadoras, watchdog, detecção de ciclo e comparação dos dois modos |

## Como executar

Linguagem: Python 3 (testado no 3.14). Não há dependências externas.

```bash
python deadlock_watchdog.py
python deadlock_watchdog.py --repeticoes 3 --duracao 8
python deadlock_watchdog.py --modo deadlock --threads 3 --recursos 3 --T 1
```

| Parâmetro | Significado | Padrão |
|---|---|---|
| `--modo` | `deadlock` (ordem livre), `ordenado` (ordem total) ou `ambos` | `ambos` |
| `--threads` | Número de threads trabalhadoras | 5 |
| `--recursos` | Número de recursos (locks) | 4 |
| `--T` | Tempo em segundos sem progresso até o watchdog disparar | 2.0 |
| `--duracao` | Tempo máximo de cada execução, em segundos | 10.0 |
| `--pausa` | Tempo máximo, em segundos, que a thread espera entre pegar um lock e o próximo | 0.01 |
| `--repeticoes` | Quantas vezes rodar cada modo | 1 |
| `--semente` | Semente do gerador aleatório, para repetir exatamente a mesma execução | aleatória |

## Explicação do código

### `Recurso`

Cada recurso tem um `id`, um `threading.Lock` e o campo `dono`, que guarda o nome da thread que o está segurando. O `Lock` do Python não informa quem é o dono, por isso esse campo é mantido à parte. Ele é o que permite ao watchdog montar o relatório.

### `Cenario`

Guarda tudo o que é compartilhado em uma execução:

| Atributo | Conteúdo |
|---|---|
| `recursos` | Lista de recursos |
| `segurando[thread]` | Recursos que a thread está segurando agora |
| `esperando[thread]` | Recurso que a thread está tentando pegar (ou `None`) |
| `operacoes[thread]` | Quantas operações a thread já concluiu |
| `ultimo_progresso[thread]` | Momento da última operação concluída |
| `estado` | Trava que protege todos os campos acima |
| `parar` | `Event` usado para mandar todas as threads pararem |

Os locks dos recursos e a trava `estado` são coisas diferentes. Os primeiros são os recursos disputados, que podem causar deadlock. A trava `estado` só protege as informações de monitoramento e é sempre segurada por pouquíssimo tempo, sem pegar nenhum outro lock junto. Por isso ela nunca participa de um deadlock.

#### `adquirir(nome, recurso)`

1. Marca em `esperando` que a thread quer aquele recurso.
2. Tenta pegar o lock com `acquire(timeout=0.05)`, repetindo enquanto `parar` não estiver ligado.
3. Quando consegue, limpa `esperando`, marca a thread como `dono` e adiciona o recurso em `segurando`.

O timeout **não** resolve o deadlock: a thread não solta o que já está segurando e continua tentando para sempre. Ele existe só para que, depois que o watchdog der o alarme, a thread consiga perceber `parar` e encerrar. Em Python não é possível matar uma thread de fora, então sem isso o programa ficaria preso para sempre e não daria para executar o modo corrigido na sequência.

#### `liberar(nome, recurso)`

Limpa `dono` e remove o recurso de `segurando`, e só depois solta o lock.

#### `trabalhador(indice)`

É o laço de cada thread:

1. Sorteia dois recursos diferentes com `rng.sample`. O sorteio já vem em ordem aleatória.
2. **Modo ordem livre:** pega os recursos na ordem sorteada. Assim, uma thread pode pegar R1 e depois R3 enquanto outra pega R3 e depois R1.
3. **Modo ordem total:** ordena os ids (`ordem.sort()`) antes de pegar. Todas as threads passam a respeitar a mesma ordem crescente.
4. Depois de cada lock, espera um tempo aleatório entre 0 e `pausa`. Isso aumenta o intervalo em que a thread segura um recurso e espera outro, deixando o deadlock mais provável no modo livre.
5. Se conseguiu os dois recursos, conta uma operação e atualiza `ultimo_progresso`.
6. Solta os recursos na ordem inversa.

O trabalho feito pelas threads é idêntico nos dois modos. A única diferença é a linha `ordem.sort()`, então qualquer diferença de comportamento vem só da ordem de aquisição.

### `watchdog`

Roda em sua própria thread e acorda periodicamente (a cada `min(0.25, T/4)` segundos):

1. Com a trava `estado` adquirida, procura threads cujo `ultimo_progresso` tenha ficado T segundos ou mais para trás.
2. Se achar alguma, monta o relatório com `montar_relatorio` enquanto ainda segura a trava. Assim, o relatório mostra um retrato consistente de um único instante.
3. Registra o momento da detecção, liga `parar` para encerrar a execução e imprime o relatório.

O relatório tem três partes:

- **Threads suspeitas:** há quanto tempo cada uma está parada, o que está segurando, o que está esperando (e quem é o dono desse recurso) e quantas operações já concluiu.
- **Recursos envolvidos:** para cada recurso ocupado ou disputado, quem é o dono e quem está esperando por ele.
- **Ciclo no grafo de espera:** a confirmação de que é um deadlock (explicada abaixo).

### Detecção de ciclo (`grafo_espera` e `encontrar_ciclo`)

O grafo de espera tem uma aresta `A -> B` quando a thread A está esperando um recurso cujo dono é a thread B. Como cada thread espera no máximo um recurso por vez, cada nó tem no máximo uma aresta de saída. Então basta seguir as arestas a partir de cada thread: se o caminho voltar a uma thread já visitada, há um ciclo, e ele é o deadlock.

Um deadlock só acontece quando as quatro condições de Coffman aparecem juntas: exclusão mútua, posse e espera, ausência de preempção e espera circular. O ciclo no grafo é exatamente a espera circular. Se o watchdog disparar e não houver ciclo, o relatório avisa que se trata de starvation (uma thread muito tempo sem conseguir o recurso), e não de deadlock.

### `executar`, `rodar` e `imprimir_comparacao`

- `executar(duracao)` inicia as threads e o watchdog, espera até o watchdog ligar `parar` ou até acabar a `duracao`, e então encerra tudo com `join()`. Devolve se houve deadlock, o tempo total, o total de operações e as operações por thread.
- `rodar` executa um modo, com uma semente diferente a cada repetição, e imprime o resultado parcial.
- `imprimir_comparacao` monta a tabela final com tempo, operações e vazão (operações por segundo) de cada execução, e conta em quantas execuções de cada modo houve deadlock.

## Por que a ordem total resolve

Suponha que exista um ciclo `T1 -> T2 -> ... -> Tk -> T1`. Cada thread segura um recurso e espera outro de id **maior**, já que todas pegam os recursos em ordem crescente. Seguindo o ciclo, os ids teriam que ficar sempre maiores: `r1 < r2 < ... < rk < r1`, o que é impossível. Portanto, com ordem total a espera circular não pode existir, e sem ela não há deadlock.

## Resultados obtidos

Execução com os valores padrão (5 threads, 4 recursos, T = 2 s), 3 repetições de cada modo e duração máxima de 8 s.

### Relatório do watchdog (ordem livre, execução 3)

```
!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
WATCHDOG: 5 thread(s) sem progresso ha pelo menos 2.0 s
!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
Threads suspeitas:
  T0: parada ha 2.07 s | segura [R0] | espera R2 (dono: T2) | operacoes concluidas: 1
  T1: parada ha 2.08 s | segura [nada] | espera R2 (dono: T2) | operacoes concluidas: 1
  T2: parada ha 2.08 s | segura [R2] | espera R1 (dono: T3) | operacoes concluidas: 0
  T3: parada ha 2.08 s | segura [R1] | espera R0 (dono: T0) | operacoes concluidas: 0
  T4: parada ha 2.08 s | segura [nada] | espera R1 (dono: T3) | operacoes concluidas: 0
Recursos envolvidos:
  R0: dono T0 | aguardado por [T3]
  R1: dono T3 | aguardado por [T2, T4]
  R2: dono T2 | aguardado por [T0, T1]
Ciclo no grafo de espera (DEADLOCK): T0 -(espera R2)-> T2 -(espera R1)-> T3 -(espera R0)-> T0
!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
```

Leitura do relatório: T0, T2 e T3 formam o ciclo. T0 segura R0 e espera R2, T2 segura R2 e espera R1, e T3 segura R1 e espera R0. T1 e T4 não fazem parte do ciclo, mas também estão paradas porque esperam recursos presos nele. Mesmo sem culpa, elas ficam travadas junto.

### Comparação

```
Modo           Execucao  Deadlock  Tempo (s)  Operacoes   Vazao (op/s)
ordem livre           1       sim       2.08          5            2.4
ordem livre           2       sim       2.10          3            1.4
ordem livre           3       sim       2.08          4            1.9
ordem total           1       nao       8.01       1139          142.3
ordem total           2       nao       8.00       1172          146.4
ordem total           3       nao       8.00       1122          140.2
ordem livre: deadlock em 3 de 3 execucao(oes)
ordem total: deadlock em 0 de 3 execucao(oes)
```

Operações por thread no modo ordem total (execução 1): `T0=232, T1=223, T2=230, T3=227, T4=227`.

## Análise

- **Ordem livre:** o deadlock aconteceu em todas as execuções e quase imediatamente. O tempo registrado, pouco acima de 2 s, é praticamente só o T do watchdog, ou seja, o sistema travou logo depois de começar, depois de 0 a 5 operações. A partir daí nenhuma thread progride mais, nem mesmo as que não fazem parte do ciclo.
- **Ordem total:** nenhum alarme em 8 s, cerca de 1.100 operações por execução (aproximadamente 140 por segundo) e divisão equilibrada entre as threads, todas com algo entre 220 e 250 operações. Isso mostra que a correção não trocou o deadlock por starvation.
- **Custo da correção:** nenhum. As threads fazem o mesmo trabalho, só mudando a ordem em que pegam os locks. A exigência é que todo o código respeite a mesma ordem, o que em sistemas maiores precisa ser uma regra do projeto.
- **Watchdog:** detectar ausência de progresso funciona para qualquer tipo de travamento, mas sozinho não diz a causa. O grafo de espera completa o diagnóstico: com ciclo, é deadlock; sem ciclo, é starvation ou uma thread lenta.

## Conclusão

Adquirir locks em ordens diferentes cria espera circular, e com ela o deadlock. O watchdog identificou o problema em todas as execuções e mostrou exatamente quais threads e recursos formavam o ciclo. Impor uma ordem total de travamento elimina a espera circular, e com isso o deadlock deixa de ser possível, sem perda de desempenho e com as threads progredindo de forma equilibrada.
