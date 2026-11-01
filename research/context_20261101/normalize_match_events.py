"""Normalize verified individual match events and player exposure.
Historical actual XIs remain retrospective unless a pre-kickoff snapshot exists.
"""
import collections,datetime as dt,json,math,unicodedata
from pathlib import Path
def read(p):return json.loads(p.read_text(encoding='utf-8'))
def clean(s):return ''.join(c for c in unicodedata.normalize('NFKD',s).casefold() if c.isalnum())
def norm(summary,shotdata,fixture,captured):
    comp=summary['header']['competitions'][0];sides={r['homeAway']:r for r in summary.get('rosters',[])};events=summary.get('keyEvents',[])
    if set(sides)!=set(('home','away')):raise ValueError('both rosters required')
    ids={str(sides[s]['team']['id']):s for s in sides};players={};reds=[];unknown=[];seen=set();substitutions=[]
    for e in events:
        if e.get('period',{}).get('number') not in (1,2):continue
        typ=e.get('type',{}).get('type','');t=e.get('clock',{}).get('value');participants=[str(x['athlete']['id']) for x in e.get('participants',[]) if x.get('athlete',{}).get('id')]
        if t is None:continue
        if typ=='substitution':substitutions.append((participants,float(t)))
        if typ in ('red-card','second-yellow-card','yellow-red-card'):
            side=ids.get(str(e.get('team',{}).get('id')));player=participants[0] if len(participants)==1 else None;key=(side,player)
            if key in seen:continue
            seen.add(key);reds.append(dict(side=side,player_id=player,seconds=float(t),display=e.get('clock',{}).get('displayValue'),period=e['period']['number'],type=typ))
    for side,r in sides.items():
        out=[]
        rawplayers=shotdata.get('rosters',{}).get('h' if side=='home' else 'a',{})
        rawplayers=list(rawplayers.values()) if isinstance(rawplayers,dict) else rawplayers
        names=collections.defaultdict(list)
        for q in rawplayers:names[clean(q['player'])].append(q)
        for p in r['roster']:
            pid=str(p['athlete']['id']);starter=p.get('starter') is True;stats={x['name']:x.get('value') for x in p.get('stats',[])};entered=p.get('subbedIn') is True;exited=p.get('subbedOut') is True
            start=0.0 if starter else None;end=5400.0 if starter or entered else None
            if entered:
                subfor=str(p.get('subbedInFor',{}).get('athlete',{}).get('id',''));found=[t for ids0,t in substitutions if pid in ids0 and subfor in ids0]
                if found:start=min(found)
            if exited:
                subfor=str(p.get('subbedOutFor',{}).get('athlete',{}).get('id',''));found=[t for ids0,t in substitutions if pid in ids0 and subfor in ids0]
                if found:end=min(found)
                else:end=None
            for red in reds:
                if red['player_id']==pid and red['side']==side:
                    onfield=start is not None and end is not None and start<=red['seconds']<=end
                    red['on_field']=onfield
                    if onfield:end=min(end,red['seconds'])
            minutes=max(0,min(end,5400)-min(start,5400))/60 if start is not None and end is not None else None
            matches=names.get(clean(p['athlete']['displayName']),[])
            match=matches[0] if len(matches)==1 else None
            if match and stats.get('totalGoals') is not None and int(match['goals'])!=stats['totalGoals']:match=None
            out.append(dict(id=pid,name=p['athlete']['displayName'],starter=starter,position=p.get('position',{}).get('abbreviation'),minutes_90_clock=minutes,minutes_exclude_stoppage=True,goals=stats.get('totalGoals'),red_cards=stats.get('redCards'),start_seconds=start,end_seconds=end,xg=float(match['xG']) if match else None,understat_player_id=match['player_id'] if match else None))
        players[side]=out
    for r in reds:
        if r.get('on_field') is None:unknown.append('red_card_on_field_status_unknown')
    allstats=[p for ps in players.values() for p in ps]
    stats_red=sum(p['red_cards'] or 0 for p in allstats);stats_known=all(p['red_cards'] is not None for p in allstats if p['starter'] or p['minutes_90_clock'] is not None)
    timeline_valid=bool(events) and comp['status']['type'].get('completed') is True and stats_known and stats_red==len(reds) and not unknown
    onfield=[r for r in reds if r.get('on_field')];cut=min([int(r['seconds']//60) for r in onfield],default=None)
    before={};sumchecks={}
    for name,short in [('home','h'),('away','a')]:
        shots=shotdata.get('shots',{}).get(short,[]);xg=sum(float(s['xG']) for s in shots)
        sumchecks[name]=abs(xg-fixture[name+'_xg'])<.03
        if cut is not None and cut>=30 and cut<=89:
            selected=[s for s in shots if int(s['minute'])<cut]
            before[name]=dict(cutoff_minute=cut,xg=sum(float(s['xG']) for s in selected),npxg=sum(float(s['xG']) for s in selected if s['situation']!='Penalty'),xg_per90=sum(float(s['xG']) for s in selected)*90/cut,method='exclude entire dismissal minute; normal-clock exposure only')
    kickoff=dt.datetime.fromisoformat(comp['date'].replace('Z','+00:00'));received=dt.datetime.fromisoformat(captured)
    starters={s:[p['id'] for p in ps if p['starter']] for s,ps in players.items()}
    return dict(understat_id=fixture['provider_match_id'],espn_id=str(comp['id']),kickoff_utc=comp['date'],home=fixture['home'],away=fixture['away'],red_events=reds,on_field_red_count=len(onfield),red_timeline_verified=timeline_valid,pre_red=before if timeline_valid and all(sumchecks.values()) else {},shot_sum_matches_provider=sumchecks,players=players,starters=starters,lineup_complete=all(len(v)==11 for v in starters.values()),captured_at=captured,captured_before_kickoff=received<kickoff,lineup_confirmation='historical_actual' if comp['status']['type'].get('completed') else 'source_starter_flags_unverified',error_flags=unknown)