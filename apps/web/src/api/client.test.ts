import { describe, expect, it } from "vitest";

import { api } from "./client";

describe("api client helpers", () => {
  it("builds artifact content URLs", () => {
    expect(api.artifactContentUrl("abc")).toBe("/api/artifacts/abc/content");
  });
});
