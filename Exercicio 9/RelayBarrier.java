import java.util.concurrent.locks.Condition;
import java.util.concurrent.locks.Lock;
import java.util.concurrent.locks.ReentrantLock;


public class RelayBarrier {

    private final int parties;          // K: número de threads (corredores) da equipe
    private final Runnable barrierAction;
    private final Lock mutex = new ReentrantLock();
    private final Condition condvar = mutex.newCondition();

    private int count;                  // quantas threads já chegaram nesta geração
    private int generation = 0;         // evita "acordar" threads da rodada errada

    public RelayBarrier(int parties, Runnable barrierAction) {
        if (parties <= 0) {
            throw new IllegalArgumentException("parties deve ser > 0");
        }
        this.parties = parties;
        this.barrierAction = barrierAction;
        this.count = parties;
    }

    public RelayBarrier(int parties) {
        this(parties, null);
    }

    public void await() throws InterruptedException {
        mutex.lock();
        try {
            int myGeneration = generation;
            count--;

            if (count == 0) {
                // Última thread a chegar: "fecha" a perna da prova.
                if (barrierAction != null) {
                    barrierAction.run();
                }
                // Prepara a próxima geração (próxima rodada) e libera todo mundo.
                count = parties;
                generation++;
                condvar.signalAll();
            } else {
                // Ainda faltam corredores chegarem: dorme na variável de condição.
                while (myGeneration == generation) {
                    condvar.await();
                }
            }
        } finally {
            mutex.unlock();
        }
    }
}
