from concurrent.futures import ThreadPoolExecutor

import pytest

from memory.store import MemoryStore
from resume.questions import sync_job_questions


def job(url='https://example.test/job'):
    return {'url':url,'status':'pending','company':'Example','title':'HR Partner',
            'fit_review':{'profile_questions':[{'topic':'Projects','evidence':'Lead HR projects',
                'question':'Which HR projects have you led?'}]},
            'evidence_draft':{'questions':['Which HR projects have you led?']}}


def test_both_question_paths_are_idempotent_and_answers_are_preserved(data_dir):
    store=MemoryStore();first=sync_job_questions(job(),store)
    assert first=={'added':1,'linked':2}
    row=store.qa_list()[0];assert row['answer']=='' and len(row['sources'])==2
    store.qa_update(row['id'],'I supported planning; no completed outcome yet.')
    assert sync_job_questions(job(),store)=={'added':0,'linked':0}
    assert sync_job_questions(job('https://example.test/second'),store)['added']==0
    assert store.qa_list()[0]['answer']=='I supported planning; no completed outcome yet.'
    assert len(store.qa_list()[0]['sources'])==4


def test_no_incorrect_merge_of_numbers_negation_or_ownership(data_dir):
    store=MemoryStore()
    for q in ['Do you have 5 years of HR experience?','Do you have 10 years of HR experience?',
              'Have you led an investigation?','Have you supported an investigation?',
              'Do you have CPHR?','Do you not have CPHR?',
              'Can you work nights?','Would you work nights?']:
        assert store.qa_add(q)
    assert len(store.qa_list())==8 and store.qa_auto_squash()==0


def test_merge_copies_existing_answer_and_refuses_conflicting_answers(data_dir):
    store=MemoryStore();a=store.qa_add('Question one');b=store.qa_add('Question two')
    store.qa_update(a['id'],'Confirmed detail')
    assert store.qa_merge(a['id'],b['id'])
    row=store.qa_list()[0];assert row['answer']=='Confirmed detail' and row['confirmed_by_user']
    assert store.qa_add('Question one') is None  # merged wording remains recognized
    assert store.qa_update(a['id'],'Stale edit') is False
    assert store.qa_list()[0]['answer']=='Confirmed detail'
    c=store.qa_add('Question three');store.qa_update(c['id'],'Different detail')
    with pytest.raises(ValueError,match='different answers'):
        store.qa_merge(c['id'],b['id'])
    assert {r['answer'] for r in store.qa_list()}=={'Confirmed detail','Different detail'}


def test_concurrent_replay_does_not_create_duplicate_rows(data_dir):
    stores=[MemoryStore(),MemoryStore()]
    def import_once(store):
        try:return sync_job_questions(job(),store)
        finally:store.close()
    with ThreadPoolExecutor(max_workers=2) as pool:
        results=list(pool.map(import_once,stores))
    assert sum(r['added'] for r in results)==1
    assert len(stores[0].qa_list())==1


def test_declined_jobs_do_not_generate_new_questions(data_dir):
    store=MemoryStore();item=job();item['status']='skipped'
    assert sync_job_questions(item,store)=={'added':0,'linked':0}
    assert store.qa_stats()['total']==0


def test_legacy_json_is_imported_from_data_dir_with_answers_intact(data_dir):
    import json
    (data_dir/'qa_repository.json').write_text(json.dumps({'Question française?':'Réponse confirmée'},ensure_ascii=False),encoding='utf-8')
    store=MemoryStore()
    assert store.qa_list()[0]['answer']=='Réponse confirmée'


def test_only_explicit_user_answers_become_profile_evidence(data_dir):
    from resume.questions import answered_profile_questions
    from core.shared_config import get_memory_store
    store=get_memory_store();sync_job_questions(job(),store)
    assert answered_profile_questions()==[]
    store.qa_update(store.qa_list()[0]['id'],'I supported the project; no completed outcome.')
    assert answered_profile_questions()[0]['statement']=='I supported the project; no completed outcome.'


def test_api_rejects_stale_answer_after_merge(data_dir,monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from api import memory
    store=MemoryStore();a=store.qa_add('First question');b=store.qa_add('Second question')
    store.qa_merge(a['id'],b['id'])
    monkeypatch.setattr(memory,'get_memory_store',lambda:store)
    app=FastAPI();app.include_router(memory.router);client=TestClient(app)
    assert client.put(f"/qa/{a['id']}",json={'answer':'Stale answer'}).status_code==409
    assert store.qa_list()[0]['answer']==''
