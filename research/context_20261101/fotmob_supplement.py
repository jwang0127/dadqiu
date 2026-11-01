import concurrent.futures,datetime as dt,json,statistics
from collect_expanded_context import D,RAW,P,TZ,read,write,fetch
FIDS={1:5803646,2:6503833,3:5803642,4:6503834,5:1000017574,6:5781792,9:5107649,10:5781794,11:5105036,15:5781789,20:5887663,24:1000019468,25:5071483}
def day(s):return dt.datetime.fromisoformat(s.replace('Z','+00:00')).astimezone(TZ).date().isoformat()
def main():
    board=read(P/'data/today.json');games={}
    for key in ('fotmob_data_matches','fotmob_data_matches_next'):
        for l in read(RAW/(key+'.json'))['leagues']:
            for m in l.get('matches',[]):games[int(m['id'])]=(l,m)
    tasks=[];mapping=[]
    for r in board['matches']:
        n=int(r['matchNumStr'][-3:])
        if n not in FIDS:continue
        l,m=games[FIDS[n]]
        mapping.append(dict(match_id=str(r['matchId']),number=r['matchNumStr'],provider_match_id=str(m['id']),provider_competition_id=l.get('primaryId',l['id']),provider_phase_id=l['id'],provider_competition=l['name'],home=m['home'],away=m['away']))
        for side in ('home','away'):
            tid=m[side]['id'];tasks.append((f'fotmob_team_{tid}',f'https://www.fotmob.com/api/data/teams?id={tid}','json','https://www.fotmob.com/'))
        tasks.append((f'fotmob_current_{m["id"]}',f'https://www.fotmob.com/api/data/matchDetails?matchId={m["id"]}','json','https://www.fotmob.com/'))
    def job(j):
        try:fetch(*j);return dict(name=j[0],ok=True)
        except Exception as e:return dict(name=j[0],ok=False,error=str(e))
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:results=list(pool.map(job,tasks))
    write(D/'fotmob-identities.json',mapping);write(D/'fotmob-team-downloads.json',results)
    joins=[];deep={};cup=[]
    for m in mapping:
        r=next(r for r in board['matches'] if str(r['matchId'])==m['match_id']);c=r['case']
        for side in ('home','away'):
            tid=m[side]['id'];p=RAW/f'fotmob_team_{tid}.json'
            if not p.exists():continue
            d=read(p);assert str(d['details']['id'])==str(tid)
            allowed={m['provider_competition_id']}
            if r['leagueAbbName']=='韩职':allowed.add(d['details']['primaryLeagueId'])
            fs=d.get('fixtures',{}).get('allFixtures',{}).get('fixtures',[])
            rows=r['prediction'][side+'_inputs']['rows'] if r['prediction'] else c[side][:12]
            def matching(h):
                return [f for f in fs if f.get('status',{}).get('finished') and day(f['status']['utcTime'])==h['date'] and str(f[h['venue']]['id'])==str(tid) and (f['home']['score'],f['away']['score'])==((h['goals_for'],h['goals_against']) if h['venue']=='home' else (h['goals_against'],h['goals_for'])) and f.get('tournament',{}).get('leagueId') in allowed]
            if any(not matching(h) for h in rows):
                try:
                    previous=fetch(f'fotmob_team_{tid}_previous',f'https://www.fotmob.com/api/data/teams?id={tid}&season=2025%2F2026','json','https://www.fotmob.com/')
                    more=previous.get('fixtures',{}).get('allFixtures',{}).get('fixtures',[]);fs=list({str(f['id']):f for f in fs+more}.values())
                except Exception:pass
            for h in rows:
                found=matching(h);f=found[0] if len(found)==1 else None
                joins.append(dict(match_id=m['match_id'],side=side,team_id=str(tid),team=m[side]['name'],history=h,fotmob_id=str(f['id']) if f else None,fixture=f,rule='Explicit club mapping, same competition ID, Beijing date, venue, goals'))
                if f:deep[str(f['id'])]=f
            if r['matchNumStr']=='周日024':
                for f in fs:
                    if f.get('status',{}).get('finished') and f['tournament']['leagueId']==m['provider_competition_id'] and day(f['status']['utcTime'])<c['date']:
                        cup.append(dict(match_id=m['match_id'],side=side,team_id=str(tid),fixture=f,usage='research only; 90-minute period must be independently verified'));deep[str(f['id'])]=f
    write(D/'fotmob-own-history-joins.json',joins);write(D/'fotmob-extra-cup-history.json',cup)
    print(json.dumps(dict(own_observations=len(joins),matched=sum(bool(x['fotmob_id']) for x in joins),individual_matches=len(deep),extra_cup=len(cup)),ensure_ascii=True),flush=True)
    tasks=[(f'fotmob_match_{i}',f'https://www.fotmob.com/api/data/matchDetails?matchId={i}','json','https://www.fotmob.com/') for i in deep]
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        results=[]
        for i,x in enumerate(pool.map(job,tasks),1):
            results.append(x)
            if i%40==0:print('supplementary matches',i,'/',len(tasks),flush=True)
    write(D/'fotmob-history-downloads.json',results);print(json.dumps(dict(downloaded=sum(x['ok'] for x in results),failures=[x for x in results if not x['ok']]),ensure_ascii=True),flush=True)
if __name__=='__main__':main()
