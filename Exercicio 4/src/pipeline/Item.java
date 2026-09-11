package pipeline;

public final class Item {

    /** Sentinela de encerramento. Qualquer item com id == -1 é o poison pill. */
    public static final Item POISON_PILL = new Item(-1, null);

    private final int id;
    private final String rawData;
    private volatile String processedData;
    private final long captureTimestamp;
    private volatile long processTimestamp;

    public Item(int id, String rawData) {
        this.id = id;
        this.rawData = rawData;
        this.captureTimestamp = System.nanoTime();
    }

    public boolean isPoisonPill() {
        return id == -1;
    }

    public int getId() {
        return id;
    }

    public String getRawData() {
        return rawData;
    }

    public String getProcessedData() {
        return processedData;
    }

    /** Simula o processamento do dado bruto capturado. */
    public void process() {
        this.processedData = rawData.toUpperCase() + "-PROCESSADO";
        this.processTimestamp = System.nanoTime();
    }

    public long getCaptureTimestamp() {
        return captureTimestamp;
    }

    public long getProcessTimestamp() {
        return processTimestamp;
    }

    @Override
    public String toString() {
        if (isPoisonPill()) {
            return "Item{POISON_PILL}";
        }
        return "Item{id=" + id + ", raw=" + rawData + ", processed=" + processedData + "}";
    }
}
