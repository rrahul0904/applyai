import Link from "next/link";
import { notFound } from "next/navigation";
import { getPublicJobBoard, listPublicBoardJobs } from "@/lib/public-job-boards";
import styles from "../job-boards.module.css";

export const dynamic = "force-dynamic";

type Props = {
  params: Promise<{ slug: string }>;
  searchParams: Promise<{ keyword?: string; location?: string }>;
};

export default async function JobBoardPage({ params, searchParams }: Props) {
  const { slug } = await params;
  const filters = await searchParams;
  let board;
  let jobs;
  try {
    [board, jobs] = await Promise.all([
      getPublicJobBoard(slug),
      listPublicBoardJobs(slug, filters),
    ]);
  } catch {
    notFound();
  }

  return (
    <main className={styles.page}>
      <div className={styles.shell}>
        <Link className={styles.back} href="/job-boards">← All job boards</Link>
        <div className={styles.eyebrow}>ApplyAI Job Network</div>
        <div className={styles.hero}>
          <div>
            <h1>{board.name}</h1>
            <p>{board.description || "A curated ApplyAI job collection."}</p>
            <div className={styles.meta}>
              <span className={styles.pill}>{board.active_job_count.toLocaleString()} active jobs</span>
              <span className={styles.pill}>{board.source_count.toLocaleString()} verified sources</span>
            </div>
          </div>
        </div>

        <form className={styles.toolbar} action={`/job-boards/${slug}`} method="get">
          <input
            className={styles.input}
            aria-label="Keyword"
            name="keyword"
            placeholder="Role, skill or title"
            defaultValue={filters.keyword || ""}
          />
          <input
            className={styles.input}
            aria-label="Location"
            name="location"
            placeholder="City, region or remote"
            defaultValue={filters.location || ""}
          />
          <button className={styles.button} type="submit">Search</button>
        </form>

        {jobs.items.length ? (
          <section className={styles.jobs} aria-label={`${board.name} jobs`}>
            {jobs.items.map((job) => (
              <article className={styles.job} key={job.id}>
                <div>
                  <h2>{job.title}</h2>
                  <p>
                    {job.company_name}
                    {job.location ? ` · ${job.location}` : ""}
                    {job.work_mode ? ` · ${job.work_mode}` : ""}
                  </p>
                  <div className={styles.meta}>
                    {job.employment_type ? <span className={styles.pill}>{job.employment_type}</span> : null}
                    <span className={styles.pill}>Verified source</span>
                  </div>
                </div>
                <div className={styles.jobLinks}>
                  <Link className={styles.secondary} href={`/job-boards/${slug}/jobs/${job.id}`}>Details</Link>
                  <a
                    className={styles.button}
                    href={`/api/public-backend/job-boards/outbound/${job.id}?board=${encodeURIComponent(slug)}&channel=DIRECT&utm_source=applyai&utm_medium=job_board&utm_campaign=${encodeURIComponent(slug)}`}
                    rel="nofollow sponsored noopener"
                  >
                    Apply
                  </a>
                </div>
              </article>
            ))}
          </section>
        ) : (
          <div className={styles.empty}>No active jobs match those filters right now.</div>
        )}
      </div>
    </main>
  );
}
