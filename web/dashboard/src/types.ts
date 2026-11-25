export interface Point {
  time: number; // milliseconds since the Unix epoch
  values: Record<string, number | null>;
}

export interface Parameter {
  name: string;
  unit: string | null;
  low: number | null;
  high: number | null;
}

export interface Definitions {
  parameters: Parameter[];
}

export interface Alarm {
  id: number;
  parameter: string;
  bound: "low" | "high";
  value: number;
  raisedAt: number;
  clearedAt: number | null;
}

export interface Command {
  id: number;
  name: string;
  args: Record<string, string | number>;
  status: string;
  error: number | null;
  sentAt: number;
}
