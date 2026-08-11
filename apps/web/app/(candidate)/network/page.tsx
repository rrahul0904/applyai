import { CareerWorkspaceTabs } from "@/components/candidate-workspace-tabs";
import { NetworkWorkspace } from "@/components/platform-workspaces";

export default function NetworkPage() {
  return (
    <>
      <CareerWorkspaceTabs activeHref="/network" />
      <NetworkWorkspace />
    </>
  );
}
