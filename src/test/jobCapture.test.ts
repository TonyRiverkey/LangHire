import { readFileSync } from "node:fs";
import { beforeEach, expect, it } from "vitest";

const source = readFileSync("backend/core/job_capture.py", "utf8");
const script = source.match(/CAPTURE_SCRIPT = r"""([\s\S]*?)"""/)![1];
const capture = () => new Function(`return (${script})()`)();

beforeEach(() => { document.body.replaceChildren(); });

it("captures the selected panel and full DOM description without copying other page text", () => {
  document.body.innerHTML = `
    <input id="jobs-search-box-location-id" value="Victoria, British Columbia, Canada">
    <div class="job-details-jobs-unified-top-card__container--two-pane">
      <a href="https://www.linkedin.com/jobs/view/1234567890/"><h1 class="job-details-jobs-unified-top-card__job-title">HR Business Partner</h1></a>
      <div class="job-details-jobs-unified-top-card__company-name">Example Employer</div>
      <div class="job-details-jobs-unified-top-card__primary-description-container">Victoria, BC</div>
      <button class="jobs-apply-button">Easy Apply</button>
    </div>
    <div id="job-details">Beginning of posting. <span>Final qualifications and salary.</span></div>
    <aside>Recommended payroll job. Unrelated salary.</aside>`;
  const result = capture();
  expect(result.title).toBe("HR Business Partner");
  expect(result.company).toBe("Example Employer");
  expect(result.location).toBe("Victoria, BC");
  expect(result.search_location).toContain("Victoria");
  expect(result.easy_apply).toBe(true);
  expect(result.source_job_url).toBe("https://www.linkedin.com/jobs/view/1234567890/");
  expect(result.description).toContain("Final qualifications and salary.");
  expect(result.description).not.toContain("Unrelated salary");
});

it("does not substitute the whole page when the selected description is unavailable", () => {
  document.body.innerHTML = "<main>Other job recommendations and unrelated information</main>";
  expect(capture().description).toBe("");
});
