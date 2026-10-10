export default function StatusBadge({ status }: { status: string | null }) {
  const s = status ?? "IN_PROGRESS";
  return <span className={`badge badge-${s.toLowerCase()}`}>{s.split("_").join(" ")}</span>;
}