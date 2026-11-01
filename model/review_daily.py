import sys,json,datetime as dt,collections,hashlib,copy,math,statistics,html
from pathlib import Path
from bs4 import BeautifulSoup
P=Path(__file__).resolve().parents[1];D=P/'data/daily/20261101'
sys.path.insert(0,str(P/'model'));import core
sys.path.insert(0,str(P/'experiments/team_v4'));import engine,run as research
def read(p):return json.loads(p.read_text(encoding='utf-8'))
def write(p,d):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(d,ensure_ascii=False,indent=2),encoding='utf-8')
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    old=read(D/'archive-20261031.json');heads={x['match_id']:x['head'] for x in read(D/'heads-yesterday.json')}
    raw=(D/'raw/500_20261031.html').read_bytes();soup=BeautifulSoup(raw.decode('gb18030',errors='replace'),'html.parser');five={}
    for tr in soup.select('#table_match tbody tr[fid]'):
        tds=tr.find_all('td',recursive=False);num=tds[0].get_text(strip=True);names=tr.get('gy').split(',');pk=tds[6].select('.pk a')
        five[num]=dict(id=tr['fid'],number=num,league=names[0],home=names[1],away=names[2],time=tds[3].get_text(strip=True),status=tr['status'],score=[int(pk[0].get_text(strip=True)),int(pk[2].get_text(strip=True))],url='https://live.500.com/detail.php?fid='+tr['fid'],home_red=int(tds[5].select_one('.redcard').get_text()) if tds[5].select_one('.redcard') else 0,away_red=int(tds[7].select_one('.redcard').get_text()) if tds[7].select_one('.redcard') else 0)
    write(D/'500-results.json',dict(source='https://live.500.com/?e=2026-10-31',raw_sha256=hashlib.sha256(raw).hexdigest(),matches=list(five.values())))
    aliases={'林肯城':'林肯城','林肯':'林肯城','AC米兰':'AC米兰','米兰':'AC米兰','国际米兰':'国际米兰','阿尔克马尔':'阿尔克马','阿尔克马':'阿尔克马','托特纳姆热刺':'热刺','诺丁汉森林':'诺丁汉','布伦特福德':'布伦特','腓特烈斯塔':'腓特烈','门兴格拉德巴赫':'门兴','帕德博恩':'帕德博恩','奥格斯堡':'奥格斯堡','勒沃库森':'勒沃库森','拜仁慕尼黑':'拜仁','曼彻斯特联':'曼联','西悉尼漫步者':'西悉尼','麦克阿瑟FC':'麦克阿瑟','东京FC':'东京FC','大宫松鼠RB':'大宫松鼠RB','金泉尚武':'金泉尚武','马拉加':'马拉加','赫尔城':'赫尔城','伊普斯维奇':'伊普斯维','考文垂':'考文垂','伯恩茅斯':'伯恩茅斯','阿拉维斯':'阿拉维斯','维戈塞尔塔':'塞尔塔','巴列卡诺':'巴列卡诺','皇家贝蒂斯':'贝蒂斯','莱比锡红牛':'莱红牛','沙尔克04':'沙尔克04','博洛尼亚':'博洛尼亚','蒙扎':'蒙扎','利兹联':'利兹联','水晶宫':'水晶宫','乌迪内斯':'乌迪内斯','罗马':'罗马','富勒姆':'富勒姆','阿斯顿维拉':'维拉','多特蒙德':'多特蒙德','斯图加特':'斯图加特','霍芬海姆':'霍芬海姆','云达不来梅':'不来梅','弗赖堡':'弗赖堡','桑德兰':'桑德兰','冈山绿雉':'冈山绿雉','仙台七夕':'仙台七夕','柏太阳神':'柏太阳神','浦和红钻':'浦和红钻','光州FC':'光州FC','巴塞罗那':'巴塞罗那','阿贾克斯':'阿贾克斯','切尔西':'切尔西','伯明翰':'伯明翰','罗森博格':'罗森博格'}
    aliases.update({'麦克阿瑟FC':'麦克阿瑟FC','马德里竞技':'马竞','伊普斯维奇':'伊普斯','巴塞罗那':'巴萨'})
    rows=[];identity_errors=[];shared=0;duplicate=0;vectors=[];historyfingerprints=[]
    for r in old['matches']:
        mid=str(r['matchId']);h=heads[mid];f=five[r['matchNumStr']];goals=list(map(int,h['fullCourtGoal'].split(':')))
        assert f['status']=='4' and f['score']==goals,('result conflict',mid,f,goals)
        expected=(r['matchDate'][5:]+' '+r['matchTime'][:5]);assert f['time']==expected,('time mismatch',mid,f['time'],expected)
        for k,oldk in [('home','homeTeamAllName'),('away','awayTeamAllName')]:
            x=r[oldk];v=aliases.get(x,x)
            if v!=f[k]:identity_errors.append(dict(id=mid,side=k,official=x,five=f[k]))
        pp=r['prediction']['probabilities'] if r['prediction'] else None;y=sum(goals)
        row=dict(match_id=mid,number=r['matchNumStr'],home=r['homeTeamAllName'],away=r['awayTeamAllName'],league=r['leagueAbbName'],score=goals,total=y,probabilities=pp,source_500=f,source_official= 'https://webapi.sporttery.cn/gateway/uniform/football/getMatchHeadV1.qry?source=web&sportteryMatchId='+mid,forecast_at=r['forecast_at'],kickoff=r['kickoff'],frozen_prediction=bool(pp),modal_bucket=core.total_goals_pick(r['prediction']),expected=r['prediction']['total_expected_goals'] if pp else None)
        if pp:
            assert dt.datetime.fromisoformat(r['forecast_at'])<dt.datetime.fromisoformat(r['kickoff'])
            assert core.predict(r['case'])['probabilities']==pp
            vectors.append(tuple(pp));c=r['case'];ids=[{x['context_match_id'] for x in r['prediction'][s+'_inputs']['rows']} for s in ('home','away')];shared+=len(ids[0]&ids[1])
            for s in ('home','away'):
                rs=r['prediction'][s+'_inputs']['rows'];duplicate+=len(rs)-len({x['context_match_id'] for x in rs})
                historyfingerprints.append(hashlib.sha256(json.dumps([(x['context_match_id'],x['goals_for'],x['goals_against']) for x in rs]).encode()).hexdigest())
        rows.append(row)
    write(D/'identity-review.json',identity_errors)
    if identity_errors:print(json.dumps(identity_errors,ensure_ascii=True));return
    eligible=[r for r in rows if r['probabilities']];labels={r['match_id']:r['total'] for r in eligible};cases={str(r['matchId']):r['case'] for r in old['matches'] if r['prediction']};preds={str(r['matchId']):r['prediction'] for r in old['matches'] if r['prediction']};ids=list(cases)
    metrics=research.metrics(ids,preds,cases,labels);modal=sum(min(r['total'],7)==r['modal_bucket'] for r in eligible)
    def top(prob,event,k):
        group=sorted(eligible,key=lambda r:(-prob(r['probabilities']),r['match_id']))[:k]
        return dict(n=len(group),hits=sum(event(r['total']) for r in group),mean_probability=statistics.mean(prob(r['probabilities']) for r in group),ids=[r['match_id'] for r in group])
    ranking=dict(five_plus_top5=top(lambda p:sum(p[5:]),lambda y:y>=5,5),four_plus_top5=top(lambda p:sum(p[4:]),lambda y:y>=4,5),zero_one_top5=top(lambda p:sum(p[:2]),lambda y:y<=1,5))
    shortlist=[r for r in eligible if r['number'][-3:] in ['023','025','027','028']];ranking['late_chat_high_four']=dict(n=len(shortlist),four_plus_hits=sum(r['total']>=4 for r in shortlist),five_plus_hits=sum(r['total']>=5 for r in shortlist),ids=[r['match_id'] for r in shortlist]);ranking['late_chat_low_two']=dict(n=2,hits=sum(r['total']<=1 for r in eligible if r['number'][-3:] in ['016','020']))
    # This challenger was selected on pre-September-29 data, before yesterday's outcomes.
    cfg=next(x for x in read(P/'experiments/team_v4/preregistered-plan.json')['candidates'] if x['name']=='window_20');challenger={}
    for i,c in cases.items():
        cc=copy.deepcopy(c)
        for s in ('home','away'):
            for x in cc[s]:x['age']=(dt.date.fromisoformat(cc['date'])-dt.date.fromisoformat(x['date'])).days
        challenger[i]=engine.predict(cc,cfg)
    paired=[i for i in ids if challenger[i]]
    compare=dict(name='window_20',selection='frozen before yesterday results; development through 2026-09-28',n=len(paired),baseline=research.metrics(paired,preds,cases,labels,False),challenger=research.metrics(paired,challenger,cases,labels,False),promotion=False,reason='One new day cannot override prior October failed promotion; no selection from yesterday results')
    audit=dict(target_duplicates=len(rows)-len({r['match_id'] for r in rows}),duplicate_selected_history_rows=duplicate,shared_head_to_head_history_pairs=shared,unique_prediction_vectors=len(set(vectors)),forecast_count=len(vectors),identical_own_history_sequences=len(historyfingerprints)-len(set(historyfingerprints)),all_500_scores_agree=True,all_500_status_finished=True,all_teams_times_verified=True,archive_sha256=digest(D/'archive-20261031.json'))
    report=dict(business_date='2026-10-31',generated_at=dt.datetime.now(dt.timezone(dt.timedelta(hours=8))).isoformat(),fixtures=len(rows),result_count=len(rows),archived_forecasts=len(eligible),no_forecast=len(rows)-len(eligible),modal_diagnostic=dict(hits=modal,n=len(eligible),rate=modal/len(eligible),warning='diagnostic argmax of archived distribution; not a newly invented published exact pick'),metrics=metrics,rankings=ranking,audit=audit,challenger=compare,matches=rows)
    write(D/'review.json',report)
    print(json.dumps({k:v for k,v in report.items() if k not in ('matches','metrics')},ensure_ascii=True,indent=2));print(json.dumps(dict(metrics={k:v for k,v in metrics.items() if k!='tails'}),indent=2))
if __name__=='__main__':main()
