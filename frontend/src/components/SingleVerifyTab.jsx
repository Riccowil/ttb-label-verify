import { useState } from "react";
import UploadZone from "./UploadZone.jsx";
import ApplicationForm from "./ApplicationForm.jsx";
import ResultsPanel from "./ResultsPanel.jsx";
import ErrorPanel from "./ErrorPanel.jsx";
import { verifyLabel, ApiError } from "../api.js";
import { COPY } from "../copy.js";
import "./SingleVerifyTab.css";

// SPEC.md section 10: "Accepted: JPEG/PNG (WebP optional). Max 10MB."
const ACCEPTED_IMAGE_TYPES = ["image/jpeg", "image/png", "image/webp"];
const MAX_IMAGE_MB = 10;

const EMPTY_FORM = {
  brandName: "",
  classType: "",
  alcoholContent: "",
  netContents: "",
  beverageType: "",
};

export default function SingleVerifyTab() {
  const [imageFile, setImageFile] = useState(null);
  const [imagePreviewUrl, setImagePreviewUrl] = useState(null);
  const [imageError, setImageError] = useState(null);
  const [form, setForm] = useState(EMPTY_FORM);
  const [touched, setTouched] = useState({});
  const [status, setStatus] = useState("idle"); // idle | submitting | success | error
  const [result, setResult] = useState(null);
  const [errorMessage, setErrorMessage] = useState(null);

  function handleFileSelected(file) {
    if (!ACCEPTED_IMAGE_TYPES.includes(file.type)) {
      setImageError(COPY.wrongFileType);
      setImageFile(null);
      setImagePreviewUrl(null);
      return;
    }
    if (file.size > MAX_IMAGE_MB * 1024 * 1024) {
      setImageError(`Image exceeds the ${MAX_IMAGE_MB}MB limit. Please upload a smaller file.`);
      setImageFile(null);
      setImagePreviewUrl(null);
      return;
    }

    setImageError(null);
    setImageFile(file);
    setImagePreviewUrl(URL.createObjectURL(file));
    setStatus("idle");
    setResult(null);
    setErrorMessage(null);
  }

  function handleFieldChange(name, value) {
    setForm((prev) => ({ ...prev, [name]: value }));
  }

  function handleBlur(name) {
    setTouched((prev) => ({ ...prev, [name]: true }));
  }

  const isFormComplete =
    Boolean(imageFile) &&
    Object.entries(form).every(([, value]) => value.trim().length > 0);

  async function handleSubmit(event) {
    event.preventDefault();
    if (!isFormComplete || status === "submitting") return;

    setStatus("submitting");
    setErrorMessage(null);
    try {
      const data = await verifyLabel(imageFile, form);
      setResult(data);
      setStatus("success");
    } catch (err) {
      setErrorMessage(err instanceof ApiError ? err.message : COPY.genericError);
      setStatus("error");
    }
  }

  return (
    <div className="single-verify">
      <form className="single-verify__form" onSubmit={handleSubmit}>
        <h2 className="section-heading">Label &amp; application</h2>
        <UploadZone previewUrl={imagePreviewUrl} onFileSelected={handleFileSelected} error={imageError} />
        <ApplicationForm values={form} onChange={handleFieldChange} touched={touched} onBlur={handleBlur} />
        <button type="submit" className="verify-button" disabled={!isFormComplete || status === "submitting"}>
          {status === "submitting" ? "Verifying…" : "Verify Label"}
        </button>
      </form>

      <div className="single-verify__results">
        <h2 className="section-heading">Results</h2>
        {status === "error" && <ErrorPanel message={errorMessage} />}
        {status === "success" && result && <ResultsPanel result={result} imageUrl={imagePreviewUrl} />}
        {status !== "success" && status !== "error" && (
          <p className="single-verify__placeholder">Results will appear here after you verify a label.</p>
        )}
      </div>
    </div>
  );
}
