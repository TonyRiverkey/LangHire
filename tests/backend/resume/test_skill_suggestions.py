from types import SimpleNamespace
from unittest.mock import AsyncMock

from resume import skill_suggestions as skills


async def test_suggestions_require_posting_evidence_and_exclude_existing_skills(monkeypatch):
    response = skills.SkillSuggestions(suggestions=[
        skills.SkillSuggestion(skill="SQL", evidence="SQL knowledge", reason="Required"),
        skills.SkillSuggestion(skill="Airflow", evidence="Airflow orchestration", reason="Fabricated"),
        skills.SkillSuggestion(skill="dbt", evidence="experience with dbt is preferred", reason="Preferred"),
    ])
    model = SimpleNamespace(ainvoke=AsyncMock(return_value=SimpleNamespace(completion=response)))
    monkeypatch.setattr(skills, "create_llm", lambda _: model)
    result = await skills.suggest_skills("Strong SQL knowledge. Experience with dbt is preferred.", ["sql"], {})
    assert [item["skill"] for item in result] == ["dbt"]
