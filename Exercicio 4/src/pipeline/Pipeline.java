package pipeline;

import java.io.PrintStream;
import java.nio.charset.StandardCharsets;
import java.util.BitSet;
import java.util.concurrent.atomic.AtomicInteger;

/**
 * Monta a linha de processamento com três threads (captura, processamento,
 * gravação) conectadas por duas filas limitadas (bounded queues) protegidas
 * por mutex + variável de condição, processa N itens e finaliza com o
 * protocolo de poison pill, validando ao final ausência de deadlock e de
 * perda de itens.
 *
 * Uso: java pipeline.Pipeline [N] [capacidadeDasFilas] [timeoutMs]
 */
public class Pipeline {

    public static void main(String[] args) throws InterruptedException {
        // Garante saída em UTF-8 independentemente do locale do sistema
        // (evita "Gravação" virar "Grava??o" em ambientes com locale POSIX/C).
        System.setOut(new PrintStream(System.out, true, StandardCharsets.UTF_8));

        final int n = args.length > 0 ? Integer.parseInt(args[0]) : 20;
        final int capacity = args.length > 1 ? Integer.parseInt(args[1]) : 5;
        final long joinTimeoutMs = args.length > 2 ? Long.parseLong(args[2]) : 10_000;

        System.out.println("==============================================");
        System.out.println(" Pipeline: Captura -> Processamento -> Gravação");
        System.out.println(" N = " + n + " itens | capacidade de cada fila = " + capacity);
        System.out.println("==============================================\n");

        BoundedQueue<Item> queue1 = new BoundedQueue<>(capacity, "captura->processamento");
        BoundedQueue<Item> queue2 = new BoundedQueue<>(capacity, "processamento->gravacao");

        AtomicInteger produced = new AtomicInteger(0);
        AtomicInteger processed = new AtomicInteger(0);
        AtomicInteger recorded = new AtomicInteger(0);
        BitSet recordedIds = new BitSet(n);

        Thread captureThread = new Thread(
                new CaptureStage(queue1, n, produced), "Captura");
        Thread processingThread = new Thread(
                new ProcessingStage(queue1, queue2, processed), "Processamento");
        Thread recordingThread = new Thread(
                new RecordingStage(queue2, recorded, recordedIds), "Gravacao");

        long start = System.currentTimeMillis();

        captureThread.start();
        processingThread.start();
        recordingThread.start();

        // join() com timeout: se qualquer thread estivesse presa em deadlock,
        // isAlive() continuaria true após o timeout e o teste abaixo falharia
        // de forma visível, em vez de o programa travar para sempre.
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
        System.out.println("Itens solicitados (N):           " + n);
        System.out.println("Itens capturados:                " + produced.get());
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
}
