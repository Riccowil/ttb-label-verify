import { COPY } from "../copy.js";

export default function NeedsBetterImage({ imageUrl, issues }) {
  return (
    <div className="needs-better-image">
      {imageUrl && <img className="needs-better-image__thumb" src={imageUrl} alt="Uploaded label" />}
      <div className="needs-better-image__body">
        <p className="needs-better-image__message">{COPY.needsBetterImage}</p>
        {issues && issues.length > 0 && (
          <ul className="needs-better-image__issues">
            {issues.map((issue) => (
              <li key={issue}>{issue}</li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}
