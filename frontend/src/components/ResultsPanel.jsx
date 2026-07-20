import VerdictBanner from "./VerdictBanner.jsx";
import FieldRow from "./FieldRow.jsx";
import NeedsBetterImage from "./NeedsBetterImage.jsx";
import "./ResultsPanel.css";

export default function ResultsPanel({ result, imageUrl }) {
  const isNeedsBetterImage = result.overall_verdict === "NEEDS BETTER IMAGE";

  if (isNeedsBetterImage) {
    return (
      <section className="results-panel" aria-label="Verification results">
        <NeedsBetterImage imageUrl={imageUrl} issues={result.image_quality?.issues} />
      </section>
    );
  }

  return (
    <section className="results-panel" aria-label="Verification results">
      <div className="results-panel__top">
        {imageUrl && <img className="results-panel__image" src={imageUrl} alt="Uploaded label" />}
        <VerdictBanner verdict={result.overall_verdict} processingTimeMs={result.processing_time_ms} />
      </div>
      <div className="results-panel__fields">
        {result.fields.map((field) => (
          <FieldRow key={field.field} field={field} />
        ))}
      </div>
    </section>
  );
}
