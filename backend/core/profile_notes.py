"""Lossless consolidation of repeated evidence snapshots with an external recovery archive."""
import hashlib
import json
import uuid

from core.config import get_data_dir, load_profile, save_profile, _save_json


def consolidate_text(notes):
    snapshots=[];plain=[];latest={};history={}
    for line in notes.splitlines():
        if line.startswith('Confirmed resume evidence') and ': {' in line:
            label,raw=line.split(': ',1)
            snapshot=json.loads(raw)
            if not isinstance(snapshot,dict) or not all(isinstance(k,str) and isinstance(v,str) for k,v in snapshot.items()):
                raise ValueError('Unsupported evidence snapshot; notes were not changed.')
            snapshots.append({'source':label,'facts':snapshot})
            for key,value in snapshot.items():
                latest[key]=value
                history.setdefault(key,[]).append({'source':label,'statement':value})
        elif line.strip() and line.strip() not in plain:
            plain.append(line.strip())
    if not snapshots:
        return notes,{'snapshots':[],'current_facts':{},'history':{},'plain_lines':plain}
    result='\n'.join([*plain,'Confirmed resume evidence (consolidated): '+json.dumps(latest,sort_keys=True,ensure_ascii=False)])
    # Verify the active record exactly retains the latest value for every topic.
    assert json.loads(result.splitlines()[-1].split(': ',1)[1])==latest
    return result,{'snapshots':snapshots,'current_facts':latest,'history':history,'plain_lines':plain}


def consolidate_profile_notes():
    original=load_profile();notes=original.get('notes','')
    revised,audit=consolidate_text(notes)
    if revised==notes:
        return {'changed':False,'before_chars':len(notes),'after_chars':len(notes)}
    archive=get_data_dir()/'notes_archives'/f'{uuid.uuid4().hex}.json'
    _save_json(archive,{'original_profile':original,'original_notes_sha256':hashlib.sha256(notes.encode()).hexdigest(),**audit})
    if load_profile()!=original:
        raise ValueError('Profile changed during consolidation; saved notes were not replaced.')
    save_profile({**original,'notes':revised})
    return {'changed':True,'before_chars':len(notes),'after_chars':len(revised),
            'topics':len(audit['current_facts']),'snapshots':len(audit['snapshots']),'archive':str(archive)}
