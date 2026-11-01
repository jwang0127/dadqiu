import concurrent.futures,datetime as dt
from collect_expanded_context import D,RAW,P,TZ,read,write,fetch
MORE={7:5749733,8:5868116,12:5749734,13:5749736,14:5881213,16:5795501,17:5881210,18:5749737,19:5868114,21:5749735,22:5802977,23:5868111}
allgames={int(m['id']):(l,m) for l in read(RAW/'fotmob_data_matches.json')['leagues'] for m in l.get('matches',[])};board=read(P/'data/today.json');mapping=read(D/'fotmob-identities.json')
def job(i):return fetch(f'fotmob_current_{i}',f'https://www.fotmob.com/api/data/matchDetails?matchId={i}','json','https://www.fotmob.com/')
with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:list(pool.map(job,MORE.values()))
for n,i in MORE.items():
    r=next(x for x in board['matches'] if int(x['matchNumStr'][-3:])==n);l,m=allgames[i]
    if not any(x['match_id']==str(r['matchId']) for x in mapping):mapping.append(dict(match_id=str(r['matchId']),number=r['matchNumStr'],provider_match_id=str(i),provider_competition_id=l.get('primaryId',l['id']),provider_phase_id=l['id'],provider_competition=l['name'],home=m['home'],away=m['away']))
assert len(mapping)==25;write(D/'fotmob-identities.json',sorted(mapping,key=lambda x:x['match_id']))
facts=read(D/'club-verified-facts.json');facts['items']+=[
dict(match_id='2042415',club='Gamba Osaka',url='https://www.gamba-osaka.net/gameinfo/index/no/1044/',facts=[dict(kind='kickoff_verification',official_local='2026-11-01T16:00:00+09:00',official_beijing='2026-11-01T15:00:00+08:00',status='Official club, Sporttery, 500 and FotMob agree; ESPN one hour earlier is rejected for current kickoff')]),
dict(match_id='2042417',club='Perth Glory',url='https://perthglory.com.au/news/alm-match-preview-griff-calls-for-front-foot-performance-in-home-clash-with-reds/',published_date='2026-10-30',facts=[dict(kind='kickoff_verification',official_local='2026-11-01T16:00:00+08:00',official_beijing='2026-11-01T16:00:00+08:00',status='Official club, Sporttery, 500 and FotMob agree; ESPN one hour earlier is rejected for current kickoff'),dict(kind='unavailable',team='Perth Glory',players=['Charbel Shamoon','Matt Dench','Henry Hore','Trent Ostler','Calem Nieuwenhof','Brian Kaltak'],status='explicitly listed unavailable in official club preview'),dict(kind='unavailable',team='Adelaide United',players=['Bart Vriends','Jake Najdovski','Dylan Pierias','Jacob Brazete','Ryan White','Mitchell Smith'],status='explicitly listed unavailable in opponent club preview'),dict(kind='recent_match_load',team='Adelaide United',status='Thursday AFC Champions League Two away match against Lion City Sailors, followed by Sunday trip to Perth'),dict(kind='lineup',status='Published squads contain more than 11 players and one omission; not confirmed starting XIs')])]
# Preserve source names as printed by each club; spelling normalization is separate.
write(D/'club-verified-facts.json',facts)
write(D/'kickoff-resolution.json',dict(resolved=[dict(match_id='2042415',accepted_beijing='2026-11-01T15:00:00+08:00',primary_url='https://www.gamba-osaka.net/gameinfo/index/no/1044/'),dict(match_id='2042417',accepted_beijing='2026-11-01T16:00:00+08:00',primary_url='https://perthglory.com.au/news/alm-match-preview-griff-calls-for-front-foot-performance-in-home-clash-with-reds/')],forecast_times_changed=False))
print('All 25 current detail sheets collected; two kickoff discrepancies resolved with primary club sources')
