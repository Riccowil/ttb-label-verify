export default function BatchUploadForm({ csvFile, imageFiles, onCsvSelected, onImagesSelected }) {
  return (
    <div className="batch-upload">
      <label className="form-field">
        <span className="form-field__label">CSV file</span>
        <input
          type="file"
          accept=".csv,text/csv"
          onChange={(event) => onCsvSelected(event.target.files?.[0] ?? null)}
        />
        {csvFile && <span className="batch-upload__filename">{csvFile.name}</span>}
      </label>

      <label className="form-field">
        <span className="form-field__label">Label images</span>
        <input
          type="file"
          accept="image/jpeg,image/png,image/webp"
          multiple
          onChange={(event) => onImagesSelected(Array.from(event.target.files ?? []))}
        />
        {imageFiles.length > 0 && (
          <span className="batch-upload__filename">{imageFiles.length} image(s) selected</span>
        )}
      </label>
    </div>
  );
}
