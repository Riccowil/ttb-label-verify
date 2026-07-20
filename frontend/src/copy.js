// Every static string here is copied verbatim from SPEC.md section 11.
// Single source so no component has to re-derive or paraphrase wording.
// unreferencedImagesNotice() below is the one exception — a post-launch
// dogfooding fix with no SPEC precedent — kept here anyway so all
// user-facing wording still lives in one place.

export const COPY = {
  uploadZone: "Drop label image here or tap to browse (JPEG/PNG, max 10MB)",
  requiredField: "Required",
  verdictChipLabel: {
    PASS: "Matches application",
    FLAG: "Needs your review",
    FAIL: "Does not match",
  },
  needsBetterImage:
    "We couldn't read this label clearly. Please request a clearer photo — straight-on, good lighting, no glare.",
  timeout: "Verification took too long. Please try again.",
  wrongFileType: "That file isn't an image we support. Please upload a JPEG or PNG.",
  diffLegend: "Red = on label but wrong / missing · Green = required text",
  genericError: "Something went wrong. Please try again.",
};

export const BEVERAGE_TYPES = [
  { value: "distilled_spirits", label: "Distilled spirits" },
  { value: "wine", label: "Wine" },
  { value: "beer", label: "Beer" },
];

export const FIELD_LABELS = {
  brand_name: "Brand name",
  class_type: "Class / type",
  alcohol_content: "Alcohol content",
  net_contents: "Net contents",
  government_warning: "Government warning",
};

// Non-blocking notice for uploaded batch images no CSV row references.
// The CSV stays the source of truth (see app.py's _preflight_validate_batch)
// — this is informational only, never an error.
export function unreferencedImagesNotice(filenames) {
  if (!filenames || filenames.length === 0) {
    return null;
  }
  const isSingle = filenames.length === 1;
  return (
    `${filenames.length} uploaded ${isSingle ? "image" : "images"} not referenced in the CSV ` +
    `${isSingle ? "was" : "were"} skipped: ${filenames.join(", ")}.`
  );
}
