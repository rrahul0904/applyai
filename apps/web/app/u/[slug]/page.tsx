import type { Metadata } from "next";

import { PublicCandidatePortfolio } from "@/components/public-candidate-portfolio";

export const metadata: Metadata = {
  title: "Candidate Portfolio | ApplyAI",
  description: "Candidate-controlled public career portfolio.",
};

export default async function PublicPortfolioPage({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  return <PublicCandidatePortfolio slug={slug} />;
}
