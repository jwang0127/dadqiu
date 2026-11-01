"""Collect observations for the two teams in each frozen fixture. Never adjust forecasts."""
import concurrent.futures,datetime as dt,gzip,hashlib,json,subprocess,sys,time
from pathlib import Path
from bs4 import BeautifulSoup
P=Path(__file__).resolve().parents[2];B=P.parents[1];D=P/'data/enrichment/20261101';RAW=D/'raw';RAW.mkdir(parents=True,exist_ok=True)
TZ=dt.timezone(dt.timedelta(hours=8));API='https://webapi.sporttery.cn/gateway/uniform/football/'
def read(p):return json.loads(p.read_text(encoding='utf-8'))
def write(p,x):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(x,ensure_ascii=False,indent=2),encoding='utf-8')
def fetch(name,url,kind='json',referer='https://www.sporttery.cn/'):
    path=RAW/(name+('.html' if kind=='html' else '.json'))
    if path.exists():return path.read_bytes().decode('gb18030',errors='replace') if kind=='html' else read(path)
    cmd=['curl.exe','-sSL','--compressed','--fail','--max-time','35','-A','Mozilla/5.0','-e',referer]
    if 'understat.com' in url:cmd+=['-H','X-Requested-With: XMLHttpRequest']
    err=''
    for retry in range(2):
        r=subprocess.run(cmd+[url],capture_output=True)
        if r.returncode==0:
            data=r.stdout
            if data[:2]==b'\x1f\x8b':data=gzip.decompress(data)
            if kind=='json':json.loads(data)
            path.write_bytes(data);write(path.with_suffix('.meta.json'),dict(url=url,received_at=dt.datetime.now(TZ).isoformat(),sha256=hashlib.sha256(data).hexdigest(),not_a_historical_prekick_snapshot=True))
            return data.decode('gb18030',errors='replace') if kind=='html' else json.loads(data)
        err=r.stderr.decode(errors='replace')[-200:]
    raise ValueError(err)
LEAGUES=['jpn.1','kor.1','aus.1','ned.1','ita.1','esp.1','swe.1','nor.1','ger.1','eng.1','por.1','fra.1','bra.copa_do_brasil','usa.1']
def collect():
    board=read(P/'data/today.json');diag={r['match_id']:r for r in read(P/'data/daily/20261101/diagnostics.json')};jobs=[]
    for r in board['matches']:
        mid=str(r['matchId']);fid=diag[mid]['source_500'].split('fid=')[-1]
        jobs.extend([(f'injury_{mid}',API+f'getInjurySuspensionV1.qry?sportteryMatchId={mid}','json','https://www.sporttery.cn/'),(f'player_{mid}',API+f'getMatchPlayerV1.qry?sportteryMatchId={mid}&termLimits=20','json','https://www.sporttery.cn/'),(f'allcomp_{mid}',API+f'getMatchResultV1.qry?sportteryMatchId={mid}&termLimits=20&tournamentFlag=0&homeAwayFlag=0','json','https://www.sporttery.cn/'),(f'500_{mid}',f'https://live.500.com/detail.php?fid={fid}','html','https://live.500.com/')])
    for league in ['EPL','La_liga','Bundesliga','Serie_A','Ligue_1']:
        for year in (2025,2026):jobs.append((f'understat_{league}_{year}',f'https://understat.com/getLeagueData/{league}/{year}','json',f'https://understat.com/league/{league}/{year}'))
    for league in LEAGUES:
        for year in (2025,2026):jobs.append((f'espn_board_{league}_{year}',f'https://site.api.espn.com/apis/site/v2/sports/soccer/{league}/scoreboard?dates={year}&limit=1000','json','https://www.espn.com/'))
    results=[]
    def job(j):
        try:
            d=fetch(*j);return dict(name=j[0],url=j[1],ok=True)
        except Exception as e:return dict(name=j[0],url=j[1],ok=False,error=str(e))
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        for i,x in enumerate(pool.map(job,jobs),1):
            results.append(x)
            if i%20==0:print('source requests',i,'/',len(jobs),flush=True)
    write(D/'collection-log.json',results);print(json.dumps(dict(requests=len(results),ok=sum(r['ok'] for r in results),failures=[r for r in results if not r['ok']]),ensure_ascii=True),flush=True)
if __name__=='__main__':collect()
