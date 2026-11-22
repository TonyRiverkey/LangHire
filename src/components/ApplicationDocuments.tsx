import { useEffect, useState } from "react";
import { getApplicationPdf } from "../lib/api";
import { getDocuments, prepareDocuments, reviewDocuments, type DocumentFile, type DocumentState } from "../lib/applicationDocuments";

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
          <button className="btn-primary" disabled={busy || edited || !confirmed} onClick={() => run(() => reviewDocuments(jobUrl))}>Approve documents for application</button>
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
