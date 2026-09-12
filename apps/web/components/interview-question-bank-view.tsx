"use client";

import Link from "next/link";
import { FormEvent, useEffect, useMemo, useState } from "react";
import { interviewIntelligenceApi, type CompanyCollection, type InterviewQuestion } from "@/lib/api/interview-intelligence-client";
import { Badge, Button, Card, EmptyState, ErrorState, Input, NativeSelect, PageHeader } from "@/components/ui";
import styles from "./interview-intelligence.module.css";

type InitialQuery = { q?: string; company?: string; track?: string; difficulty?: string; min_confidence?: string; sort?: string };

function label(value: string) { return value.replaceAll("_", " ").toLowerCase().replace(/\b\w/g, (char) => char.toUpperCase()); }

function QuestionRow({ question }: { question: InterviewQuestion }) {
  return <Link href={`/interview-prep/questions/${question.slug}`}><Card className={styles.questionRow}><div><div className={styles.chipRow}><Badge tone="info">{label(question.track)}</Badge><Badge>{question.difficulty}</Badge></div><h3>{question.title}</h3><p className={styles.muted}>{question.summary}</p><div className={styles.questionMeta}>{question.companies.map((company)=><Badge key={company}>{company}</Badge>)}{question.skills.slice(0,3).map((skill)=><Badge key={skill}>{skill}</Badge>)}</div></div><div className={styles.score}><strong>{question.frequency_score}</strong><span className={styles.muted}>frequency</span><Badge tone={question.confidence >= 90 ? "success" : "warning"}>{question.confidence}% confidence</Badge></div></Card></Link>;
}

export function InterviewQuestionBankView({ initialQuery }: { initialQuery: InitialQuery }) {
  const [filters, setFilters] = useState({ q: initialQuery.q ?? "", company: initialQuery.company ?? "", track: initialQuery.track ?? "", difficulty: initialQuery.difficulty ?? "", min_confidence: initialQuery.min_confidence ?? "", sort: initialQuery.sort ?? "FREQUENCY" });
  const initialParams = useMemo(() => { const params = new URLSearchParams(); Object.entries(initialQuery).forEach(([key,value]) => value && params.set(key,value)); return params; }, [initialQuery]);
  const [query, setQuery] = useState(initialParams);
  const [items, setItems] = useState<InterviewQuestion[] | null>(null);
  const [total, setTotal] = useState(0);
  const [companies, setCompanies] = useState<CompanyCollection[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => { interviewIntelligenceApi.companies().then(setCompanies).catch(()=>undefined); }, []);
  useEffect(() => { let cancelled=false; setLoading(true); setError(null); interviewIntelligenceApi.questions(query).then((page)=>{if(!cancelled){setItems(page.items);setTotal(page.total)}}).catch((cause:unknown)=>{if(!cancelled)setError(cause instanceof Error?cause.message:"Could not load questions")}).finally(()=>{if(!cancelled)setLoading(false)}); return()=>{cancelled=true}; }, [query]);

  function submit(event: FormEvent) { event.preventDefault(); const params=new URLSearchParams(); Object.entries(filters).forEach(([key,value])=>value&&params.set(key,value)); setQuery(params); window.history.replaceState(null,"",`${window.location.pathname}${params.size?`?${params}`:""}`); }
  function reset(){const blank={q:"",company:"",track:"",difficulty:"",min_confidence:"",sort:"FREQUENCY"};setFilters(blank);setQuery(new URLSearchParams());window.history.replaceState(null,"",window.location.pathname)}

  return <div className={styles.shell}><PageHeader eyebrow="Question bank" title="Search interview intelligence." description="Filter by company, track, difficulty and evidence confidence. Deep links preserve the selected company or track."/><Card className={styles.contentCard}><form className={styles.toolbar} onSubmit={submit}><Input placeholder="Search questions…" value={filters.q} onChange={(e)=>setFilters({...filters,q:e.target.value})}/><NativeSelect value={filters.company} onChange={(e)=>setFilters({...filters,company:e.target.value})}><option value="">All companies</option>{companies.map((item)=><option key={item.slug} value={item.name}>{item.name}</option>)}</NativeSelect><NativeSelect value={filters.track} onChange={(e)=>setFilters({...filters,track:e.target.value})}><option value="">All tracks</option>{["CODING","SQL","SYSTEM_DESIGN","ML_SYSTEM_DESIGN","OOD","BEHAVIORAL"].map((track)=><option key={track} value={track}>{label(track)}</option>)}</NativeSelect><NativeSelect value={filters.difficulty} onChange={(e)=>setFilters({...filters,difficulty:e.target.value})}><option value="">All difficulty</option><option>EASY</option><option>MEDIUM</option><option>HARD</option></NativeSelect><NativeSelect value={filters.min_confidence} onChange={(e)=>setFilters({...filters,min_confidence:e.target.value})}><option value="">Any confidence</option><option value="80">80%+</option><option value="90">90%+</option></NativeSelect><NativeSelect value={filters.sort} onChange={(e)=>setFilters({...filters,sort:e.target.value})}><option value="FREQUENCY">Frequency</option><option value="RECENT">Recent</option><option value="CONFIDENCE">Confidence</option></NativeSelect><div className={styles.toolbarActions}><Button type="submit">Apply filters</Button><Button type="button" variant="ghost" onClick={reset}>Reset</Button></div></form></Card>{loading?<div className={styles.loading}>Loading question bank…</div>:error?<ErrorState message={error}/>:items?.length?<><p className={styles.muted}>{total} matching questions</p><div className={styles.questionList}>{items.map((question)=><QuestionRow key={question.id} question={question}/>)}</div></>:<EmptyState title="No matching questions" description="Broaden the filters or clear the search."/>}</div>;
}
