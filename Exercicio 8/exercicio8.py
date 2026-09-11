import threading
import random
import time


def buffer_criar(capacidade, limite_backpressure):
    return {
        "capacidade": capacidade,
        # backpressure: produtores esperam mais cedo, antes do buffer encher
        # de fato, se a ocupacao ja passou do limite (sinal de consumo lento).
        "limite_backpressure": limite_backpressure,
        "itens": [],
        "cond": threading.Condition(),
        "ocupacao": [],
        "inicio": time.monotonic(),
    }


def registrar_ocupacao(buf):
    buf["ocupacao"].append((time.monotonic() - buf["inicio"], len(buf["itens"])))


def buffer_put(buf, item):
    with buf["cond"]:
        while len(buf["itens"]) >= buf["limite_backpressure"]:
            buf["cond"].wait()  # produtor aguarda: aplica backpressure
        buf["itens"].append(item)
        registrar_ocupacao(buf)
        buf["cond"].notify_all()


def buffer_get(buf):
    with buf["cond"]:
        while len(buf["itens"]) == 0:
            buf["cond"].wait()
        item = buf["itens"].pop(0)
        registrar_ocupacao(buf)
        buf["cond"].notify_all()
        return item


def produtor_com_rajadas(buf, n_itens, prob_rajada=0.1):
    i = 0
    while i < n_itens:
        if random.random() < prob_rajada:
            # rajada: varios itens em sequencia, quase sem pausa
            tamanho_rajada = random.randint(5, 15)
            for _ in range(min(tamanho_rajada, n_itens - i)):
                buffer_put(buf, f"item-{i}")
                i += 1
        else:
            buffer_put(buf, f"item-{i}")
            i += 1
        time.sleep(random.uniform(0.01, 0.05))  # ritmo normal


def consumidor_com_ociosidade(buf, n_itens, prob_ociosidade=0.05):
    for _ in range(n_itens):
        buffer_get(buf)
        if random.random() < prob_ociosidade:
            time.sleep(random.uniform(0.1, 0.3))  # periodo de ociosidade/lentidao
        else:
            time.sleep(random.uniform(0.01, 0.03))


def main():
    CAPACIDADE = 200
    LIMITE_BACKPRESSURE = 30
    N_ITENS = 300

    buf = buffer_criar(CAPACIDADE, LIMITE_BACKPRESSURE)
    t_prod = threading.Thread(target=produtor_com_rajadas, args=(buf, N_ITENS))
    t_cons = threading.Thread(target=consumidor_com_ociosidade, args=(buf, N_ITENS))

    t_prod.start()
    t_cons.start()
    t_prod.join()
    t_cons.join()

    ocupacoes = [tam for _, tam in buf["ocupacao"]]
    print(f"Amostras de ocupacao: {len(ocupacoes)}")
    print(
        f"Ocupacao maxima observada: {max(ocupacoes)} (limite de backpressure = {LIMITE_BACKPRESSURE})"
    )
    print(f"Ocupacao media: {sum(ocupacoes)/len(ocupacoes):.2f}")


if __name__ == "__main__":
    main()
