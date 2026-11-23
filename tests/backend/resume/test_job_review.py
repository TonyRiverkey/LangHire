from datetime import date
from types import SimpleNamespace
from unittest.mock import AsyncMock

from resume.job_review import JobReview, Salary, ProfileQuestion, validate_review, review_job


def posting():
    return {"title": "HR Business Partner", "company": "Example", "location": "Victoria, BC",
            "search_location": "Victoria, BC", "source_metadata": "HR Business Partner, Victoria, BC",
            "description": "CPHR preferred. CAD 68,000 to 80,000 per year. Workday experience. "
                           "Closing Date: November 20, 2026. Combine cover letter and resume into one PDF."}


def review(**changes):
    return JobReview(role_fit="relevant", role_evidence="HR Business Partner", role_reason="Matches target role.",
                     location_fit="within_target", location_evidence="Victoria, BC", **changes)


PROFILE = {"target_job_titles": ["HR Business Partner"],
           "salary_expectation": {"min": 80000, "currency": "CAD"}}


def test_only_posting_supported_questions_and_instructions_survive():
    result = validate_review(review(profile_questions=[
        ProfileQuestion(topic="CPHR", evidence="CPHR preferred", question="Are you pursuing CPHR?"),
        ProfileQuestion(topic="Payroll", evidence="Payroll certification required", question="Do you have it?")],
        cover_letter_instructions="Combine cover letter and resume into one PDF."), posting(), PROFILE)
    assert [q["topic"] for q in result["profile_questions"]] == ["CPHR"]
    assert result["cover_letter_instructions"]
    assert "skills" not in result


def test_supported_salary_at_ceiling_and_closed_date():
    result = validate_review(review(salary=Salary(evidence="CAD 68,000 to 80,000 per year", minimum=68000,
        maximum=80000, currency="CAD", period="annual"), closing_date=date(2026, 11, 20),
        closing_evidence="Closing Date: November 20, 2026"), posting(), PROFILE, today=date(2026, 11, 21))
    assert result["salary_fit"] == "at_or_below_minimum"
    assert result["closed"] is True


def test_invented_numbers_currency_and_pay_period_remain_unknown():
    for salary in [Salary(evidence="Made up salary", minimum=90000, currency="CAD", period="annual"),
                   Salary(evidence="CPHR preferred", minimum=90000, currency="CAD", period="annual")]:
        result = validate_review(review(salary=salary), posting(), PROFILE)
        assert result["salary_fit"] == "unknown"
        assert result["salary"]["minimum"] is None
        assert result["salary"]["currency"] == ""


def test_unsupported_fit_is_uncertain():
    value = review()
    value.role_evidence = "Completely different role"
    value.location_evidence = "Vancouver"
    result = validate_review(value, posting(), PROFILE)
    assert result["role_fit"] == "uncertain"
    assert result["location_fit"] == "uncertain"


def test_unknown_salary_and_unsupported_closing_date_are_not_invented():
    result = validate_review(review(closing_date=date(2026, 10, 1), closing_evidence="CPHR preferred"), posting(), PROFILE)
    assert result["salary_fit"] == "unknown"
    assert result["closing_date"] is None
    assert result["closed"] is False


async def test_copilot_factory_model_is_used_without_contact_details_or_profile_writes():
    profile = {**PROFILE, "name": "Private Name", "email": "private@example.test", "skills": ["Employee Relations"]}
    llm = SimpleNamespace(ainvoke=AsyncMock(return_value=SimpleNamespace(completion=review())))
    original = profile.copy()
    result = await review_job(posting(), profile, llm)
    assert result["role_fit"] == "relevant"
    prompt = llm.ainvoke.call_args.args[0][0].content
    assert "Employee Relations" in prompt
    assert "private@example.test" not in prompt
    assert "Private Name" not in prompt
    assert profile == original


async def test_fit_evidence_is_corrected_once_without_loosening_validation():
    invalid=review();invalid.location_evidence='Located in Victoria, British Columbia'
    llm=SimpleNamespace(ainvoke=AsyncMock(side_effect=[SimpleNamespace(completion=invalid),SimpleNamespace(completion=review())]))
    result=await review_job(posting(),PROFILE,llm)
    assert result['location_fit']=='within_target' and llm.ainvoke.await_count==2
    llm=SimpleNamespace(ainvoke=AsyncMock(return_value=SimpleNamespace(completion=invalid)))
    result=await review_job(posting(),PROFILE,llm)
    assert result['location_fit']=='uncertain' and llm.ainvoke.await_count==2
