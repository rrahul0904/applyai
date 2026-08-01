import { ApplicationDetailView } from "@/components/application-detail-view";

export default async function ApplicationDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return <ApplicationDetailView applicationId={id} />;
}
