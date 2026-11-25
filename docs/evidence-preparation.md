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

The Automation setting Minimum match score retains below-threshold queued jobs as Skipped,
with a reason. The comparison is strict: a score equal to the minimum remains eligible.
Zero disables the rule. Collection, manual additions, description recovery and rescoring use
the same policy. Applied history and active attempts keep their status; manually skipped
jobs are not automatically restored. Only skips made by this policy can be restored after
their score improves. Document approval and new application attempts also enforce the current
minimum, including when a stale UI or manual status change would otherwise bypass it.

## Profile questions and evidence notes

Successful LinkedIn collection and resume analysis publish profile gaps to Q&A without starting an
application. Startup also backfills saved active jobs; the Q&A Sync saved job questions button retries
that import. Skipped and already-applied jobs are not used to create new profile-gap questions.
Every question retains its job, review/preparation origin, original wording and supporting excerpt.
Repeated imports reuse source keys and canonical questions, including earlier merged wordings.

Automatic matching ignores punctuation and limited conversational filler. Numbers, negation,
tools and ownership verbs remain significant. Related but distinct requirements stay separate unless
explicitly merged. A merge copies an existing answer into an empty target and refuses different
nonempty answers. Context and original question rows are retained. No unanswered profile question
is auto-filled. Only answers explicitly saved by the user become profile evidence for later reviews
and resume drafts; a changed answer invalidates an older preparation context.

POST `/profile/notes/consolidate` condenses repeated evidence snapshots, retaining the most recent
statement for every topic and unique surrounding notes. The full original profile and every dated
snapshot remain under the private data directory's `notes_archives`. The operation is idempotent
and refuses to replace a profile changed during consolidation. It never changes the resume PDF.
Existing document files remain available, but preparation drafts require refresh after evidence-context
changes. These archives and candidate data must never be committed.
