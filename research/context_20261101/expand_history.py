import collections,concurrent.futures,datetime as dt,json,sys,unicodedata
from pathlib import Path
from collect_expanded_context import B,P,D,RAW,TZ,read,write,fetch
CURRENT={1:('jpn.1','401877578'),3:('jpn.1','401877581'),5:('aus.1','401892145'),6:('ned.1','401875560'),7:('ita.1','401875002'),8:('esp.1','401882821'),9:('swe.1','401842868'),10:('ned.1','401875559'),11:('nor.1','401843474'),12:('ita.1','401874782'),13:('ita.1','401874983'),14:('ger.1','401884750'),15:('ned.1','401875557'),16:('eng.1','401879246'),17:('ger.1','401884752'),18:('ita.1','401874968'),19:('esp.1','401882823'),20:('por.1','401885411'),21:('ita.1','401874949'),22:('fra.1','401876417'),23:('esp.1','401882826'),25:('usa.1','761932')}
U_LEAGUE={'eng.1':'EPL','esp.1':'La_liga','ger.1':'Bundesliga','ita.1':'Serie_A','fra.1':'Ligue_1'}
U_ALIAS={'1. FC Union Berlin':'Union Berlin','Hamburg SV':'Hamburger SV'}
def localdate(s):return dt.datetime.fromisoformat(s.replace('Z','+00:00')).astimezone(TZ).date().isoformat()
def goal(x):return int(x['score']['value']) if isinstance(x.get('score'),dict) else int(x['score'])
def main():
    board=read(P/'data/today.json');events={};league_indexes=collections.defaultdict(list);under=[]
    for path in RAW.glob('espn_board_*.json'):
        league=path.stem.removeprefix('espn_board_').rsplit('_',1)[0]
        for e in read(path).get('events',[]):
            events[(league,str(e['id']))]=e
    for (l,eid),e in events.items():league_indexes[l].append(e)
    for path in RAW.glob('understat_*.json'):
        if path.name.endswith('.meta.json'):continue
        league=path.stem.removeprefix('understat_').rsplit('_',1)[0]
        for r in read(path)['dates']:
            if not r['isResult'] or any(r['xG'].get(s) is None for s in ('h','a')):continue
            under.append(dict(league=league,id=str(r['id']),date=localdate(r['datetime']+'Z'),home=r['h']['title'],away=r['a']['title'],home_goals=int(r['goals']['h']),away_goals=int(r['goals']['a']),home_xg=float(r['xG']['h']),away_xg=float(r['xG']['a'])))
    unique={x['id']:x for x in under};under=list(unique.values())
    joins=[];mapping=[];conflicts=[];jobs={}
    for r in board['matches']:
        c=r['case'];mid=c['match_id'];n=int(r['matchNumStr'][-3:]);cur=CURRENT.get(n)
        if not cur:continue
        league,eid=cur;e=events[(league,eid)];sides={x['homeAway']:x for x in e['competitions'][0]['competitors']}
        delta=(dt.datetime.fromisoformat(e['date'].replace('Z','+00:00'))-dt.datetime.fromisoformat(r['kickoff'])).total_seconds()/60
        mapping.append(dict(match_id=mid,league=league,espn_id=eid,home=sides['home']['team']['displayName'],away=sides['away']['team']['displayName'],kickoff_difference_minutes=delta,kickoff_agrees=delta==0))
        jobs['espn_current_'+eid]=(f'espn_current_{eid}',f'https://site.api.espn.com/apis/site/v2/sports/soccer/{league}/summary?event={eid}','json','https://www.espn.com/')
        for side in ('home','away'):
            team=sides[side]['team']['displayName'];tid=str(sides[side]['team']['id']);uname=U_ALIAS.get(team,team);rows=r['prediction'][side+'_inputs']['rows'] if r['prediction'] else c[side][:12]
            for h in rows:
                matches=[]
                for ev in league_indexes[league]:
                    if localdate(ev['date'])!=h['date']:continue
                    comp=ev['competitions'][0];cs={x['homeAway']:x for x in comp['competitors']}
                    if str(cs[h['venue']]['team']['id'])!=tid:continue
                    other='away' if h['venue']=='home' else 'home'
                    if not comp.get('status',ev['status'])['type'].get('completed'):continue
                    if (goal(cs[h['venue']]),goal(cs[other]))!=(h['goals_for'],h['goals_against']):
                        conflicts.append(dict(match_id=mid,side=side,history=h['context_match_id'],reason='ESPN goals disagree'));continue
                    matches.append(ev)
                ej=matches[0] if len(matches)==1 else None
                us=[x for x in under if x['league']==U_LEAGUE.get(league) and x['date']==h['date'] and x['home' if h['venue']=='home' else 'away']==uname and (x['home_goals'],x['away_goals'])==((h['goals_for'],h['goals_against']) if h['venue']=='home' else (h['goals_against'],h['goals_for']))]
                uj=us[0] if len(us)==1 else None
                joins.append(dict(match_id=mid,side=side,own_team_id=c[side+'_id'],own_team=team,history=h,espn_id=str(ej['id']) if ej else None,understat=uj,identity_rule='explicit current club mapping plus same competition, own club ID/name, Beijing date, venue and observed goals; opponent name not independently translated'))
                if ej:
                    eid0=str(ej['id']);jobs['espn_summary_'+eid0]=(f'espn_summary_{eid0}',f'https://site.api.espn.com/apis/site/v2/sports/soccer/{league}/summary?event={eid0}','json','https://www.espn.com/')
                if uj:jobs['understat_match_'+uj['id']]=(f'understat_match_{uj["id"]}',f'https://understat.com/getMatchData/{uj["id"]}','json',f'https://understat.com/match/{uj["id"]}')
    write(D/'current-identities.json',mapping);write(D/'own-history-joins.json',joins);write(D/'join-conflicts.json',conflicts)
    print(json.dumps(dict(own_history_rows=len(joins),espn_matches=sum(bool(x['espn_id']) for x in joins),xg_matches=sum(bool(x['understat']) for x in joins),downloads=len(jobs),kickoff_conflicts=[x for x in mapping if not x['kickoff_agrees']]),ensure_ascii=True),flush=True)
    results=[]
    def job(j):
        try:fetch(*j);return dict(name=j[0],ok=True)
        except Exception as e:return dict(name=j[0],ok=False,error=str(e))
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        for i,x in enumerate(pool.map(job,jobs.values()),1):
            results.append(x)
            if i%40==0:print('individual matches',i,'/',len(jobs),flush=True)
    write(D/'history-download-log.json',results);print(json.dumps(dict(downloads=len(results),failed=[x for x in results if not x['ok']]),ensure_ascii=True),flush=True)
if __name__=='__main__':main()
