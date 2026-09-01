import type { Metadata } from "next";

import { PublicRecruiterLensReport } from "@/components/public-recruiter-lens-report";

export const metadata: Metadata = {
  title: "Recruiter Lens Report | ApplyAI",
  description: "Candidate-controlled Recruiter Lens self-assessment report.",
  robots: { index: false, follow: false },
};

export default async function RecruiterReportPage({ params }: { params: Promise<{ token: string }> }) {
  const { token } = await params;
  return <PublicRecruiterLensReport token={token} />;
}
