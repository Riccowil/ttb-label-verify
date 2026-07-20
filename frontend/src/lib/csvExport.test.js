import { describe, expect, it } from "vitest";
import { buildBatchResultsCsv } from "./csvExport.js";

const HEADER =
  "row,filename,status,overall_verdict,processing_time_ms," +
  "brand_name_verdict,class_type_verdict,alcohol_content_verdict,net_contents_verdict,government_warning_verdict," +
  "error";

describe("buildBatchResultsCsv", () => {
  it("returns just the header for an empty batch", () => {
    expect(buildBatchResultsCsv([])).toBe(HEADER + "\r\n");
  });

  it("flattens a done row's per-field verdicts into columns", () => {
    const rows = [
      {
        row: 1,
        filename: "t1.png",
        status: "done",
        error: null,
        result: {
          overall_verdict: "PASS",
          processing_time_ms: 2646,
          fields: [
            { field: "brand_name", verdict: "PASS" },
            { field: "class_type", verdict: "PASS" },
            { field: "alcohol_content", verdict: "PASS" },
            { field: "net_contents", verdict: "PASS" },
            { field: "government_warning", verdict: "PASS" },
          ],
        },
      },
    ];

    const csv = buildBatchResultsCsv(rows);
    const lines = csv.trim().split("\r\n");
    expect(lines[0]).toBe(HEADER);
    expect(lines[1]).toBe("1,t1.png,done,PASS,2646,PASS,PASS,PASS,PASS,PASS,");
  });

  it("leaves verdict columns empty and includes the error message for a failed row", () => {
    const rows = [
      { row: 2, filename: "t2.png", status: "failed", error: "Verification took too long. Please try again.", result: null },
    ];

    const csv = buildBatchResultsCsv(rows);
    const lines = csv.trim().split("\r\n");
    expect(lines[1]).toBe(
      "2,t2.png,failed,,,,,,,,Verification took too long. Please try again."
    );
  });

  it("quotes values containing commas or quotes", () => {
    const rows = [
      {
        row: 3,
        filename: 'weird,"name.png',
        status: "done",
        error: null,
        result: { overall_verdict: "FAIL", processing_time_ms: 100, fields: [] },
      },
    ];

    const csv = buildBatchResultsCsv(rows);
    const lines = csv.trim().split("\r\n");
    expect(lines[1]).toContain('"weird,""name.png"');
  });
});
