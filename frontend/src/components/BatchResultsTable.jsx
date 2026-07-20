import VerdictChip from "./VerdictChip.jsx";
import { buildBatchResultsCsv } from "../lib/csvExport.js";

const STATUS_LABEL = {
  pending: "Pending",
  processing: "Processing…",
  done: "Done",
  failed: "Failed",
};

function downloadCsv(rows) {
  const csv = buildBatchResultsCsv(rows);
  const blob = new Blob([csv], { type: "text/csv;charset=utf-8;" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = "ttb-batch-results.csv";
  link.click();
  URL.revokeObjectURL(url);
}

export default function BatchResultsTable({ rows, isComplete }) {
  const doneCount = rows.filter((row) => row.status === "done" || row.status === "failed").length;

  return (
    <div className="batch-results">
      <div className="batch-results__header">
        <h2 className="section-heading">Results {isComplete ? "" : `(${doneCount}/${rows.length})`}</h2>
        <button
          type="button"
          className="export-button"
          onClick={() => downloadCsv(rows)}
          disabled={rows.length === 0}
        >
          Export CSV
        </button>
      </div>
      <table className="batch-results__table">
        <thead>
          <tr>
            <th>Row</th>
            <th>Filename</th>
            <th>Status</th>
            <th>Verdict</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.row}>
              <td>{row.row}</td>
              <td className="mono">{row.filename}</td>
              <td>
                <span className={`row-status row-status--${row.status}`}>
                  {STATUS_LABEL[row.status] ?? row.status}
                </span>
              </td>
              <td>
                {row.result && <VerdictChip verdict={row.result.overall_verdict} />}
                {row.status === "failed" && row.error && (
                  <span className="batch-results__row-error">{row.error}</span>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
