import { request } from "./api";

export interface DocumentFile { kind: string; name: string; asset: string }
export interface DocumentRecord {
  mode: string; letter: string; files: DocumentFile[]; reviewed: boolean;
  id?: string; prepared_at?: string; started_at?: string; status?: string;
  uploaded_assets?: string[];
  provided_assets?: string[];
}
export interface DocumentState {
  required_mode: string; current: DocumentRecord | null; ready: boolean; message: string;
  attempts: DocumentRecord[];
  evidence_draft?: { id: string; positioning: string; questions: string[];
    requirements: { quote: string; kind: string; strength: string; evidence_ids: string[]; gap: string }[];
    edits: { section: number; revised: string; reason: string; evidence_ids: string[] }[];
    evidence: Record<string, { statement: string; status: string }>;
    before: Record<string, string>; letter: string };
}
export const analyzeDocuments = (jobUrl: string, instruction = "") => request<DocumentState>("/application-documents/analyze", {method:"POST",body:JSON.stringify({job_url:jobUrl,instruction})});
export const generateDocuments = (jobUrl: string, draftId: string, mode: string) => request<DocumentState>("/application-documents/generate", {method:"POST",body:JSON.stringify({job_url:jobUrl,draft_id:draftId,mode})});
export const confirmEvidence = (jobUrl: string, statement: string) => request<DocumentState>("/application-documents/evidence", {method:"POST",body:JSON.stringify({job_url:jobUrl,statement})});
export interface ResumeDraft { id: string; original: string; revised: string; source_asset: string; draft_asset: string }
export const getDocuments = (jobUrl: string) => request<DocumentState>(`/application-documents?job_url=${encodeURIComponent(jobUrl)}`);
export const prepareDocuments = (jobUrl: string, mode: string, letter?: string) => request<DocumentState>("/application-documents/prepare", {
  method: "POST", body: JSON.stringify({ job_url: jobUrl, mode, ...(letter === undefined ? {} : { letter }) }),
});
export const reviewDocuments = (jobUrl: string, preparedAt?: string) => request<DocumentState>("/application-documents/review", { method: "POST", body: JSON.stringify({ job_url: jobUrl, prepared_at: preparedAt }) });
export const draftMainResume = (jobUrl: string, skills: { skill: string; experience: string }[]) => request<ResumeDraft>("/main-resume/draft", { method: "POST", body: JSON.stringify({ job_url: jobUrl, skills }) });
export const activateMainResume = (id: string) => request<{ success: boolean; previous_path: string }>("/main-resume/activate", { method: "POST", body: JSON.stringify({ id }) });
