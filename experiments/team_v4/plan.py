"""Fixed candidate set and objective, written before this run's evaluation."""
import copy
BASE=dict(name='v3',family='baseline',other=.5,half=180,limit=12,season_weight=1,variance='original')
CANDIDATES=[BASE]
def add(name,family,**kw):
    c=dict(BASE,name=name,family=family);c.update(kw);CANDIDATES.append(c)
add('unbiased','weighted_variance',variance='unbiased')
add('cluster','overlap_covariance',variance='cluster')
for half in (45,90,365):add('half_'+str(half),'time_window_venue',half=half)
for n in (8,20):add('window_'+str(n),'time_window_venue',limit=n)
for v in (.25,.75,1):add('venue_'+str(v),'time_window_venue',other=v)
for v in (0,.25,.5):add('season_'+str(v),'regime',season_weight=v)
add('recent_gap','regime',gap=True)
for k in (1.35,2):add('huber_'+str(k),'outlier',robust=k)
for strength in (.25,.5):add('opponents_'+str(strength),'opponent_strength',opponents=strength)
for factor in (.25,.5,1):add('process_'+str(factor),'distribution',process=factor,variance='cluster')
for alpha in (.1,.25):add('empirical_'+str(alpha),'distribution',empirical=alpha,variance='cluster')
for alpha in (.25,.5):add('hurdle_'+str(alpha),'distribution',hurdle=alpha,variance='cluster')
for half in (90,180):
    for season in (.5,1):
        add(f'combo_{half}_{season}','combined',variance='cluster',half=half,season_weight=season,process=.25)
PROTOCOL=dict(training_start='2026-04-01',training_end='2026-09-28',embargo_days=2,
    rolling_test_months=['2026-06','2026-07','2026-08','2026-09','2026-10'],
    objective='mean(Brier P0-1, Brier P5+, Brier P6+) + 0.01 * eight-bucket logloss',
    eligibility='at least 200 baseline-available training targets; candidate covers every baseline training target; logloss <= baseline + 0.02',
    selection='minimum objective, then logloss, then name; candidates include unchanged v3',
    evaluation='paired fixtures plus all-target coverage; daily top20pct ranking, AP, calibration, date-block bootstrap',
    warning='October and earlier model evaluations have previously been viewed; all results remain retrospective, not blind',
    no_league_statistics_or_priors=True,no_market_inputs=True,no_html_changes=True)
