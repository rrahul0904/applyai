import { CareerNavigationWorkspace } from "@/components/career-navigation-workspace";
import { CareerWorkspaceTabs } from "@/components/candidate-workspace-tabs";

export default function CareerNavigationPage() {
  return <>
    <CareerWorkspaceTabs activeHref="/career/navigation" />
    <CareerNavigationWorkspace />
  </>;
}
