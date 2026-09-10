import argparse
import sys
import threading
import time
from collections import deque
from dataclasses import dataclass


class FilaConcorrente:
    def __init__(self):
        self._itens = deque()
        self._cond = threading.Condition(threading.Lock())
        self._fechada = False
        self.inseridos = 0
        self.removidos = 0

    def colocar(self, item):
        with self._cond:
            if self._fechada:
                raise RuntimeError("fila fechada: nao aceita novas tarefas")
            self._itens.append(item)
            self.inseridos += 1
            self._cond.notify()

    def retirar(self):
        with self._cond:
            while not self._itens and not self._fechada:
                self._cond.wait()
            if not self._itens:
                return None
            self.removidos += 1
            return self._itens.popleft()

    def fechar(self):
        with self._cond:
            self._fechada = True
            self._cond.notify_all()

    def __len__(self):
        with self._cond:
            return len(self._itens)


def eh_primo(n):
    if n < 2:
        return False
    if n < 4:
        return True
    if n % 2 == 0 or n % 3 == 0:
        return False
    i = 5
    while i * i <= n:
        if n % i == 0 or n % (i + 2) == 0:
            return False
        i += 6
    return True


def fibonacci(n):
    a, b = 0, 1
    for _ in range(n):
        a, b = b, a + b
    return a


OPERACOES = {"primo": eh_primo, "fib": fibonacci}


@dataclass(frozen=True)
class Tarefa:
    id: int
    operacao: str
    valor: int


def formatar(resultado):
    if isinstance(resultado, bool):
        return "primo" if resultado else "nao primo"
    texto = str(resultado)
    return texto if len(texto) <= 30 else f"<{len(texto)} digitos>"


class PoolDeThreads:
    def __init__(self, n_threads, silencioso=False):
        self.fila = FilaConcorrente()
        self.resultados = {}
        self.duplicadas = []
        self.por_worker = {}
        self.silencioso = silencioso
        self._lock_resultados = threading.Lock()
        self._lock_saida = threading.Lock()
        self.workers = [
            threading.Thread(target=self._executar, name=f"worker-{i}")
            for i in range(n_threads)
        ]
        for worker in self.workers:
            worker.start()

    def submeter(self, tarefa):
        self.fila.colocar(tarefa)

    def _executar(self):
        nome = threading.current_thread().name
        feitas = 0
        while True:
            tarefa = self.fila.retirar()
            if tarefa is None:
                break
            inicio = time.perf_counter()
            resultado = OPERACOES[tarefa.operacao](tarefa.valor)
            duracao = (time.perf_counter() - inicio) * 1000
            with self._lock_resultados:
                if tarefa.id in self.resultados:
                    self.duplicadas.append(tarefa.id)
                self.resultados[tarefa.id] = (tarefa, resultado, nome)
            feitas += 1
            if not self.silencioso:
                with self._lock_saida:
                    print(
                        f"[{nome}] tarefa #{tarefa.id} {tarefa.operacao}({tarefa.valor}) "
                        f"= {formatar(resultado)} ({duracao:.2f} ms)",
                        flush=True,
                    )
        with self._lock_resultados:
            self.por_worker[nome] = feitas

    def encerrar(self):
        self.fila.fechar()
        for worker in self.workers:
            worker.join()


def interpretar(linha):
    partes = linha.split()
    if len(partes) == 1:
        operacao, valor = "primo", partes[0]
    elif len(partes) == 2:
        operacao, valor = partes[0].lower(), partes[1]
    else:
        return None
    if operacao not in OPERACOES or not valor.isdigit():
        return None
    return operacao, int(valor)


def ler_tarefas(pool, entrada):
    total = 0
    rejeitadas = 0
    for numero_linha, linha in enumerate(entrada, 1):
        if not linha.strip():
            continue
        interpretada = interpretar(linha)
        if interpretada is None:
            print(f"linha {numero_linha} ignorada: {linha.strip()!r}", file=sys.stderr)
            rejeitadas += 1
            continue
        total += 1
        pool.submeter(Tarefa(total, *interpretada))
    return total, rejeitadas


def verificar(pool, total):
    assert pool.fila.inseridos == total, "quantidade inserida na fila difere da lida"
    assert pool.fila.removidos == total, "quantidade retirada da fila difere da inserida"
    assert len(pool.fila) == 0, "sobraram tarefas na fila"
    assert not pool.duplicadas, f"tarefas processadas mais de uma vez: {pool.duplicadas}"
    assert set(pool.resultados) == set(range(1, total + 1)), "ha tarefas perdidas"
    assert sum(pool.por_worker.values()) == total, "soma por worker difere do total"
    for tarefa, resultado, _ in pool.resultados.values():
        assert OPERACOES[tarefa.operacao](tarefa.valor) == resultado, f"resultado errado na tarefa {tarefa.id}"


def teste_fila(produtores, consumidores, itens_por_produtor):
    sys.setswitchinterval(1e-6)
    fila = FilaConcorrente()
    consumidos = [[] for _ in range(consumidores)]

    def produzir(p):
        for i in range(itens_por_produtor):
            fila.colocar((p, i))

    def consumir(c):
        while (item := fila.retirar()) is not None:
            consumidos[c].append(item)

    threads_c = [threading.Thread(target=consumir, args=(c,)) for c in range(consumidores)]
    threads_p = [threading.Thread(target=produzir, args=(p,)) for p in range(produtores)]
    inicio = time.perf_counter()
    for t in threads_c + threads_p:
        t.start()
    for t in threads_p:
        t.join()
    fila.fechar()
    for t in threads_c:
        t.join()
    decorrido = time.perf_counter() - inicio

    todos = [item for lista in consumidos for item in lista]
    esperado = {(p, i) for p in range(produtores) for i in range(itens_por_produtor)}
    print(f"Produtores: {produtores} | Consumidores: {consumidores} | Itens: {len(esperado)}")
    for c, lista in enumerate(consumidos):
        print(f"  consumidor-{c}: {len(lista)} itens")
    print(f"Tempo: {decorrido:.2f} s")
    assert len(todos) == len(esperado), f"esperado {len(esperado)} itens, consumidos {len(todos)}"
    assert set(todos) == esperado, "itens perdidos ou desconhecidos"
    for c, lista in enumerate(consumidos):
        for p in range(produtores):
            sequencia = [i for (origem, i) in lista if origem == p]
            assert sequencia == sorted(sequencia), f"ordem FIFO violada no consumidor {c}"
    print("OK: todos os itens foram consumidos exatamente uma vez e a ordem FIFO foi preservada.")


def main():
    parser = argparse.ArgumentParser(description="Pool fixo de threads com fila concorrente")
    parser.add_argument("threads", nargs="?", type=int, default=4)
    parser.add_argument("--silencioso", action="store_true")
    parser.add_argument("--teste-fila", action="store_true")
    parser.add_argument("--produtores", type=int, default=4)
    parser.add_argument("--itens", type=int, default=50000)
    args = parser.parse_args()
    sys.set_int_max_str_digits(0)

    if args.teste_fila:
        teste_fila(args.produtores, args.threads, args.itens)
        return

    if sys.stdin.isatty():
        print(
            f"Pool com {args.threads} threads. Digite tarefas ('primo N' ou 'fib N'), "
            "uma por linha. Finalize com EOF (Ctrl+Z e Enter no Windows, Ctrl+D no Linux).",
            flush=True,
        )

    pool = PoolDeThreads(args.threads, args.silencioso)
    inicio = time.perf_counter()
    total, rejeitadas = ler_tarefas(pool, sys.stdin)
    pool.encerrar()
    decorrido = time.perf_counter() - inicio

    print("\n===== Resumo =====")
    print(f"Threads no pool: {args.threads}")
    print(f"Tarefas lidas: {total} (linhas rejeitadas: {rejeitadas})")
    print(f"Inseridas na fila: {pool.fila.inseridos} | Retiradas da fila: {pool.fila.removidos}")
    print(f"Tarefas processadas: {len(pool.resultados)}")
    for nome in sorted(pool.por_worker):
        print(f"  {nome}: {pool.por_worker[nome]} tarefas")
    print(f"Tempo total: {decorrido:.3f} s")
    verificar(pool, total)
    print("Verificacao: OK - nenhuma tarefa perdida, nenhuma duplicada e todos os resultados conferem.")


if __name__ == "__main__":
    main()
