import { CareerWorkspaceTabs } from "@/components/candidate-workspace-tabs";
import { CandidateResumeStudioView } from "@/components/candidate-resume-studio-view";
import { ResumeIntelligencePanel } from "@/components/resume-intelligence-panel";

export default function ResumeStudioPage() {
  return (
    <>
      <CareerWorkspaceTabs activeHref="/resume/studio" />
      <CandidateResumeStudioView />
      <ResumeIntelligencePanel />
    </>
  );
}
