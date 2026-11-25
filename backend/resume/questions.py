"""Publish source-linked profile gaps without starting an application or inventing answers."""
import hashlib
import json
import logging

from core import db
from core.shared_config import get_memory_store

log=logging.getLogger(__name__)


def sync_job_questions(job, store=None):
    if job.get('status') in ('skipped','applied'):
        return {'added':0,'linked':0}
    store=store or get_memory_store()
    items=[('collection',q) for q in (job.get('fit_review') or {}).get('profile_questions',[])]
    items += [('tailoring',{'question':q,'topic':'Tailoring gap','evidence':''})
              for q in (job.get('evidence_draft') or {}).get('questions',[])]
    added=linked=0
    for kind,q in items:
        question=q.get('question','').strip()
        if not question:
            continue
        if len(question)>8000:
            raise ValueError('Profile question is too long; original remains on the job.')
        evidence=q.get('evidence','')
        key=hashlib.sha256(json.dumps([kind,job['url'],store._normalize_qa(question),evidence],ensure_ascii=False).encode()).hexdigest()
        result=store.qa_import_profile_question(question,source_key=key,kind=kind,job_url=job['url'],
            job_label=f"{job.get('company','')} — {job.get('title','')}",topic=q.get('topic',''),evidence=evidence)
        added+=result['created'];linked+=result['linked']
    return {'added':added,'linked':linked}


def publish_job_questions(job):
    try:
        result=sync_job_questions(job)
        if job.get('qa_sync_error'):
            db.update_job(job['url'],qa_sync_error=None)
        return {**result,'errors':0}
    except Exception as error:
        log.warning('Profile questions remain on job for retry: %s',error)
        db.update_job(job['url'],qa_sync_error=str(error))
        return {'added':0,'linked':0,'errors':1}


def sync_saved_questions():
    totals={'added':0,'linked':0,'errors':0}
    for job in db.read_jobs().values():
        result=publish_job_questions(job)
        for key in totals:totals[key]+=result[key]
    return totals


def answered_profile_questions():
    return [{'id':f"qa-{q['id']}",'question':q['question'],'statement':q['answer'],
             'status':'confirmed','source':'User answer in Q&A'}
            for q in get_memory_store().qa_list() if q.get('confirmed_by_user') and (q['answer'] or '').strip()
            and (q['question_type']=='profile' or any(s['kind'] in ('collection','tailoring') for s in q.get('sources',[])))]
