import type { Metadata } from "next";

import { CandidateValueDemo } from "./candidate-value-demo";

export const metadata: Metadata = {
  title: "ApplyAI Candidate Demo",
  description:
    "A candidate-first ApplyAI walkthrough for personalized job discovery, truthful tailoring, and application planning.",
};

export default function DemoPage() {
  return <CandidateValueDemo />;
}
