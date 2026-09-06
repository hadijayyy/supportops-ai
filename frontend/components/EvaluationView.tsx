import type { Evaluation } from "@/lib/types";

const metricLabels: Record<string, string> = {
  task_success_rate: "Task success",
  groundedness: "Groundedness",
  tool_selection_accuracy: "Tool selection",
  retrieval_recall_at_3: "Retrieval recall@3",
  escalation_accuracy: "Escalation accuracy",
  hallucination_rate: "Hallucination rate",
};

export function EvaluationView({ evaluation }: { evaluation: Evaluation | null }) {
  if (!evaluation) return <div className="loading-panel">Evaluation artifact unavailable. Run <code>python -m evals.run</code>.</div>;
  const { metrics } = evaluation;
  return (
    <section className="evaluation-view">
      <div className="section-heading">
        <div><span className="eyebrow">Executed benchmark</span><h1>Reliability, measured.</h1></div>
        <div className="run-stamp">{metrics.cases_executed} cases<br/><span>{new Date(evaluation.generated_at).toLocaleDateString()}</span></div>
      </div>
      <div className="metric-grid">
        {Object.entries(metricLabels).map(([key, label]) => {
          const value = metrics[key] ?? 0;
          const success = key === "hallucination_rate" ? 1 - value : value;
          return (
            <article className="metric-card" key={key}>
              <div className="metric-value">{(value * 100).toFixed(value === 0 || value === 1 ? 0 : 1)}<span>%</span></div>
              <div className="metric-label">{label}</div>
              <div className="metric-track"><span style={{ width: `${success * 100}%` }} /></div>
            </article>
          );
        })}
      </div>
      <div className="eval-details">
        <article className="data-panel">
          <h2>Operational envelope</h2>
          <dl className="key-values">
            <div><dt>P50 latency</dt><dd>{metrics.p50_latency_ms.toFixed(2)} ms</dd></div>
            <div><dt>P95 latency</dt><dd>{metrics.p95_latency_ms.toFixed(2)} ms</dd></div>
            <div><dt>Avg. input tokens</dt><dd>{metrics.average_input_tokens}</dd></div>
            <div><dt>Avg. output tokens</dt><dd>{metrics.average_output_tokens}</dd></div>
            <div><dt>Estimated cost / case</dt><dd>${metrics.estimated_cost_per_case.toFixed(6)}</dd></div>
          </dl>
        </article>
        <article className="data-panel">
          <h2>Coverage by failure mode</h2>
          <div className="category-list">
            {Object.entries(evaluation.category_counts).map(([name, count]) => (
              <div key={name}><span>{name.replaceAll("_", " ")}</span><strong>{count}</strong></div>
            ))}
          </div>
        </article>
      </div>
      <p className="method-note">Results come from isolated execution against a freshly seeded database per case. This synthetic benchmark measures the defined operating envelope—not production generalization.</p>
    </section>
  );
}
