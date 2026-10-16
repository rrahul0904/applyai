export type PublicJobBoard = {
  id: string;
  slug: string;
  name: string;
  description: string | null;
  website_url: string | null;
  logo_url: string | null;
  status: string;
  visibility: string;
  source_count: number;
  active_job_count: number;
};

export type PublicBoardJob = {
  id: string;
  title: string;
  company_name: string;
  location: string | null;
  work_mode: string | null;
  employment_type: string | null;
  posted_at: string | null;
  last_seen_at: string;
  data_origin: string;
  outbound_url: string;
};

export type PublicBoardJobPage = {
  items: PublicBoardJob[];
  returned: number;
  limit: number;
  offset: number;
};

export type JobPostingSchema = {
  "@context": string;
  "@type": "JobPosting";
  title: string;
  description: string;
  datePosted: string;
  hiringOrganization: { "@type": "Organization"; name: string };
  url: string;
  directApply: boolean;
  employmentType?: string;
  jobLocationType?: string;
  jobLocation?: {
    "@type": "Place";
    address: { "@type": "PostalAddress"; addressLocality: string };
  };
  baseSalary?: {
    "@type": "MonetaryAmount";
    currency: string;
    value: {
      "@type": "QuantitativeValue";
      minValue?: number | null;
      maxValue?: number | null;
      unitText: string;
    };
  };
};

function apiBase() {
  const value = process.env.APPLYAI_API_URL?.trim();
  if (!value) throw new Error("APPLYAI_API_URL is not configured");
  return value.replace(/\/$/, "");
}

async function publicGet<T>(path: string): Promise<T> {
  const response = await fetch(`${apiBase()}/api/v1${path}`, {
    cache: "no-store",
    headers: { accept: "application/json" },
  });
  if (!response.ok) {
    const error = new Error(`Public ApplyAI request failed with ${response.status}`);
    (error as Error & { status?: number }).status = response.status;
    throw error;
  }
  return response.json() as Promise<T>;
}

export function listPublicJobBoards() {
  return publicGet<PublicJobBoard[]>("/job-boards");
}

export function getPublicJobBoard(slug: string) {
  return publicGet<PublicJobBoard>(`/job-boards/${encodeURIComponent(slug)}`);
}

export function listPublicBoardJobs(slug: string, params: { keyword?: string; location?: string } = {}) {
  const search = new URLSearchParams();
  if (params.keyword) search.set("keyword", params.keyword);
  if (params.location) search.set("location", params.location);
  search.set("limit", "50");
  const query = search.toString();
  return publicGet<PublicBoardJobPage>(`/job-boards/${encodeURIComponent(slug)}/jobs?${query}`);
}

export function getPublicJobStructuredData(slug: string, jobId: string) {
  return publicGet<JobPostingSchema>(
    `/job-boards/${encodeURIComponent(slug)}/jobs/${encodeURIComponent(jobId)}/structured-data`,
  );
}
