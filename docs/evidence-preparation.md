# Evidence-led application preparation

Open a job's Application documents panel and select Review evidence and draft changes.
The analysis maps quoted posting requirements to source resume sections and saved evidence,
proposes edits, and asks up to five questions. Unknown information remains a gap. Confirmed
answers are saved to the profile; analyze again after changing the evidence. Optional draft
direction can request a different emphasis or shorter wording.

Inspect the before/after text, then create PDFs from the draft. Review the final files and
attachment format before approving that exact document set. The main resume is never edited
by this flow. Profile, posting, provider configuration and policy revisions invalidate stale
drafts. PDF hashes and input fingerprints protect reviewed packs and application attempts.
Evidence references and number checks do not replace human review of meaning and ownership.

The runtime writing rules in `backend/resume/evidence.py` adapt Reactive Resume's content-guide,
bullet-writer and tailor skills. Source hashes and MIT license are in `backend/resume/policy`.
No instructions are downloaded at generation time. Bump `POLICY` for released behavior changes.
ReportLab renders the final resume and letter; existing packaging handles separate or combined
attachments. The older tailoring path remains available.

Profile/settings writes retain prior copies under `config-backups`. Backend startup makes one
daily local snapshot of databases, configuration and documents under `recovery-backups`.
Backups do not automatically overwrite live files. Invalid profile/settings JSON raises an error
instead of silently replacing it with defaults. Inspect and restore an appropriate backup when needed.

Development imports do not publish a new connection token; duplicate direct launches refuse an
occupied backend port. Run tests with an isolated `LANGHIRE_DATA_DIR`. Personal output, temporary
trial data and private plans must remain outside commits.
