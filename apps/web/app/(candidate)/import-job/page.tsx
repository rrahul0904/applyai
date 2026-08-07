import { Suspense } from "react";
import { JobImportWorkspace } from "@/components/job-import-workspace";

export default function ImportJobPage() {
  return <Suspense><JobImportWorkspace /></Suspense>;
}
