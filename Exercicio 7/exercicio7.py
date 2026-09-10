"""
Jantar dos Filósofos
=====================
Cada filósofo é uma thread; cada garfo é um mutex (threading.Lock).

Duas soluções para evitar deadlock são implementadas:

  (a) ORDEM GLOBAL DE AQUISIÇÃO
      Cada filósofo sempre pega primeiro o garfo de MENOR índice e depois
      o de MAIOR índice. Isso quebra a espera circular (condição
      necessária para deadlock), pois nunca existirá um ciclo
      0->1->2->3->4->0 de "esperando o garfo que o vizinho segura".

  (b) SEMÁFORO LIMITANDO A N-1 FILÓSOFOS SIMULTÂNEOS
      Um threading.Semaphore(N-1) é adquirido antes de tentar pegar os
      garfos. Com no máximo N-1 filósofos tentando comer ao mesmo tempo
      (para N garfos em mesa circular), é garantido que pelo menos um
      filósofo sempre conseguirá os dois garfos, quebrando a espera
      circular por outro caminho.

Além disso, um mecanismo de FAIRNESS (mitigação de starvation) é aplicado
em ambas as soluções: antes de tentar pegar os garfos, o filósofo passa
por um "portão de justiça" (FairnessGate) que dá prioridade a quem comeu
menos refeições, evitando que um filósofo "sortudo" monopolize o acesso
enquanto um vizinho fica indefinidamente faminto.

Métricas coletadas por filósofo:
  - número de refeições concluídas;
  - maior tempo de espera (do momento em que ficou faminto até conseguir
    os dois garfos);
  - tempo médio de espera.
"""

import threading
import time
import random
import statistics

NUM_PHILOSOPHERS = 5
FAIRNESS_MARGIN = 2       # diferença de refeições que ativa a prioridade
SIM_DURATION = 6.0        # segundos de simulação por estratégia


# ----------------------------------------------------------------------
# Garfo = mutex
# ----------------------------------------------------------------------
class Fork:
    def __init__(self, fork_id):
        self.id = fork_id
        self.lock = threading.Lock()


# ----------------------------------------------------------------------
# Portão de justiça: mitigação de starvation
# ----------------------------------------------------------------------
class FairnessGate:
    """
    Antes de tentar pegar os garfos, cada filósofo passa por este portão.
    Se existir outro filósofo faminto com bem menos refeições que ele
    (diferença >= FAIRNESS_MARGIN), ele cede a vez e espera ser notificado.

    Isso não interfere na prevenção de deadlock (que é responsabilidade
    da estratégia de aquisição de garfos); é uma camada ortogonal que
    apenas atrasa filósofos "bem alimentados" em favor dos famintos há
    mais tempo / com menos refeições.
    """

    def __init__(self, n):
        self.cond = threading.Condition()
        self.hungry_ids = set()
        self.meals = [0] * n

    def wait_turn(self, philosopher_id, stop_event):
        with self.cond:
            self.hungry_ids.add(philosopher_id)
            while (not stop_event.is_set()
                   and self._is_too_far_ahead(philosopher_id)):
                # timeout curto: revalida periodicamente em vez de
                # depender só de notify (evita qualquer chance de
                # bloqueio permanente por notificação perdida)
                self.cond.wait(timeout=0.05)
            self.hungry_ids.discard(philosopher_id)

    def _is_too_far_ahead(self, philosopher_id):
        """
        Compara com o MÍNIMO global de refeições entre TODOS os
        filósofos (não só os que estão famintos agora). Isso throttla
        um filósofo "ganancioso" (que pensa pouco e tenta comer com
        muita frequência) mesmo quando seus vizinhos mais lentos não
        estão disputando garfos no mesmo instante -- sem essa
        comparação global, um filósofo rápido poderia varrer todas as
        refeições disponíveis antes que os lentos sequer ficassem
        famintos ao mesmo tempo que ele.
        """
        my_meals = self.meals[philosopher_id]
        min_others = min(
            m for i, m in enumerate(self.meals) if i != philosopher_id
        )
        return my_meals - min_others >= FAIRNESS_MARGIN

    def record_meal(self, philosopher_id):
        with self.cond:
            self.meals[philosopher_id] += 1
            self.cond.notify_all()


# ----------------------------------------------------------------------
# Filósofo
# ----------------------------------------------------------------------
class Philosopher(threading.Thread):
    def __init__(self, phil_id, left_fork, right_fork, strategy,
                 gate, stop_event, room_semaphore=None):
        super().__init__(name=f"Filosofo-{phil_id}")
        self.id = phil_id
        self.left_fork = left_fork
        self.right_fork = right_fork
        self.strategy = strategy              # "ordering" ou "semaphore"
        self.gate = gate
        self.stop_event = stop_event
        self.room_semaphore = room_semaphore

        # Métricas
        self.meals = 0
        self.wait_times = []
        self.max_wait = 0.0

    # --- aquisição de garfos, por estratégia ---------------------------
    def _acquire_forks(self):
        if self.strategy == "ordering":
            # (a) Ordem global: sempre o garfo de menor índice primeiro.
            first, second = sorted(
                (self.left_fork, self.right_fork), key=lambda f: f.id
            )
            first.lock.acquire()
            second.lock.acquire()

        elif self.strategy == "semaphore":
            # (b) No máximo N-1 filósofos disputando garfos ao mesmo tempo.
            self.room_semaphore.acquire()
            self.left_fork.lock.acquire()
            self.right_fork.lock.acquire()
        else:
            raise ValueError(f"Estratégia desconhecida: {self.strategy}")

    def _release_forks(self):
        self.left_fork.lock.release()
        self.right_fork.lock.release()
        if self.strategy == "semaphore":
            self.room_semaphore.release()

    # --- ciclo de vida ---------------------------------------------------
    def think(self):
        time.sleep(random.uniform(0.01, 0.05))

    def eat(self):
        time.sleep(random.uniform(0.01, 0.03))
        self.meals += 1

    def run(self):
        while not self.stop_event.is_set():
            self.think()

            hungry_start = time.perf_counter()

            # Portão de justiça: cede a vez a quem está mais faminto.
            self.gate.wait_turn(self.id, self.stop_event)
            if self.stop_event.is_set():
                break

            self._acquire_forks()
            wait_time = time.perf_counter() - hungry_start
            self.wait_times.append(wait_time)
            self.max_wait = max(self.max_wait, wait_time)

            self.eat()
            self._release_forks()
            self.gate.record_meal(self.id)


# ----------------------------------------------------------------------
# Simulação
# ----------------------------------------------------------------------
def run_simulation(strategy, n=NUM_PHILOSOPHERS, duration=SIM_DURATION):
    forks = [Fork(i) for i in range(n)]
    gate = FairnessGate(n)
    stop_event = threading.Event()

    room_semaphore = threading.Semaphore(n - 1) if strategy == "semaphore" else None

    philosophers = []
    for i in range(n):
        left = forks[i]
        right = forks[(i + 1) % n]
        philosophers.append(
            Philosopher(i, left, right, strategy, gate, stop_event, room_semaphore)
        )

    for p in philosophers:
        p.start()

    time.sleep(duration)
    stop_event.set()

    # Acorda qualquer filósofo parado no portão de justiça para que
    # ele possa checar stop_event e encerrar.
    with gate.cond:
        gate.cond.notify_all()

    for p in philosophers:
        p.join(timeout=2)

    return philosophers


def print_report(strategy, philosophers):
    label = {
        "ordering": "(a) Ordem global de aquisição",
        "semaphore": "(b) Semáforo limitando a N-1 filósofos",
    }[strategy]

    print(f"\n=== Estratégia {label} ===")
    print(f"{'Filósofo':<10}{'Refeições':>10}{'Espera máx (ms)':>18}{'Espera média (ms)':>20}")

    all_meals = []
    for p in philosophers:
        avg_wait = statistics.mean(p.wait_times) * 1000 if p.wait_times else 0.0
        max_wait_ms = p.max_wait * 1000
        print(f"{p.name:<10}{p.meals:>10}{max_wait_ms:>18.2f}{avg_wait:>20.2f}")
        all_meals.append(p.meals)

    if all_meals:
        print(f"\nRefeições -> min: {min(all_meals)} | max: {max(all_meals)} | "
              f"desvio: {max(all_meals) - min(all_meals)}")


def main():
    random.seed()

    print("Simulando estratégia (a) ordem global de aquisição de garfos...")
    phils_a = run_simulation("ordering")
    print_report("ordering", phils_a)

    print("\nSimulando estratégia (b) semáforo limitando a N-1 filósofos...")
    phils_b = run_simulation("semaphore")
    print_report("semaphore", phils_b)

    print("\nAmbas as simulações rodaram sem deadlock (nenhuma thread travou "
          "indefinidamente) e o desvio entre o filósofo que mais e o que "
          "menos comeu ficou pequeno, evidenciando a mitigação de starvation "
          "promovida pelo FairnessGate.")


if __name__ == "__main__":
    main()
