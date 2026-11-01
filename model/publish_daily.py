"""Build the 2026-11-01 release from frozen, independently collected inputs.
No outcomes or prices are passed to the production predictor.
Run python model/publish_daily.py after collecting and reviewing the dated files.
"""
import collections,copy,datetime as dt,hashlib,html,json,shutil,statistics
from pathlib import Path
from bs4 import BeautifulSoup
import core,build_html
P=Path(__file__).resolve().parents[1];D=P/'data/daily/20261101';TZ=dt.timezone(dt.timedelta(hours=8))
def read(p):return json.loads(p.read_text(encoding='utf-8'))
def write(p,d):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(d,ensure_ascii=False,indent=2),encoding='utf-8')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def esc(s):return html.escape(str(s))
def pct(p):return f'{100*p:.1f}%'

ISSUES=[
 ('赛果列表缓存与空比分','列表仍有空比分和待派奖状态，逐场详情已有比分。','用500完场记录核对28场球队、开球时间、主客与比分；全部一致。','已修复采集核验'),
 ('预测覆盖口径混乱','28场赛果中只有23场有18:14冻结预测；早场5场没有本版预测。','逐场保留5个未预测行，任何正确率只用23场；不赛后补算充数。','已修复统计口径'),
 ('相对前五被当成强信号','5+前五平均31.1%，并不代表5+发生概率超过一半；0–1前五仅29.3%。','今天一律低置信观察，页面写明相对排名，展示每个阈值概率。','已修复展示'),
 ('单一2/3球掩盖两端','取最大单档会把宽分布压成一个数字。','保留0–7+全分布及4+/5+/6+/0–1；不再把众数当大球答案。','沿用并加强'),
 ('全场与主客场接口重复','同一历史比赛会同时从all/venue接口返回。','以历史context_match_id合并，冲突拒绝；昨日实际入模重复行0条。今天再次逐场审计。','已去重'),
 ('共同交锋的相关性遗漏','昨日3组共同交锋同时用于两队；数据各有意义，但不等于两个独立样本。','页面显示重叠数量；保留聚类协方差候选，不凭一天换成主模型。','数值修正待验证'),
 ('近期状态变化被长期窗口稀释','007近期4场总进球均值4.50，此前8场1.88；原4+仅29.0%。','新增近期4场/此前8场对照警示，不人为给概率加点；短窗口继续历史验证。','诊断已加入'),
 ('红牌与比赛状态没有进入赛前分布','500记录昨日006、015、022客队红牌；红牌也可能降低总进球。','仅作赛后事实，不能把“有红牌”直接当大球理由；历史红牌分钟与正常人数曝光仍需采集。','缺口明确'),
 ('射门质量与阵容覆盖不足','此前德甲xG/红牌候选在24场10月对照没有稳定改善；首发仅3场10月可比。','不使用未经验证的缺阵固定系数；当前缺失情况逐场明示。','候选不升主线'),
 ('赛程阶段/对手差异与过拟合','韩职002/004进入争冠组；普通阶段历史未必可平移。弱队单边失守、对手质量与状态相关也未充分建模。','韩职标阶段切换风险；巴西杯024缺足够已验证90分钟历史，留空。20场窗口只做固定候选复核。','风险层已加入'),
]

def enrich(board):
    soup=BeautifulSoup((D/'raw/500_20261101.html').read_bytes().decode('gb18030',errors='replace'),'html.parser')
    five={t.find_all('td')[0].get_text(strip=True):t for t in soup.select('#table_match tbody tr[fid]')}
    alias={'町田泽维亚':'町田泽维','珀斯光荣':'珀斯','阿德莱德联':'阿德莱德','弗洛西诺内':'弗洛西诺','鹿特丹斯巴达':'鹿斯巴达','毕尔巴鄂竞技':'毕尔巴鄂','米内罗竞技':'米竞技','新英格兰革命':'新英格兰'}
    shadow=[];diagnostics=[]
    for r in board['matches']:
        c=r['case'];p=r['prediction'];f=five[r['matchNumStr']];td=f.find_all('td');_,home,away=f['gy'].split(',')
        assert alias.get(r['homeTeamAllName'],r['homeTeamAllName'])==home,(r['matchNumStr'],'home',home)
        assert alias.get(r['awayTeamAllName'],r['awayTeamAllName'])==away,(r['matchNumStr'],'away',away)
        assert td[3].get_text(strip=True)==r['matchDate'][5:]+' '+r['matchTime'][:5]
        assert f['status']!='4','Refuse to publish a completed game as a new forecast'
        risk=['缺确认首发、完整逐场xG及历史红牌分钟；低置信观察']
        detail=dict(match_id=c['match_id'],verified_500_fixture=True,source_500='https://live.500.com/detail.php?fid='+f['fid'],phase=c['phase'],shared_history=0,changes=[])
        if c['phase']!='Regular Season':risk.append('阶段为'+c['phase']+'，未单独验证阶段效应')
        if p:
            assert core.predict(c)['probabilities']==p['probabilities']
            h=p['home_inputs']['rows'];a=p['away_inputs']['rows'];shared=len({x['context_match_id'] for x in h}&{x['context_match_id'] for x in a});detail['shared_history']=shared
            if shared:risk.append(f'双方历史含{shared}场共同交锋，相关性未校正')
            for side,rows in [('home',h),('away',a)]:
                if len(rows)>=12:
                    recent=statistics.mean(x['goals_for']+x['goals_against'] for x in rows[:4]);prior=statistics.mean(x['goals_for']+x['goals_against'] for x in rows[4:12]);change=recent-prior
                    detail['changes'].append(dict(side=side,recent4_mean=recent,previous8_mean=prior,difference=change))
                    if abs(change)>=1.25:risk.append(c[side+'_team']+f'近4场总进球均值{recent:.2f}，此前8场{prior:.2f}，存在状态变化风险')
                n=p[side+'_inputs']['effective_n']
                if n<6:risk.append(c[side+'_team']+f'有效样本仅{n:.1f}场')
            # A distribution comparison is shown separately and never replaces the frozen forecast.
            import sys
            sys.path.insert(0,str(P/'experiments/team_v4'));import engine
            cfg=next(x for x in read(P/'experiments/team_v4/preregistered-plan.json')['candidates'] if x['name']=='window_20')
            s=engine.predict(c,cfg)
            if s:shadow.append(dict(match_id=c['match_id'],model='window_20_not_promoted',probabilities=s['probabilities'],difference_5plus=sum(s['probabilities'][5:])-p['p5']))
        else:risk.append(f"已核实90分钟历史：主队{len(c['home'])}场、客队{len(c['away'])}场，未达入模门槛；不套联赛均值")
        r['risk_text']=' 风险：'+'；'.join(risk)+'。';r['confidence']='low' if p else 'insufficient';r['source_500']=detail['source_500'];diagnostics.append(detail)
    write(D/'diagnostics.json',diagnostics);write(D/'shadow-window20.json',shadow)
    return board

def review_page(review):
    m=review['metrics'];ranking=review['rankings'];modal=review['modal_diagnostic'];rows=[]
    hi=set(ranking['five_plus_top5']['ids']);lo=set(ranking['zero_one_top5']['ids'])
    for r in review['matches']:
        pp=r['probabilities'];y=r['total'];tags=[]
        if r['match_id'] in hi:tags.append('网页5+前五：'+('中' if y>=5 else '未中'))
        if r['match_id'] in lo:tags.append('网页0–1前五：'+('中' if y<=1 else '未中'))
        if not pp:tags.append('无本版赛前预测，不计正确率')
        shade='background:#dcece9' if y>=5 else 'background:#edf4fd' if y<=1 else ''
        cells=''.join(f'<td>{pct(v)}</td>' for v in pp) if pp else '<td>—</td>'*8
        rows.append(f'<tr data-id="{r["match_id"]}" style="{shade}"><th>{esc(r["number"])} · {esc(r["league"])}<br>{esc(r["home"])}—{esc(r["away"])}</th><td>{r["score"][0]}–{r["score"][1]}<br><b>{y}球</b></td>{cells}<td>{pct(sum(pp[:2])) if pp else "—"}</td><td>{pct(sum(pp[4:])) if pp else "—"}</td><td>{pct(sum(pp[5:])) if pp else "—"}</td><td>{pct(sum(pp[6:])) if pp else "—"}</td><td>{esc("；".join(tags)) or "普通观察"}</td><td><a href="{esc(r["source_500"]["url"])}">500完场</a> · <a href="{esc(r["source_official"])}">官方</a></td></tr>')
    issues=''.join(f'<tr><th>{i+1}. {esc(title)}</th><td>{esc(problem)}</td><td>{esc(action)}</td><td>{esc(status)}</td></tr>' for i,(title,problem,action,status) in enumerate(ISSUES))
    tail=''.join(f'<tr><th>{name}</th><td>{pct(m["tails"][key]["all"]["mean_probability"])}</td><td>{m["tails"][key]["all"]["observed_events"]}/23 · {pct(m["tails"][key]["all"]["observed_rate"])}</td><td>{m[key]:.4f}</td></tr>' for name,key in [('0–1球','zero_one'),('4球以上','four_plus'),('5球以上','five_plus'),('6球以上','six_plus')])
    heads=''.join(f'<th>{i if i<7 else "7+"}球概率</th>' for i in range(8))
    page=f'''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>10月31日完整复盘 · 单场观察</title><style>{build_html.CSS}h2{{font-size:21px;margin-top:28px}}.review-table{{width:100%;border-collapse:collapse;background:white;font-size:13px}}.review-table th,.review-table td{{padding:12px;border:1px solid #dce5ef;text-align:left}}.wide{{min-width:1500px}}.review-table th{{color:#24476c}}.cards{{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:14px}}.cards p{{padding:18px;background:white;border:1px solid #dce5ef;border-radius:8px}}.cards b{{display:block;font-size:26px}}</style><header><div class="wrap top"><a class="brand" href="index.html">单场观察</a><nav><a href="index.html">11月1日预测</a><a href="20261031/index.html">昨日原版</a></nav></div></header><main class="wrap"><section class="hero"><div class="eyebrow">2026.10.31 / 按竞彩营业日 / 90分钟</div><h1>两端筛选表现不理想，失败场次全部保留</h1><p>28/28场取得赛果并与500完场逐场核对，全部一致。23场有18:14冻结预测，早场5场无本版预测，不计正确率。数据与新预测分开保存。</p></section><section class="cards"><p>网页大球前五 · 5球以上<b>0/5 · 0%</b>同组达到4球以上：2/5 · 40%</p><p>网页极小球前五 · 0–1球<b>0/5 · 0%</b>全23场实际0–1球2场</p><p>昨晚后段列出的4场 · 4球以上<b>3/4 · 75%</b>5球以上1/4 · 25%；不可替代网页前五成绩</p><p>单档众数诊断<b>{modal['hits']}/23 · {pct(modal['rate'])}</b>按原分布argmax复算；并非事后宣称发布过23个单球推荐</p></section><h2>概率是否符合实际</h2><p>Brier越小越好。这是一天23场的前向结果，无法证明长期准确。0–1球和5球以上整体偏高，6球以上没有同样偏高，不能统一压缩所有尾部。</p><table class="review-table"><thead><tr><th>事件</th><th>原平均概率</th><th>实际发生</th><th>Brier误差</th></tr></thead><tbody>{tail}</tbody></table><p>八档对数损失 {m['logloss']:.4f}。网页前五名单、昨晚后段名单分别固定，不从赛后挑中场次重组。模型没有比分或胜平负预测，因此不编造这两项正确率。</p><h2>最需要正视的几场</h2><p>不来梅—霍芬海姆2–0：原5+最高仍未打出；拜仁—多特2–2：4+中、5+不中；阿贾克斯—阿尔克马尔1–0：大球警报落空；乌迪内斯—罗马2–5：原5+约17%，未排入前五；巴萨—阿拉维斯6–1：高进球路径实现；007林肯城—伯明翰1–3：近期开放趋势被长期均值稀释。这些比分本身不能证明原因。</p><h2>28场逐场对照</h2><p>绿色为实际5+，蓝色为实际0–1；颜色标实际结果，不表示预测命中。7+合并档，右侧尾部事件重叠。早场5场的破折号必须保留。</p><div class="table-wrap"><table class="review-table wide"><thead><tr><th>比赛</th><th>90分钟赛果</th>{heads}<th>原0–1</th><th>原4+</th><th>原5+</th><th>原6+</th><th>原筛选结果</th><th>核实来源</th></tr></thead><tbody>{''.join(rows)}</tbody></table></div><h2>十个问题与处理状态</h2><div class="table-wrap"><table class="review-table"><thead><tr><th>问题</th><th>证据 / 限制</th><th>处理</th><th>状态</th></tr></thead><tbody>{issues}</tbody></table></div><h2>数值模型为什么暂时保留</h2><p>此前已选定的20场窗口候选，昨日同23场两端目标误差从0.12849降至0.12504，对数损失从1.86064降至1.84245；但此前10月整月未稳定优于主模型。因此今天仅保存候选分布作对照，不用昨日结果重新挑权重。聚类相关性、红牌、xG和首发仍待共同样本与前向验证。</p><p>接下来固定主线与候选，按营业日留档；累计至少10个新营业日、200场可比样本后再作阶段评估。即使达到数量门槛，也需按日期分组的误差区间支持改善，且0–1、5+、6+不能出现明显退步；不承诺达到门槛就换模。</p><p><a href="data/daily/20261101/review.json">全部复盘JSON</a> · <a href="data/daily/20261101/diagnostics.json">今天逐场诊断</a> · <a href="data/daily/20261101/archive-20261031.json">昨日原始预测</a> · <a href="data/daily/20261101/shadow-window20.json">今日候选对照</a></p></main><footer class="wrap">仅90分钟总进球，不含加时和点球。以上仅为公开信息整理后的娱乐分析，不构成任何购彩建议，请理性参考。</footer></html>'''
    (P/'review.html').write_text(page,encoding='utf-8')

def main():
    review=read(D/'review.json');board=enrich(read(D/'forecast.json'))
    assert sha(D/'archive-20261031.json')==review['audit']['archive_sha256']
    write(D/'published-forecast.json',board);write(P/'data/today.json',board)
    validation=read(P/'data/validation.json');build_html.build('today',board,validation);build_html.build('history',board,validation);review_page(review)
    page=P/'index.html';s=page.read_text(encoding='utf-8');s=s.replace('<section class="leaders"', '<p class="note"><a href="review.html">昨日完整复盘</a>：网页5+前五0/5、0–1前五0/5。今天仍是相对排序的低置信观察；概率不因昨日输赢手工加减。韩职争冠组与杯赛另列风险。</p><section class="leaders"');page.write_text(s,encoding='utf-8')
    # Store an immutable dated forecast page. Relative links remain valid via base href.
    dated=P/'20261101';dated.mkdir(exist_ok=True);(dated/'index.html').write_text(s.replace('<head>','<head><base href="../">'),encoding='utf-8')
    out=P.parents[1]/'outputs/20261101';out.mkdir(parents=True,exist_ok=True)
    for f in ('index.html','review.html','validation.html','README.md','RESEARCH.md'):shutil.copy2(P/f,out/f)
    shutil.copytree(P/'data',out/'data',dirs_exist_ok=True);shutil.copytree(P/'20261031',out/'20261031',dirs_exist_ok=True)
    summary=dict(business_date='2026-11-01',published_at=dt.datetime.now(TZ).isoformat(),fixtures=len(board['matches']),forecasts=sum(bool(r['prediction']) for r in board['matches']),missing=[r['matchNumStr'] for r in board['matches'] if not r['prediction']],all_confidence_low=True,model_changed=False,all_500_fixtures_verified=True,archive_unchanged=True)
    write(D/'publication.json',summary);print(json.dumps(summary,ensure_ascii=True))
if __name__=='__main__':main()
