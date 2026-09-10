import argparse
import random
import threading
import time


class Recurso:
    def __init__(self, id):
        self.id = id
        self.lock = threading.Lock()
        self.dono = None

    def __str__(self):
        return f"R{self.id}"


class Cenario:
    def __init__(self, n_threads, n_recursos, ordenado, limite_t, pausa, semente):
        self.recursos = [Recurso(i) for i in range(n_recursos)]
        self.ordenado = ordenado
        self.limite_t = limite_t
        self.pausa = pausa
        self.semente = semente
        self.parar = threading.Event()
        self.estado = threading.Lock()
        self.nomes = [f"T{i}" for i in range(n_threads)]
        self.segurando = {nome: [] for nome in self.nomes}
        self.esperando = {nome: None for nome in self.nomes}
        self.operacoes = {nome: 0 for nome in self.nomes}
        self.ultimo_progresso = {}
        self.relatorio = None
        self.instante_deteccao = None

    def adquirir(self, nome, recurso):
        with self.estado:
            self.esperando[nome] = recurso.id
        while not self.parar.is_set():
            if recurso.lock.acquire(timeout=0.05):
                with self.estado:
                    self.esperando[nome] = None
                    recurso.dono = nome
                    self.segurando[nome].append(recurso.id)
                return True
        with self.estado:
            self.esperando[nome] = None
        return False

    def liberar(self, nome, recurso):
        with self.estado:
            recurso.dono = None
            self.segurando[nome].remove(recurso.id)
        recurso.lock.release()

    def trabalhador(self, indice):
        nome = self.nomes[indice]
        rng = random.Random(None if self.semente is None else f"{self.semente}-{indice}")
        while not self.parar.is_set():
            ordem = rng.sample(range(len(self.recursos)), 2)
            if self.ordenado:
                ordem.sort()
            pegos = []
            completo = True
            for rid in ordem:
                recurso = self.recursos[rid]
                if not self.adquirir(nome, recurso):
                    completo = False
                    break
                pegos.append(recurso)
                time.sleep(rng.uniform(0, self.pausa))
            if completo:
                with self.estado:
                    self.operacoes[nome] += 1
                    self.ultimo_progresso[nome] = time.monotonic()
            for recurso in reversed(pegos):
                self.liberar(nome, recurso)

    def watchdog(self):
        intervalo = min(0.25, self.limite_t / 4)
        while not self.parar.wait(intervalo):
            agora = time.monotonic()
            with self.estado:
                parados = [n for n in self.nomes if agora - self.ultimo_progresso[n] >= self.limite_t]
                if parados:
                    self.relatorio = self.montar_relatorio(parados, agora)
                    self.instante_deteccao = agora
                    self.parar.set()
            if self.relatorio:
                print(self.relatorio, flush=True)
                return

    def grafo_espera(self):
        grafo = {}
        for nome in self.nomes:
            rid = self.esperando[nome]
            if rid is not None and self.recursos[rid].dono is not None:
                grafo[nome] = (rid, self.recursos[rid].dono)
        return grafo

    def encontrar_ciclo(self, grafo):
        for inicio in grafo:
            posicao = {}
            caminho = []
            atual = inicio
            while atual in grafo and atual not in posicao:
                posicao[atual] = len(caminho)
                caminho.append(atual)
                atual = grafo[atual][1]
            if atual in posicao:
                return caminho[posicao[atual]:]
        return None

    def montar_relatorio(self, parados, agora):
        linhas = [
            "",
            "!" * 70,
            f"WATCHDOG: {len(parados)} thread(s) sem progresso ha pelo menos {self.limite_t:.1f} s",
            "!" * 70,
            "Threads suspeitas:",
        ]
        for nome in parados:
            segura = ", ".join(f"R{r}" for r in self.segurando[nome]) or "nada"
            rid = self.esperando[nome]
            if rid is None:
                espera = "nada"
            else:
                espera = f"R{rid} (dono: {self.recursos[rid].dono or 'livre'})"
            linhas.append(
                f"  {nome}: parada ha {agora - self.ultimo_progresso[nome]:.2f} s | "
                f"segura [{segura}] | espera {espera} | operacoes concluidas: {self.operacoes[nome]}"
            )
        linhas.append("Recursos envolvidos:")
        for recurso in self.recursos:
            aguardando = [n for n in self.nomes if self.esperando[n] == recurso.id]
            if recurso.dono or aguardando:
                linhas.append(
                    f"  {recurso}: dono {recurso.dono or '-'} | aguardado por [{', '.join(aguardando) or '-'}]"
                )
        grafo = self.grafo_espera()
        ciclo = self.encontrar_ciclo(grafo)
        if ciclo:
            trecho = " ".join(f"{n} -(espera R{grafo[n][0]})->" for n in ciclo)
            linhas.append(f"Ciclo no grafo de espera (DEADLOCK): {trecho} {ciclo[0]}")
        else:
            linhas.append("Nenhum ciclo no grafo de espera: possivel starvation, nao deadlock.")
        linhas.append("!" * 70)
        return "\n".join(linhas)

    def executar(self, duracao):
        inicio = time.monotonic()
        for nome in self.nomes:
            self.ultimo_progresso[nome] = inicio
        threads = [
            threading.Thread(target=self.trabalhador, args=(i,), name=nome, daemon=True)
            for i, nome in enumerate(self.nomes)
        ]
        vigia = threading.Thread(target=self.watchdog, name="watchdog", daemon=True)
        for t in threads:
            t.start()
        vigia.start()
        self.parar.wait(duracao)
        fim = time.monotonic()
        self.parar.set()
        for t in threads:
            t.join()
        vigia.join()
        if self.instante_deteccao is not None:
            fim = self.instante_deteccao
        return {
            "deadlock": self.relatorio is not None,
            "tempo": fim - inicio,
            "operacoes": sum(self.operacoes.values()),
            "por_thread": dict(self.operacoes),
        }


NOMES_MODOS = {
    "deadlock": "ordem livre",
    "ordenado": "ordem total",
}


def rodar(modo, args, repeticao):
    ordenado = modo == "ordenado"
    semente = None if args.semente is None else args.semente + repeticao
    print(f"\n=== {NOMES_MODOS[modo]} ({'locks em ordem crescente de id' if ordenado else 'cada thread escolhe sua ordem'}) "
          f"| execucao {repeticao + 1} ===", flush=True)
    cenario = Cenario(args.threads, args.recursos, ordenado, args.T, args.pausa, semente)
    resultado = cenario.executar(args.duracao)
    resultado["modo"] = NOMES_MODOS[modo]
    if resultado["deadlock"]:
        print(f"Execucao interrompida pelo watchdog apos {resultado['tempo']:.2f} s.")
    else:
        print(f"Executou os {args.duracao:.1f} s sem alarme do watchdog.")
    print("Operacoes por thread: " + ", ".join(f"{n}={q}" for n, q in resultado["por_thread"].items()))
    return resultado


def imprimir_comparacao(resultados):
    print("\n" + "=" * 72)
    print("Comparacao dos comportamentos")
    print("=" * 72)
    print(f"{'Modo':<14}{'Execucao':>9}{'Deadlock':>10}{'Tempo (s)':>11}{'Operacoes':>11}{'Vazao (op/s)':>15}")
    for r in resultados:
        vazao = r["operacoes"] / r["tempo"] if r["tempo"] > 0 else 0
        print(f"{r['modo']:<14}{r['execucao']:>9}{'sim' if r['deadlock'] else 'nao':>10}"
              f"{r['tempo']:>11.2f}{r['operacoes']:>11}{vazao:>15.1f}")
    for modo in dict.fromkeys(r["modo"] for r in resultados):
        do_modo = [r for r in resultados if r["modo"] == modo]
        travados = sum(r["deadlock"] for r in do_modo)
        print(f"{modo}: deadlock em {travados} de {len(do_modo)} execucao(oes)")


def main():
    parser = argparse.ArgumentParser(description="Deadlock por ordem de locks, watchdog e correcao por ordem total")
    parser.add_argument("--modo", choices=["deadlock", "ordenado", "ambos"], default="ambos")
    parser.add_argument("--threads", type=int, default=5)
    parser.add_argument("--recursos", type=int, default=4)
    parser.add_argument("--T", type=float, default=2.0)
    parser.add_argument("--duracao", type=float, default=10.0)
    parser.add_argument("--pausa", type=float, default=0.01)
    parser.add_argument("--repeticoes", type=int, default=1)
    parser.add_argument("--semente", type=int, default=None)
    args = parser.parse_args()
    if args.recursos < 2:
        parser.error("sao necessarios pelo menos 2 recursos")

    print(f"Threads: {args.threads} | Recursos: {args.recursos} | T do watchdog: {args.T:.1f} s | "
          f"Duracao maxima: {args.duracao:.1f} s")
    modos = ["deadlock", "ordenado"] if args.modo == "ambos" else [args.modo]
    resultados = []
    for modo in modos:
        for repeticao in range(args.repeticoes):
            resultado = rodar(modo, args, repeticao)
            resultado["execucao"] = repeticao + 1
            resultados.append(resultado)
    imprimir_comparacao(resultados)


if __name__ == "__main__":
    main()
