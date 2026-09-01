import { InterviewWorkspace } from "@/components/platform-workspaces";
import { TechnicalInterviewLab } from "@/components/technical-interview-lab";

export default async function InterviewPage({ params }: { params: Promise<{ jobId: string }> }) {
  const { jobId } = await params;
  return <>
    <InterviewWorkspace jobId={jobId} />
    <TechnicalInterviewLab jobId={jobId} />
  </>;
}
