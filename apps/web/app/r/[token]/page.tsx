import type { Metadata } from "next";

import { ResumeSharePublic } from "@/components/resume-share-public";

export const metadata: Metadata = {
  title: "Shared resume · ApplyAI",
  robots: { index: false, follow: false },
};

export default async function SharedResumePage({ params }: { params: Promise<{ token: string }> }) {
  const { token } = await params;
  return <ResumeSharePublic token={token} />;
}
