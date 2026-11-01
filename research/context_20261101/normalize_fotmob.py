import collections,datetime as dt,math,re,statistics
from collect_expanded_context import D,RAW,P,TZ,read,write
def normalize(path):
    d=read(path);g=d['general'];h=d['header'];content=d['content'];status=h['status'];teams=h['teams'];periods=content.get('stats') or {};stats={}
    for group in periods.get('Periods',{}).get('All',{}).get('stats',[]):
        for s in group.get('stats',[]):
            raw=s.get('rawStats') or []
            if len(raw)==2 and all(isinstance(x,dict) and isinstance(x.get('value'),(int,float)) for x in raw):stats[s['key']]=[x['value'] for x in raw]
    halves=status.get('halfs') or {};normal90=status.get('finished') is True and not status.get('cancelled') and not status.get('awarded') and (status.get('reason') or {}).get('short')=='FT' and not halves.get('firstExtraHalfStarted') and not halves.get('secondExtraHalfStarted') and not status.get('whoLostOnPenalties')
    allshots=(content.get('shotmap') or {}).get('shots') or [];shots=[{k:s.get(k) for k in ('id','teamId','playerId','keeperId','min','minAdded','period','expectedGoals','expectedGoalsOnTarget','situation','shotType','eventType','isOwnGoal','isOnTarget','isFromInsideBox','x','y')} for s in allshots if s.get('period') in ('FirstHalf','SecondHalf')]
    xg=stats.get('expected_goals');shot_ok=bool(xg and shots and all(s['expectedGoals'] is not None for s in shots) and all(abs(sum(s['expectedGoals'] for s in shots if str(s['teamId'])==str(t['id']))-xg[i])<.035 for i,t in enumerate(teams)))
    events=((content.get('matchFacts') or {}).get('events') or {}).get('events') or [];reds=[]
    for e in events:
        if e.get('type')=='Card' and e.get('card') in ('Red','YellowRed','SecondYellow'):
            reds.append(dict(side='home' if e.get('isHome') else 'away',player_id=e.get('playerId'),name=e.get('nameStr'),minute=e.get('time'),added_minute=e.get('overloadTime'),type=e.get('card'),on_field_status='not_independently_validated'))
    lineup=content.get('lineup') or {};players={}
    for side in ('home','away'):
        team=lineup.get(side+'Team') or {};players[side]=[dict(id=p.get('id'),name=p.get('name'),position_id=p.get('positionId'),usual_position_id=p.get('usualPlayingPositionId')) for p in team.get('starters',[])]
    return dict(provider='FotMob',match_id=str(g['matchId']),home=g['homeTeam'],away=g['awayTeam'],kickoff_utc=g['matchTimeUTCDate'],finished=g.get('finished'),normal_90_scope_verified=normal90,statistics=stats,xg=xg if normal90 else None,shot_sum_verified=shot_ok and normal90,shots_90=shots if normal90 else [],red_events=reds,historical_starters=players,lineup_type=lineup.get('lineupType'),source_lineup=lineup.get('source'),historical_actual_xi_complete=g.get('finished') and lineup.get('lineupType')!='predicted' and all(len(ps)==11 for ps in players.values()),collected_retrospectively=True,raw_file=path.name)
def main():
    games={};errors=[]
    for p in RAW.glob('fotmob_match_*.json'):
        if not re.fullmatch(r'fotmob_match_\d+\.json',p.name):continue
        try:
            n=normalize(p);assert n['match_id']==p.stem.removeprefix('fotmob_match_');games[n['match_id']]=n
        except Exception as e:errors.append(dict(file=p.name,error=str(e)))
    write(D/'fotmob-normalized-history.json',list(games.values()));write(D/'fotmob-normalization-errors.json',errors)
    joins=read(D/'fotmob-own-history-joins.json');out=[];board=read(P/'data/today.json')
    for r in board['matches']:
        mid=str(r['matchId']);sides={}
        for side in ('home','away'):
            rows=[x for x in joins if x['match_id']==mid and x['side']==side];eligible=[]
            for x in rows:
                n=games.get(x['fotmob_id'])
                if not n:continue
                assert str(n[x['history']['venue']]['id'])==x['team_id']
                if n['xg'] is not None:eligible.append((x,n))
            weights=[(1 if x['history']['venue']==side else .5)*2**(-((dt.date.fromisoformat(r['case']['date'])-dt.date.fromisoformat(x['history']['date'])).days)/180) for x,n in eligible]
            s=dict(own_rows=len(rows),matched_rows=sum(bool(x['fotmob_id']) for x in rows),xg_rows=len(eligible),weighted_xgf=None,weighted_xga=None,weighted_goals_for_matched=None,weighted_goals_against_matched=None,shot_quality_rows=sum(bool(games.get(x['fotmob_id'],{}).get('shot_sum_verified')) for x in rows))
            if eligible:
                for key,index in [('weighted_xgf',lambda x:0 if x['history']['venue']=='home' else 1),('weighted_xga',lambda x:1 if x['history']['venue']=='home' else 0)]:s[key]=sum(w*n['xg'][index(x)] for w,(x,n) in zip(weights,eligible))/sum(weights)
                s['weighted_goals_for_matched']=sum(w*x['history']['goals_for'] for w,(x,n) in zip(weights,eligible))/sum(weights);s['weighted_goals_against_matched']=sum(w*x['history']['goals_against'] for w,(x,n) in zip(weights,eligible))/sum(weights)
            sides[side]=s
        if any(s['own_rows'] for s in sides.values()):out.append(dict(match_id=mid,sides=sides,provider='FotMob',numerical_prediction_changed=False))
    write(D/'fotmob-fixture-features.json',out)
    current=[]
    for m in read(D/'fotmob-identities.json'):
        p=RAW/f'fotmob_current_{m["provider_match_id"]}.json'
        if not p.exists():continue
        d=read(p);assert str(d['general']['matchId'])==m['provider_match_id'];l=d['content'].get('lineup') or {};kick=dt.datetime.fromisoformat(d['general']['matchTimeUTCDate'].replace('Z','+00:00')).astimezone(TZ)
        raw=r=next(x for x in board['matches'] if str(x['matchId'])==m['match_id'])
        unavailable={side:[{k:p.get(k) for k in ('id','name','injury','expectedReturn','type','expectedReturnDate')} for p in (l.get(side+'Team') or {}).get('unavailable',[])] for side in ('home','away')}
        current.append(dict(match_id=m['match_id'],kickoff_source=kick.isoformat(),kickoff_agrees=kick==dt.datetime.fromisoformat(raw['kickoff']),weather_forecast=d['content'].get('weather'),wind_speed_unit='not independently verified; no numeric effect',lineup_type=l.get('lineupType'),lineup_source=l.get('source'),club_confirmed_xi=False,unavailable=unavailable,team_match_duration_not_inferred_from_player_flags=True))
    write(D/'fotmob-current-context.json',current)
    cup=read(D/'fotmob-extra-cup-history.json');cups=[dict(**x,normal_90_scope_verified=games.get(str(x['fixture']['id']),{}).get('normal_90_scope_verified',False)) for x in cup];write(D/'fotmob-cup-period-audit.json',cups)
    coverage=dict(matches_downloaded=len(games),normal_90_scope_verified=sum(x['normal_90_scope_verified'] for x in games.values()),matches_with_xg=sum(x['xg'] is not None for x in games.values()),shot_quality_sum_verified_matches=sum(x['shot_sum_verified'] for x in games.values()),historical_actual_xi_complete=sum(x['historical_actual_xi_complete'] for x in games.values()),red_event_records=sum(len(x['red_events']) for x in games.values()),own_matched_xg_observations=sum(s['xg_rows'] for r in out for s in r['sides'].values()),fixtures_both_sides_5plus_xg=sum(all(s['xg_rows']>=5 for s in r['sides'].values()) for r in out),current_weather_forecasts=sum(bool(x['weather_forecast']) for x in current),extra_cup_history=len(cup),extra_cup_normal90=sum(x['normal_90_scope_verified'] for x in cups),errors=errors,provider_not_mixed_with_understat=True)
    write(D/'fotmob-coverage.json',coverage);print(coverage)
if __name__=='__main__':main()
