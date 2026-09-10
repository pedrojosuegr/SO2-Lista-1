#include <stdio.h>
#include <stdlib.h>
#include <pthread.h>
#include <string.h>
#include <time.h>

#define TAM_HISTOGRAMA 10

typedef struct {
    long *dados;
    long inicio;
    long fim;
    long soma_parcial;
    long histograma_parcial[TAM_HISTOGRAMA];
} tarefa_thread_t;

void *mapear(void *arg) {
    tarefa_thread_t *t = (tarefa_thread_t *)arg;
    t->soma_parcial = 0;
    memset(t->histograma_parcial, 0, sizeof(t->histograma_parcial));
    for (long i = t->inicio; i < t->fim; i++) {
        long valor = t->dados[i];
        t->soma_parcial += valor;
        int indice = (int)(valor % TAM_HISTOGRAMA);
        if (indice < 0) indice += TAM_HISTOGRAMA;
        t->histograma_parcial[indice]++;
    }
    return NULL;
}

long carregar_arquivo(const char *caminho, long **out_dados) {
    FILE *f = fopen(caminho, "r");
    if (!f) {
        perror("fopen");
        exit(1);
    }
    long capacidade = 1024;
    long *dados = malloc(capacidade * sizeof(long));
    long n = 0;
    long valor;
    while (fscanf(f, "%ld", &valor) == 1) {
        if (n == capacidade) {
            capacidade *= 2;
            dados = realloc(dados, capacidade * sizeof(long));
        }
        dados[n++] = valor;
    }
    fclose(f);
    *out_dados = dados;
    return n;
}

double processar_paralelo(long *dados, long n, int p, long *soma_total, long *histograma_total) {
    pthread_t threads[p];
    tarefa_thread_t tarefas[p];

    struct timespec t0, t1;
    clock_gettime(CLOCK_MONOTONIC, &t0);

    long bloco = n / p;
    for (int i = 0; i < p; i++) {
        tarefas[i].dados = dados;
        tarefas[i].inicio = i * bloco;
        tarefas[i].fim = (i == p - 1) ? n : (i + 1) * bloco;
        pthread_create(&threads[i], NULL, mapear, &tarefas[i]);
    }

    *soma_total = 0;
    memset(histograma_total, 0, TAM_HISTOGRAMA * sizeof(long));

    for (int i = 0; i < p; i++) {
        pthread_join(threads[i], NULL);
        *soma_total += tarefas[i].soma_parcial;
        for (int h = 0; h < TAM_HISTOGRAMA; h++) {
            histograma_total[h] += tarefas[i].histograma_parcial[h];
        }
    }

    clock_gettime(CLOCK_MONOTONIC, &t1);
    return (t1.tv_sec - t0.tv_sec) + (t1.tv_nsec - t0.tv_nsec) / 1e9;
}

int main(int argc, char **argv) {
    if (argc < 2) {
        fprintf(stderr, "Uso: %s arquivo_de_inteiros.txt\n", argv[0]);
        return 1;
    }

    long *dados;
    long n = carregar_arquivo(argv[1], &dados);
    printf("Total de inteiros lidos: %ld\n", n);

    int niveis_p[] = {1, 2, 4, 8};
    double tempo_base = 0.0;

    for (int k = 0; k < 4; k++) {
        int p = niveis_p[k];
        long soma_total;
        long histograma_total[TAM_HISTOGRAMA];
        double tempo = processar_paralelo(dados, n, p, &soma_total, histograma_total);

        if (p == 1) tempo_base = tempo;

        printf("\nP = %d\n", p);
        printf("Soma total: %ld\n", soma_total);
        printf("Tempo: %.4f s\n", tempo);
        printf("Speedup vs P=1: %.2fx\n", tempo_base / tempo);
        printf("Histograma (valor mod %d): ", TAM_HISTOGRAMA);
        for (int h = 0; h < TAM_HISTOGRAMA; h++) {
            printf("%ld ", histograma_total[h]);
        }
        printf("\n");
    }

    free(dados);
    return 0;
}
