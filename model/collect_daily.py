import sys,json,datetime as dt,concurrent.futures,hashlib,collections,math,copy,shutil,importlib.util,csv
from pathlib import Path
PROJECT=Path(__file__).resolve().parents[1]; OUT=PROJECT/'data/daily/20261101';RAW=OUT/'raw';RAW.mkdir(parents=True,exist_ok=True)
sys.path.insert(0,str(PROJECT/'model'))
from core import predict,own_rates
import subprocess,re
API='https://webapi.sporttery.cn/gateway/uniform/football/'
URL=API+'getMatchCalculatorV1.qry?channel=c&poolCode=ttg,had,hhad,crs,hafu'
def score(s):
    m=re.fullmatch(r'(\d+)\s*[:：-]\s*(\d+)',str(s or '').strip())
    return tuple(map(int,m.groups())) if m else None
def category(name):
    return '杯赛' if any(x in name for x in ('杯','冠军','预选','奥运','亚运','欧罗巴','欧协','欧洲联赛')) else '联赛'
def get(url,path):
    p=subprocess.run(['curl.exe','-sSL','--compressed','--fail','--max-time','30','-A','Mozilla/5.0','-e','https://www.sporttery.cn/',url],capture_output=True)
    if p.returncode:raise RuntimeError(p.stderr.decode(errors='replace')[-200:])
    d=json.loads(p.stdout)
    if str(d.get('errorCode'))!='0':raise ValueError('source error')
    path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(p.stdout)
    path.with_suffix('.meta.json').write_text(json.dumps(dict(url=url,received_at=dt.datetime.now(dt.timezone(dt.timedelta(hours=8))).isoformat(),sha256=hashlib.sha256(p.stdout).hexdigest())),encoding='utf-8')
    return d['value']
TZ=dt.timezone(dt.timedelta(hours=8))
def write(p,x):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(x,ensure_ascii=False,indent=2),encoding='utf-8')
def read(p):return json.loads(p.read_text(encoding='utf-8'))
def collect_boards():
    records=[];page=1
    while True:
        u=API+f'getUniformMatchResultV1.qry?matchBeginDate=2026-10-31&matchEndDate=2026-10-31&leagueId=&pageSize=100&pageNo={page}&isFix=0&matchPage=1&pcOrWap=1'
        d=get(u,RAW/f'results_{page}.json');records+=d.get('matchResult',[])
        if page>=d.get('pages',1):break
        page+=1
    write(OUT/'official-results.json',records)
    d=get(URL,RAW/'calculator.json');rows=[r for g in d.get('matchInfoList',[]) for r in g['subMatchList']]
    write(OUT/'fixtures.json',rows)
    print(json.dumps(dict(results=len(records),dates=dict(collections.Counter(r.get('businessDate') for r in rows)),result_example=records[:1],fixture_example=rows[:1]),ensure_ascii=False),flush=True)
def get_cached(url,path):
    return read(path)['value'] if path.exists() else get(url,path)
def collect_context():
    old=read(OUT/'archive-20261031.json');today=[r for r in read(OUT/'fixtures.json') if r['businessDate']=='2026-11-01']
    gold=read(OUT/'settled-history-reference.json')
    def past(r):
        mid=str(r['matchId']);h=get_cached(API+'getMatchHeadV1.qry?source=web&sportteryMatchId='+mid,RAW/f'{mid}_head.json')
        return dict(match_id=mid,head=h)
    def future(r):
        mid=str(r['matchId']);h=get_cached(API+'getMatchHeadV1.qry?source=web&sportteryMatchId='+mid,RAW/f'{mid}_head.json')
        assert str(h['sportteryMatchId'])==mid and str(h['sportteryHomeTeamId'])==str(r['homeTeamId']) and str(h['sportteryAwayTeamId'])==str(r['awayTeamId'])
        assert h['matchDateTime']==r['matchDate']+' '+r['matchTime'][:5]
        vals={n:get_cached(API+f'getMatchResultV1.qry?sportteryMatchId={mid}&termLimits=20&tournamentFlag=1&homeAwayFlag={flag}',RAW/f'{mid}_{n}.json') for flag,n in [(0,'all'),(1,'venue')]}
        latest=(dt.date.fromisoformat(r['matchDate'])-dt.timedelta(days=2)).isoformat();sides={};dups=0;conflicts=[]
        for side in ('home','away'):
            uid=str(h['uniformHomeTeamId' if side=='home' else 'uniformAwayTeamId']);merged={}
            for n in ('all','venue'):
                body=vals[n].get(side) or {};assert str((body.get('statistics') or {}).get('uniformTeamId'))==uid
                for x in body.get('matchList',[]):
                    sc=score(x.get('fullCourtGoal'));day=x.get('matchDate','')
                    if not sc or not day or day>latest or (dt.date.fromisoformat(r['matchDate'])-dt.date.fromisoformat(day)).days>365:continue
                    if str(x.get('tournamentId'))!=str(h['tournamentId']):continue
                    if category(r['leagueAllName'])!='联赛':
                        official=gold.get(str(x.get('sportteryMatchId')))
                        if not official or sc!=(int(official['home_goals_90']),int(official['away_goals_90'])):continue
                    ih=str(x.get('uniformHomeTeamId'))==uid;ia=str(x.get('uniformAwayTeamId'))==uid
                    if ih==ia:raise ValueError('bad historical team mapping')
                    rec=dict(date=day,age=(dt.date.fromisoformat(r['matchDate'])-dt.date.fromisoformat(day)).days,venue='home' if ih else 'away',goals_for=sc[0] if ih else sc[1],goals_against=sc[1] if ih else sc[0],own_season=str(x.get('seasonId'))==str(h['seasonId']),source_competition_id=str(x['tournamentId']),opponent_id=str(x.get('uniformAwayTeamId' if ih else 'uniformHomeTeamId')),opponent=x.get('awayTeamShortName' if ih else 'homeTeamShortName',''),context_match_id=str(x['matchId']),competition=x.get('tournamentShortName',''))
                    key=str(x['matchId'])
                    if key in merged:
                        dups+=1
                        if rec!=merged[key]:conflicts.append(dict(side=side,id=key))
                    merged[key]=rec
            sides[side]=sorted(merged.values(),key=lambda x:(x['date'],x['context_match_id']),reverse=True)
        if conflicts:raise ValueError('conflicting duplicate own history')
        c=dict(match_id=mid,date=r['matchDate'],competition=r['leagueAllName'],home_team=r['homeTeamAllName'],away_team=r['awayTeamAllName'],season_id=h['seasonId'],season=h['seasonName'],phase=h['phaseName'],latest_permitted_date=latest,kickoff=r['matchDate']+'T'+r['matchTime']+'+08:00',home_id=str(h['uniformHomeTeamId']),away_id=str(h['uniformAwayTeamId']),source_competition_id=str(h['tournamentId']),**sides)
        now=dt.datetime.now(TZ);p=predict(c) if dt.datetime.fromisoformat(c['kickoff'])>now else None
        row={k:r[k] for k in ('matchId','matchNumStr','businessDate','matchDate','matchTime','leagueAllName','leagueAbbName','homeTeamAllName','awayTeamAllName')}
        row.update(case=c,prediction=p,forecast_at=now.isoformat() if p else None,kickoff=c['kickoff'],verdict='watch' if p else 'missing',audit=dict(merged_duplicates=dups,identity_verified=True))
        return row
    errors=[];heads=[];forecasts=[]
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        fs={pool.submit(past,r):('past',r) for r in old['matches']}
        fs.update({pool.submit(future,r):('future',r) for r in today})
        for f in concurrent.futures.as_completed(fs):
            kind,r=fs[f]
            try:
                value=f.result();(heads if kind=='past' else forecasts).append(value)
            except Exception as e:errors.append(dict(kind=kind,id=r['matchId'],error=str(e)))
    write(OUT/'heads-yesterday.json',heads);write(OUT/'collection-errors.json',errors)
    forecasts.sort(key=lambda r:r['matchNumStr']);now=dt.datetime.now(TZ)
    write(OUT/'forecast.json',dict(business_date='2026-11-01',forecast_at=now.isoformat(),fixture_source_received_at=read(RAW/'calculator.meta.json')['received_at'],model_version='team-only-researched-v3',matches=forecasts))
    print(json.dumps(dict(heads=len(heads),today=len(forecasts),eligible=sum(bool(r['prediction']) for r in forecasts),errors=errors),ensure_ascii=True),flush=True)
if __name__=='__main__':
    if dt.datetime.now(TZ).date().isoformat()!='2026-11-01':raise SystemExit('This is the dated 2026-11-01 collector, not a generic daily runner')
    if '--context' in sys.argv:collect_context()
    else:collect_boards()
