import { buildProofOfWorkReport, type GitHubRepositoryInput, type TargetRole } from "@/lib/proof-of-work";

const TARGET_ROLES = new Set<TargetRole>(["frontend", "backend", "fullstack", "data", "mobile"]);
const USERNAME_PATTERN = /^(?!-)[A-Za-z0-9-]{1,39}(?<!-)$/;
const MAX_REPOSITORIES = 6;

type GitHubRepo = {
  name: string;
  full_name: string;
  html_url: string;
  description: string | null;
  language: string | null;
  pushed_at: string;
  fork: boolean;
  archived: boolean;
};

type GitHubRootEntry = { name?: string };

function githubHeaders() {
  const headers: Record<string, string> = {
    Accept: "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
    "User-Agent": "ApplyAI-Proof-of-Work-Lab",
  };
  if (process.env.GITHUB_TOKEN) headers.Authorization = `Bearer ${process.env.GITHUB_TOKEN}`;
  return headers;
}

async function githubJson<T>(url: string): Promise<T> {
  const response = await fetch(url, {
    headers: githubHeaders(),
    cache: "no-store",
  });

  if (!response.ok) {
    const rateRemaining = response.headers.get("x-ratelimit-remaining");
    if (response.status === 403 && rateRemaining === "0") {
      throw new Error("GitHub API rate limit reached. Configure GITHUB_TOKEN for a higher server-side limit.");
    }
    if (response.status === 404) throw new Error("GitHub user or repository was not found.");
    throw new Error(`GitHub API request failed with status ${response.status}.`);
  }
  return response.json() as Promise<T>;
}

export async function GET(request: Request) {
  const url = new URL(request.url);
  const username = url.searchParams.get("username")?.trim() ?? "";
  const requestedRole = url.searchParams.get("role")?.trim() ?? "fullstack";

  if (!USERNAME_PATTERN.test(username)) {
    return Response.json({ error: "Enter a valid public GitHub username." }, { status: 400 });
  }
  if (!TARGET_ROLES.has(requestedRole as TargetRole)) {
    return Response.json({ error: "Choose a supported target role." }, { status: 400 });
  }
  const targetRole = requestedRole as TargetRole;

  try {
    const repos = await githubJson<GitHubRepo[]>(
      `https://api.github.com/users/${encodeURIComponent(username)}/repos?sort=updated&direction=desc&per_page=12&type=owner`,
    );

    const selected = repos.filter((repo) => !repo.fork && !repo.archived).slice(0, MAX_REPOSITORIES);
    const inputs: GitHubRepositoryInput[] = await Promise.all(selected.map(async (repo) => {
      let rootEntries: string[] = [];
      try {
        const entries = await githubJson<GitHubRootEntry[]>(`https://api.github.com/repos/${repo.full_name}/contents`);
        rootEntries = Array.isArray(entries)
          ? entries.map((entry) => entry.name).filter((name): name is string => Boolean(name))
          : [];
      } catch {
        rootEntries = [];
      }

      return {
        name: repo.name,
        html_url: repo.html_url,
        description: repo.description,
        language: repo.language,
        pushed_at: repo.pushed_at,
        rootEntries,
      };
    }));

    return Response.json(buildProofOfWorkReport(username, targetRole, inputs), {
      headers: { "Cache-Control": "private, no-store" },
    });
  } catch (error) {
    const message = error instanceof Error ? error.message : "Unable to analyze GitHub right now.";
    return Response.json({ error: message }, { status: message.includes("rate limit") ? 429 : 502 });
  }
}
