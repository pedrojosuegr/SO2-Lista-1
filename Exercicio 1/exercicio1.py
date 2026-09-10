"""
Corrida de Cavalos com Threads
================================
Cada cavalo é uma thread que avança em passos aleatórios até cruzar a
linha de chegada. A largada é sincronizada entre todas as threads, o
placar é atualizado com exclusão mútua e o primeiro colocado é
registrado sem condições de corrida, com empates resolvidos de forma
determinística.
"""

import threading
import random
import time

# ----------------------------------------------------------------------
# Configuração da corrida
# ----------------------------------------------------------------------
FINISH_LINE = 40          # distância da linha de chegada
NUM_HORSES = 6
HORSE_NAMES = ["Relâmpago", "Trovão", "Fúria", "Estrela", "Vento", "Sombra"]


class Horse(threading.Thread):
    """Representa um cavalo que corre em sua própria thread."""

    def __init__(self, horse_id, name, start_barrier,
                 scoreboard, scoreboard_lock,
                 finish_registry, finish_lock,
                 finish_line):
        super().__init__(name=name)
        self.horse_id = horse_id
        self.horse_name = name
        self.start_barrier = start_barrier

        # Estruturas compartilhadas entre todas as threads
        self.scoreboard = scoreboard              # dict {horse_id: posicao}
        self.scoreboard_lock = scoreboard_lock     # protege o placar
        self.finish_registry = finish_registry     # lista de chegada, em ordem
        self.finish_lock = finish_lock             # protege o registro de chegada

        self.finish_line = finish_line
        self.position = 0

    def run(self):
        # --- Largada sincronizada -----------------------------------
        # Todas as threads ficam bloqueadas aqui até que TODAS estejam
        # prontas; só então a corrida começa para todas ao mesmo tempo.
        self.start_barrier.wait()

        # --- Corrida: passos aleatórios até cruzar a linha ----------
        while True:
            step = random.randint(1, 3)
            time.sleep(random.uniform(0.01, 0.05))  # simula tempo de corrida

            with self.scoreboard_lock:
                self.position = min(self.position + step, self.finish_line)
                self.scoreboard[self.horse_id] = self.position
                crossed = self.position >= self.finish_line

            if crossed:
                # --- Registro do primeiro colocado, sem condição de corrida
                # O lock garante que apenas uma thread por vez consiga
                # inserir sua posição de chegada na lista. A ORDEM em que
                # as threads conseguem o lock é exatamente a ordem de
                # chegada registrada -- não há disputa não determinística
                # sobre "quem escreve por último", pois a escrita é atômica.
                with self.finish_lock:
                    arrival_order = len(self.finish_registry)
                    self.finish_registry.append(
                        (arrival_order, self.horse_id, self.horse_name)
                    )
                break


def render_scoreboard(scoreboard, names, lock, finish_line):
    """Imprime uma linha de placar (sobrescrevendo a anterior)."""
    with lock:
        parts = []
        for horse_id in sorted(scoreboard.keys()):
            pos = scoreboard[horse_id]
            bar = "#" * pos + "-" * (finish_line - pos)
            parts.append(f"{names[horse_id]:>10s} |{bar}|")
    print("\033[H\033[J", end="")  # limpa o terminal a cada atualização
    print("=== Corrida em andamento ===\n")
    print("\n".join(parts))


def ler_aposta():
    print("Cavalos disponíveis:")
    for i, name in enumerate(HORSE_NAMES):
        print(f"  {i}: {name}")

    while True:
        entrada = input(f"\nAposte no cavalo (0-{NUM_HORSES - 1}): ").strip()
        if entrada.isdigit() and 0 <= int(entrada) < NUM_HORSES:
            return int(entrada)
        print("Entrada inválida. Digite um número de cavalo válido.")


def main():
    print("=== Bem-vindo à Corrida de Cavalos ===\n")
    aposta = ler_aposta()

    # Estruturas compartilhadas
    scoreboard = {i: 0 for i in range(NUM_HORSES)}
    scoreboard_lock = threading.Lock()
    finish_registry = []          # preenchido em ordem de chegada
    finish_lock = threading.Lock()

    # Barreira: só libera quando todas as NUM_HORSES threads chegarem nela
    start_barrier = threading.Barrier(NUM_HORSES)

    horses = [
        Horse(i, HORSE_NAMES[i], start_barrier,
              scoreboard, scoreboard_lock,
              finish_registry, finish_lock,
              FINISH_LINE)
        for i in range(NUM_HORSES)
    ]

    print("\nCavalos na largada... prontos... já!\n")
    time.sleep(0.5)

    for h in horses:
        h.start()

    # Acompanha e imprime o placar enquanto a corrida ocorre
    while any(h.is_alive() for h in horses):
        render_scoreboard(scoreboard, HORSE_NAMES, scoreboard_lock, FINISH_LINE)
        time.sleep(0.1)

    for h in horses:
        h.join()

    render_scoreboard(scoreboard, HORSE_NAMES, scoreboard_lock, FINISH_LINE)

    # --- Resultado final -------------------------------------------
    # Ordena estritamente pela ordem de chegada (arrival_order), que é
    # única e determinística por construção (ver comentário no run()).
    finish_registry.sort(key=lambda entry: entry[0])

    _, winner_id, winner_name = finish_registry[0]

    print("\n=== Corrida encerrada! ===\n")
    print("Ordem de chegada:")
    for posicao, (_, hid, name) in enumerate(finish_registry, start=1):
        print(f"  {posicao}º lugar: {name}")

    print(f"\n🏆 Vencedor: {winner_name} (cavalo {winner_id})")

    if aposta == winner_id:
        print(f"✅ Você apostou em {HORSE_NAMES[aposta]} e ACERTOU! Parabéns!")
    else:
        print(f"❌ Você apostou em {HORSE_NAMES[aposta]}, mas o vencedor foi "
              f"{winner_name}. Não foi dessa vez.")


if __name__ == "__main__":
    main()
