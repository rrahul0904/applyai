import { InterviewIntelligenceWorkspace } from "@/components/interview-intelligence-workspace";

export default async function InterviewPage({ params }: { params: Promise<{ jobId: string }> }) {
  const { jobId } = await params;
  return <InterviewIntelligenceWorkspace jobId={jobId} />;
}
