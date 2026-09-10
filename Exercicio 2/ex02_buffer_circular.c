#include <stdio.h>
#include <stdlib.h>
#include <pthread.h>
#include <unistd.h>
#include <time.h>
#include <sys/time.h>

#ifndef TAM_BUFFER
#define TAM_BUFFER 8
#endif
#define NUM_PRODUTORES 3
#define NUM_CONSUMIDORES 3
#define ITENS_POR_PRODUTOR 200

typedef struct {
    long timestamp_produzido_us;
} item_t;

static item_t buffer[TAM_BUFFER];
static int inicio = 0;
static int fim = 0;
static int contagem = 0;

static pthread_mutex_t mtx = PTHREAD_MUTEX_INITIALIZER;
static pthread_cond_t cv_nao_cheio = PTHREAD_COND_INITIALIZER;
static pthread_cond_t cv_nao_vazio = PTHREAD_COND_INITIALIZER;

static long total_produzido = 0;
static long total_consumido = 0;
static double soma_tempo_espera_us = 0.0;
static int produtores_ativos = NUM_PRODUTORES;

static long agora_us(void) {
    struct timeval tv;
    gettimeofday(&tv, NULL);
    return tv.tv_sec * 1000000L + tv.tv_usec;
}

void *produtor(void *arg) {
    unsigned int seed = (unsigned int)(long)arg;
    for (int i = 0; i < ITENS_POR_PRODUTOR; i++) {
        item_t novo;
        novo.timestamp_produzido_us = agora_us();

        pthread_mutex_lock(&mtx);
        while (contagem == TAM_BUFFER) {
            pthread_cond_wait(&cv_nao_cheio, &mtx);
        }
        buffer[fim] = novo;
        fim = (fim + 1) % TAM_BUFFER;
        contagem++;
        total_produzido++;
        pthread_cond_signal(&cv_nao_vazio);
        pthread_mutex_unlock(&mtx);

        usleep(rand_r(&seed) % 2000);
    }

    pthread_mutex_lock(&mtx);
    produtores_ativos--;
    if (produtores_ativos == 0) {
        pthread_cond_broadcast(&cv_nao_vazio);
    }
    pthread_mutex_unlock(&mtx);
    return NULL;
}

void *consumidor(void *arg) {
    unsigned int seed = (unsigned int)(long)arg;
    while (1) {
        pthread_mutex_lock(&mtx);
        while (contagem == 0 && produtores_ativos > 0) {
            pthread_cond_wait(&cv_nao_vazio, &mtx);
        }
        if (contagem == 0 && produtores_ativos == 0) {
            pthread_mutex_unlock(&mtx);
            break;
        }
        item_t item = buffer[inicio];
        inicio = (inicio + 1) % TAM_BUFFER;
        contagem--;
        total_consumido++;
        soma_tempo_espera_us += (double)(agora_us() - item.timestamp_produzido_us);
        pthread_cond_signal(&cv_nao_cheio);
        pthread_mutex_unlock(&mtx);

        usleep(rand_r(&seed) % 2500);
    }
    return NULL;
}

int main(void) {
    pthread_t prods[NUM_PRODUTORES];
    pthread_t cons[NUM_CONSUMIDORES];

    long inicio_us = agora_us();

    for (long i = 0; i < NUM_PRODUTORES; i++) {
        pthread_create(&prods[i], NULL, produtor, (void *)(i * 31 + 1));
    }
    for (long i = 0; i < NUM_CONSUMIDORES; i++) {
        pthread_create(&cons[i], NULL, consumidor, (void *)(i * 17 + 5));
    }

    for (int i = 0; i < NUM_PRODUTORES; i++) {
        pthread_join(prods[i], NULL);
    }
    for (int i = 0; i < NUM_CONSUMIDORES; i++) {
        pthread_join(cons[i], NULL);
    }

    long fim_us = agora_us();
    double duracao_s = (fim_us - inicio_us) / 1000000.0;

    printf("Buffer de tamanho %d\n", TAM_BUFFER);
    printf("Itens produzidos: %ld\n", total_produzido);
    printf("Itens consumidos: %ld\n", total_consumido);
    printf("Duracao total: %.3f s\n", duracao_s);
    printf("Throughput: %.2f itens/s\n", total_consumido / duracao_s);
    printf("Tempo medio de espera na fila: %.2f us\n",
           soma_tempo_espera_us / total_consumido);
    return 0;
}
