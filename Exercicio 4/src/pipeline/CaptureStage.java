package pipeline;

import java.util.concurrent.atomic.AtomicInteger;
import java.util.concurrent.ThreadLocalRandom;

/**
 * Estágio 1: Captura.
 * Gera N itens e os publica na fila captura->processamento.
 * Ao final, publica o poison pill para sinalizar o fim do fluxo
 * ao próximo estágio.
 */
public class CaptureStage implements Runnable {

    private final BoundedQueue<Item> output;
    private final int totalItems;
    private final AtomicInteger producedCount;

    public CaptureStage(BoundedQueue<Item> output, int totalItems, AtomicInteger producedCount) {
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
