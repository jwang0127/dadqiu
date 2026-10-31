"""Reproduce experiment without touching production model, data or HTML."""
import collections,datetime as dt,hashlib,json,math,random,sys
from pathlib import Path
import engine
from plan import CANDIDATES,PROTOCOL
ROOT=Path(__file__).resolve().parents[2];HERE=Path(__file__).resolve().parent;OUT=HERE/'results'
TAILS={'zero_one':(lambda p:sum(p[:2]),lambda y:y<=1),'five_plus':(lambda p:sum(p[5:]),lambda y:y>=5),'six_plus':(lambda p:sum(p[6:]),lambda y:y>=6),'four_plus':(lambda p:sum(p[4:]),lambda y:y>=4),'three_plus':(lambda p:sum(p[3:]),lambda y:y>=3)}
def write(path,d):path.write_text(json.dumps(d,ensure_ascii=False,indent=2),encoding='utf-8')
def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def loss(p,y):
    pp=p['probabilities'];ll=-math.log(max(pp[min(y,7)],1e-12))
    b={k:(f(pp)-g(y))**2 for k,(f,g) in TAILS.items()}
    return dict(logloss=ll,objective=sum(b[k] for k in ('zero_one','five_plus','six_plus'))/3+.01*ll,**b)
def average_precision(items):
    total=sum(y for p,y in items)
    if not total:return None
    groups=collections.defaultdict(list)
    for p,y in items:groups[p].append(y)
    tp=n=0;ap=0
    for p,ys in sorted(groups.items(),reverse=True):
        gained=sum(ys);tp+=gained;n+=len(ys);ap+=(gained/total)*(tp/n)
    return ap
def binary_metrics(items):
    if not items:return dict(n=0)
    return dict(n=len(items),mean_probability=sum(p for p,y in items)/len(items),observed_events=sum(y for p,y in items),observed_rate=sum(y for p,y in items)/len(items),brier=sum((p-y)**2 for p,y in items)/len(items),average_precision=average_precision(items))
def metrics(ids,pred,cases,labels,detail=True):
    if not ids:return dict(n=0)
    errors=[loss(pred[i],labels[i]) for i in ids]
    result=dict(n=len(ids),**{k:sum(s[k] for s in errors)/len(ids) for k in errors[0]})
    if not detail:return result
    daily=collections.defaultdict(list)
    for i in ids:daily[cases[i]['date']].append(i)
    tails={}
    for name,(prob,event) in TAILS.items():
        items=[(prob(pred[i]['probabilities']),event(labels[i])) for i in ids]
        top20=[];top5=[]
        for day,group in daily.items():
            order=sorted(group,key=lambda i:(-prob(pred[i]['probabilities']),i));top20+=order[:max(1,math.ceil(.2*len(order)))];top5+=order[:5]
        allm=binary_metrics(items);topm=binary_metrics([(prob(pred[i]['probabilities']),event(labels[i])) for i in top20]);topm['lift']=topm['observed_rate']/allm['observed_rate'] if allm['observed_rate'] else None
        bands=[dict(low=low,high=min(1,high),**binary_metrics([(p,y) for p,y in items if low<=p<high])) for low,high in [(0,.1),(.1,.2),(.2,.3),(.3,.4),(.4,.5),(.5,1.000001)]]
        tails[name]=dict(all=allm,daily_top20percent=topm,daily_top5=binary_metrics([(prob(pred[i]['probabilities']),event(labels[i])) for i in top5]),calibration_bands=bands)
    result['tails']=tails
    return result
def select(train,preds,cases,labels):
    baseline=[i for i in train if i in preds['v3']];reference=metrics(baseline,preds['v3'],cases,labels,False)
    scores=[]
    for cfg in CANDIDATES:
        name=cfg['name'];ids=[i for i in baseline if i in preds[name]]
        m=metrics(ids,preds[name],cases,labels,False)
        eligible=len(baseline)>=200 and len(ids)==len(baseline) and m['logloss']<=reference['logloss']+.02
        scores.append(dict(name=name,family=cfg['family'],eligible=eligible,missing_baseline_targets=len(baseline)-len(ids),**m))
    valid=[s for s in scores if s['eligible']]
    return (min(valid,key=lambda s:(s['objective'],s['logloss'],s['name']))['name'] if valid else 'v3'),scores
def bootstrap(ids,left,right,cases,labels):
    daily=collections.defaultdict(list)
    for i in ids:
        a=loss(left[i],labels[i]);b=loss(right[i],labels[i]);daily[cases[i]['date']].append({k:a[k]-b[k] for k in a})
    groups=list(daily.values());rng=random.Random(20261031);draws=collections.defaultdict(list)
    for _ in range(1500):
        sample=[r for _ in groups for r in rng.choice(groups)]
        for k in sample[0]:draws[k].append(sum(r[k] for r in sample)/len(sample))
    return {k:dict(mean_difference=sum(r[k] for rs in groups for r in rs)/len(ids),date_block_95_interval=[sorted(v)[int(.025*len(v))],sorted(v)[int(.975*len(v))]]) for k,v in draws.items()}
def main():
    OUT.mkdir(exist_ok=True)
    plan=dict(protocol=PROTOCOL,candidates=CANDIDATES,created_at=dt.datetime.now(dt.timezone.utc).isoformat(),data_sha256=digest(ROOT/'data/cases.jsonl'))
    planpath=HERE/'preregistered-plan.json'
    if planpath.exists():
        old=json.loads(planpath.read_text(encoding='utf-8'))
        assert old['protocol']==PROTOCOL and old['candidates']==CANDIDATES and old['data_sha256']==plan['data_sha256'],'Do not silently edit registered protocol'
    else:write(planpath,plan)
    website={name:digest(ROOT/name) for name in ('index.html','validation.html')}
    cases={c['match_id']:c for c in (json.loads(s) for s in (ROOT/'data/cases.jsonl').read_text(encoding='utf-8').splitlines())}
    labels=json.loads((ROOT/'data/outcomes.json').read_text(encoding='utf-8'))
    engine.load_graph(HERE/'opponent_histories.json')
    quality=collections.Counter();invalid={};diagnostics=collections.Counter()
    for mid,c in cases.items():
        try:
            audit=engine.validate(c);quality.update(audit)
        except (ValueError,KeyError,TypeError) as e:invalid[mid]=str(e);continue
        if any(not r['own_season'] for side in ('home','away') for r in c[side][:12]):diagnostics['targets_with_cross_season_input']+=1
        if any(r['goals_for']+r['goals_against']>=7 for side in ('home','away') for r in c[side][:12]):diagnostics['targets_with_7plus_context']+=1
    preds={cfg['name']:{} for cfg in CANDIDATES}
    for cfg in CANDIDATES:
        for mid,c in cases.items():
            if mid in invalid:continue
            p=engine.predict(c,cfg,checked=True)
            if p:preds[cfg['name']][mid]=p
        print('computed',cfg['name'],len(preds[cfg['name']]),flush=True)
    folds=[];oof={};oofbaseline={}
    for month in PROTOCOL['rolling_test_months']:
        first=dt.date.fromisoformat(month+'-01');end=(first-dt.timedelta(days=2)).isoformat()
        train=[i for i,c in cases.items() if PROTOCOL['training_start']<=c['date']<=end and i in labels]
        selected,scores=select(train,preds,cases,labels)
        test=[i for i,c in cases.items() if c['date'][:7]==month and i in labels]
        paired=[i for i in test if i in preds['v3'] and i in preds[selected]]
        for i in paired:oof[i]=preds[selected][i];oofbaseline[i]=preds['v3'][i]
        folds.append(dict(month=month,training_max=end,selected=selected,targets=len(test),baseline_available=sum(i in preds['v3'] for i in test),candidate_available=sum(i in preds[selected] for i in test),paired=len(paired),baseline=metrics(paired,preds['v3'],cases,labels),candidate=metrics(paired,preds[selected],cases,labels),selection_scores=scores))
    train=[i for i,c in cases.items() if PROTOCOL['training_start']<=c['date']<=PROTOCOL['training_end'] and i in labels]
    selected,scores=select(train,preds,cases,labels);cfg=next(c for c in CANDIDATES if c['name']==selected)
    periods=[]
    for name,start in [('last30','2026-10-01'),('last20','2026-10-11')]:
        targets=[i for i,c in cases.items() if start<=c['date']<='2026-10-30' and i in labels]
        paired=[i for i in targets if i in preds['v3'] and i in preds[selected]]
        periods.append(dict(period=name,targets=len(targets),paired=len(paired),baseline_available=sum(i in preds['v3'] for i in targets),candidate_available=sum(i in preds[selected] for i in targets),baseline=metrics(paired,preds['v3'],cases,labels),candidate=metrics(paired,preds[selected],cases,labels),paired_date_bootstrap=bootstrap(paired,preds[selected],preds['v3'],cases,labels)))
    all_oof=list(oof);oof_metrics=dict(baseline=metrics(all_oof,oofbaseline,cases,labels),candidate=metrics(all_oof,oof,cases,labels))
    # Resolve each family on development only; report October even if it worsens.
    families=[]
    for family in sorted({c['family'] for c in CANDIDATES}):
        fs=[s for s in scores if s['family']==family and s['eligible']]
        if not fs:families.append(dict(family=family,status='ineligible coverage or logloss'));continue
        best=min(fs,key=lambda s:(s['objective'],s['logloss'],s['name']));name=best['name'];octids=[i for i,c in cases.items() if '2026-10-01'<=c['date']<='2026-10-30' and i in labels and i in preds['v3'] and i in preds[name]]
        families.append(dict(family=family,name=name,development=best,october=metrics(octids,preds[name],cases,labels,False)))
    live=[]
    for mid,c in cases.items():
        if mid in labels:continue
        live.append(dict(case=c,prediction=preds[selected].get(mid),baseline=preds['v3'].get(mid),recomputed_from_frozen_inputs=True,prospective_publish=False))
    write(OUT/'selected.json',dict(config=cfg,protocol=PROTOCOL,selection_scores=scores,plan_sha256=digest(planpath),experimental_only=True))
    write(OUT/'evaluation.json',dict(quality=dict(quality),invalid_targets=invalid,diagnostics=dict(diagnostics),folds=folds,rolling_aggregate=oof_metrics,periods=periods,family_ablation=families,website_sha256_unchanged=website))
    write(OUT/'today-recomputed.json',live)
    write(OUT/'october-predictions.json',[dict(case=cases[i],prediction=preds[selected].get(i),baseline=preds['v3'].get(i),actual=labels[i]) for i in cases if '2026-10-01'<=cases[i]['date']<='2026-10-30' and i in labels])
    assert website=={name:digest(ROOT/name) for name in website}
    print(json.dumps(dict(selected=selected,rolling_baseline=oof_metrics['baseline']['objective'],rolling_candidate=oof_metrics['candidate']['objective'],october=[dict(period=p['period'],n=p['paired'],baseline=p['baseline']['objective'],candidate=p['candidate']['objective']) for p in periods],invalid=len(invalid),quality=dict(quality)),ensure_ascii=False),flush=True)
if __name__=='__main__':main()
