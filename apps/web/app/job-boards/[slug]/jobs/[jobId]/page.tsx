import Link from "next/link";
import { notFound } from "next/navigation";
import { getPublicJobBoard, getPublicJobStructuredData } from "@/lib/public-job-boards";
import styles from "../../../job-boards.module.css";

export const dynamic = "force-dynamic";

type Props = { params: Promise<{ slug: string; jobId: string }> };

function compensationText(schema: Awaited<ReturnType<typeof getPublicJobStructuredData>>) {
  const salary = schema.baseSalary;
  if (!salary) return null;
  const { minValue, maxValue, unitText } = salary.value;
  const currency = salary.currency || "USD";
  const format = new Intl.NumberFormat("en-US", { style: "currency", currency, maximumFractionDigits: 0 });
  if (minValue != null && maxValue != null) return `${format.format(minValue)}–${format.format(maxValue)} / ${unitText.toLowerCase()}`;
  if (minValue != null) return `From ${format.format(minValue)} / ${unitText.toLowerCase()}`;
  if (maxValue != null) return `Up to ${format.format(maxValue)} / ${unitText.toLowerCase()}`;
  return null;
}

export default async function PublicBoardJobPage({ params }: Props) {
  const { slug, jobId } = await params;
  let board;
  let schema;
  try {
    [board, schema] = await Promise.all([
      getPublicJobBoard(slug),
      getPublicJobStructuredData(slug, jobId),
    ]);
  } catch {
    notFound();
  }
  const location = schema.jobLocation?.address.addressLocality || (schema.jobLocationType === "TELECOMMUTE" ? "Remote" : null);
  const compensation = compensationText(schema);

  return (
    <main className={styles.page}>
      <div className={styles.shell}>
        <script
          type="application/ld+json"
          dangerouslySetInnerHTML={{ __html: JSON.stringify(schema).replace(/</g, "\\u003c") }}
        />
        <Link className={styles.back} href={`/job-boards/${slug}`}>← {board.name}</Link>
        <article className={styles.detail}>
          <div className={styles.eyebrow}>Verified ApplyAI job</div>
          <h1>{schema.title}</h1>
          <div className={styles.company}>
            {schema.hiringOrganization.name}{location ? ` · ${location}` : ""}
          </div>
          <div className={styles.meta}>
            {schema.employmentType ? <span className={styles.pill}>{schema.employmentType}</span> : null}
            {schema.jobLocationType === "TELECOMMUTE" ? <span className={styles.pill}>Remote</span> : null}
            <span className={styles.pill}>Posted {schema.datePosted}</span>
          </div>
          {compensation ? <div className={styles.salary}>{compensation}</div> : null}
          <div className={styles.description}>{schema.description}</div>
          <a
            className={styles.button}
            href={`/api/public-backend/job-boards/outbound/${jobId}?board=${encodeURIComponent(slug)}&channel=SEARCH&utm_source=applyai&utm_medium=public_job_detail&utm_campaign=${encodeURIComponent(slug)}`}
            rel="nofollow sponsored noopener"
          >
            Apply on verified source
          </a>
        </article>
      </div>
    </main>
  );
}
