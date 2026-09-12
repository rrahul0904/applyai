import { InterviewQuestionDetail } from "@/components/interview-intelligence-view";

export default async function InterviewQuestionPage({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  return <InterviewQuestionDetail slug={slug} />;
}
