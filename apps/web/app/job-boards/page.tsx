import Link from "next/link";
import { listPublicJobBoards } from "@/lib/public-job-boards";
import styles from "./job-boards.module.css";

export const dynamic = "force-dynamic";

export default async function JobBoardsPage() {
  let boards = [];
  try {
    boards = await listPublicJobBoards();
  } catch {
    boards = [];
  }

  return (
    <main className={styles.page}>
      <div className={styles.shell}>
        <div className={styles.eyebrow}>ApplyAI Job Network</div>
        <div className={styles.hero}>
          <div>
            <h1>Focused job boards, backed by one verified job graph.</h1>
            <p>
              Explore niche collections without losing provenance, freshness, deduplication,
              or the ApplyAI workflow that takes you from discovery to application.
            </p>
          </div>
        </div>

        {boards.length ? (
          <section className={styles.grid} aria-label="Job boards">
            {boards.map((board) => (
              <Link className={styles.card} href={`/job-boards/${board.slug}`} key={board.id}>
                <h2>{board.name}</h2>
                <p>{board.description || "A curated ApplyAI job collection."}</p>
                <div className={styles.meta}>
                  <span className={styles.pill}>{board.active_job_count.toLocaleString()} active jobs</span>
                  <span className={styles.pill}>{board.source_count.toLocaleString()} verified sources</span>
                </div>
              </Link>
            ))}
          </section>
        ) : (
          <div className={styles.empty}>
            No public boards are available yet. Existing ApplyAI job search continues to work normally.
          </div>
        )}
      </div>
    </main>
  );
}
