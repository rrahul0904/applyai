import { describe, expect, it } from "vitest";

import { buildProofOfWorkReport, detectRepositorySignals } from "@/lib/proof-of-work";

describe("proof-of-work evidence", () => {
  it("derives only deterministic signals from repository metadata", () => {
    expect(detectRepositorySignals({
      name: "career-lab",
      html_url: "https://github.com/example/career-lab",
      description: null,
      language: "TypeScript",
      pushed_at: "2026-10-01T00:00:00Z",
      rootEntries: ["package.json", "tsconfig.json", "next.config.ts", "Dockerfile", ".github", "tests"],
    })).toEqual(["CI/CD", "Docker", "Next.js", "Node.js", "Testing", "TypeScript"]);
  });

  it("separates evidence depth from target-role gaps", () => {
    const report = buildProofOfWorkReport("example", "fullstack", [
      {
        name: "one",
        html_url: "https://github.com/example/one",
        description: null,
        language: "TypeScript",
        pushed_at: "2026-10-01T00:00:00Z",
        rootEntries: ["package.json", "tsconfig.json", "tests"],
      },
      {
        name: "two",
        html_url: "https://github.com/example/two",
        description: null,
        language: "TypeScript",
        pushed_at: "2026-09-30T00:00:00Z",
        rootEntries: ["package.json", "tsconfig.json"],
      },
    ], "2026-10-01T12:00:00Z");

    expect(report.skillEvidence.find((item) => item.skill === "TypeScript")?.depth).toBe("Repeated");
    expect(report.requirements.find((item) => item.label === "Automated testing")?.met).toBe(true);
    expect(report.gaps).toContain("Containerization");
    expect(report.gaps).toContain("Data persistence");
    expect(report.nextBuild.title).toBe("Containerize one existing service");
    expect(report.methodology.readsSourceBodies).toBe(false);
  });
});
