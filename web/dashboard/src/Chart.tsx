import { useEffect, useRef, useState } from "react";
import uPlot from "uplot";
import "uplot/dist/uPlot.min.css";
import { column } from "./series";
import type { Parameter, Point } from "./types";

const HEIGHT = 220;
const clock = (seconds: number) => new Date(seconds * 1000).toLocaleTimeString("en-GB");

function useDarkMode() {
  const query = window.matchMedia("(prefers-color-scheme: dark)");
  const [dark, setDark] = useState(query.matches);
  useEffect(() => {
    const update = () => setDark(query.matches);
    query.addEventListener("change", update);
    return () => query.removeEventListener("change", update);
  }, []);
  return dark;
}

/** Dashed reference lines for the alarm limits that fall inside the plot. */
function limitLines(parameter: Parameter, color: string, text: string): uPlot.Plugin {
  return {
    hooks: {
      draw: (plot) => {
        const { ctx, bbox, scales } = plot;
        ctx.save();
        ctx.strokeStyle = color;
        ctx.fillStyle = text;
        ctx.lineWidth = devicePixelRatio;
        ctx.setLineDash([4 * devicePixelRatio, 4 * devicePixelRatio]);
        ctx.font = `${11 * devicePixelRatio}px system-ui, sans-serif`;
        ctx.textAlign = "left";
        ctx.textBaseline = "bottom";
        for (const [name, limit] of [["low", parameter.low], ["high", parameter.high]] as const) {
          if (limit === null || limit < scales.y.min! || limit > scales.y.max!) continue;
          const y = Math.round(plot.valToPos(limit, "y", true));
          ctx.beginPath();
          ctx.moveTo(bbox.left, y);
          ctx.lineTo(bbox.left + bbox.width, y);
          ctx.stroke();
          ctx.fillText(`${name} limit ${limit}`, bbox.left + 4 * devicePixelRatio, y - 2);
        }
        ctx.restore();
      },
    },
  };
}

interface Props {
  parameter: Parameter;
  title: string;
  points: Point[];
  /** The y axis always shows at least this range. */
  atLeast: [number, number];
}

export function Chart({ parameter, title, points, atLeast }: Props) {
  const element = useRef<HTMLDivElement>(null);
  const plot = useRef<uPlot>(null);
  const dark = useDarkMode();

  useEffect(() => {
    const node = element.current!;
    const css = getComputedStyle(node);
    const token = (name: string) => css.getPropertyValue(name).trim();
    const axis = {
      stroke: token("--text-muted"),
      grid: { stroke: token("--grid"), width: 1 },
      ticks: { stroke: token("--grid"), width: 1 },
    };
    const instance = new uPlot(
      {
        width: node.clientWidth,
        height: HEIGHT,
        scales: {
          y: {
            range: (_, min, max) => [
              Math.floor(Math.min(atLeast[0], min ?? atLeast[0])),
              Math.ceil(Math.max(atLeast[1], max ?? atLeast[1])),
            ],
          },
        },
        // 24-hour clock, as everywhere else on the page
        axes: [{ ...axis, values: (_, ticks) => ticks.map(clock) }, axis],
        series: [
          { label: "Time", value: (_, v) => (v === null ? "–" : clock(v)) },
          {
            label: `${title} (${parameter.unit})`,
            stroke: token("--series-1"),
            width: 2,
            points: { show: false },
            value: (_, v) => (v === null ? "–" : v.toFixed(2)),
          },
        ],
        plugins: [limitLines(parameter, token("--critical"), token("--text-secondary"))],
      },
      [[], []],
      node,
    );
    plot.current = instance;
    const resize = new ResizeObserver(() =>
      instance.setSize({ width: node.clientWidth, height: HEIGHT }),
    );
    resize.observe(node);
    return () => {
      resize.disconnect();
      instance.destroy();
    };
  }, [parameter, title, atLeast[0], atLeast[1], dark]);

  useEffect(() => {
    plot.current?.setData(column(points, parameter.name));
  }, [points, parameter, dark]);

  return (
    <section className="card">
      <h2>
        {title} <span className="muted">({parameter.unit}), last 2 minutes</span>
      </h2>
      <div ref={element} />
      <details>
        <summary>Latest values as a table</summary>
        <table>
          <thead>
            <tr>
              <th>Time</th>
              <th>
                {title} ({parameter.unit})
              </th>
            </tr>
          </thead>
          <tbody>
            {points
              .slice(-10)
              .reverse()
              .map((p) => (
                <tr key={p.time}>
                  <td>{new Date(p.time).toLocaleTimeString("en-GB")}</td>
                  <td>{p.values[parameter.name]?.toFixed(2) ?? "–"}</td>
                </tr>
              ))}
          </tbody>
        </table>
      </details>
    </section>
  );
}
