import VerdictChip from "./VerdictChip.jsx";
import WarningDiff from "./WarningDiff.jsx";
import { FIELD_LABELS } from "../copy.js";

export default function FieldRow({ field }) {
  const { field: fieldName, verdict, reason, evidence } = field;
  const isWarning = fieldName === "government_warning";
  const verdictModifier = verdict.toLowerCase().replace(/\s+/g, "-");

  return (
    <div className={`field-row field-row--${verdictModifier}`}>
      <div className="field-row__header">
        <span className="field-row__label">{FIELD_LABELS[fieldName] ?? fieldName}</span>
        <VerdictChip verdict={verdict} />
      </div>
      <p className="field-row__reason">{reason}</p>

      {isWarning && evidence.diff ? (
        <WarningDiff diff={evidence.diff} />
      ) : (
        <dl className="field-row__evidence">
          {evidence.application !== undefined && (
            <div className="field-row__evidence-item">
              <dt>Application</dt>
              <dd className="mono">{evidence.application ?? "—"}</dd>
            </div>
          )}
          {evidence.extracted !== undefined && (
            <div className="field-row__evidence-item">
              <dt>Label</dt>
              <dd className="mono">{evidence.extracted ?? "—"}</dd>
            </div>
          )}
          {typeof evidence.similarity === "number" && (
            <div className="field-row__evidence-item">
              <dt>Similarity</dt>
              <dd className="mono">{Math.round(evidence.similarity * 100)}%</dd>
            </div>
          )}
        </dl>
      )}
    </div>
  );
}
