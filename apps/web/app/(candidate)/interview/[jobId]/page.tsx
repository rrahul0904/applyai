import { InterviewWorkspace } from "@/components/platform-workspaces";

export default async function InterviewPage({ params }: { params: Promise<{ jobId: string }> }) {
  const { jobId } = await params;
  return <InterviewWorkspace jobId={jobId} />;
}
