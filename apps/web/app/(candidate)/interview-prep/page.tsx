import { InterviewPrepHub, InterviewReportSubmitter } from "@/components/interview-intelligence-view";

export default function InterviewPrepPage() {
  return (
    <div style={{ display: "grid", gap: 28 }}>
      <InterviewPrepHub />
      <InterviewReportSubmitter />
    </div>
  );
}
