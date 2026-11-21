import { useState, useEffect, useRef } from "react";
import { FolderOpen, CheckCircle, Loader2, Upload } from "lucide-react";
import { getSettings, saveSettings, uploadResume } from "../../lib/api";
import { open } from "@tauri-apps/plugin-dialog";
import { isTauri } from "@tauri-apps/api/core";

interface ResumePickerFormProps {
  onSaved?: () => void;
}

const isPdf = (name: string, type?: string) =>
  type === "application/pdf" || name.toLowerCase().endsWith(".pdf");

export default function ResumePickerForm({ onSaved }: ResumePickerFormProps) {
  const [resumePath, setResumePath] = useState("");
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [loading, setLoading] = useState(true);
  const [dragging, setDragging] = useState(false);
  const [dropError, setDropError] = useState("");
  const saveTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const lastSaved = useRef("");
  const fileInput = useRef<HTMLInputElement>(null);

  useEffect(() => {
    getSettings()
      .then((data) => {
        const path = data.resume_path || "";
        setResumePath(path);
        lastSaved.current = path;
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    return () => { if (saveTimer.current) clearTimeout(saveTimer.current); };
  }, []);

  const doSave = async (path: string) => {
    if (path === lastSaved.current || !path.trim()) return;
    setSaving(true);
    try {
      const current = await getSettings();
      await saveSettings({ ...current, resume_path: path });
      lastSaved.current = path;
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
      onSaved?.();
    } catch { setDropError("Could not save the resume selection. Please try again."); }
    finally { setSaving(false); }
  };

  const handleChange = (path: string) => {
    setResumePath(path);
    setSaved(false);
    setDropError("");
    if (saveTimer.current) clearTimeout(saveTimer.current);
    saveTimer.current = setTimeout(() => doSave(path), 800);
  };

  const handleBrowse = async () => {
    setDropError("");
    if (!isTauri()) {
      fileInput.current?.click();
      return;
    }
    try {
      const file = await open({ filters: [{ name: "PDF", extensions: ["pdf"] }] });
      if (file) {
        if (saveTimer.current) clearTimeout(saveTimer.current);
        setSaved(false);
        setResumePath(file as string);
        doSave(file as string); // Save immediately on browse
      }
    } catch { setDropError("Could not open the file picker. Please try again."); }
  };

  const handleFile = async (file: File) => {
    if (!isPdf(file.name, file.type)) {
      setDropError("Only PDF files are supported. Please select a .pdf resume.");
      return;
    }
    if (file.size > 10 * 1024 * 1024) {
      setDropError("Resume must be 10 MB or smaller.");
      return;
    }
    if (saveTimer.current) clearTimeout(saveTimer.current);
    setDropError("");
    setSaved(false);
    setSaving(true);
    try {
      const path = (file as File & { path?: string }).path
        || (await uploadResume(file)).resume_path;
      setResumePath(path);
      await doSave(path);
    } catch {
      setDropError("Could not upload the resume. Please try again.");
    } finally {
      setSaving(false);
    }
  };

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (!dragging) setDragging(true);
  };

  const handleDragEnter = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDropError("");
    setDragging(true);
  };

  const handleDragLeave = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragging(false);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragging(false);

    const file = e.dataTransfer?.files?.[0];
    if (!file) {
      setDropError("No file detected. Please drop a PDF resume.");
      return;
    }
    void handleFile(file);
  };

  if (loading) return <div className="flex justify-center py-4"><Loader2 className="w-5 h-5 animate-spin text-primary" /></div>;

  return (
    <div className="space-y-2">
      <input
        ref={fileInput}
        type="file"
        accept=".pdf,application/pdf"
        aria-label="Choose a PDF resume"
        hidden
        onChange={(e) => {
          const file = e.target.files?.[0];
          e.target.value = "";
          if (file) void handleFile(file);
        }}
      />
      <label className="block text-sm font-medium text-foreground">Resume PDF Path</label>
      <div className="flex gap-2">
        <input
          value={resumePath}
          onChange={(e) => handleChange(e.target.value)}
          placeholder="/path/to/your/resume.pdf"
          className="flex-1 px-3 py-2 border border-border rounded-lg text-sm"
        />
        <button onClick={handleBrowse} className="flex items-center gap-2 px-3 py-2 border border-border rounded-lg text-sm hover:bg-secondary">
          <FolderOpen className="w-4 h-4" /> Browse
        </button>
      </div>
      <div
        role="button"
        tabIndex={0}
        aria-label="Drop a PDF resume here to upload"
        onClick={handleBrowse}
        onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); handleBrowse(); } }}
        onDragEnter={handleDragEnter}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
        className={`flex flex-col items-center justify-center gap-1 px-3 py-4 border-2 border-dashed rounded-lg text-sm text-center cursor-pointer transition-colors ${
          dragging
            ? "border-primary bg-secondary text-foreground"
            : "border-border text-muted-foreground hover:bg-secondary"
        }`}
      >
        <Upload className="w-5 h-5" />
        <span>{dragging ? "Drop your PDF resume" : "Drag & drop a PDF resume here, or click to browse"}</span>
      </div>
      <div className="flex items-center gap-2 min-h-5">
        {dropError && <span className="text-xs text-red-600">{dropError}</span>}
        {!dropError && saving && <span className="flex items-center gap-1 text-xs text-muted-foreground"><Loader2 className="w-3 h-3 animate-spin" /> Saving...</span>}
        {!dropError && saved && <span className="flex items-center gap-1 text-xs text-green-600"><CheckCircle className="w-3 h-3" /> Saved ✓</span>}
        {!dropError && !saving && !saved && resumePath && <span className="text-xs text-muted-foreground">PDF file used for job applications</span>}
      </div>
    </div>
  );
}
