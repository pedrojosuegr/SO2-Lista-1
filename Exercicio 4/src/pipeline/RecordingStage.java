package pipeline;

import java.util.BitSet;
import java.util.concurrent.atomic.AtomicInteger;
import java.util.concurrent.ThreadLocalRandom;

/**
 * Estágio 3: Gravação.
 * Consome itens já processados da fila processamento->gravação e
 * "grava" o resultado final (aqui simulado). Ao receber o poison pill,
 * apenas encerra (é o último estágio, não há para quem repassar).
 *
 * Também marca, em uma BitSet compartilhada, o id de cada item gravado.
 * Isso permite, ao final da execução, verificar que TODOS os ids de
 * 1..N foram gravados exatamente uma vez — evidência direta de
 * ausência de perda (ou duplicação) de itens.
 */
public class RecordingStage implements Runnable {

    private final BoundedQueue<Item> input;
    private final AtomicInteger recordedCount;
    private final BitSet recordedIds;

    public RecordingStage(BoundedQueue<Item> input, AtomicInteger recordedCount, BitSet recordedIds) {
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
