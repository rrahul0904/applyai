export type EvidenceDepth = "Observed" | "Repeated" | "Sustained";

export type RepositoryEvidence = {
  name: string;
  url: string;
  description: string | null;
  language: string | null;
  pushedAt: string;
  rootArtifacts: string[];
  signals: string[];
};

export type SkillEvidence = {
  skill: string;
  repositoryCount: number;
  repositories: string[];
  depth: EvidenceDepth;
};

export type RoleRequirement = {
  label: string;
  acceptedSignals: string[];
  met: boolean;
  evidence: string[];
};

export type NextBuildRecommendation = {
  title: string;
  rationale: string;
  acceptanceCriteria: string[];
};

export type ProofOfWorkReport = {
  username: string;
  targetRole: TargetRole;
  generatedAt: string;
  repositories: RepositoryEvidence[];
  skillEvidence: SkillEvidence[];
  requirements: RoleRequirement[];
  gaps: string[];
  nextBuild: NextBuildRecommendation;
  methodology: {
    scannedRepositoryCount: number;
    maxRepositories: number;
    readsSourceBodies: false;
    note: string;
  };
};

export type TargetRole = "frontend" | "backend" | "fullstack" | "data" | "mobile";

export type GitHubRepositoryInput = {
  name: string;
  html_url: string;
  description: string | null;
  language: string | null;
  pushed_at: string;
  rootEntries: string[];
};

const ROLE_REQUIREMENTS: Record<TargetRole, Array<{ label: string; acceptedSignals: string[] }>> = {
  frontend: [
    { label: "Typed web code", acceptedSignals: ["TypeScript"] },
    { label: "Web framework/tooling", acceptedSignals: ["Next.js", "Frontend tooling"] },
    { label: "Automated testing", acceptedSignals: ["Testing"] },
    { label: "Continuous integration", acceptedSignals: ["CI/CD"] },
  ],
  backend: [
    { label: "Server runtime", acceptedSignals: ["Node.js", "Python", "Go", "Java", "Rust"] },
    { label: "Automated testing", acceptedSignals: ["Testing"] },
    { label: "Containerization", acceptedSignals: ["Docker"] },
    { label: "Continuous integration", acceptedSignals: ["CI/CD"] },
    { label: "Data persistence", acceptedSignals: ["SQL/Data"] },
  ],
  fullstack: [
    { label: "Typed or modern JavaScript", acceptedSignals: ["TypeScript", "JavaScript"] },
    { label: "Server runtime", acceptedSignals: ["Node.js", "Python", "Go", "Java", "Rust"] },
    { label: "Automated testing", acceptedSignals: ["Testing"] },
    { label: "Containerization", acceptedSignals: ["Docker"] },
    { label: "Data persistence", acceptedSignals: ["SQL/Data"] },
  ],
  data: [
    { label: "Data programming", acceptedSignals: ["Python", "SQL/Data"] },
    { label: "Automated testing", acceptedSignals: ["Testing"] },
    { label: "Containerization", acceptedSignals: ["Docker"] },
    { label: "Continuous integration", acceptedSignals: ["CI/CD"] },
    { label: "Infrastructure as code", acceptedSignals: ["Terraform"] },
  ],
  mobile: [
    { label: "Mobile-capable language", acceptedSignals: ["Swift", "Kotlin", "TypeScript"] },
    { label: "Automated testing", acceptedSignals: ["Testing"] },
    { label: "Continuous integration", acceptedSignals: ["CI/CD"] },
    { label: "Build automation", acceptedSignals: ["Build automation", "JVM build"] },
  ],
};

const LANGUAGE_SIGNALS: Record<string, string> = {
  TypeScript: "TypeScript",
  JavaScript: "JavaScript",
  Python: "Python",
  Go: "Go",
  Java: "Java",
  Rust: "Rust",
  Swift: "Swift",
  Kotlin: "Kotlin",
};

function normalizedEntries(entries: string[]) {
  return new Set(entries.map((entry) => entry.toLowerCase()));
}

function hasPrefix(entries: Set<string>, prefix: string) {
  return Array.from(entries).some((entry) => entry.startsWith(prefix));
}

function hasSuffix(entries: Set<string>, suffix: string) {
  return Array.from(entries).some((entry) => entry.endsWith(suffix));
}

export function detectRepositorySignals(repository: GitHubRepositoryInput): string[] {
  const entries = normalizedEntries(repository.rootEntries);
  const signals = new Set<string>();

  if (repository.language && LANGUAGE_SIGNALS[repository.language]) {
    signals.add(LANGUAGE_SIGNALS[repository.language]);
  }

  if (entries.has("tsconfig.json")) signals.add("TypeScript");
  if (entries.has("package.json")) signals.add("Node.js");
  if (hasPrefix(entries, "next.config.")) signals.add("Next.js");
  if (hasPrefix(entries, "vite.config.")) signals.add("Frontend tooling");
  if (entries.has("dockerfile") || entries.has("docker-compose.yml") || entries.has("docker-compose.yaml") || entries.has("compose.yml") || entries.has("compose.yaml")) signals.add("Docker");
  if (entries.has(".github")) signals.add("CI/CD");
  if (entries.has("tests") || entries.has("test") || entries.has("__tests__") || hasPrefix(entries, "vitest.config.") || hasPrefix(entries, "jest.config.") || entries.has("pytest.ini")) signals.add("Testing");
  if (entries.has("prisma") || entries.has("migrations") || hasSuffix(entries, ".sql")) signals.add("SQL/Data");
  if (entries.has("terraform") || hasSuffix(entries, ".tf")) signals.add("Terraform");
  if (entries.has("makefile")) signals.add("Build automation");
  if (entries.has("pyproject.toml") || entries.has("requirements.txt")) signals.add("Python");
  if (entries.has("go.mod")) signals.add("Go");
  if (entries.has("cargo.toml")) signals.add("Rust");
  if (entries.has("package.swift")) signals.add("Swift");
  if (entries.has("build.gradle") || entries.has("build.gradle.kts") || entries.has("gradlew")) signals.add("JVM build");

  return Array.from(signals).sort((a, b) => a.localeCompare(b));
}

export function aggregateSkillEvidence(repositories: RepositoryEvidence[]): SkillEvidence[] {
  const map = new Map<string, Set<string>>();
  for (const repository of repositories) {
    for (const signal of repository.signals) {
      const names = map.get(signal) ?? new Set<string>();
      names.add(repository.name);
      map.set(signal, names);
    }
  }

  return Array.from(map.entries())
    .map(([skill, repositoriesForSkill]) => {
      const repositoryCount = repositoriesForSkill.size;
      const depth: EvidenceDepth = repositoryCount >= 3 ? "Sustained" : repositoryCount === 2 ? "Repeated" : "Observed";
      return {
        skill,
        repositoryCount,
        repositories: Array.from(repositoriesForSkill).sort((a, b) => a.localeCompare(b)),
        depth,
      };
    })
    .sort((a, b) => b.repositoryCount - a.repositoryCount || a.skill.localeCompare(b.skill));
}

export function evaluateRole(targetRole: TargetRole, skillEvidence: SkillEvidence[]): RoleRequirement[] {
  const evidenceBySkill = new Map(skillEvidence.map((item) => [item.skill, item]));
  return ROLE_REQUIREMENTS[targetRole].map((requirement) => {
    const supporting = requirement.acceptedSignals
      .map((signal) => evidenceBySkill.get(signal))
      .filter((item): item is SkillEvidence => Boolean(item));

    return {
      label: requirement.label,
      acceptedSignals: requirement.acceptedSignals,
      met: supporting.length > 0,
      evidence: supporting.flatMap((item) => item.repositories).filter((name, index, all) => all.indexOf(name) === index),
    };
  });
}

function recommendationForGap(gap: string): NextBuildRecommendation {
  const recommendations: Record<string, NextBuildRecommendation> = {
    "Strengthen evidence depth": {
      title: "Deepen one existing signal across a second project",
      rationale: "The target-role checklist is covered, but repeated evidence is stronger and more explainable than a single occurrence.",
      acceptanceCriteria: ["Choose one currently Observed signal", "Use it in a second bounded project", "Add an independent test or CI receipt"],
    },
    "Automated testing": {
      title: "Add a testable feature with a regression suite",
      rationale: "Your public repository metadata does not yet show an obvious root-level testing signal.",
      acceptanceCriteria: ["Add focused unit tests", "Add one integration or browser-level test", "Run tests in CI on pull requests"],
    },
    "Containerization": {
      title: "Containerize one existing service",
      rationale: "A deployable service with a reproducible container boundary is a concrete way to add container evidence.",
      acceptanceCriteria: ["Add a minimal Dockerfile", "Expose a health/readiness check", "Document a clean build-and-run path"],
    },
    "Continuous integration": {
      title: "Add a pull-request quality gate",
      rationale: "Repository metadata does not show a root .github directory, so CI evidence is currently absent.",
      acceptanceCriteria: ["Run lint/typecheck/tests on pull requests", "Fail closed on test errors", "Document the required checks"],
    },
    "Data persistence": {
      title: "Ship a small persisted feature",
      rationale: "A migration-backed feature can produce evidence for data modeling and persistence without inventing a proficiency label.",
      acceptanceCriteria: ["Define a small relational schema", "Add a migration", "Add read/write tests around the persisted feature"],
    },
    "Infrastructure as code": {
      title: "Codify a minimal deployment environment",
      rationale: "No root Terraform signal was observed in the bounded repository scan.",
      acceptanceCriteria: ["Declare one bounded environment", "Keep credentials outside source", "Add validation in CI"],
    },
    "Typed web code": {
      title: "Build one typed web workflow",
      rationale: "The scan did not observe TypeScript evidence in the selected recent repositories.",
      acceptanceCriteria: ["Use TypeScript for the workflow", "Include input/error/loading states", "Add at least one automated test"],
    },
    "Web framework/tooling": {
      title: "Build and deploy a small web interface",
      rationale: "The scan did not observe Next.js or common root-level frontend tooling markers.",
      acceptanceCriteria: ["Implement one complete user flow", "Add accessibility states", "Publish a reproducible build command"],
    },
    "Server runtime": {
      title: "Build a small API with a documented contract",
      rationale: "The bounded scan did not observe a common server-runtime signal.",
      acceptanceCriteria: ["Expose a health endpoint", "Validate request input", "Add deterministic API tests"],
    },
    "Typed or modern JavaScript": {
      title: "Build one TypeScript product slice",
      rationale: "The scan did not observe TypeScript or JavaScript as primary repository signals.",
      acceptanceCriteria: ["Use strict TypeScript", "Implement one end-to-end flow", "Add tests and a build gate"],
    },
    "Data programming": {
      title: "Build a reproducible data workflow",
      rationale: "The scan did not observe Python or SQL/Data signals in the recent owned repositories.",
      acceptanceCriteria: ["Ingest a synthetic dataset", "Validate transformations", "Add deterministic data-quality tests"],
    },
    "Mobile-capable language": {
      title: "Build one small native-capable client flow",
      rationale: "The scan did not observe Swift, Kotlin, or TypeScript evidence in the recent repositories.",
      acceptanceCriteria: ["Implement one stateful screen", "Handle loading/error/empty states", "Add a repeatable test or build check"],
    },
    "Build automation": {
      title: "Add a reproducible build pipeline",
      rationale: "The scan did not observe Make or common JVM build markers.",
      acceptanceCriteria: ["Expose one documented build command", "Make the command non-interactive", "Run it in CI"],
    },
  };

  return recommendations[gap] ?? {
    title: "Strengthen one missing role signal",
    rationale: `The bounded scan did not find public repository evidence for ${gap.toLowerCase()}.`,
    acceptanceCriteria: ["Scope one small feature", "Create observable implementation evidence", "Add a repeatable verification step"],
  };
}

export function buildProofOfWorkReport(
  username: string,
  targetRole: TargetRole,
  repositoryInputs: GitHubRepositoryInput[],
  generatedAt = new Date().toISOString(),
): ProofOfWorkReport {
  const repositories: RepositoryEvidence[] = repositoryInputs.map((repository) => ({
    name: repository.name,
    url: repository.html_url,
    description: repository.description,
    language: repository.language,
    pushedAt: repository.pushed_at,
    rootArtifacts: repository.rootEntries.slice().sort((a, b) => a.localeCompare(b)),
    signals: detectRepositorySignals(repository),
  }));

  const skillEvidence = aggregateSkillEvidence(repositories);
  const requirements = evaluateRole(targetRole, skillEvidence);
  const gaps = requirements.filter((item) => !item.met).map((item) => item.label);
  const nextBuild = recommendationForGap(gaps[0] ?? "Strengthen evidence depth");

  return {
    username,
    targetRole,
    generatedAt,
    repositories,
    skillEvidence,
    requirements,
    gaps,
    nextBuild,
    methodology: {
      scannedRepositoryCount: repositories.length,
      maxRepositories: 6,
      readsSourceBodies: false,
      note: "Signals are deterministic observations from public repository metadata and root artifact names. Evidence depth is not a hiring score, proficiency grade, or claim that a skill was independently verified.",
    },
  };
}
