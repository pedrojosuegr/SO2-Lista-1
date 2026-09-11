# Relatório — Buffer Produtor-Consumidor com Backpressure

## 1. Objetivo

Este programa demonstra o padrão **produtor-consumidor** usando um buffer compartilhado, sincronizado com `threading.Condition`. O destaque é o mecanismo de **backpressure**: o produtor é forçado a desacelerar quando o buffer atinge um limite de ocupação, mesmo antes de estar totalmente cheio — simulando um sinal de que o consumidor está processando devagar.

## 2. Parâmetros

| Constante | Valor | Descrição |
|---|---|---|
| `CAPACIDADE` | 200 | Capacidade máxima teórica do buffer |
| `LIMITE_BACKPRESSURE` | 30 | Ocupação a partir da qual o produtor passa a esperar |
| `N_ITENS` | 300 | Total de itens produzidos e consumidos |

## 3. Como funciona

### 3.1 Estrutura do buffer (`buffer_criar`)

- Guarda os itens em uma lista (`itens`), protegida por uma `threading.Condition` (`cond`).
- Registra amostras de ocupação ao longo do tempo (`ocupacao`), para análise posterior.

### 3.2 Produção (`buffer_put`)

- Antes de inserir, verifica se a ocupação já atingiu `limite_backpressure`.
- Se sim, o produtor **espera** (`cond.wait()`) — isso é o backpressure: ele para de produzir cedo, antes do buffer encher de verdade, dando tempo ao consumidor.
- Após inserir, notifica todas as threads esperando (`notify_all()`), pois tanto consumidores esperando item quanto produtores esperando espaço podem precisar acordar.

### 3.3 Consumo (`buffer_get`)

- Se o buffer está vazio, o consumidor espera (`cond.wait()`).
- Remove o item mais antigo (FIFO, `pop(0)`) e notifica as threads esperando.

### 3.4 Comportamento simulado das threads

- **Produtor com rajadas** (`produtor_com_rajadas`): na maior parte do tempo produz em ritmo constante, mas com 10% de chance inicia uma "rajada" de 5 a 15 itens seguidos, quase sem pausa — simulando picos de carga.
- **Consumidor com ociosidade** (`consumidor_com_ociosidade`): consome em ritmo normal, mas com 5% de chance entra em um período mais lento (0.1 a 0.3s de pausa) — simulando lentidão momentânea de processamento.

## 4. Resultado esperado

- A ocupação do buffer deve **oscilar em torno do limite de backpressure (30)**, sem disparar muito além dele — mesmo durante as rajadas do produtor, pois ele é freado assim que a ocupação atinge o limite.
- O programa imprime ao final: número de amostras de ocupação registradas, a ocupação máxima observada e a ocupação média — permitindo verificar se o backpressure realmente conteve o crescimento do buffer.

## 5. Conceitos demonstrados

- Padrão produtor-consumidor com buffer compartilhado
- Variável de condição (`threading.Condition`) para espera e notificação eficientes (em vez de *busy-waiting*)
- Backpressure como mecanismo de controle de fluxo entre produtor e consumidor
- Simulação de carga variável (rajadas) e desempenho variável (ociosidade) para testar a robustez da sincronização

## 6. Conclusão

O código evidencia como uma `Condition` permite coordenar produtores e consumidores sem polling ativo, e como um limite de backpressure evita que o buffer cresça descontroladamente mesmo diante de picos de produção, mantendo o sistema estável mesmo quando o consumo é irregular.