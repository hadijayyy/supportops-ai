const nodes = [
  ["01", "Support console", "Case selection, conversation, evidence, trace"],
  ["02", "FastAPI boundary", "Validated requests and sanitized responses"],
  ["03", "Agent orchestrator", "Explicit state across six workflow nodes"],
  ["04", "Controlled capabilities", "Policy retrieval · typed tools · rules · escalation"],
  ["05", "Operational state", "PostgreSQL + pgvector production target"],
];

export function ArchitectureView() {
  return (
    <section className="architecture-view">
      <div className="section-heading"><div><span className="eyebrow">System architecture</span><h1>Language proposes. Rules dispose.</h1></div></div>
      <p className="architecture-intro">The model may classify ambiguous language. It cannot authorize money, invent an order, or override policy. Those boundaries live in deterministic code.</p>
      <div className="architecture-flow">
        {nodes.map(([index, title, detail], i) => (
          <article className="architecture-node" key={index}>
            <span>{index}</span><div><h2>{title}</h2><p>{detail}</p></div>{i < nodes.length - 1 && <i aria-hidden="true">↓</i>}
          </article>
        ))}
      </div>
      <div className="guardrail-band">
        <div><span>Financial boundary</span><strong>$250 auto-refund ceiling</strong></div>
        <div><span>Idempotency</span><strong>Duplicate refunds blocked</strong></div>
        <div><span>Untrusted context</span><strong>Retrieved text cannot instruct tools</strong></div>
        <div><span>Unsafe outcome</span><strong>Structured human handoff</strong></div>
      </div>
    </section>
  );
}
