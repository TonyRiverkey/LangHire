# Application documents and resume review

Goal: each selected job has reviewed, job-specific documents, with immutable PDFs retained for each application attempt. Support separate letters and cover-letter-first combined PDFs. Display salary and help the user incorporate only confirmed skill evidence into a new main-resume draft.

Constraints: isolated worktree; do not restart the user's app or alter the other agent's checkout. Preserve source resumes and previous application files. Do not submit real applications during tests. Push the feature branch after verification; no deployment.

Source of truth: saved job description, candidate profile, configured source PDF, and generated PDF bytes. Review must become invalid if those inputs change. Unexpected employer attachment requirements stop automation rather than generating an unreviewed attachment.

Verification: isolated FastAPI router tests for job isolation, document requirements, combined PDF order, stale review rejection, retained attempts, and safe file serving; main-resume draft/activation tests with fake AI; component tests for review and confirmed skill evidence; TypeScript and lint; PDF rendering and an isolated UI smoke test. Never import the production backend against the real app-data directory in tests.

Coordination: another agent owns collection, job capture and review metadata. Keep new features in separate modules/components; limit shared edits in backend/main.py and PendingTab.tsx, and reconcile current remote changes before pushing.
