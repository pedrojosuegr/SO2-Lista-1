import java.util.ArrayList;
import java.util.List;
import java.util.Locale;
import java.util.concurrent.ThreadLocalRandom;
import java.util.concurrent.atomic.AtomicBoolean;
import java.util.concurrent.atomic.AtomicInteger;

public class RelayRace {

    // Quantidade de rodadas (pernas) a completar em cada medição.
    private static final int ROUNDS_PER_TEST = 150;

    // Faixa de duração simulada de uma "perna" individual (ms).
    private static final int LEG_MIN_MS = 10;
    private static final int LEG_MAX_MS = 40;

    // Tamanhos de equipe (K) a testar.
    private static final int[] TEAM_SIZES = {2, 4, 8, 16, 32, 64};

    public static void main(String[] args) throws InterruptedException {
        System.out.println("=== Simulação de corrida de revezamento com barreira (Java) ===");
        System.out.printf(Locale.US,
                "Rodadas por teste: %d | Duração da perna: %d-%dms por thread%n%n",
                ROUNDS_PER_TEST, LEG_MIN_MS, LEG_MAX_MS);

        List<double[]> results = new ArrayList<>(); // [K, rodadasPorMinuto, segundosTotais]

        for (int k : TEAM_SIZES) {
            double[] r = runTeam(k);
            results.add(r);
        }

        printReportTable(results);
    }

    /**
     * Executa a simulação para uma equipe de K threads e retorna
     * {K, rodadasPorMinuto, tempoTotalSegundos}.
     */
    private static double[] runTeam(int k) throws InterruptedException {
        AtomicInteger completedRounds = new AtomicInteger(0);
        AtomicBoolean finished = new AtomicBoolean(false);

        RelayBarrier barrier = new RelayBarrier(k, () -> {
            // Executado por uma única thread (a última a chegar) a cada rodada.
            int done = completedRounds.incrementAndGet();
            if (done >= ROUNDS_PER_TEST) {
                finished.set(true);
            }
        });

        Thread[] runners = new Thread[k];
        long start = System.nanoTime();

        for (int i = 0; i < k; i++) {
            final int runnerId = i;
            runners[i] = new Thread(() -> {
                ThreadLocalRandom rnd = ThreadLocalRandom.current();
                try {
                    while (!finished.get()) {
                        // Simula o tempo que o corredor leva para correr sua "perna".
                        int legTime = rnd.nextInt(LEG_MIN_MS, LEG_MAX_MS + 1);
                        Thread.sleep(legTime);
                        // Espera o resto da equipe chegar na barreira.
                        barrier.await();
                    }
                } catch (InterruptedException e) {
                    Thread.currentThread().interrupt();
                }
            }, "corredor-" + runnerId + "-equipe" + k);
            runners[i].start();
        }

        for (Thread t : runners) {
            t.join();
        }

        long elapsedNanos = System.nanoTime() - start;
        double elapsedSeconds = elapsedNanos / 1_000_000_000.0;
        double roundsPerMinute = (completedRounds.get() / elapsedSeconds) * 60.0;

        System.out.printf(Locale.US,
                "Equipe K=%-3d -> %d rodadas em %.2fs => %.1f rodadas/min%n",
                k, completedRounds.get(), elapsedSeconds, roundsPerMinute);

        return new double[]{k, roundsPerMinute, elapsedSeconds};
    }

    private static void printReportTable(List<double[]> results) {
        System.out.println();
        System.out.println("=== Resumo ===");
        System.out.printf(Locale.US, "%-6s | %-18s | %-12s%n", "K", "Rodadas/minuto", "Tempo (s)");
        System.out.println("-------|--------------------|-------------");
        for (double[] r : results) {
            System.out.printf(Locale.US, "%-6d | %-18.1f | %-12.2f%n", (int) r[0], r[1], r[2]);
        }
    }
}
