import { COPY } from "../copy.js";

function DiffSegment({ op }) {
  switch (op.op) {
    case "equal":
      return <span>{op.text} </span>;
    case "replace":
      return (
        <span>
          <span className="diff-wrong">{op.found}</span> <span className="diff-required">{op.expected}</span>{" "}
        </span>
      );
    case "delete":
      return (
        <span>
          <span className="diff-wrong">{op.expected}</span>{" "}
        </span>
      );
    case "insert":
      return (
        <span>
          <span className="diff-inserted">{op.found}</span>{" "}
        </span>
      );
    default:
      return null;
  }
}

export default function WarningDiff({ diff }) {
  if (!diff || diff.length === 0) {
    return null;
  }

  const hasChanges = diff.some((op) => op.op !== "equal");

  return (
    <div className="warning-diff">
      <p className="warning-diff__text mono">
        {diff.map((op, index) => (
          <DiffSegment key={index} op={op} />
        ))}
      </p>
      {hasChanges && <p className="warning-diff__legend">{COPY.diffLegend}</p>}
    </div>
  );
}
