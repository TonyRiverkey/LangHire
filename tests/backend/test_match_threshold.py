import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from core import db
from core.config import save_settings, save_profile
from engine import matching


@pytest.mark.parametrize('score,skipped',[(49,True),(50,False),(51,False)])
def test_threshold_is_strictly_below(score,skipped,monkeypatch):
    monkeypatch.setattr(matching,'match_score',lambda *_:score)
    result=matching.score_updates({'status':'pending'},{},50)
    assert (result.get('status')=='skipped') is skipped


@pytest.mark.parametrize('status',['applied','in_progress','skipped'])
def test_history_active_attempts_and_manual_skips_keep_status(status,monkeypatch):
    monkeypatch.setattr(matching,'match_score',lambda *_:10)
    result=matching.score_updates({'status':status},{},50)
    assert result=={'match_score':10}


def test_only_automatic_skip_is_restored_when_score_improves(monkeypatch):
    monkeypatch.setattr(matching,'match_score',lambda *_:50)
    result=matching.score_updates({'status':'skipped','skip_source':'match_threshold','skip_previous_status':'needs_input'},{},50)
    assert result['status']=='needs_input' and result['skip_source'] is None


def test_rescore_applies_policy_and_retains_job_details(data_dir,monkeypatch):
    from api import jobs
    save_settings({'minimum_match_score':50});save_profile({'name':'Candidate'})
    job={'url':'https://example.test/a','title':'Role','status':'pending','description':'Original description','application_documents':{'reviewed':False}}
    db.add_jobs([job]);monkeypatch.setattr(matching,'match_score',lambda *_:49)
    app=FastAPI();app.include_router(jobs.router);client=TestClient(app)
    assert client.post('/jobs/rescore').json()['rescored']==1
    updated=db.get_job(job['url'])
    assert updated['status']=='skipped' and updated['match_score']==49
    assert updated['description']==job['description'] and updated['application_documents']==job['application_documents']
    assert '49%' in updated['skip_reason']


def test_low_match_cannot_bypass_document_application_guard(data_dir,monkeypatch):
    from resume.application_documents import validated_documents
    save_settings({'minimum_match_score':50});save_profile({})
    monkeypatch.setattr(matching,'match_score',lambda *_:49)
    with pytest.raises(ValueError,match='below the 50%'):
        validated_documents({'status':'pending','application_documents':{'reviewed':True}})


def test_exact_threshold_reaches_normal_review_gate(data_dir,monkeypatch):
    from resume.application_documents import validated_documents
    save_settings({'minimum_match_score':50});save_profile({})
    monkeypatch.setattr(matching,'match_score',lambda *_:50)
    with pytest.raises(ValueError,match='review the application documents'):
        validated_documents({'status':'pending','application_documents':{'reviewed':False}})
