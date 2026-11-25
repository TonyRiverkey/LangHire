import json
from pathlib import Path

from core.config import save_profile,load_profile
from core.profile_notes import consolidate_text,consolidate_profile_notes


def test_consolidation_retains_current_facts_plain_notes_and_every_prior_version():
    notes='Preference: permanent only.\nConfirmed resume evidence (old): '+json.dumps({'coverage':'Estimated 18 months','metric':'About 30 employees'})+'\nConfirmed resume evidence (new): '+json.dumps({'coverage':'Across vacancies since October 2024; not a continuous appointment','credential':'Enrolled, starts January 2027'})+'\nPreference: permanent only.'
    result,audit=consolidate_text(notes)
    assert audit['current_facts']=={'coverage':'Across vacancies since October 2024; not a continuous appointment','metric':'About 30 employees','credential':'Enrolled, starts January 2027'}
    assert result.count('Preference: permanent only.')==1
    assert len(audit['history']['coverage'])==2
    assert consolidate_text(result)[0]==result


def test_profile_only_changes_notes_and_archive_preserves_original(data_dir):
    notes='Confirmed resume evidence (a): {"skill":"User confirmed Excel"}\nConfirmed resume evidence (b): {"skill":"User confirmed Excel"}'
    save_profile({'name':'Candidate','skills':['Excel'],'notes':notes,'confirmed_evidence':[{'id':'keep','statement':'Exact fact'}]})
    before=load_profile();result=consolidate_profile_notes();after=load_profile()
    assert result['changed'] and {k:v for k,v in after.items() if k!='notes'}=={k:v for k,v in before.items() if k!='notes'}
    assert json.loads(Path(result['archive']).read_text(encoding='utf-8'))['original_profile']==before
    assert not consolidate_profile_notes()['changed']
