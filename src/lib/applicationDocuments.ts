import { request } from "./api";

export interface DocumentFile { kind: string; name: string; asset: string }
export interface DocumentRecord {
  mode: string; letter: string; files: DocumentFile[]; reviewed: boolean;
  id?: string; started_at?: string; status?: string;
  uploaded_assets?: string[];
  provided_assets?: string[];
}
export interface DocumentState {
  required_mode: string; current: DocumentRecord | null; ready: boolean; message: string;
  attempts: DocumentRecord[];
}
export interface ResumeDraft { id: string; original: string; revised: string; source_asset: string; draft_asset: string }
export const getDocuments = (jobUrl: string) => request<DocumentState>(`/application-documents?job_url=${encodeURIComponent(jobUrl)}`);
export const prepareDocuments = (jobUrl: string, mode: string, letter?: string) => request<DocumentState>("/application-documents/prepare", {
  method: "POST", body: JSON.stringify({ job_url: jobUrl, mode, ...(letter === undefined ? {} : { letter }) }),
});
export const reviewDocuments = (jobUrl: string) => request<DocumentState>("/application-documents/review", { method: "POST", body: JSON.stringify({ job_url: jobUrl }) });
export const draftMainResume = (jobUrl: string, skills: { skill: string; experience: string }[]) => request<ResumeDraft>("/main-resume/draft", { method: "POST", body: JSON.stringify({ job_url: jobUrl, skills }) });
export const activateMainResume = (id: string) => request<{ success: boolean; previous_path: string }>("/main-resume/activate", { method: "POST", body: JSON.stringify({ id }) });
