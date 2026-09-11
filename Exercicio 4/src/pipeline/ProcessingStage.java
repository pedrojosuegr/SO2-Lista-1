package pipeline;

import java.util.concurrent.atomic.AtomicInteger;
import java.util.concurrent.ThreadLocalRandom;

/**
 * Estágio 2: Processamento.
 * Consome itens da fila captura->processamento, transforma o dado e
 * publica o resultado na fila processamento->gravação.
 * Ao receber o poison pill, repassa-o adiante e encerra.
 */
public class ProcessingStage implements Runnable {

    private final BoundedQueue<Item> input;
    private final BoundedQueue<Item> output;
    private final AtomicInteger processedCount;

    public ProcessingStage(BoundedQueue<Item> input, BoundedQueue<Item> output, AtomicInteger processedCount) {
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
