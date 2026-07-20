// Pure mapping from a verdict string to the chip styling/label to render.
// No React, no DOM — kept testable in isolation.

const VERDICT_STYLES = {
  PASS: { className: "chip--pass", label: "PASS" },
  FLAG: { className: "chip--flag", label: "FLAG" },
  FAIL: { className: "chip--fail", label: "FAIL" },
  "NEEDS BETTER IMAGE": { className: "chip--needs-image", label: "NEEDS BETTER IMAGE" },
};

export function verdictStyle(verdict) {
  return VERDICT_STYLES[verdict] ?? { className: "chip--unknown", label: verdict };
}
