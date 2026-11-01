import collections,copy,datetime as dt,hashlib,html,importlib.util,json,math,re,statistics,sys,unicodedata
from pathlib import Path
from bs4 import BeautifulSoup
from collect_expanded_context import B,P,D,RAW,TZ,read,write
from normalize_match_events import norm
def canon(s):
    alias={'1. FC Union Berlin':'Union Berlin','Hamburg SV':'Hamburger SV','SC Freiburg':'Freiburg','SC Paderborn 07':'Paderborn','RB Leipzig':'RasenBallsport Leipzig','Borussia Mönchengladbach':'Borussia M.Gladbach','Mainz':'Mainz 05','FC Augsburg':'Augsburg','Schalke 04':'Schalke 04','TSG Hoffenheim':'Hoffenheim','SV Elversberg':'Elversberg','1. FC Heidenheim 1846':'FC Heidenheim','VfL Wolfsburg':'Wolfsburg','VfL Bochum':'Bochum','AFC Bournemouth':'Bournemouth','Ipswich Town':'Ipswich','Hull City':'Hull','Coventry City':'Coventry','Leeds United':'Leeds','Brighton & Hove Albion':'Brighton','Tottenham Hotspur':'Tottenham','AS Roma':'Roma','Internazionale':'Inter','Parma':'Parma Calcio 1913','AJ Auxerre':'Auxerre','AS Monaco':'Monaco','Paris Saint-Germain':'Paris Saint Germain','Le Mans FC':'Le Mans','Deportivo':'Deportivo La Coruna','Alavés':'Alaves','Atlético Madrid':'Atletico Madrid'}
    alias.update({'Hellas Verona':'Verona','Le Havre AC':'Le Havre','Stade Rennais':'Rennes'})
    return ''.join(c for c in unicodedata.normalize('NFKD',alias.get(s,s)).casefold() if c.isalnum())
def meta(path):return read(path.with_suffix('.meta.json'))
def summary_norm(eid,uj=None):
    path=RAW/f'espn_summary_{eid}.json'
    if not path.exists():return None
    d=read(path);comp=d['header']['competitions'][0];sides={x['homeAway']:x for x in comp['competitors']}
    if not comp['status']['type'].get('completed'):return None
    assert str(comp['id'])==str(eid),'summary event identity mismatch'
    home=sides['home']['team']['displayName'];away=sides['away']['team']['displayName'];valid=bool(uj and canon(uj['home'])==canon(home) and canon(uj['away'])==canon(away))
    if valid:
        assert (int(sides['home']['score']),int(sides['away']['score']))==(uj['home_goals'],uj['away_goals']),'summary/Understat score disagreement'
    sf=RAW/f'understat_match_{uj["id"]}.json' if valid else None;shots=read(sf) if sf and sf.exists() else None
    fixture=dict(provider_match_id=uj['id'] if valid else None,home=home,away=away,home_xg=uj['home_xg'] if valid else 0,away_xg=uj['away_xg'] if valid else 0)
    out=norm(d,shots or {},fixture,meta(path)['received_at'])
    if not shots:out['pre_red']={};out['shot_sum_matches_provider']={'home':False,'away':False}
    out.update(understat_ordered_identity_verified=valid,shot_quality_available=bool(shots),date_beijing=dt.datetime.fromisoformat(comp['date'].replace('Z','+00:00')).astimezone(TZ).date().isoformat(),team_statistics={},shot_observations={},known_at_historical_kickoff=False)
    for t in d.get('boxscore',{}).get('teams',[]):
        s=t.get('homeAway');out['team_statistics'][s]={x['name']:x.get('displayValue') for x in t.get('statistics',[])}
    if shots:
        for side,short in [('home','h'),('away','a')]:
            rs=shots.get('shots',{}).get(short,[])
            out['shot_observations'][side]=dict(shots=len(rs),npxg=sum(float(x['xG']) for x in rs if x.get('situation')!='Penalty'),xg=sum(float(x['xG']) for x in rs),penalty_shots=sum(x.get('situation')=='Penalty' for x in rs),big_shots_xg_030_or_more=sum(float(x['xG'])>=.30 for x in rs),note='0.30 is an explicit diagnostic threshold, not a validated big-chance definition')
    return out
def expected500(mid):
    soup=BeautifulSoup((RAW/f'500_{mid}.html').read_bytes().decode('gb18030',errors='replace'),'html.parser');boxes=soup.select('.box_side');out=[]
    for box in boxes:
        title=box.select_one('.title');body=box.select_one('.content');players=[]
        if body:
            for tr in body.select('tr'):
                text=tr.get_text(' ',strip=True)
                if text in ('替补','后备'):break
                if text:players.append(text)
        out.append(dict(title=title.get_text(strip=True) if title else '',players=players[:11],confirmed=False))
    return dict(sides=out,officially_confirmed=False,note='Source labels these as predicted starters; never promoted to confirmed XI')
def korean_norm():
    rows=[]
    for p in RAW.glob('500_history_*.html'):
        soup=BeautifulSoup(p.read_bytes().decode('gb18030',errors='replace'),'html.parser');events=[]
        for tr in soup.select('table.mtable tr'):
            tds=tr.find_all('td',recursive=False)
            if len(tds)!=5:continue
            clock=tds[2].get_text(strip=True)
            for side,ico,person in [('home',0,1),('away',4,3)]:
                codes=[x.get('src','').split('/')[-1].split('.')[0] for x in tds[ico].select('img')]
                if '5' in codes or '6' in codes:events.append(dict(side=side,clock=clock,type='second_yellow' if '6' in codes else 'red',player=tds[person].get_text(strip=True),on_field_status='unknown'))
        stats={}
        for tr in soup.select('tr'):
            tds=tr.find_all('td',recursive=False)
            if len(tds)==5 and tds[2].get_text(strip=True) in ('射门','射正','红牌','控球率'):
                stats[tds[2].get_text(strip=True)]=[tds[1].get_text(strip=True),tds[3].get_text(strip=True)]
        rows.append(dict(provider_match_id=p.stem.removeprefix('500_history_'),red_events=events,technical_statistics_raw=stats,technical_statistics_verified=False,warning='Some historical technical tables contain placeholder zeros; not admitted as shot inputs. No independent on-field/bench validation of red events.'))
    return rows
def main():
    board=read(P/'data/today.json');joins=read(D/'own-history-joins.json');identities={x['match_id']:x for x in read(D/'current-identities.json')};byespn={};failures=[]
    for j in joins:
        if j['espn_id']:
            key=j['espn_id']
            if key not in byespn:
                try:byespn[key]=summary_norm(key,j['understat'])
                except Exception as e:failures.append(dict(id=key,error=str(e)));byespn[key]=None
    write(D/'normalized-history.json',[v for v in byespn.values() if v]);write(D/'normalization-errors.json',failures)
    kr=korean_norm();write(D/'korean-events.json',kr)
    reports=[];all_players=0;allinj=0
    for r in board['matches']:
        mid=str(r['matchId']);c=r['case'];out=dict(match_id=mid,number=r['matchNumStr'],home=r['homeTeamAllName'],away=r['awayTeamAllName'],phase=c['phase'],kickoff=r['kickoff'],source_identity=identities.get(mid),expected_lineup=expected500(mid),sides={})
        allcomp=read(RAW/f'allcomp_{mid}.json')['value'];players=read(RAW/f'player_{mid}.json')['value'];inj=read(RAW/f'injury_{mid}.json')['value']
        for side in ('home','away'):
            uid=c[side+'_id'];assert str(allcomp[side]['statistics']['uniformTeamId'])==uid
            assert str(players[side]['uniformTeamId'])==uid and str(inj[side]['uniformTeamId'])==uid
            games={}
            for x in allcomp[side]['matchList']:
                if not x.get('fullCourtGoal') or x['matchDate']>=c['date']:continue
                assert uid in (str(x['uniformHomeTeamId']),str(x['uniformAwayTeamId']))
                games[str(x['matchId'])]=dict(date=x['matchDate'],competition=x['tournamentShortName'],opponent=x['awayTeamShortName'] if str(x['uniformHomeTeamId'])==uid else x['homeTeamShortName'],source_match_id=str(x['matchId']),venue='home' if str(x['uniformHomeTeamId'])==uid else 'away',score_not_used='period of cup totals not independently certified')
            games=sorted(games.values(),key=lambda x:(x['date'],x['source_match_id']),reverse=True)
            own=[j for j in joins if j['match_id']==mid and j['side']==side];gday=dt.date.fromisoformat(c['date']);ss=[]
            for j in own:
                if j['understat']:ss.append(j)
            rawplayers=players[side]['playerList'];rawinj=inj[side]['injuriesAndSuspensionsList'];all_players+=len(rawplayers);allinj+=len(rawinj)
            s=dict(player_summary_records=[{k:x.get(k) for k in ('personId','personName','playerPositionCode','appearanceCnt','startedMatchCnt','substituteMatchCnt','goalCnt','assistCnt','injuryFlag','suspensionFlag')} for x in rawplayers],injury_suspension_records=[{k:x.get(k) for k in ('personId','personName','playerPositionCode','appearanceCnt','startedMatchCnt','injuryFlag','suspensionFlag')} for x in rawinj],injury_list_club_verified=False,empty_injury_list_does_not_mean_healthy=True,cross_competition_recent_games=games,minimum_observed_rest_calendar_days=(gday-dt.date.fromisoformat(games[0]['date'])).days if games else None,calendar_days_not_exact_rest_hours=True,games_last7=sum(1<=(gday-dt.date.fromisoformat(x['date'])).days<=7 for x in games),games_last14=sum(1<=(gday-dt.date.fromisoformat(x['date'])).days<=14 for x in games),selected_model_history=len(r['prediction'][side+'_inputs']['rows']) if r['prediction'] else len(c[side]),history_join_rows=len(own),xg_rows=len(ss),event_rows=sum(bool(byespn.get(j['espn_id'])) for j in own),red_timeline_verified_rows=sum(bool(byespn.get(j['espn_id'],{}).get('red_timeline_verified')) for j in own if byespn.get(j['espn_id'])),weighted_xgf=None,weighted_xga=None)
            if ss:
                weights=[(1 if j['history']['venue']==side else .5)*2**(-((gday-dt.date.fromisoformat(j['history']['date'])).days)/180) for j in ss]
                s['weighted_xgf']=sum(w*j['understat']['home_xg' if j['history']['venue']=='home' else 'away_xg'] for w,j in zip(weights,ss))/sum(weights);s['weighted_xga']=sum(w*j['understat']['away_xg' if j['history']['venue']=='home' else 'home_xg'] for w,j in zip(weights,ss))/sum(weights)
                s['weighted_goals_for_matched']=sum(w*j['history']['goals_for'] for w,j in zip(weights,ss))/sum(weights);s['weighted_goals_against_matched']=sum(w*j['history']['goals_against'] for w,j in zip(weights,ss))/sum(weights)
                s['xg_average_scope']='Matched subset of exactly the frozen own-team history; no missing value imputation; descriptive only'
            out['sides'][side]=s
        cur=identities.get(mid);path=RAW/f'espn_current_{cur["espn_id"]}.json' if cur else None
        if path and path.exists():
            d=read(path);out['venue']=d.get('gameInfo',{}).get('venue');out['current_source_starter_flags']={x['homeAway']:sum(p.get('starter') is True for p in x.get('roster',[])) for x in d.get('rosters',[])}
        out['confirmed_lineup']=False;out['prediction_changed']=False;reports.append(out)
    write(D/'fixture-context.json',reports)
    hist=[v for v in byespn.values() if v];summary=dict(collected_at=dt.datetime.now(TZ).isoformat(),fixtures=len(reports),team_player_summary_records=all_players,listed_injury_suspension_records=allinj,fixtures_with_injury_list_records=sum(any(s['injury_suspension_records'] for s in r['sides'].values()) for r in reports),cross_competition_schedules=sum(bool(s['cross_competition_recent_games']) for r in reports for s in r['sides'].values()),unique_historical_event_matches=len(hist),historical_actual_lineups=sum(x['lineup_complete'] for x in hist),red_timeline_verified_matches=sum(x['red_timeline_verified'] for x in hist),matches_with_on_field_red=sum(x['on_field_red_count']>0 for x in hist),xg_own_team_observations=sum(bool(j['understat']) for j in joins),fixtures_xg_both_sides=sum(all(s['xg_rows']>=5 for s in r['sides'].values()) for r in reports),unique_shot_quality_matches=sum(x['shot_quality_available'] for x in hist),pre_red_xg_segments=sum(bool(x['pre_red']) for x in hist),predicted_lineup_pages=25,confirmed_current_lineups=0,korean_historical_pages=len(kr),korean_red_event_records=sum(len(x['red_events']) for x in kr),kickoff_conflicts=[x for x in identities.values() if not x['kickoff_agrees']],normalization_errors=failures,no_league_aggregates_in_normalized_data=True,forecast_probabilities_changed=False,coverage_caveats=['xG matches use own club/date/venue/goals; opponent names only cross-validated where ESPN and Understat canonical names agree','500 expected lineups are not confirmed; historical placeholders excluded','Sporttery injury lists are not complete club medical bulletins','Calendar-day gaps are not exact rest hours; cup extra time must be separately verified','All historical actual XIs and events were collected retrospectively'])
    write(D/'coverage.json',summary);print(json.dumps(summary,ensure_ascii=True),flush=True)
if __name__=='__main__':main()
