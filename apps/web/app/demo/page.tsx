import type { Metadata } from "next";

import { FunctionalCandidateDemo } from "./functional-candidate-demo";

export const metadata: Metadata = {
  title: "ApplyAI Functional Candidate Workspace",
  description:
    "An end-to-end ApplyAI workspace backed by the real profile, jobs, recommendation, resume tailoring, and application APIs.",
};

export default function DemoPage() {
  return <FunctionalCandidateDemo />;
}
