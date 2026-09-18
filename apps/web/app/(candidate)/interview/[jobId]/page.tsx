import { ApplicationKitPanel } from "@/components/application-kit-panel";
import { InterviewIntelligenceLifecycle } from "@/components/interview-intelligence-lifecycle";
import { PrepareWorkspace } from "@/components/prepare-workspace";

export default async function InterviewPage({ params }: { params: Promise<{ jobId: string }> }) {
  const { jobId } = await params;
  return (
    <>
      <ApplicationKitPanel jobId={jobId} />
      <PrepareWorkspace jobId={jobId} />
      <InterviewIntelligenceLifecycle jobId={jobId} />
    </>
  );
}
