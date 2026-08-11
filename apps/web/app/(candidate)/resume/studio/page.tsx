import { CareerWorkspaceTabs } from "@/components/candidate-workspace-tabs";
import { CandidateResumeStudioView } from "@/components/candidate-resume-studio-view";

export default function ResumeStudioPage() {
  return (
    <>
      <CareerWorkspaceTabs activeHref="/resume/studio" />
      <CandidateResumeStudioView />
    </>
  );
}
