import { verdictStyle } from "../lib/verdict.js";

const BANNER_HEADLINE = {
  PASS: "This label matches the application.",
  FLAG: "This label needs your review.",
  FAIL: "This label does not match the application.",
};

export default function VerdictBanner({ verdict, processingTimeMs }) {
  const style = verdictStyle(verdict);
  const headline = BANNER_HEADLINE[verdict] ?? verdict;

  return (
    <div className={`verdict-banner ${style.className}`}>
      <p className="verdict-banner__headline">{headline}</p>
      {typeof processingTimeMs === "number" && (
        <p className="verdict-banner__meta">Verified in {(processingTimeMs / 1000).toFixed(1)}s</p>
      )}
    </div>
  );
}
