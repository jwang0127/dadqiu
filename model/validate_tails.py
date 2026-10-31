"""Retrospective checks of each displayed tail, never used to alter probabilities."""
import collections,json,math
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
TAILS={'zero_one':(lambda p:sum(p[:2]),lambda y:y<=1),'four_plus':(lambda p:sum(p[4:]),lambda y:y>=4),'five_plus':(lambda p:sum(p[5:]),lambda y:y>=5),'six_plus':(lambda p:sum(p[6:]),lambda y:y>=6)}
def metrics(items):
    if not items:return dict(n=0)
    return dict(n=len(items),mean_probability=sum(p for p,y in items)/len(items),actual_events=sum(y for p,y in items),observed_rate=sum(y for p,y in items)/len(items),brier=sum((p-y)**2 for p,y in items)/len(items))
def main():
    validation=json.loads((ROOT/'data/validation.json').read_text(encoding='utf-8'));reviews=validation['reviews'];out={}
    for period,start in [('last30','2026-10-01'),('last20','2026-10-11')]:
        targets=[r for r in reviews if r['case']['date']>=start];available=[r for r in targets if r['prediction']];report={}
        for name,(prob,event) in TAILS.items():
            items=[(prob(r['prediction']['probabilities']),event(r['actual_total_goals_90'])) for r in available]
            daily=collections.defaultdict(list)
            for r in available:daily[r['case']['date']].append(r)
            top=[r for day,rs in daily.items() for r in sorted(rs,key=lambda r:(-prob(r['prediction']['probabilities']),r['case']['match_id']))[:5]]
            bands=[]
            for low,high in [(0,.1),(.1,.2),(.2,.3),(.3,.4),(.4,.5),(.5,1.00001)]:
                bands.append(dict(low=low,high=min(high,1),**metrics([(p,y) for p,y in items if low<=p<high])))
            report[name]=dict(all_available=metrics(items),daily_top_five=metrics([(prob(r['prediction']['probabilities']),event(r['actual_total_goals_90'])) for r in top]),calibration_bands=bands)
        out[period]=dict(targets=len(targets),available=len(available),skipped=len(targets)-len(available),tails=report)
    result=dict(method='Frozen own-team distributions; per-day top five ranked without target results; may contain fewer than five on a day',warning='Previously viewed retrospective October data, not blind; no market edge inferred',periods=out)
    (ROOT/'data/tail-validation.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({period:{tail:v['all_available'] for tail,v in r['tails'].items()} for period,r in out.items()},ensure_ascii=False))
if __name__=='__main__':main()
