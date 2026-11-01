"""Audit result joins, frozen forecasts, provenance and missing-data handling."""
import copy,datetime as dt,hashlib,json,math,sys
from pathlib import Path
import core
P=Path(__file__).resolve().parents[1];D=P/'data/daily/20261101'
def read(p):return json.loads(p.read_text(encoding='utf-8'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    review=read(D/'review.json');old=read(D/'archive-20261031.json');today=read(P/'data/today.json');five={r['number']:r for r in read(D/'500-results.json')['matches']}
    assert len(review['matches'])==len(old['matches'])==28
    assert review['archived_forecasts']==23 and review['no_forecast']==5
    assert sha(D/'archive-20261031.json')==review['audit']['archive_sha256']=='c116d9ab2b5611b99a6b75e7280ab7e23a6fc06dceeda50f321ada2b72995f56'
    for r in review['matches']:
        original=next(x for x in old['matches'] if str(x['matchId'])==r['match_id'])
        assert r['score']==five[r['number']]['score'] and five[r['number']]['status']=='4'
        assert r['probabilities']==(original['prediction']['probabilities'] if original['prediction'] else None)
        assert r['total']==sum(r['score'])
    assert len(today['matches'])==len({r['matchId'] for r in today['matches']})==25
    vectors=[];duplicate_merges=0;common=0
    sys.path.insert(0,str(P/'experiments/team_v4'));import engine
    def forbidden(x):
        if isinstance(x,dict):
            for k,v in x.items():
                assert k not in ('odds','ttg','had','hhad','crs','hafu','target_result','league_average','league_prior'),k
                forbidden(v)
        elif isinstance(x,list):
            for v in x:forbidden(v)
    for r in today['matches']:
        c=r['case'];p=r['prediction'];engine.validate(c);forbidden(c)
        if not p:
            assert r['matchNumStr']=='周日024' and core.predict(c) is None
            assert len(c['home'])==3 and len(c['away'])==0
            continue
        assert r['confidence']=='low' and r['risk_text']
        assert dt.datetime.fromisoformat(r['forecast_at'])<dt.datetime.fromisoformat(r['kickoff'])
        assert core.predict(c)==p
        pp=p['probabilities'];assert len(pp)==8 and min(pp)>=0 and abs(sum(pp)-1)<1e-12
        assert abs(p['p5']-sum(pp[5:]))<1e-12
        vectors.append(tuple(pp));duplicate_merges+=r['audit']['merged_duplicates']
        h={x['context_match_id'] for x in p['home_inputs']['rows']};a={x['context_match_id'] for x in p['away_inputs']['rows']};common+=len(h&a)
        for side in ('home','away'):
            rows=p[side+'_inputs']['rows'];assert len(rows)==len({x['context_match_id'] for x in rows})
            assert all(2<=(dt.date.fromisoformat(c['date'])-dt.date.fromisoformat(x['date'])).days<=365 for x in rows)
        poisoned=copy.deepcopy(c);poisoned.update(league_average=100,odds=[1]*8,target_result='8:8');assert core.predict(poisoned)==p
    assert len(vectors)==len(set(vectors))==24
    for path in (D/'raw').glob('*.meta.json'):
        meta=read(path);source=path.with_name(path.name.replace('.meta.json','.json'))
        if '500_' in path.name:source=path.with_name(path.name.replace('.meta.json','.html'))
        if source.exists() and 'sha256' in meta:assert sha(source)==meta['sha256'],str(source)
    # Verify generated page JSON, not just its presence.
    import re
    for filename in ('index.html','20261101/index.html'):
        s=(P/filename).read_text(encoding='utf-8');board=json.loads(re.search(r'<script id="board-data" type="application/json">(.*?)</script>',s,re.S).group(1))
        assert len(board['matches'])==25
        for r in board['matches']:
            source=next(x for x in today['matches'] if str(x['matchId'])==r['id']);assert r['p']==(source['prediction']['probabilities'] if source['prediction'] else None)
    report=dict(passed=True,review_rows=28,archived_forecasts=23,missing_archive=5,current_fixtures=25,current_forecasts=24,unique_probability_vectors=24,raw_duplicates_merged_current_predicted=duplicate_merges,current_shared_historical_pairs=common,results_500_all_agree=True,archive_sha256_verified=True,case_inputs_market_and_outcome_free=True,poisoning_ignored=True,all_before_kickoff=True,source_hashes_verified=True,html_json_equal=True)
    (D/'verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(report,ensure_ascii=True))
if __name__=='__main__':main()
