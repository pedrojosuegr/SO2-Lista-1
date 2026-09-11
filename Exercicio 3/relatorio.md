# Relatório — Simulação de Transferências Bancárias Concorrentes

## 1. Objetivo

Este programa demonstra, na prática, o problema de **condição de corrida (race condition)** em programação concorrente e como resolvê-lo com **locks (mutex)**, evitando também o risco de **deadlock**.

Ele simula 8 threads realizando transferências aleatórias entre 10 contas bancárias, comparando duas versões:

- **Com trava** → correta, usa `threading.Lock`.
- **Sem trava** → incorreta (proposital), mostra a corrida acontecendo.

## 2. Parâmetros

| Constante | Valor | Descrição |
|---|---|---|
| `M_CONTAS` | 10 | Número de contas |
| `T_THREADS` | 8 | Número de threads |
| `TRANSFERENCIAS_POR_THREAD` | 2000 | Transferências por thread |
| `SALDO_INICIAL` | 1000 | Saldo inicial por conta |

## 3. Como funciona cada versão

### 3.1 Com trava (`transferir_com_trava`)

- Trava as duas contas envolvidas (origem e destino) antes de mexer nos saldos.
- Sempre trava primeiro a conta de **menor índice** (`sorted([origem, destino])`).
- Isso evita **deadlock**: se duas threads tentam travar as mesmas duas contas em ordem invertida, a ordenação garante que nunca haverá espera circular.
- A verificação de saldo suficiente também acontece **dentro** da seção travada, evitando inconsistência.

### 3.2 Sem trava (`transferir_sem_trava`)

- Lê o saldo, calcula o novo valor e escreve de volta **sem nenhuma proteção**.
- Entre a leitura e a escrita, outra thread pode alterar o mesmo saldo, causando **updates perdidos**.
- Resultado: a soma total de todos os saldos (que deveria ser sempre constante) pode ficar **diferente** do valor inicial.

## 4. Resultado esperado

- **Com trava:** soma inicial = soma final sempre → invariante preservado (validado com `assert`).
- **Sem trava:** a soma pode divergir, evidenciando a corrida (o efeito pode variar entre execuções, pois depende do escalonamento das threads).

## 5. Conceitos demonstrados

- Seção crítica e exclusão mútua (mutex)
- Condição de corrida (race condition) e *lost update*
- Deadlock e como evitá-lo por **ordenação de locks**
- Invariante de sistema (soma total constante)

## 6. Conclusão

O código mostra de forma clara por que sincronização é necessária em sistemas concorrentes: sem locks, dados compartilhados ficam vulneráveis a corrupção; com locks bem projetados (travando sempre na mesma ordem), é possível garantir corretude **sem** introduzir deadlock.