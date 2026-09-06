export type Demo = {
  demo_id: number;
  label: string;
  prompt: string;
  customer: { id: string; name: string; tier: string; verified: number };
  order: { id: string; status: string; total: number };
};

export type Evidence = {
  document_id: string;
  title: string;
  version: string;
  category: string;
  effective_date: string;
  excerpt: string;
  score: number;
};

export type TraceEvent = {
  step: string;
  status: "completed" | "failed" | "escalated" | "blocked";
  label: string;
  detail?: string;
  tool?: string;
  input?: Record<string, unknown>;
  output?: Record<string, unknown>;
};

export type AgentResult = {
  run_id: string;
  conversation_id: string;
  intent: string;
  confidence: number;
  outcome: string;
  response: string;
  customer?: Record<string, unknown>;
  order?: Record<string, unknown>;
  shipment?: Record<string, unknown>;
  evidence: Evidence[];
  trace: TraceEvent[];
  risk_flags: string[];
  authorization: string;
  escalation: boolean;
  handoff?: {
    case_id: string;
    customer?: string;
    order?: string;
    reason: string;
    relevant_evidence: string[];
    actions_attempted: string[];
    recommended_next_step: string;
  };
  action_result?: Record<string, unknown>;
  latency_ms: number;
  usage: { input_tokens: number; output_tokens: number; estimated_cost: number };
};

export type Evaluation = {
  benchmark: string;
  generated_at: string;
  execution_mode: string;
  metrics: Record<string, number>;
  category_counts: Record<string, number>;
  result_count: number;
};
