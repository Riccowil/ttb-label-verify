import { describe, expect, it } from "vitest";
import { verdictStyle } from "./verdict.js";

describe("verdictStyle", () => {
  it("maps PASS to the pass chip class", () => {
    expect(verdictStyle("PASS").className).toBe("chip--pass");
  });

  it("maps FLAG to the flag chip class", () => {
    expect(verdictStyle("FLAG").className).toBe("chip--flag");
  });

  it("maps FAIL to the fail chip class", () => {
    expect(verdictStyle("FAIL").className).toBe("chip--fail");
  });

  it("maps NEEDS BETTER IMAGE to the needs-image chip class", () => {
    expect(verdictStyle("NEEDS BETTER IMAGE").className).toBe("chip--needs-image");
  });

  it("falls back to an unknown class for an unrecognized verdict", () => {
    expect(verdictStyle("SOMETHING ELSE").className).toBe("chip--unknown");
  });
});
