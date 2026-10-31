"""python model/predict.py path/to/case.json [--replay]
Future cases need a verified Beijing kickoff. Replay never claims a live forecast.
"""
import argparse,datetime as dt,json
from pathlib import Path
from core import predict,verdict
p=argparse.ArgumentParser(); p.add_argument('case');p.add_argument('--replay',action='store_true');a=p.parse_args()
case=json.loads(Path(a.case).read_text(encoding='utf-8'))
now=dt.datetime.now(dt.timezone(dt.timedelta(hours=8)))
if not a.replay:
    if not case.get('kickoff'): raise SystemExit('Verified kickoff required')
    kickoff=dt.datetime.fromisoformat(case['kickoff']).replace(tzinfo=now.tzinfo)
    if kickoff<=now: raise SystemExit('Already started: use --replay for retrospective evaluation')
prediction=predict(case)
print(json.dumps(dict(match_id=case['match_id'],prediction=prediction,verdict=verdict(prediction),replay=a.replay,generated_at=now.isoformat()),ensure_ascii=False,indent=2))
