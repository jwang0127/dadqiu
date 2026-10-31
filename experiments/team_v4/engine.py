"""Independent research engine; never imports labels or league aggregates.
Only normalized histories of the fixture teams and optional past opponents.
"""
import collections,datetime as dt,functools,hashlib,json,math,statistics,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'model'))
import core as v3
GRAPH={}

def load_graph(path):
    GRAPH.clear();before.cache_clear()
    data=json.loads(Path(path).read_text(encoding='utf-8'))
    for r in data['histories']:
        GRAPH[(str(r['team_id']),str(r['competition_id']))]=r['matches']

def validate(case):
    day=dt.date.fromisoformat(case['date']);dt.datetime.fromisoformat(case['kickoff'])
    if case['kickoff'][:10]!=case['date']:raise ValueError('kickoff/date mismatch')
    if str(case['home_id'])==str(case['away_id']):raise ValueError('same team on both sides')
    seen={};audit=collections.Counter()
    for side in ('home','away'):
        ids=set()
        for r in case[side]:
            age=(day-dt.date.fromisoformat(r['date'])).days
            if age<2 or age>365:
                audit['outside_time_window']+=1;continue
            if str(r['source_competition_id'])!=str(case['source_competition_id']):raise ValueError('competition mismatch')
            if not r['context_match_id'] or r['context_match_id'] in ids:raise ValueError('duplicate own historical match')
            ids.add(r['context_match_id'])
            if r['venue'] not in ('home','away'):raise ValueError('invalid venue')
            if any(type(r[k]) is not int or r[k]<0 for k in ('goals_for','goals_against')):raise ValueError('invalid goals')
            if not isinstance(r['own_season'],bool):raise ValueError('season flag must be boolean')
            if r['age']!=age:audit['stale_age_recomputed']+=1
            if not r.get('opponent_id') or str(r['opponent_id'])==str(case[side+'_id']):raise ValueError('invalid opponent identity')
            if r['context_match_id'] in seen:
                old=seen[r['context_match_id']]
                if str(old[0])!=str(r['opponent_id']) or str(old[1])!=str(case[side+'_id']) or old[2]!=r['date'] or old[3]!=(r['goals_against'],r['goals_for']):raise ValueError('shared match is not mirrored')
                audit['shared_historical_fixture']+=1
            else:seen[r['context_match_id']]=(case[side+'_id'],r['opponent_id'],r['date'],(r['goals_for'],r['goals_against']))
    return dict(audit)

def huber_mean(values,weights,k):
    loc=statistics.median(values);scale=max(.5,1.4826*statistics.median(abs(x-loc) for x in values))
    for _ in range(30):
        ww=[w*min(1,k*scale/max(abs(x-loc),1e-12)) for x,w in zip(values,weights)]
        new=sum(x*w for x,w in zip(values,ww))/sum(ww)
        if abs(new-loc)<1e-10:break
        loc=new
    return max(0,new)

def own(case,side,cfg):
    day=dt.date.fromisoformat(case['date']);eligible=[]
    for orig in case[side]:
        r=dict(orig);r['age']=(day-dt.date.fromisoformat(r['date'])).days
        if 2<=r['age']<=365 and (cfg['season_weight']>0 or r['own_season']):eligible.append(r)
    eligible.sort(key=lambda r:(r['date'],r['context_match_id']),reverse=True);rows=eligible[:cfg['limit']]
    if len(rows)<5 or sum(r['venue']==side for r in rows)<2:return None
    weights=[]
    for r in rows:
        w=(1 if r['venue']==side else cfg['other'])*2**(-r['age']/cfg['half'])*(1 if r['own_season'] else cfg['season_weight'])
        if cfg.get('gap') and r['age']>60:w*=.25
        weights.append(w)
    sw=sum(weights)
    if sw<=0:return None
    a=[w/sw for w in weights];neff=1/sum(w*w for w in a)
    if neff<3:return None
    vals={k:sum(w*r[k] for w,r in zip(a,rows)) for k in ('goals_for','goals_against')}
    if cfg.get('robust'):
        vals={k:huber_mean([r[k] for r in rows],weights,cfg['robust']) for k in vals}
    totals=[r['goals_for']+r['goals_against'] for r in rows];m=sum(w*x for w,x in zip(a,totals));ss=sum(w*(x-m)**2 for w,x in zip(a,totals));corr=1-sum(w*w for w in a)
    hc=sum((w*(x-m))**2 for w,x in zip(a,totals))/corr
    return dict(rows=rows,weights=weights,normalized=a,n=len(rows),venue_n=sum(r['venue']==side for r in rows),effective_n=neff,gf=vals['goals_for'],ga=vals['goals_against'],total_mean=m,total_var=ss,unbiased_var=ss/corr,mean_var=ss/corr/neff,hc_mean_var=hc)

@functools.lru_cache(maxsize=200000)
def before(team,cid,date):
    target=dt.date.fromisoformat(date);rs=[r for r in GRAPH.get((str(team),str(cid)),[]) if 2<=(target-dt.date.fromisoformat(r['date'])).days<=365][-12:]
    if len(rs)<5:return None
    ws=[2**(-(target-dt.date.fromisoformat(r['date'])).days/180) for r in rs];sw=sum(ws)
    return dict(gf=sum(w*r['gf'] for w,r in zip(ws,rs))/sw,ga=sum(w*r['ga'] for w,r in zip(ws,rs))/sw,n=len(rs),max_date=max(r['date'] for r in rs))

def predict(case,cfg,checked=False):
    if not checked:validate(case)
    if cfg['name']=='v3':return v3.predict(case)
    h=own(case,'home',cfg);a=own(case,'away',cfg)
    if not h or not a:return None
    lh=(h['gf']+a['ga'])/2;la=(a['gf']+h['ga'])/2;opponent_audit=[]
    if cfg.get('opponents'):
        if not GRAPH:raise ValueError('own opponent graph required')
        estimates=[]
        for side,other in [(h,a),(a,h)]:
            ratios=[]
            for r,w in zip(side['rows'],side['weights']):
                prior=before(str(r['opponent_id']),str(case['source_competition_id']),r['date'])
                if prior and prior['ga']>=.3:
                    ratios.append((min(2,max(.5,r['goals_for']/prior['ga'])),w));opponent_audit.append(dict(team=r['opponent_id'],history_max=prior['max_date'],before=r['date']))
            estimates.append(sum(v*w for v,w in ratios)/sum(w for v,w in ratios)*other['ga'] if len(ratios)>=3 else None)
        strength=cfg['opponents']
        if estimates[0] is not None:lh=(1-strength)*lh+strength*estimates[0]
        if estimates[1] is not None:la=(1-strength)*la+strength*estimates[1]
    mu=lh+la;mode=cfg['variance'];cov=0
    if mode=='original':var=(h['total_var']/h['effective_n']+a['total_var']/a['effective_n'])/4
    else:
        var=(h['mean_var']+a['mean_var'])/4
        if mode=='cluster':
            var=(h['hc_mean_var']+a['hc_mean_var'])/4
            ah={r['context_match_id']:(w,r['goals_for']+r['goals_against']-h['total_mean']) for r,w in zip(h['rows'],h['normalized'])}
            for r,w in zip(a['rows'],a['normalized']):
                if r['context_match_id'] in ah:
                    wh,rh=ah[r['context_match_id']];cov+=wh*w*rh*(r['goals_for']+r['goals_against']-a['total_mean'])
            corr=math.sqrt((1-1/h['effective_n'])*(1-1/a['effective_n']));cov/=corr
            bound=math.sqrt(h['hc_mean_var']*a['hc_mean_var']);cov=max(-bound,min(bound,cov));var=max(0,var+cov/2)
    if cfg.get('process'):
        over=max(0,((h['unbiased_var']-h['total_mean'])+(a['unbiased_var']-a['total_mean']))/2)
        var+=cfg['process']*over
    pp=v3.negative_binomial(mu,mu*mu/var) if mu>0 and var>1e-10 else v3.poisson(mu)
    if cfg.get('empirical'):
        empirical=[0.0]*8
        for side in (h,a):
            for r,w in zip(side['rows'],side['normalized']):empirical[min(7,r['goals_for']+r['goals_against'])]+=.5*w
        alpha=cfg['empirical'];pp=[(1-alpha)*p+alpha*q for p,q in zip(pp,empirical)]
    if cfg.get('hurdle'):
        # A zero-hurdle sensitivity model, not a fully fitted count regression.
        observed=.5*sum(sum(w for r,w in zip(s['rows'],s['normalized']) if r['goals_for']+r['goals_against']==0) for s in (h,a))
        z=(1-cfg['hurdle'])*pp[0]+cfg['hurdle']*observed
        if pp[0]<1-1e-12:pp=[z]+[p*(1-z)/(1-pp[0]) for p in pp[1:]]
    assert all(math.isfinite(p) and p>=0 for p in pp) and abs(sum(pp)-1)<1e-9
    # Hurdle/empirical variants can change the distribution mean, so do not claim
    # their original attack/defence intensity equals the final predictive mean.
    return dict(probabilities=pp,p3=sum(pp[3:]),p4=sum(pp[4:]),p5=sum(pp[5:]),total_intensity=mu,home_intensity=lh,away_intensity=la,
                uncertainty_variance=var,shared_history_covariance=cov,home_inputs=h,away_inputs=a,opponent_audit=opponent_audit,
                league_statistics_used=False,market_inputs_used=False,mean_is_intensity_only=bool(cfg.get('empirical') or cfg.get('hurdle')))

def live_contract(case,manifest,source_blobs):
    """Refuse to call retrospective or unverified histories a prospective capture."""
    validate(case)
    kickoff=dt.datetime.fromisoformat(case['kickoff']).replace(tzinfo=dt.timezone(dt.timedelta(hours=8)))
    captured=dt.datetime.fromisoformat(manifest['captured_at'])
    if captured.tzinfo is None or captured>=kickoff:raise ValueError('capture must be timestamped before kickoff')
    if manifest.get('match_id')!=case['match_id']:raise ValueError('capture identity mismatch')
    expected=manifest.get('source_sha256')
    if not isinstance(expected,dict) or not expected or set(expected)!=set(source_blobs):raise ValueError('source proof missing')
    for name,blob in source_blobs.items():
        if hashlib.sha256(blob).hexdigest()!=expected[name]:raise ValueError('source hash mismatch')
    normalized=json.dumps(case,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()
    if hashlib.sha256(normalized).hexdigest()!=manifest.get('normalized_case_sha256'):raise ValueError('case hash mismatch')
    head=json.loads(source_blobs['head'])['value']
    if str(head['sportteryMatchId'])!=str(case['match_id']) or str(head['uniformHomeTeamId'])!=str(case['home_id']) or str(head['uniformAwayTeamId'])!=str(case['away_id']):raise ValueError('raw source team identity mismatch')
    if str(head['tournamentId'])!=str(case['source_competition_id']) or head['matchDateTime']!=case['kickoff']:raise ValueError('raw source fixture mismatch')
    if not {'head','all','venue'}.issubset(source_blobs):raise ValueError('raw own histories required')
    originals={'home':{},'away':{}}
    for source in ('all','venue'):
        data=json.loads(source_blobs[source])['value']
        for side in ('home','away'):
            body=data[side]
            if str(body['statistics']['uniformTeamId'])!=str(case[side+'_id']):raise ValueError('history source team mismatch')
            for r in body.get('matchList',[]):originals[side].setdefault(str(r['matchId']),[]).append(r)
    for side in ('home','away'):
        for r in case[side]:
            if not 2<=(dt.date.fromisoformat(case['date'])-dt.date.fromisoformat(r['date'])).days<=365:continue
            matches=[]
            for original in originals[side].get(str(r['context_match_id']),[]):
                try:
                    hg,ag=map(int,original['fullCourtGoal'].split(':'))
                    ih=str(original['uniformHomeTeamId'])==str(case[side+'_id']);ia=str(original['uniformAwayTeamId'])==str(case[side+'_id'])
                    if ih==ia:continue
                    pair=(hg,ag) if ih else (ag,hg)
                    opponent=original['uniformAwayTeamId' if ih else 'uniformHomeTeamId']
                    season=bool(head.get('seasonId')) and bool(original.get('seasonId')) and str(head['seasonId'])==str(original['seasonId'])
                    matches.append(original['matchDate']==r['date'] and str(original['tournamentId'])==str(case['source_competition_id']) and pair==(r['goals_for'],r['goals_against']) and str(opponent)==str(r['opponent_id']) and ('home' if ih else 'away')==r['venue'] and season==r['own_season'])
                except (KeyError,ValueError,TypeError):continue
            if not any(matches):raise ValueError('normalized history not supported by raw source')
    if not manifest.get('team_identity_verified'):raise ValueError('team proof missing')
    if not manifest.get('period_90_verified') or not manifest.get('venue_status_verified'):raise ValueError('90-minute/venue proof missing')
    return True
