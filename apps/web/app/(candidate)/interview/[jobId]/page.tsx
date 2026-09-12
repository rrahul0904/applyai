import { ApplicationKitPanel } from "@/components/application-kit-panel";
import { PrepareWorkspace } from "@/components/prepare-workspace";

export default async function InterviewPage({ params }: { params: Promise<{ jobId: string }> }) {
  const { jobId } = await params;
  return (
    <>
      <ApplicationKitPanel jobId={jobId} />
      <PrepareWorkspace jobId={jobId} />
    </>
  );
}
