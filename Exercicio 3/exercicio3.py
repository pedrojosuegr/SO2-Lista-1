import random
import threading

M_CONTAS = 10
T_THREADS = 8
TRANSFERENCIAS_POR_THREAD = 2000
SALDO_INICIAL = 1000


def transferir_com_trava(saldos, locks, origem, destino, valor):
    # Trava as duas contas sempre na mesma ordem (menor indice primeiro)
    # para evitar deadlock por ordem cruzada de aquisicao.
    primeiro, segundo = sorted([origem, destino])
    with locks[primeiro]:
        with locks[segundo]:
            if saldos[origem] >= valor:
                saldos[origem] -= valor
                saldos[destino] += valor


def transferir_sem_trava(saldos, origem, destino, valor):
    # Sem exclusao mutua: read-modify-write nao atomico -> condicao de corrida
    if saldos[origem] >= valor:
        saldo_atual = saldos[origem]
        saldos[origem] = saldo_atual - valor
        saldos[destino] += valor


def rodar_experimento(com_trava):
    saldos = [SALDO_INICIAL] * M_CONTAS
    locks = [threading.Lock() for _ in range(M_CONTAS)]
    soma_inicial = sum(saldos)

    def trabalho():
        for _ in range(TRANSFERENCIAS_POR_THREAD):
            origem, destino = random.sample(range(M_CONTAS), 2)
            valor = random.randint(1, 50)
            if com_trava:
                transferir_com_trava(saldos, locks, origem, destino, valor)
            else:
                transferir_sem_trava(saldos, origem, destino, valor)

    threads = [threading.Thread(target=trabalho) for _ in range(T_THREADS)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    soma_final = sum(saldos)
    return soma_inicial, soma_final


if __name__ == "__main__":
    print("== Execucao COM trava (correta) ==")
    inicial, final = rodar_experimento(com_trava=True)
    print(f"Soma inicial: {inicial} | Soma final: {final}")
    assert inicial == final, "Invariante violado mesmo com trava!"
    print("Invariante mantido (soma global constante).\n")

    print("== Execucao SEM trava (incorreta, apenas demonstrativa) ==")
    inicial, final = rodar_experimento(com_trava=False)
    print(f"Soma inicial: {inicial} | Soma final: {final}")
    if inicial != final:
        print("Invariante VIOLADO como esperado: condicao de corrida evidenciada.")
    else:
        print(
            "Nenhuma corrida detectada nesta execucao (pode variar entre execucoes)."
        )