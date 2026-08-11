import { CareerWorkspaceTabs } from "@/components/candidate-workspace-tabs";
import { ResumeStudioWorkspace } from "@/components/platform-workspaces";

export default function ResumeStudioPage() {
  return (
    <>
      <CareerWorkspaceTabs activeHref="/resume/studio" />
      <ResumeStudioWorkspace />
    </>
  );
}
