package pipeline;

import java.util.ArrayDeque;
import java.util.Deque;
import java.util.concurrent.locks.Condition;
import java.util.concurrent.locks.ReentrantLock;

public class BoundedQueue<T> {

    private final Deque<T> buffer = new ArrayDeque<>();
    private final int capacity;
    private final String name;

    private final ReentrantLock lock = new ReentrantLock();
    private final Condition notFull = lock.newCondition();
    private final Condition notEmpty = lock.newCondition();

    public BoundedQueue(int capacity, String name) {
        if (capacity <= 0) {
            throw new IllegalArgumentException("capacity deve ser > 0");
        }
        this.capacity = capacity;
        this.name = name;
    }

    /** Insere um item, bloqueando a thread chamadora enquanto a fila estiver cheia. */
    public void put(T item) throws InterruptedException {
        lock.lock();
        try {
            while (buffer.size() == capacity) {
                notFull.await(); // libera o mutex e dorme até haver espaço
            }
            buffer.addLast(item);
            // signalAll: acorda todos os consumidores potencialmente esperando,
            // evitando "lost wakeup" mesmo com múltiplos esperando na condição.
            notEmpty.signalAll();
        } finally {
            lock.unlock();
        }
    }

    /** Remove e retorna um item, bloqueando a thread chamadora enquanto a fila estiver vazia. */
    public T take() throws InterruptedException {
        lock.lock();
        try {
            while (buffer.isEmpty()) {
                notEmpty.await(); // libera o mutex e dorme até haver item
            }
            T item = buffer.removeFirst();
            notFull.signalAll();
            return item;
        } finally {
            lock.unlock();
        }
    }

    public int size() {
        lock.lock();
        try {
            return buffer.size();
        } finally {
            lock.unlock();
        }
    }

    public String getName() {
        return name;
    }
}
