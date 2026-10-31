"""Research-only inference, strict prospective provenance or explicit replay.
No HTML generation and no production model/config changes.
"""
import argparse,datetime as dt,json
from pathlib import Path
import engine
HERE=Path(__file__).resolve().parent
p=argparse.ArgumentParser();p.add_argument('case');p.add_argument('--replay',action='store_true');p.add_argument('--manifest');a=p.parse_args()
case=json.loads(Path(a.case).read_text(encoding='utf-8'));selected=json.loads((HERE/'results/selected.json').read_text(encoding='utf-8'))['config']
if not a.replay:
    now=dt.datetime.now(dt.timezone(dt.timedelta(hours=8)));kickoff=dt.datetime.fromisoformat(case['kickoff']).replace(tzinfo=now.tzinfo)
    if kickoff<=now:raise SystemExit('Already started; use --replay')
    if not a.manifest:raise SystemExit('Prospective mode requires source manifest and raw head/all/venue files')
    mp=Path(a.manifest);manifest=json.loads(mp.read_text(encoding='utf-8'))
    blobs={name:(mp.parent/path).read_bytes() for name,path in manifest['source_paths'].items()}
    engine.live_contract(case,manifest,blobs)
if selected.get('opponents'):engine.load_graph(HERE/'opponent_histories.json')
prediction=engine.predict(case,selected)
print(json.dumps(dict(experimental_only=True,promoted=False,replay=a.replay,config=selected,prediction=prediction),ensure_ascii=False,indent=2))
