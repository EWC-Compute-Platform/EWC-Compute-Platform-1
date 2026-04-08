import { describe, it, expect } from "vitest";

// Phase 0 frontend smoke test.
// Confirms the test runner itself is wired correctly.
// Component tests are added in Phase 1 when the UI has real behaviour to verify.

describe("EWC Compute frontend", () => {
  it("test runner is configured", () => {
    expect(true).toBe(true);
  });

  it("environment is not production", () => {
    // In CI, import.meta.env.MODE is 'test'
    expect(import.meta.env.MODE).not.toBe("production");
  });
});
