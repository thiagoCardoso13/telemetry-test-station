import { useEffect, useState } from "react";
import { get } from "./api";
import { merge } from "./series";
import type { Alarm, Command, Definitions, Point } from "./types";

const RETRY_MS = 2000;
const STALE_MS = 3000;

export type Link = "connecting" | "live" | "stale";

/** Everything the page shows, kept up to date through the live connection. */
export function useStation() {
  const [definitions, setDefinitions] = useState<Definitions>();
  const [points, setPoints] = useState<Point[]>([]);
  const [alarms, setAlarms] = useState<Alarm[]>([]);
  const [commands, setCommands] = useState<Command[]>([]);
  const [counters, setCounters] = useState<Record<string, number>>({});
  const [link, setLink] = useState<Link>("connecting");

  useEffect(() => {
    let socket: WebSocket | undefined;
    let retry: number | undefined;
    let lastTelemetry = 0;
    let closed = false;

    // A failed read keeps what is on screen; the next refresh tries again.
    const load = <T>(path: string, apply: (value: T) => void) =>
      get<T>(path).then((value) => !closed && apply(value), () => {});
    const loadAlarms = () => load<Alarm[]>("/api/alarms", setAlarms);
    const loadCommands = () => load<Command[]>("/api/commands", setCommands);
    const loadCounters = () => load<Record<string, number>>("/api/link", setCounters);

    function connect() {
      const scheme = location.protocol === "https:" ? "wss" : "ws";
      socket = new WebSocket(`${scheme}://${location.host}/api/live`);
      // history is read after subscribing, so nothing falls between the two
      socket.onopen = () => {
        load<Definitions>("/api/definitions", setDefinitions);
        load<Point[]>("/api/telemetry?seconds=120", (history) =>
          setPoints((current) => merge(current, history)),
        );
        loadAlarms();
        loadCommands();
        loadCounters();
      };
      socket.onmessage = ({ data }) => {
        const notice = JSON.parse(data);
        if (notice.type === "telemetry") {
          lastTelemetry = Date.now();
          setLink("live");
          const point = { time: Date.parse(notice.time), values: notice.values };
          setPoints((current) => merge(current, [point]));
        } else if (notice.type === "alarm") loadAlarms();
        else if (notice.type === "command") loadCommands();
      };
      socket.onclose = () => {
        if (closed) return;
        setLink("connecting");
        retry = window.setTimeout(connect, RETRY_MS);
      };
    }

    connect();
    const clock = window.setInterval(() => {
      if (socket?.readyState !== WebSocket.OPEN) return;
      if (Date.now() - lastTelemetry > STALE_MS) setLink("stale");
      loadCounters();
    }, 2000);

    return () => {
      closed = true;
      window.clearTimeout(retry);
      window.clearInterval(clock);
      socket?.close();
    };
  }, []);

  return { definitions, points, alarms, commands, counters, link };
}
