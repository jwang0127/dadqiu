"""Recalculate every October target and compare frozen forecasts and labels.
Run: python model/validate.py
"""
import copy,datetime as dt,hashlib,json,math
from pathlib import Path
from core import predict,metrics,verdict
ROOT=Path(__file__).resolve().parents[1]
def read(p):return json.loads(p.read_text(encoding='utf-8'))
def main():
    cases={c['match_id']:c for c in (json.loads(s) for s in (ROOT/'data/cases.jsonl').read_text(encoding='utf-8').splitlines())}
    labels=read(ROOT/'data/outcomes.json'); frozen=read(ROOT/'data/validation.json')
    results=[];vectors=[]
    for row in frozen['reviews']:
        case=cases[row['case']['match_id']];p=predict(case);original=row['prediction']
        assert labels[case['match_id']]==row['actual_total_goals_90']
        assert (p is None)==(original is None)
        if p:
            assert max(abs(a-b) for a,b in zip(p['probabilities'],original['probabilities']))<1e-12
            results.append((case,p,labels[case['match_id']]))
    reports={}
    for name,start in [('last30','2026-10-01'),('last20','2026-10-11')]:
        rows=[r for r in results if r[0]['date']>=start]
        reports[name]=dict(scope='all available selected-model forecasts',**metrics([(p,y) for c,p,y in rows]))
    today=read(ROOT/'data/today.json')
    for row in today['matches']:
        if row['verdict'] in ('started','missing'):
            assert row['prediction'] is None and row['forecast_at'] is None
            if row['verdict']=='missing':assert predict(row['case']) is None
            continue
        c=copy.deepcopy(row['case']);p=predict(c);vectors.append(tuple(p['probabilities']))
        assert p['probabilities']==row['prediction']['probabilities']
        assert dt.datetime.fromisoformat(row['forecast_at'])<dt.datetime.fromisoformat(row['kickoff'])
        poisoned=copy.deepcopy(c)
        poisoned.update(competition='injected label',league_average=99,league_prior=[1]*8,odds=99,target_result=99)
        assert predict(poisoned)==p
        no_data=copy.deepcopy(c);no_data['home']=[]
        assert predict(no_data) is None
        future=copy.deepcopy(c);r=copy.deepcopy(c['home'][0]);r.update(date=c['date'],age=0,goals_for=99,context_match_id='future-test');future['home'].append(r)
        assert predict(future)==p
        changed=copy.deepcopy(c);changed['home'][0]['goals_for']+=3
        assert abs(predict(changed)['total_expected_goals']-p['total_expected_goals'])>1e-6
        for side in ('home_inputs','away_inputs'):
            assert all(r['date']<=c['latest_permitted_date'] for r in p[side]['rows'])
    assert len(vectors)==len(set(vectors))==sum(bool(r['prediction']) for r in today['matches'])
    report=dict(passed=True,historical_targets=len(frozen['reviews']),available=len(results),today_predictions=len(vectors),
                unique_probability_vectors=len(set(vectors)),league_poisoning_ignored=True,target_outcome_ignored=True,
                prices_ignored=True,future_records_ignored=True,own_data_changes_result=True,no_data_returns_none=True,
                all_available_scores=reports,warning='Previously viewed retrospective data; not blind validation')
    (ROOT/'data/audit.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
