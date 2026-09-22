"""Bounded on-access receipt retention; SOAR objects are never modified."""
from datetime import datetime, timedelta, timezone
from .core import Conflict, utcnow


def age_out_submissions(service):
    settings=service.settings()
    days=settings.get('retention_days',0)
    if type(days) is not int or not 1<=days<=3650: return
    now=datetime.fromisoformat(utcnow().replace('Z','+00:00'))
    # One batch per hour, shared by all search heads.
    slot='retention:'+str(int(now.timestamp()//3600))
    try:
        service.store.insert('ratelimits',{'_key':slot,'minute':int(now.timestamp()//60),'bucket':'retention'})
    except Conflict: return
    cutoff=(now-timedelta(days=days)).isoformat().replace('+00:00','Z')
    candidates=service.store.list('submissions',{'status':'submitted','updated_at':{'$lt':cutoff}},limit=100)
    removed=0
    for candidate in candidates:
        sid=candidate['_key']
        if service.store.get('locks','delivery:'+sid): continue
        record=service.store.get('submissions',sid)
        if not record or record.get('status')!='submitted': continue
        try: updated=datetime.fromisoformat(record['updated_at'].replace('Z','+00:00'))
        except (KeyError,ValueError,TypeError): continue
        if updated.tzinfo is None or updated>=now-timedelta(days=days): continue
        # Replace atomically at the SAME key. Never leave an absent key that
        # another search head could reuse to create a second SOAR event.
        service.store.put('submissions',{'_key':sid,'id':sid,'status':'expired','expired_at':now.astimezone(timezone.utc).isoformat().replace('+00:00','Z')})
        removed+=1
    if removed:
        service.audit({'username':'system'},'submissions.expired',{'count':removed,'retention_days':days,'cutoff':cutoff})
