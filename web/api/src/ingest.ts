export interface Reply {
  status: number;
  body: unknown;
}

/** The ingest service's internal HTTP interface. */
export interface Ingest {
  definitions(): Promise<Reply>;
  send(command: unknown): Promise<Reply>;
}

export function ingestClient(baseUrl: string): Ingest {
  async function call(path: string, init?: RequestInit): Promise<Reply> {
    const response = await fetch(new URL(path, baseUrl), {
      ...init,
      signal: AbortSignal.timeout(3000),
    });
    return { status: response.status, body: await response.json() };
  }

  return {
    definitions: () => call("/definitions"),
    send: (command) =>
      call("/commands", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify(command),
      }),
  };
}
