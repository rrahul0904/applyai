import { JobInterviewIntelligencePanel } from "@/components/interview-intelligence-view";
import { InterviewWorkspace } from "@/components/platform-workspaces";

export default async function InterviewPage({ params }: { params: Promise<{ jobId: string }> }) {
  const { jobId } = await params;
  return (
    <div style={{ display: "grid", gap: 20 }}>
      <JobInterviewIntelligencePanel jobId={jobId} />
      <InterviewWorkspace jobId={jobId} />
    </div>
  );
}
