import { useEffect, useState } from "react";
import BatchUploadForm from "./BatchUploadForm.jsx";
import BatchValidationErrors from "./BatchValidationErrors.jsx";
import BatchResultsTable from "./BatchResultsTable.jsx";
import ErrorPanel from "./ErrorPanel.jsx";
import { submitBatch, getBatchStatus, ApiError } from "../api.js";
import { COPY } from "../copy.js";
import "./BatchTab.css";

const POLL_INTERVAL_MS = 1200;

export default function BatchTab() {
  const [csvFile, setCsvFile] = useState(null);
  const [imageFiles, setImageFiles] = useState([]);
  const [status, setStatus] = useState("idle"); // idle | submitting | polling | done | error
  const [batchId, setBatchId] = useState(null);
  const [rows, setRows] = useState([]);
  const [validationError, setValidationError] = useState(null);
  const [errorMessage, setErrorMessage] = useState(null);

  const isSubmittable = Boolean(csvFile) && imageFiles.length > 0 && status !== "submitting";

  async function handleSubmit(event) {
    event.preventDefault();
    if (!isSubmittable) return;

    setStatus("submitting");
    setValidationError(null);
    setErrorMessage(null);
    setRows([]);

    try {
      const { batch_id } = await submitBatch(csvFile, imageFiles);
      setBatchId(batch_id);
      setStatus("polling");
    } catch (err) {
      if (err instanceof ApiError && err.detail && typeof err.detail === "object") {
        setValidationError(err.detail);
      } else {
        setErrorMessage(err instanceof ApiError ? err.message : COPY.genericError);
      }
      setStatus("error");
    }
  }

  useEffect(() => {
    if (status !== "polling" || !batchId) {
      return undefined;
    }

    let cancelled = false;

    const poll = async () => {
      try {
        const data = await getBatchStatus(batchId);
        if (cancelled) return;
        setRows(data.rows);
        if (data.status === "done") {
          setStatus("done");
        }
      } catch (err) {
        if (cancelled) return;
        setErrorMessage(err instanceof ApiError ? err.message : COPY.genericError);
        setStatus("error");
      }
    };

    poll();
    const intervalId = setInterval(poll, POLL_INTERVAL_MS);
    return () => {
      cancelled = true;
      clearInterval(intervalId);
    };
  }, [status, batchId]);

  return (
    <div className="batch-tab">
      <form className="batch-tab__form" onSubmit={handleSubmit}>
        <h2 className="section-heading">Batch upload</h2>
        <BatchUploadForm
          csvFile={csvFile}
          imageFiles={imageFiles}
          onCsvSelected={setCsvFile}
          onImagesSelected={setImageFiles}
        />
        <button type="submit" className="verify-button" disabled={!isSubmittable}>
          {status === "submitting" ? "Starting batch…" : "Run Batch"}
        </button>
      </form>

      {validationError && <BatchValidationErrors detail={validationError} />}
      {errorMessage && <ErrorPanel message={errorMessage} />}
      {(status === "polling" || status === "done") && (
        <BatchResultsTable rows={rows} isComplete={status === "done"} />
      )}
    </div>
  );
}
