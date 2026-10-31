"""Frozen team-only total-goals model. Python standard library only.

Competition names, market prices and target outcomes are never predictors.
Case history must be normalized and source/team identities verified upstream.
"""
import datetime as dt
import math

CONFIG = dict(other=.5, half=180, limit=12)

def own_rates(case, side):
    day = dt.date.fromisoformat(case['date'])
    eligible = []
    seen = set()
    for original in case[side]:
        r = dict(original)
        age = (day-dt.date.fromisoformat(r['date'])).days
        if not 2 <= age <= 365:
            continue
        if str(r['source_competition_id']) != str(case['source_competition_id']):
            raise ValueError('Historical competition identity mismatch')
        if r['context_match_id'] in seen:
            raise ValueError('Duplicate own match')
        seen.add(r['context_match_id'])
        r['age'] = age
        if r['venue'] not in ('home','away') or any(not isinstance(r[k],int) or r[k]<0 for k in ('goals_for','goals_against')):
            raise ValueError('Invalid normalized history')
        eligible.append(r)
    eligible.sort(key=lambda r:(r['date'],r['context_match_id']), reverse=True)
    rows = eligible[:CONFIG['limit']]
    venue_n = sum(r['venue']==side for r in rows)
    if len(rows)<5 or venue_n<2:
        return None
    weights = [(1 if r['venue']==side else CONFIG['other'])*2**(-r['age']/CONFIG['half']) for r in rows]
    sw = sum(weights)
    effective_n = sw*sw/sum(w*w for w in weights)
    if effective_n<3:
        return None
    rates = {k:sum(w*r[k] for w,r in zip(weights,rows))/sw for k in ('goals_for','goals_against')}
    return dict(rows=rows,weights=weights,n=len(rows),venue_n=venue_n,effective_n=effective_n,gf=rates['goals_for'],ga=rates['goals_against'])

def poisson(mean):
    pp=[math.exp(-mean)]
    for k in range(1,7): pp.append(pp[-1]*mean/k)
    return pp+[max(0,1-sum(pp))]

def negative_binomial(mean, shape):
    prob=shape/(shape+mean)
    pp=[prob**shape]
    for k in range(1,7): pp.append(pp[-1]*(k-1+shape)/k*(1-prob))
    return pp+[max(0,1-sum(pp))]

def predict(case):
    h=own_rates(case,'home'); a=own_rates(case,'away')
    if not h or not a: return None
    lh=(h['gf']+a['ga'])/2; la=(a['gf']+h['ga'])/2; mean=lh+la
    variances=[]
    for side in (h,a):
        totals=[r['goals_for']+r['goals_against'] for r in side['rows']]
        weights=side['weights']; sw=sum(weights)
        m=sum(v*w for v,w in zip(totals,weights))/sw
        variance=sum(w*(v-m)**2 for v,w in zip(totals,weights))/sw
        variances.append(variance/side['effective_n'])
    var_mean=sum(variances)/4
    pp=negative_binomial(mean,mean*mean/var_mean) if mean>0 and var_mean>1e-10 else poisson(mean)
    assert min(pp)>=0 and abs(sum(pp)-1)<1e-9
    return dict(home_expected_goals=lh,away_expected_goals=la,total_expected_goals=mean,
                probabilities=pp,p3=sum(pp[3:]),p4=sum(pp[4:]),p5=sum(pp[5:]),
                home_inputs=h,away_inputs=a,uncertainty_variance=var_mean,
                distribution_family='own_uncertainty',league_statistics_used=False)

def verdict(p):
    if p is None: return 'missing'
    return 'over' if p['p3']>=.60 else 'under' if p['p3']<=.40 else 'watch'

def scores(p,y):
    return dict(logloss=-math.log(max(p['probabilities'][min(y,7)],1e-12)),
                brier3=(p['p3']-(y>=3))**2,brier4=(p['p4']-(y>=4))**2)

def metrics(items):
    return dict(n=len(items),**{k:sum(scores(p,y)[k] for p,y in items)/len(items) for k in ('logloss','brier3','brier4')}) if items else dict(n=0)
