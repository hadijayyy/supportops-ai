import type { TraceEvent } from "@/lib/types";

export function ResolutionRail({ trace }: { trace: TraceEvent[] }) {
  if (!trace.length) {
    return <div className="rail-empty">Run a case to see evidence and actions move through the safety boundary.</div>;
  }
  return (
    <ol className="resolution-rail" aria-label="Resolution trace">
      {trace.map((event, index) => (
        <li className={`rail-step rail-step--${event.status}`} key={`${event.step}-${index}`}>
          <div className="rail-marker">{event.status === "completed" ? "✓" : event.status === "blocked" ? "×" : "!"}</div>
          <div className="rail-content">
            <div className="rail-heading">
              <span>{event.label}</span>
              {event.tool && <code>{event.tool}</code>}
            </div>
            {event.detail && <p>{event.detail}</p>}
            {event.output && Object.keys(event.output).length > 0 && (
              <details>
                <summary>Sanitized output</summary>
                <pre>{JSON.stringify(event.output, null, 2)}</pre>
              </details>
            )}
          </div>
        </li>
      ))}
    </ol>
  );
}
