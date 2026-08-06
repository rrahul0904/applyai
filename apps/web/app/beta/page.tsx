import type { Metadata } from "next";

import { CandidateBetaJourney } from "./beta-client";

export const metadata: Metadata = {
  title: "ApplyAI Candidate Beta",
  description:
    "A realistic candidate journey from explainable job matching through truthful resume tailoring and a reviewed application package.",
};

export default function CandidateBetaPage() {
  return <CandidateBetaJourney />;
}
