import pg from "pg";

/** The part of a WebSocket that broadcasting needs. */
export interface Client {
  readonly bufferedAmount: number;
  send(data: string): void;
}

// A browser this far behind is skipped until it catches up, so it cannot exhaust memory.
const MAX_BUFFERED_BYTES = 256 * 1024;
export const MAX_CLIENTS = 100;

export class Hub {
  private readonly clients = new Set<Client>();

  add(client: Client): boolean {
    if (this.clients.size >= MAX_CLIENTS) return false;
    this.clients.add(client);
    return true;
  }

  remove(client: Client): void {
    this.clients.delete(client);
  }

  broadcast(message: string): void {
    for (const client of this.clients) {
      if (client.bufferedAmount < MAX_BUFFERED_BYTES) client.send(message);
    }
  }
}

/** Forward the database notifications to the hub, reconnecting for as long as it runs. */
export function listen(url: string, hub: Hub, retryMs = 1000): () => Promise<void> {
  let current: pg.Client | undefined;
  let timer: NodeJS.Timeout | undefined;
  let stopped = false;

  async function connect(): Promise<void> {
    const client = new pg.Client({ connectionString: url });
    let lost = false;
    const retry = (error?: Error) => {
      if (lost || stopped) return;
      lost = true;
      if (error) console.warn(`lost the database listener: ${error.message}`);
      void client.end().catch(() => {});
      timer = setTimeout(() => void connect(), retryMs);
    };
    client.on("error", retry);
    client.on("end", () => retry());
    client.on("notification", (notice) => hub.broadcast(notice.payload ?? ""));
    current = client;
    try {
      await client.connect();
      await client.query("LISTEN station");
    } catch (error) {
      retry(error as Error);
    }
  }

  void connect();
  return async () => {
    stopped = true;
    clearTimeout(timer);
    await current?.end().catch(() => {});
  };
}
