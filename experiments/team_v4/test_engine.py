"""Meaningful adversarial checks for temporal isolation and uncertainty math."""
import copy,datetime as dt,hashlib,json,unittest
import engine
from plan import BASE,CANDIDATES

def case():
    day=dt.date(2026,10,31);h=[];a=[]
    for i,total in enumerate([1,2,3,4,5,6]):
        row=dict(date=(day-dt.timedelta(days=7*(i+1))).isoformat(),age=7*(i+1),venue='home',goals_for=total//2,goals_against=total-total//2,own_season=True,source_competition_id='78',opponent_id='B',context_match_id=str(i))
        h.append(row);r=copy.deepcopy(row);r.update(venue='away',goals_for=row['goals_against'],goals_against=row['goals_for'],opponent_id='A');a.append(r)
    return dict(match_id='target',date=day.isoformat(),kickoff='2026-10-31 22:30',home_id='A',away_id='B',source_competition_id='78',home=h,away=a)

class Audit(unittest.TestCase):
    def test_weight_correction_and_shared_fixture_covariance(self):
        c=case();u=engine.predict(c,dict(BASE,name='u',variance='unbiased'));g=engine.predict(c,dict(BASE,name='g',variance='cluster'))
        # Identical mirrored observations are one sample, not two independent
        # samples: combined variance must equal one side's coherent HC variance.
        self.assertAlmostEqual(g['uncertainty_variance'],g['home_inputs']['hc_mean_var'])
        side=u['home_inputs'];aa=side['normalized'];xs=[r['goals_for']+r['goals_against'] for r in side['rows']];m=sum(a*x for a,x in zip(aa,xs));manual=sum(a*(x-m)**2 for a,x in zip(aa,xs))/(1-sum(a*a for a in aa))
        self.assertAlmostEqual(side['unbiased_var'],manual)
    def test_future_rows_and_stale_age_cannot_change_result(self):
        c=case();cfg=dict(BASE,name='cluster',variance='cluster');p=engine.predict(c,cfg)
        future=copy.deepcopy(c['home'][0]);future.update(date=c['date'],age=0,goals_for=99);c['home'].append(future)
        self.assertEqual(engine.predict(c,cfg),p)
        c['home'].pop()
        for side in ('home','away'):
            for r in c[side]:r['age']=1
        self.assertEqual(engine.predict(c,cfg),p)
    def test_duplicates_conflicting_identity_and_invalid_scores_fail(self):
        for mutation in ('duplicate','wrong_competition','bool_goal','negative_goal','mirrored_conflict','same_teams'):
            c=case()
            if mutation=='duplicate':c['home'].append(copy.deepcopy(c['home'][0]))
            elif mutation=='wrong_competition':c['home'][0]['source_competition_id']='evil'
            elif mutation=='bool_goal':c['home'][0]['goals_for']=True
            elif mutation=='negative_goal':c['home'][0]['goals_for']=-1
            elif mutation=='mirrored_conflict':c['away'][0]['goals_for']+=1
            else:c['away_id']=c['home_id']
            with self.subTest(mutation=mutation),self.assertRaises(ValueError):engine.validate(c)
    def test_labels_prices_and_league_aggregates_do_not_enter(self):
        c=case()
        for cfg in CANDIDATES:
            if cfg.get('opponents'):continue
            p=engine.predict(c,cfg);poison=copy.deepcopy(c);poison.update(league_mean=99,league_prior=[1]*8,competition='injected',odds=99,actual_total=99)
            self.assertEqual(engine.predict(poison,cfg),p)
    def test_zero_data_and_zero_goals(self):
        c=case();c['home']=[];self.assertIsNone(engine.predict(c,dict(BASE,name='cluster',variance='cluster')))
        c=case()
        for side in ('home','away'):
            for r in c[side]:r['goals_for']=r['goals_against']=0
        for cfg in CANDIDATES:
            if cfg.get('opponents'):continue
            p=engine.predict(c,cfg)
            if p:self.assertEqual(p['probabilities'],[1.0]+[0.0]*7)
    def test_opponent_history_excludes_future(self):
        engine.GRAPH.clear();engine.before.cache_clear();day=dt.date(2026,10,1)
        engine.GRAPH[('Z','78')]=[dict(date=(day-dt.timedelta(days=i*7)).isoformat(),gf=i,ga=1,match_id=str(i)) for i in range(6,0,-1)]
        first=engine.before('Z','78',day.isoformat());engine.GRAPH[('Z','78')].append(dict(date=day.isoformat(),gf=99,ga=99,match_id='future'));engine.before.cache_clear()
        self.assertEqual(first,engine.before('Z','78',day.isoformat()))
    def test_live_contract_fails_on_retrospective_or_changed_source(self):
        c=case();head=dict(value=dict(sportteryMatchId='target',uniformHomeTeamId='A',uniformAwayTeamId='B',tournamentId='78',seasonId=42,matchDateTime=c['kickoff']))
        raw=[dict(matchId=r['context_match_id'],matchDate=r['date'],fullCourtGoal=str(r['goals_for'])+':'+str(r['goals_against']),uniformHomeTeamId='A',uniformAwayTeamId='B',tournamentId='78',seasonId=42) for r in c['home']]
        recent=dict(value={side:dict(statistics=dict(uniformTeamId=c[side+'_id']),matchList=raw) for side in ('home','away')})
        blobs={'head':json.dumps(head).encode(),'all':json.dumps(recent).encode(),'venue':json.dumps(recent).encode()}
        m=dict(match_id='target',captured_at='2026-10-31T18:00:00+08:00',source_sha256={k:hashlib.sha256(v).hexdigest() for k,v in blobs.items()},normalized_case_sha256=hashlib.sha256(json.dumps(c,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest(),team_identity_verified=True,period_90_verified=True,venue_status_verified=True)
        self.assertTrue(engine.live_contract(c,m,blobs))
        with self.assertRaises(ValueError):engine.live_contract(c,dict(m,captured_at='2026-11-01T00:00:00+08:00'),blobs)
        with self.assertRaises(ValueError):engine.live_contract(c,m,{'head':blobs['head']+b' '})
        with self.assertRaises(ValueError):engine.live_contract(c,dict(m,period_90_verified=False),blobs)
        changed=copy.deepcopy(c);changed['home'][0]['goals_for']+=2;changed['away'][0]['goals_against']+=2
        mm=dict(m,normalized_case_sha256=hashlib.sha256(json.dumps(changed,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest())
        with self.assertRaises(ValueError):engine.live_contract(changed,mm,blobs)

if __name__=='__main__':unittest.main(verbosity=2)
