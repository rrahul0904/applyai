"use client";

import { useEffect, useState } from "react";
import { Play, ShieldCheck } from "lucide-react";

import { Badge, Button, Card, Field, NativeSelect, Textarea } from "@/components/ui";

type Capability = {
  configured: boolean;
  provider: string;
  languages: string[];
  sql_execution: boolean;
  trust_boundary: string;
};

type RunResult = {
  provider: string;
  language: string;
  stdout: string;
  stderr: string;
  exit_code: number | null;
  signal: string | null;
  status: "PASSED" | "FAILED";
  sandboxed: boolean;
};

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const response = await fetch(`/api/backend/api/v1/interview-intelligence/execution${path}`, {
    ...init,
    headers: init.body ? { "content-type": "application/json", ...init.headers } : init.headers,
  });
  if (!response.ok) {
    const body = await response.json().catch(() => null) as { error?: { message?: string } } | null;
    throw new Error(body?.error?.message ?? `Execution request failed (${response.status})`);
  }
  return response.json() as Promise<T>;
}

export function InterviewCodeRunner({ code, onCodeChange }: { code: string; onCodeChange: (code: string) => void }) {
  const [capability, setCapability] = useState<Capability | null>(null);
  const [language, setLanguage] = useState("python");
  const [stdin, setStdin] = useState("");
  const [result, setResult] = useState<RunResult | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [running, setRunning] = useState(false);

  useEffect(() => {
    request<Capability>("/capability")
      .then((value) => {
        setCapability(value);
        if (value.languages.length && !value.languages.includes(language)) setLanguage(value.languages[0]);
      })
      .catch((cause: unknown) => setMessage(cause instanceof Error ? cause.message : "Could not inspect execution capability"));
  }, []);

  async function run() {
    setRunning(true);
    setMessage(null);
    setResult(null);
    try {
      const value = await request<RunResult>("/run", {
        method: "POST",
        body: JSON.stringify({ language, code, stdin }),
      });
      setResult(value);
    } catch (cause) {
      setMessage(cause instanceof Error ? cause.message : "Execution failed");
    } finally {
      setRunning(false);
    }
  }

  return <Card className="detail-section">
    <div className="section-header">
      <div>
        <p className="eyebrow">Isolated practice runtime</p>
        <h2>Run interview code safely</h2>
        <p>Code is never executed inside the ApplyAI web/API process. This panel only calls the configured remote sandbox.</p>
      </div>
      <Badge tone={capability?.configured ? "success" : "neutral"}>
        <ShieldCheck size={14} /> {capability?.configured ? "Sandbox ready" : "Sandbox disabled"}
      </Badge>
    </div>

    <div className="dashboard-grid">
      <Field label="Language" htmlFor="interview-run-language">
        <NativeSelect id="interview-run-language" value={language} onChange={(event) => setLanguage(event.target.value)}>
          {(capability?.languages ?? ["python", "javascript", "typescript", "java", "cpp", "c++", "go"]).map((item) => <option key={item} value={item}>{item}</option>)}
        </NativeSelect>
      </Field>
      <Field label="Standard input (optional)" htmlFor="interview-run-stdin">
        <Textarea id="interview-run-stdin" rows={3} value={stdin} onChange={(event) => setStdin(event.target.value)} />
      </Field>
    </div>

    <Field label="Code" htmlFor="interview-run-code">
      <Textarea id="interview-run-code" rows={14} value={code} onChange={(event) => onCodeChange(event.target.value)} />
    </Field>

    <Button onClick={run} disabled={!capability?.configured || !code.trim() || running}>
      <Play size={15} /> {running ? "Running…" : "Run in isolated sandbox"}
    </Button>

    {!capability?.configured ? <p className="muted">Execution is intentionally fail-closed until an isolated provider is configured in the backend runtime.</p> : null}
    {message ? <p>{message}</p> : null}
    {result ? <Card style={{ marginTop: 14 }}>
      <div className="section-header"><strong>{result.status}</strong><Badge tone={result.status === "PASSED" ? "success" : "warning"}>exit {result.exit_code ?? "n/a"}</Badge></div>
      {result.stdout ? <pre style={{ whiteSpace: "pre-wrap" }}>{result.stdout}</pre> : null}
      {result.stderr ? <pre style={{ whiteSpace: "pre-wrap" }}>{result.stderr}</pre> : null}
    </Card> : null}
  </Card>;
}
