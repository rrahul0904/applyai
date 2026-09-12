import { InterviewCompanyView } from "@/components/interview-intelligence-view";

export default async function InterviewCompanyPage({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  return <InterviewCompanyView slug={slug} />;
}
