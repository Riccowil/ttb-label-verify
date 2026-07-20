import { verdictStyle } from "../lib/verdict.js";
import { COPY } from "../copy.js";

export default function VerdictChip({ verdict }) {
  const style = verdictStyle(verdict);
  const label = COPY.verdictChipLabel[verdict] ?? verdict;
  return <span className={`chip ${style.className}`}>{label}</span>;
}
