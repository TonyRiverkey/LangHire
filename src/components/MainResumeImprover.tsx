import { useState } from "react";
import { activateMainResume, draftMainResume, type ResumeDraft } from "../lib/applicationDocuments";
import { PdfFiles } from "./ApplicationDocuments";

export default function MainResumeImprover({ jobUrl, skills }: { jobUrl: string; skills: { skill: string; evidence: string; reason: string }[] }) {
  const [selected, setSelected] = useState<Record<string, string>>({});
  const [draft, setDraft] = useState<ResumeDraft | null>(null);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [reviewed, setReviewed] = useState(false);
  if (!skills.length) return null;
  const generate = async () => {
    setBusy(true); setError(""); setMessage(""); setDraft(null); setReviewed(false);
    try { setDraft(await draftMainResume(jobUrl, Object.entries(selected).map(([skill, experience]) => ({ skill, experience })))); }
    catch (e) { setError(e instanceof Error ? e.message : "Could not generate draft"); }
    finally { setBusy(false); }
  };
  const activate = async () => {
    if (!draft) return;
    setBusy(true); setError("");
    try {
      const result = await activateMainResume(draft.id);
      setMessage(`Main resume updated. Your previous file is preserved at ${result.previous_path}. Prepare fresh application documents before applying.`);
      setDraft(null); setSelected({});
    } catch (e) { setError(e instanceof Error ? e.message : "Could not update main resume"); }
    finally { setBusy(false); }
  };
  return <details className="mt-2 border border-border rounded-lg p-3 text-sm">
    <summary className="cursor-pointer font-semibold">Improve main resume from these skills</summary>
    <p className="my-3">Only select skills you actually have. Describe your experience so the draft can improve wording without inventing qualifications. Your main resume changes only after you review and accept the draft.</p>
    {skills.map(item => <div key={item.skill} className="mb-3">
      <label className="flex items-start gap-2"><input type="checkbox" checked={item.skill in selected} disabled={busy} onChange={e => {
        const next = { ...selected };
        if (e.target.checked) next[item.skill] = ""; else delete next[item.skill];
        setSelected(next); setDraft(null); setReviewed(false);
      }} />I have experience with {item.skill}</label>
      {item.skill in selected && <label className="block mt-1">Your actual experience with {item.skill}
        <textarea aria-label={`Your actual experience with ${item.skill}`} className="input-base mt-1" value={selected[item.skill]} disabled={busy} onChange={e => {
          setSelected({ ...selected, [item.skill]: e.target.value }); setDraft(null); setReviewed(false);
        }} placeholder="Describe what you did, where, and when; include results only if you can substantiate them." />
      </label>}
    </div>)}
    <button className="btn-secondary" disabled={busy || !Object.keys(selected).length || Object.values(selected).some(value => value.trim().length < 10)} onClick={generate}>
      {busy ? "Working…" : "Generate main resume improvement draft"}
    </button>
    {draft && <div className="mt-3 space-y-3">
      <div className="grid md:grid-cols-2 gap-3"><label>Original resume<textarea aria-label="Original resume" readOnly value={draft.original} className="input-base min-h-64" /></label>
        <label>Proposed main resume<textarea aria-label="Proposed main resume" readOnly value={draft.revised} className="input-base min-h-64" /></label></div>
      <PdfFiles files={[{ kind: "source", name: "Original main resume", asset: draft.source_asset }, { kind: "draft", name: "Proposed main resume", asset: draft.draft_asset }]} />
      <label className="flex gap-2"><input type="checkbox" checked={reviewed} onChange={e => setReviewed(e.target.checked)} />I reviewed the draft PDF and confirmed every statement is accurate.</label>
      <button className="btn-primary" disabled={busy || !reviewed} onClick={activate}>Use this as my main resume</button>
    </div>}
    {message && <p role="status" className="mt-2">{message}</p>}
    {error && <p role="alert" className="text-destructive mt-2">{error}</p>}
  </details>;
}
