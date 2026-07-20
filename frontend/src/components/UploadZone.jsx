import { useCallback, useRef, useState } from "react";
import { COPY } from "../copy.js";
import "./UploadZone.css";

export default function UploadZone({ previewUrl, onFileSelected, error }) {
  const inputRef = useRef(null);
  const [isDragOver, setIsDragOver] = useState(false);

  const handleFiles = useCallback(
    (fileList) => {
      const selected = fileList?.[0];
      if (selected) {
        onFileSelected(selected);
      }
    },
    [onFileSelected]
  );

  return (
    <div
      className={`upload-zone${isDragOver ? " upload-zone--active" : ""}${previewUrl ? " upload-zone--filled" : ""}`}
      onDragOver={(event) => {
        event.preventDefault();
        setIsDragOver(true);
      }}
      onDragLeave={() => setIsDragOver(false)}
      onDrop={(event) => {
        event.preventDefault();
        setIsDragOver(false);
        handleFiles(event.dataTransfer.files);
      }}
      onClick={() => inputRef.current?.click()}
      role="button"
      tabIndex={0}
      aria-label={COPY.uploadZone}
      onKeyDown={(event) => {
        if (event.key === "Enter" || event.key === " ") {
          event.preventDefault();
          inputRef.current?.click();
        }
      }}
    >
      <input
        ref={inputRef}
        type="file"
        accept="image/jpeg,image/png,image/webp"
        className="upload-zone__input"
        onChange={(event) => handleFiles(event.target.files)}
      />
      {previewUrl ? (
        <img src={previewUrl} alt="Selected label preview" className="upload-zone__preview" />
      ) : (
        <p className="upload-zone__prompt">{COPY.uploadZone}</p>
      )}
      {error && <p className="upload-zone__error">{error}</p>}
    </div>
  );
}
