import { useEffect, useState } from "react";
import { getApplicationPdf } from "../lib/api";
import { analyzeDocuments, generateDocuments, confirmEvidence, getDocuments, prepareDocuments, reviewDocuments, type DocumentFile, type DocumentState } from "../lib/applicationDocuments";

export function PdfFiles({ files }: { files: DocumentFile[] }) {
  const [preview, setPreview] = useState<{ url: string; name: string } | null>(null);
  const [error, setError] = useState("");
  useEffect(() => () => { if (preview) URL.revokeObjectURL(preview.url); }, [preview]);
  const open = async (file: DocumentFile, download = false) => {
    setError("");
    try {
      const url = URL.createObjectURL(await getApplicationPdf(file.asset));
      if (download) {
        const link = document.createElement("a");
        link.href = url; link.download = file.asset.split("/").pop() || "application.pdf"; link.click();
        setTimeout(() => URL.revokeObjectURL(url), 1000);
      } else setPreview({ url, name: file.name });
    } catch (e) { setError(e instanceof Error ? e.message : "Could not open PDF"); }
  };
  return <div className="space-y-2">
    {files.map(file => <div key={file.asset} className="flex flex-wrap items-center gap-3 text-sm">
      <button className="text-primary underline" onClick={() => open(file)}>Preview {file.name}</button>
      <button className="text-muted-foreground underline" onClick={() => open(file, true)}>Download {file.name}</button>
    </div>)}
    {error && <p role="alert" className="text-destructive">{error}</p>}
    {preview && <div><button className="text-sm underline" onClick={() => setPreview(null)}>Close PDF preview</button>
      <iframe title={preview.name} src={preview.url} className="w-full h-[32rem] rounded border border-border mt-2" />
    </div>}
  </div>;
}

export default function ApplicationDocuments({ jobUrl, historyOnly = false, onDirtyChange }: { jobUrl: string; historyOnly?: boolean; onDirtyChange?: (dirty: boolean) => void }) {
  const [data, setData] = useState<DocumentState | null>(null);
  const [mode, setMode] = useState("auto");
  const [letter, setLetter] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [confirmed, setConfirmed] = useState(false);
  const [evidence, setEvidence] = useState("");
  const [direction, setDirection] = useState("");
  const accept = (next: DocumentState) => { setData(next); setLetter(next.current?.letter || ""); setConfirmed(false); onDirtyChange?.(false); };
  const run = async (action: () => Promise<DocumentState>, changesDocuments = false) => {
    setBusy(true); setError("");
    if (changesDocuments) onDirtyChange?.(true);
    try { accept(await action()); } catch (e) { setError(e instanceof Error ? e.message : "Could not prepare documents"); }
    finally { setBusy(false); }
  };
  const edited = !!data?.current && (letter !== data.current.letter || (mode !== "auto" && mode !== data.current.mode));
  return <details className="mt-3 rounded-lg border border-border p-3" onToggle={e => {
    if (e.currentTarget.open && !data && !busy) void run(() => getDocuments(jobUrl));
  }}>
    <summary className="cursor-pointer text-sm font-semibold">{historyOnly ? "Application files and history" : "Application documents"}</summary>
    <div className="mt-3 space-y-3 text-sm">
      {!historyOnly && <>
        <p>Prepare the PDFs, inspect them, then approve the exact documents before applying.</p>
        <p>Check the employer’s attachment instructions when choosing the document format.</p>
        <label className="block">Draft direction (optional)<textarea className="input-base" value={direction} onChange={e => setDirection(e.target.value)} placeholder="For example: emphasize manager coaching and shorten older roles" /></label>
        <button className="btn-secondary" disabled={busy} onClick={() => run(() => analyzeDocuments(jobUrl,direction), true)}>Review evidence and draft changes</button>
        {data?.evidence_draft && <section aria-label="Evidence review" className="space-y-3">
          <p>{data.evidence_draft.positioning}</p>
          <div className="overflow-x-auto"><table><thead><tr><th>Requirement</th><th>Evidence</th><th>Gap</th></tr></thead>
            <tbody>{data.evidence_draft.requirements.map((r,i) => <tr key={i}><td>{r.quote} ({r.kind})</td><td>{r.strength}{r.evidence_ids.map(id => <details key={id}><summary>{id}</summary><p>{data.evidence_draft?.evidence[id]?.statement}</p><p>{data.evidence_draft?.evidence[id]?.status}</p></details>)}</td><td>{r.gap}</td></tr>)}</tbody></table></div>
          {data.evidence_draft.questions.map((q,i) => <p key={i}>{i+1}. {q}</p>)}
          <label className="block">Confirm additional experience (include employer, dates and your role)
            <textarea className="input-base" value={evidence} onChange={e => setEvidence(e.target.value)} /></label>
          <button className="btn-secondary" disabled={busy || evidence.trim().length < 10} onClick={() => run(() => confirmEvidence(jobUrl,evidence), true)}>Save confirmed evidence</button>
          <p>You can leave gaps unanswered. They stay out of the documents. After saving evidence, analyze again.</p>
          {data.evidence_draft.edits.map(e => <details key={e.section}><summary>{e.reason}</summary><p>Evidence: {e.evidence_ids.join(", ")}</p><h4>Before</h4><pre className="whitespace-pre-wrap">{data.evidence_draft?.before[String(e.section)]}</pre><h4>After</h4><pre className="whitespace-pre-wrap">{e.revised}</pre></details>)}
          <details><summary>Proposed cover letter</summary><pre className="whitespace-pre-wrap">{data.evidence_draft.letter}</pre></details>
          <button className="btn-primary" disabled={busy} onClick={() => run(() => generateDocuments(jobUrl,data.evidence_draft!.id,mode),true)}>Create PDFs from this draft</button>
        </section>}
        <label className="block">Document format
          <select aria-label="Document format" value={mode} onChange={e => { setMode(e.target.value); setConfirmed(false); onDirtyChange?.(true); }} className="input-base mt-1">
            <option value="auto">From job description{data ? ` (${data.required_mode})` : ""}</option>
            <option value="none">Resume only</option><option value="separate">Resume and separate cover letter</option>
            <option value="combined">Cover letter and resume in one PDF</option>
          </select>
        </label>
        <button className="btn-secondary" disabled={busy} onClick={() => run(() => prepareDocuments(jobUrl, mode, data?.current && data.current.mode !== "none" ? letter : undefined), true)}>
          {busy ? "Preparing…" : "Prepare application PDFs"}
        </button>
        <button className="btn-secondary ml-2" disabled={busy} onClick={() => run(() => prepareDocuments(jobUrl, mode), true)}>Regenerate job-specific letter</button>
        {data?.current && <>
          {data.current.mode !== "none" && <label className="block">This job’s cover letter
            <textarea aria-label="This job’s cover letter" value={letter} onChange={e => { setLetter(e.target.value); setConfirmed(false); onDirtyChange?.(true); }} className="input-base min-h-48 mt-1" />
          </label>}
          <PdfFiles files={data.current.files} />
          <p role="status">{edited ? "Unsaved changes: prepare the PDFs again before reviewing." : data.message}</p>
          <label className="flex gap-2 items-start"><input type="checkbox" checked={confirmed} onChange={e => setConfirmed(e.target.checked)} />
            I reviewed these PDFs and confirmed the required attachment format.</label>
          <button className="btn-primary" disabled={busy || edited || !confirmed} onClick={() => run(() => reviewDocuments(jobUrl, data.current?.prepared_at))}>Approve documents for application</button>
        </>}
      </>}
      {data?.attempts.length === 0 && <p>{historyOnly ? "No saved document record is available for this application." : "No recorded application attempts yet."}</p>}
      {data?.attempts.slice().reverse().map(attempt => <details key={attempt.id} className="border-t border-border pt-2">
        <summary className="cursor-pointer">{attempt.started_at ? new Date(attempt.started_at).toLocaleString() : "Attempt"} — {attempt.status}</summary>
        <p className="my-2">Exact document versions prepared for this attempt.</p>
        {attempt.provided_assets && <p className="my-2">Supplied to automation: {attempt.files.filter(file => attempt.provided_assets?.includes(file.asset)).map(file => file.name).join(", ")}</p>}
        <p className="my-2">{attempt.uploaded_assets?.length
          ? `Upload tool confirmed: ${attempt.files.filter(file => attempt.uploaded_assets?.includes(file.asset)).map(file => file.name).join(", ")}`
          : "No upload confirmation was captured for this attempt."}</p>
        <PdfFiles files={attempt.files} />
        {attempt.letter && <pre className="whitespace-pre-wrap mt-2">{attempt.letter}</pre>}
      </details>)}
      {busy && <p role="status">Loading documents…</p>}
      {error && <p role="alert" className="text-destructive">{error}</p>}
    </div>
  </details>;
}
