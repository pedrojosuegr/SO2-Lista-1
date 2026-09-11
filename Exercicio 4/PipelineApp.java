import java.io.PrintStream;
import java.nio.charset.StandardCharsets;
import java.util.ArrayDeque;
import java.util.BitSet;
import java.util.Deque;
import java.util.concurrent.ThreadLocalRandom;
import java.util.concurrent.atomic.AtomicInteger;
import java.util.concurrent.locks.Condition;
import java.util.concurrent.locks.ReentrantLock;

public class PipelineApp {

    public static void main(String[] args) throws InterruptedException {

        System.setOut(new PrintStream(System.out, true, StandardCharsets.UTF_8));

        final int n = args.length > 0 ? Integer.parseInt(args[0]) : 20;
        final int capacity = args.length > 1 ? Integer.parseInt(args[1]) : 5;
        final long joinTimeoutMs = args.length > 2 ? Long.parseLong(args[2]) : 10_000;

        System.out.println("==============================================");
        System.out.println(" Pipeline: Captura -> Processamento -> Gravação");
        System.out.println(" N = " + n + " itens | capacidade de cada fila = " + capacity);
        System.out.println("==============================================\n");

        // ---- monta as duas filas limitadas (mutex + condição) ----
        BoundedQueue<Item> queue1 = new BoundedQueue<>(capacity, "captura->processamento");
        BoundedQueue<Item> queue2 = new BoundedQueue<>(capacity, "processamento->gravacao");

        // ---- contadores para validar ausência de perda ----
        AtomicInteger produced = new AtomicInteger(0);
        AtomicInteger processed = new AtomicInteger(0);
        AtomicInteger recorded = new AtomicInteger(0);
        BitSet recordedIds = new BitSet(n);

        // ---- cria as três threads do pipeline ----
        Thread captureThread = new Thread(new CaptureStage(queue1, n, produced), "Captura");
        Thread processingThread = new Thread(new ProcessingStage(queue1, queue2, processed), "Processamento");
        Thread recordingThread = new Thread(new RecordingStage(queue2, recorded, recordedIds), "Gravacao");

        long start = System.currentTimeMillis();

        captureThread.start();
        processingThread.start();
        recordingThread.start();

        // join() com timeout: se alguma thread travasse em deadlock, isAlive()
        // continuaria true após o timeout, evidenciando a falha em vez de
        // travar o programa para sempre.
        captureThread.join(joinTimeoutMs);
        processingThread.join(joinTimeoutMs);
        recordingThread.join(joinTimeoutMs);

        long elapsed = System.currentTimeMillis() - start;

        boolean noDeadlock = !captureThread.isAlive()
                && !processingThread.isAlive()
                && !recordingThread.isAlive();
        boolean noItemLoss = produced.get() == n
                && processed.get() == n
                && recorded.get() == n;
        boolean allIdsRecorded = recordedIds.cardinality() == n;

        System.out.println("\n================ RELATÓRIO ================");
        System.out.println("Itens solicitados (N):            " + n);
        System.out.println("Itens capturados:                 " + produced.get());
        System.out.println("Itens processados:                " + processed.get());
        System.out.println("Itens gravados:                   " + recorded.get());
        System.out.println("Tempo total de execução:          " + elapsed + " ms");
        System.out.println("Todas as threads terminaram:      " + noDeadlock + "  (ausência de deadlock)");
        System.out.println("Contagens batem em todos estágios: " + noItemLoss + "  (ausência de perda)");
        System.out.println("Todos os IDs 1.." + n + " foram gravados: " + allIdsRecorded);
        System.out.println("=============================================");

        if (noDeadlock && noItemLoss && allIdsRecorded) {
            System.out.println("\nSUCESSO: pipeline concluído, sem deadlock e sem perda de itens.");
        } else {
            System.out.println("\nFALHA: verifique os contadores acima.");
            System.exit(1);
        }
    }

    static final class Item {

        static final Item POISON_PILL = new Item(-1, null);

        private final int id;
        private final String rawData;
        private volatile String processedData;

        Item(int id, String rawData) {
            this.id = id;
            this.rawData = rawData;
        }

        boolean isPoisonPill() {
            return id == -1;
        }

        int getId() {
            return id;
        }

        void process() {
            this.processedData = rawData.toUpperCase() + "-PROCESSADO";
        }

        @Override
        public String toString() {
            return isPoisonPill() ? "Item{POISON_PILL}" : "Item{id=" + id + ", processed=" + processedData + "}";
        }

    }

    static final class BoundedQueue<T> {

        private final Deque<T> buffer = new ArrayDeque<>();
        private final int capacity;
        private final String name;
        private final ReentrantLock lock = new ReentrantLock();
        private final Condition notFull = lock.newCondition();
        private final Condition notEmpty = lock.newCondition();

        BoundedQueue(int capacity, String name) {
            if (capacity <= 0) {
                throw new IllegalArgumentException("capacity deve ser > 0");
            }
            this.capacity = capacity;
            this.name = name;
        }

        void put(T item) throws InterruptedException {
            lock.lock();
            try {
                while (buffer.size() == capacity) {
                    notFull.await(); // libera o mutex e dorme até haver espaço
                }
                buffer.addLast(item);
                notEmpty.signalAll(); // acorda quem espera para consumir
            } finally {
                lock.unlock();
            }
        }

        T take() throws InterruptedException {
            lock.lock();
            try {
                while (buffer.isEmpty()) {
                    notEmpty.await(); // libera o mutex e dorme até haver item
                }
                T item = buffer.removeFirst();
                notFull.signalAll(); // acorda quem espera para produzir
                return item;
            } finally {
                lock.unlock();
            }
        }

        int size() {
            lock.lock();
            try {
                return buffer.size();
            } finally {
                lock.unlock();
            }
        }

    }

    // Estágio 1: Captura — gera N itens e, ao final, envia o poison pill
    static final class CaptureStage implements Runnable {

        private final BoundedQueue<Item> output;
        private final int totalItems;
        private final AtomicInteger producedCount;

        CaptureStage(BoundedQueue<Item> output, int totalItems, AtomicInteger producedCount) {
            this.output = output;
            this.totalItems = totalItems;
            this.producedCount = producedCount;
        }

        @Override
        public void run() {
            try {
                for (int i = 1; i <= totalItems; i++) {
                    Item item = new Item(i, "dado-" + i);
                    output.put(item); // bloqueia se a fila estiver cheia
                    producedCount.incrementAndGet();
                    System.out.printf("[Captura      ] item %3d capturado  (fila=%d)%n", i, output.size());
                    Thread.sleep(ThreadLocalRandom.current().nextInt(0, 15));
                }
                output.put(Item.POISON_PILL);
                System.out.println("[Captura      ] poison pill enviado. Encerrando.");
            } catch (InterruptedException e) {
                Thread.currentThread().interrupt();
                System.out.println("[Captura      ] interrompida.");
            }
        }

    }

    // Estágio 2: Processamento — consome da fila 1, publica na fila 2, repassa o poison pill adiante quando ele chega
    static final class ProcessingStage implements Runnable {

        private final BoundedQueue<Item> input;
        private final BoundedQueue<Item> output;
        private final AtomicInteger processedCount;

        ProcessingStage(BoundedQueue<Item> input, BoundedQueue<Item> output, AtomicInteger processedCount) {
            this.input = input;
            this.output = output;
            this.processedCount = processedCount;
        }

        @Override
        public void run() {
            try {
                while (true) {
                    Item item = input.take(); // bloqueia se a fila estiver vazia

                    if (item.isPoisonPill()) {
                        output.put(item); // repassa o sinal de encerramento
                        System.out.println("[Processamento] poison pill recebido e repassado. Encerrando.");
                        break;
                    }

                    item.process();
                    processedCount.incrementAndGet();
                    System.out.printf("[Processamento] item %3d processado (fila_in=%d, fila_out=%d)%n",
                            item.getId(), input.size(), output.size());
                    Thread.sleep(ThreadLocalRandom.current().nextInt(0, 25));

                    output.put(item);
                }
            } catch (InterruptedException e) {
                Thread.currentThread().interrupt();
                System.out.println("[Processamento] interrompido.");
            }
        }

    }

    // Estágio 3: Gravação — consome da fila 2 e "grava" o item final; encerra ao ver o poison pill (é o último estágio)
    static final class RecordingStage implements Runnable {

        private final BoundedQueue<Item> input;
        private final AtomicInteger recordedCount;
        private final BitSet recordedIds;

        RecordingStage(BoundedQueue<Item> input, AtomicInteger recordedCount, BitSet recordedIds) {
            this.input = input;
            this.recordedCount = recordedCount;
            this.recordedIds = recordedIds;
        }

        @Override
        public void run() {
            try {
                while (true) {
                    Item item = input.take();

                    if (item.isPoisonPill()) {
                        System.out.println("[Gravação     ] poison pill recebido. Encerrando.");
                        break;
                    }

                    synchronized (recordedIds) {
                        recordedIds.set(item.getId() - 1);
                    }
                    recordedCount.incrementAndGet();
                    System.out.printf("[Gravação     ] item %3d gravado    (fila=%d)%n", item.getId(), input.size());
                    Thread.sleep(ThreadLocalRandom.current().nextInt(0, 10));
                }
            } catch (InterruptedException e) {
                Thread.currentThread().interrupt();
                System.out.println("[Gravação     ] interrompida.");
            }
        }

    }

}
