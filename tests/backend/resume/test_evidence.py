import asyncio
import json

import pytest
from fastapi import HTTPException

from resume.evidence import Analysis, validate, GenerateRequest, generate
from core.config import save_profile, load_profile


def sample():
    return Analysis(positioning='HR advice', requirements=[{'quote':'Formal investigations','kind':'required',
        'evidence_ids':['section-0'],'strength':'direct'}], edits=[{'section':0,'revised':'Managed HR investigations.',
        'evidence_ids':['section-0'],'reason':'Clarify scope'}])


def test_unknown_evidence_and_inferred_qualification_rejected():
    a=sample(); sections=[{'text':'Managed HR investigations.','section_type':'experience'}]
    with pytest.raises(ValueError,match='Unknown evidence'):
        validate(a,sections,{},'Formal investigations','Managed HR investigations.')
    with pytest.raises(ValueError,match='Inferred evidence'):
        validate(a,sections,{'section-0':{'statement':'HR','status':'inferred'}},'Formal investigations','Managed HR investigations.')


def test_locked_dates_and_new_numbers_rejected():
    a=sample();sections=[{'text':'HR Specialist | 2023 - 2026\nManaged HR investigations.','section_type':'experience'}]
    evidence={'section-0':{'statement':sections[0]['text'],'status':'source_resume'}}
    with pytest.raises(ValueError,match='locked'):
        validate(a,sections,evidence,'Formal investigations',sections[0]['text'])
    a.edits=[];a.letter='Reduced errors by 95%.';a.letter_evidence_ids=['section-0']
    with pytest.raises(ValueError,match='numbers'):
        validate(a,sections,evidence,'Formal investigations',sections[0]['text'])


def test_locked_line_accepts_bullet_and_whitespace_changes_only():
    source='- Provided HR coverage beginning in October 2024.'
    a=sample();a.edits[0].revised='• Provided HR coverage beginning\nin October 2024.'
    sections=[{'text':source,'section_type':'experience'}]
    evidence={'section-0':{'statement':source,'status':'source_resume'}}
    assert validate(a,sections,evidence,'Formal investigations',source)


def test_false_requirement_quote_rejected():
    with pytest.raises(ValueError,match='quote'):
        validate(sample(),[],{},'Recruitment','')


def test_profile_save_keeps_recoverable_previous_copy(data_dir):
    save_profile({'name':'Ary','skills':['HR']})
    save_profile({'name':'Ary','skills':['HR','Excel']})
    copies=list((data_dir/'config-backups').glob('candidate_profile-*.json'))
    assert len(copies)==1
    assert json.loads(copies[0].read_text())['skills']==['HR']
    assert load_profile()['skills']==['HR','Excel']


def test_stale_draft_cannot_replace_documents(monkeypatch):
    from resume import evidence
    job={'url':'https://example.test/job','status':'pending','evidence_draft':{'id':'old','revision':'old'}}
    monkeypatch.setattr(evidence.packs,'get_job',lambda _:job)
    monkeypatch.setattr(evidence,'inputs',lambda _: ([], '', {}, 'new'))
    with pytest.raises(HTTPException) as error:
        asyncio.run(generate(GenerateRequest(job_url=job['url'],draft_id='old')))
    assert error.value.status_code==400 and 'stale' in error.value.detail


def test_renderer_keeps_cross_role_attribution(tmp_path):
    import pymupdf
    from resume.render_documents import render_resume
    text='Employer | Contributions across roles\n2023 - Present\n- Documented work.'
    sections=[{'section_type':'experience','title':'Experience','text':text},
              {'section_type':'experience','title':'Page continuation','text':text}]
    path=tmp_path/'resume.pdf'
    render_resume(sections,{},'Candidate','City',path)
    with pymupdf.open(path) as pdf:
        content=''.join(p.get_text() for p in pdf)
        assert content.count('Employer | Contributions across roles')==2


def test_corrupt_profile_is_not_silently_reset(data_dir):
    source=data_dir/'candidate_profile.json';source.write_text('{broken')
    with pytest.raises(ValueError,match='preserved'):
        load_profile()
    assert source.read_text()=='{broken'
