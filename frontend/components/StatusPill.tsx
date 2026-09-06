export function StatusPill({ value }: { value: string }) {
  const normalized = value.toLowerCase();
  const tone = normalized.includes("refund") || normalized.includes("resolved") || normalized.includes("approved")
    ? "positive"
    : normalized.includes("escalat") || normalized.includes("human")
      ? "warning"
      : normalized.includes("block") || normalized.includes("denied")
        ? "danger"
        : "neutral";
  return <span className={`pill pill--${tone}`}>{value.replaceAll("_", " ")}</span>;
}
