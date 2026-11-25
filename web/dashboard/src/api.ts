export async function get<T>(path: string): Promise<T> {
  const response = await fetch(path);
  if (!response.ok) throw new Error(`${path} answered ${response.status}`);
  return response.json();
}

/** Returns a message to show when the command was not accepted, otherwise null. */
export async function sendCommand(
  name: string,
  args: Record<string, string | number> = {},
): Promise<string | null> {
  try {
    const response = await fetch("/api/commands", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ name, args }),
    });
    if (response.ok) return null;
    if (response.status === 429) return "Too many commands. Wait a minute and try again.";
    const body = await response.json().catch(() => ({}));
    return `Command refused: ${body.error ?? response.status}`;
  } catch {
    return "Could not reach the server.";
  }
}
