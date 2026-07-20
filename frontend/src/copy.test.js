import { describe, expect, it } from "vitest";
import { unreferencedImagesNotice } from "./copy.js";

describe("unreferencedImagesNotice", () => {
  it("returns null when there are no unreferenced files", () => {
    expect(unreferencedImagesNotice([])).toBeNull();
  });

  it("returns null when filenames is undefined", () => {
    expect(unreferencedImagesNotice(undefined)).toBeNull();
  });

  it("uses singular wording for exactly one file", () => {
    expect(unreferencedImagesNotice(["t7_bad_image_glare.png"])).toBe(
      "1 uploaded image not referenced in the CSV was skipped: t7_bad_image_glare.png."
    );
  });

  it("uses plural wording and joins multiple filenames", () => {
    expect(
      unreferencedImagesNotice(["t7_bad_image_glare.png", "t8_wine_no_abv.png"])
    ).toBe(
      "2 uploaded images not referenced in the CSV were skipped: " +
        "t7_bad_image_glare.png, t8_wine_no_abv.png."
    );
  });
});
