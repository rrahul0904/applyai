import { InterviewQuestionBankView } from "@/components/interview-question-bank-view";

type SearchParams = Record<string, string | string[] | undefined>;

function first(value: string | string[] | undefined) {
  return Array.isArray(value) ? value[0] : value;
}

export default async function InterviewQuestionsPage({ searchParams }: { searchParams: Promise<SearchParams> }) {
  const raw = await searchParams;
  return <InterviewQuestionBankView initialQuery={{ q:first(raw.q), company:first(raw.company), track:first(raw.track), difficulty:first(raw.difficulty), min_confidence:first(raw.min_confidence), sort:first(raw.sort) }} />;
}
