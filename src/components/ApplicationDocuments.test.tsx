import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import ApplicationDocuments from "./ApplicationDocuments";
import { getApplicationPdf } from "../lib/api";
import { analyzeDocuments, generateDocuments, getDocuments, prepareDocuments, reviewDocuments, type DocumentState } from "../lib/applicationDocuments";

vi.mock("../lib/api", () => ({ getApplicationPdf: vi.fn() }));
vi.mock("../lib/applicationDocuments", () => ({ analyzeDocuments: vi.fn(), generateDocuments: vi.fn(), confirmEvidence: vi.fn(), getDocuments: vi.fn(), prepareDocuments: vi.fn(), reviewDocuments: vi.fn() }));
const prepared: DocumentState = {
  required_mode: "combined", ready: false, message: "Review the documents", attempts: [],
  current: { mode: "combined", letter: "Dear Alpha", reviewed: false, files: [{ kind: "combined", name: "Combined application PDF", asset: "version/application.pdf" }] },
};
beforeEach(() => {
  vi.mocked(getDocuments).mockResolvedValue({ ...prepared, current: null });
  vi.mocked(prepareDocuments).mockResolvedValue(prepared);
  vi.mocked(reviewDocuments).mockResolvedValue({ ...prepared, ready: true, message: "Reviewed documents are ready." });
  vi.mocked(getApplicationPdf).mockResolvedValue(new Blob(["%PDF-1.4"], { type: "application/pdf" }));
  URL.createObjectURL = vi.fn(() => "blob:preview");
  URL.revokeObjectURL = vi.fn();
});
describe("ApplicationDocuments", () => {
  it("shows cited draft changes and leaves generated files unapproved", async () => {
    const draft = {id:"draft-1",positioning:"Operational HR",questions:["Which project did you own?"],
      requirements:[{quote:"Formal investigations",kind:"required",strength:"direct",evidence_ids:["source"],gap:""}],
      edits:[{section:0,revised:"Revised HR summary",reason:"Emphasize investigations",evidence_ids:["source"]}],
      evidence:{source:{statement:"Conducted investigations",status:"source_resume"}},before:{"0":"Original summary"},letter:""};
    vi.mocked(analyzeDocuments).mockResolvedValue({...prepared,current:null,evidence_draft:draft});
    vi.mocked(generateDocuments).mockResolvedValue({...prepared,evidence_draft:draft});
    const user=userEvent.setup();render(<ApplicationDocuments jobUrl="https://example.com/a" />);
    await user.click(screen.getByText("Application documents"));
    await user.click(await screen.findByRole("button",{name:"Review evidence and draft changes"}));
    expect(await screen.findByText("Formal investigations (required)")).toBeInTheDocument();
    await user.click(screen.getByText("Emphasize investigations"));
    expect(screen.getByText("Original summary")).toBeInTheDocument();
    expect(screen.getByText("Revised HR summary")).toBeInTheDocument();
    await user.click(screen.getByRole("button",{name:"Create PDFs from this draft"}));
    expect(generateDocuments).toHaveBeenCalledWith("https://example.com/a","draft-1","auto");
    expect(await screen.findByRole("button",{name:"Approve documents for application"})).toBeDisabled();
    expect(reviewDocuments).not.toHaveBeenCalled();
  });
  it("prepares per-job files, previews a PDF, and requires explicit review", async () => {
    const user = userEvent.setup();
    render(<ApplicationDocuments jobUrl="https://example.com/a" />);
    await user.click(screen.getByText("Application documents"));
    await waitFor(() => expect(getDocuments).toHaveBeenCalledWith("https://example.com/a"));
    await user.click(screen.getByRole("button", { name: "Prepare application PDFs" }));
    expect(prepareDocuments).toHaveBeenCalledWith("https://example.com/a", "auto", undefined);
    const approve = await screen.findByRole("button", { name: "Approve documents for application" });
    expect(approve).toBeDisabled();
    await user.click(screen.getByRole("button", { name: "Preview Combined application PDF" }));
    expect(await screen.findByTitle("Combined application PDF")).toHaveAttribute("src", "blob:preview");
    await user.click(screen.getByRole("checkbox"));
    await user.click(approve);
    expect(reviewDocuments).toHaveBeenCalledWith("https://example.com/a", undefined);
    expect(await screen.findByText("Reviewed documents are ready.")).toBeInTheDocument();
  });
  it("keeps edited letter text separate until PDF preparation", async () => {
    vi.mocked(getDocuments).mockResolvedValue(prepared);
    const user = userEvent.setup();
    const onDirtyChange = vi.fn();
    render(<ApplicationDocuments jobUrl="https://example.com/b" onDirtyChange={onDirtyChange} />);
    await user.click(screen.getByText("Application documents"));
    const letter = await screen.findByLabelText("This job’s cover letter");
    await user.clear(letter); await user.type(letter, "Dear Beta");
    expect(onDirtyChange).toHaveBeenLastCalledWith(true);
    await user.click(screen.getByRole("checkbox"));
    expect(screen.getByRole("button", { name: "Approve documents for application" })).toBeDisabled();
    await user.click(screen.getByRole("button", { name: "Prepare application PDFs" }));
    expect(prepareDocuments).toHaveBeenCalledWith("https://example.com/b", "auto", "Dear Beta");
  });
  it("shows retained attempt files in application history", async () => {
    vi.mocked(getDocuments).mockResolvedValue({ ...prepared, attempts: [{ ...prepared.current!, id: "old", started_at: "2026-11-21T12:00:00Z", status: "applied" }] });
    const user = userEvent.setup();
    render(<ApplicationDocuments jobUrl="https://example.com/a" historyOnly />);
    await user.click(screen.getByText("Application files and history"));
    await user.click(await screen.findByText(/— applied/));
    expect(screen.getByRole("button", { name: "Download Combined application PDF" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Prepare application PDFs" })).not.toBeInTheDocument();
  });
});
