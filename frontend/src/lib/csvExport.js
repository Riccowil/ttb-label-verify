// Pure CSV serialization for the batch results table. No React, no DOM —
// download triggering lives in the component that calls this.

const FIELD_ORDER = ["brand_name", "class_type", "alcohol_content", "net_contents", "government_warning"];

const HEADER = [
  "row",
  "filename",
  "status",
  "overall_verdict",
  "processing_time_ms",
  ...FIELD_ORDER.map((field) => `${field}_verdict`),
  "error",
];

function escapeCsvValue(value) {
  const text = value === null || value === undefined ? "" : String(value);
  if (/[",\r\n]/.test(text)) {
    return `"${text.replace(/"/g, '""')}"`;
  }
  return text;
}

function toCsvRow(values) {
  return values.map(escapeCsvValue).join(",");
}

export function buildBatchResultsCsv(rows) {
  const lines = [toCsvRow(HEADER)];

  for (const row of rows) {
    const verdictByField = Object.fromEntries(
      (row.result?.fields ?? []).map((field) => [field.field, field.verdict])
    );
    lines.push(
      toCsvRow([
        row.row,
        row.filename,
        row.status,
        row.result?.overall_verdict ?? "",
        row.result?.processing_time_ms ?? "",
        ...FIELD_ORDER.map((field) => verdictByField[field] ?? ""),
        row.error ?? "",
      ])
    );
  }

  return lines.join("\r\n") + "\r\n";
}
