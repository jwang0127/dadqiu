import concurrent.futures,datetime as dt,json,re
from bs4 import BeautifulSoup
from collect_expanded_context import D,RAW,P,read,write,fetch
def main():
    board=read(P/'data/today.json');di={r['match_id']:r for r in read(P/'data/daily/20261101/diagnostics.json')};jobs={};rows=[]
    for r in board['matches']:
        if r['matchNumStr'] not in ('周日002','周日004'):continue
        mid=str(r['matchId']);fid=di[mid]['source_500'].split('fid=')[-1]
        s=BeautifulSoup(fetch('500_analysis_'+mid,f'https://odds.500.com/fenxi/shuju-{fid}.shtml','html','https://live.500.com/'),'html.parser')
        for side,suffix in [('home','1'),('away','0')]:
            for tr in s.select('#team_zhanji1_'+suffix+' tr[fid]'):
                td=tr.find_all('td');d=td[1].get_text(strip=True);em=tr.select_one('.dz em')
                if not re.fullmatch(r'\d{2}-\d{2}-\d{2}',d) or not em:continue
                day=dt.datetime.strptime(d,'%y-%m-%d').date().isoformat();sc=re.fullmatch(r'(\d+):(\d+)',em.get_text(strip=True))
                if not sc or day>=r['matchDate']:continue
                spans=[tr.select_one('.dz-l'),tr.select_one('.dz-r')];names=[]
                for sp in spans:
                    for q in sp.select('.gray'):q.decompose()
                    names.append(sp.get_text(strip=True))
                rec=dict(match_id=mid,side=side,provider_match_id=tr['fid'],date=day,home=names[0],away=names[1],score=list(map(int,sc.groups())),competition=td[0].get_text(strip=True))
                rows.append(rec);jobs[tr['fid']]=('500_history_'+tr['fid'],f'https://live.500.com/detail.php?fid={tr["fid"]}','html','https://live.500.com/')
    results=[]
    def job(j):
        try:fetch(*j);return dict(name=j[0],ok=True)
        except Exception as e:return dict(name=j[0],ok=False,error=str(e))
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:results=list(pool.map(job,jobs.values()))
    write(D/'korean-history-index.json',rows);write(D/'korean-download-log.json',results)
    print(json.dumps(dict(history_rows=len(rows),unique_matches=len(jobs),downloaded=sum(x['ok'] for x in results)),ensure_ascii=True))
if __name__=='__main__':main()
