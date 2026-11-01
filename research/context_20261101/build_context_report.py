import csv,datetime as dt,hashlib,html,json,shutil,subprocess,zipfile
from pathlib import Path
from collect_expanded_context import B,P,D,RAW,TZ,read,write
def h(s):return html.escape(str(s))
def main():
    coverage=read(D/'coverage.json');fc=read(D/'fotmob-coverage.json');ctx=read(D/'fixture-context.json');fs={x['match_id']:x for x in read(D/'fotmob-fixture-features.json')};cur={x['match_id']:x for x in read(D/'fotmob-current-context.json')}
    rows=[];wide=[]
    for r in ctx:
        mid=r['match_id'];p='Understat' if all(s['xg_rows'] for s in r['sides'].values()) else 'FotMob';features=r['sides'] if p=='Understat' else fs.get(mid,{}).get('sides',r['sides']);both=all(s.get('xg_rows',0)>=5 for s in features.values())
        srows=[];data={}
        for side in ('home','away'):
            v=features[side];s=r['sides'][side];n=v.get('xg_rows',0);den=s['selected_model_history'];xgf=v.get('weighted_xgf');xga=v.get('weighted_xga');gf=v.get('weighted_goals_for_matched');ga=v.get('weighted_goals_against_matched')
            data[side]=dict(source=p,xg_rows=n,selected_rows=den,weighted_xgf=xgf,weighted_xga=xga,weighted_gf_matched=gf,weighted_ga_matched=ga,listed_injury_records=len(s['injury_suspension_records']),rest_calendar_days=s['minimum_observed_rest_calendar_days'],recent_matches=s['cross_competition_recent_games'][:5])
            last=s['cross_competition_recent_games'][0] if s['cross_competition_recent_games'] else None
            xg=f'{xgf:.2f} / {xga:.2f}' if xgf is not None else '缺失'
            srows.append(f'<td>{n}/{den}<br><small>{p}</small></td><td>{xg}</td><td>{len(s["injury_suspension_records"])}</td><td>{h(last["date"])}<br>{h(last["competition"])} · {h(last["opponent"])}</td>' if last else f'<td>{n}/{den}</td><td>{xg}</td><td>待补</td><td>待补</td>')
        notes=[]
        if r['phase']!='Regular Season':notes.append('阶段：'+r['phase'])
        if mid=='2042427':notes.append('斯巴达周中杯赛120分钟，官网已核实；两队联赛历史之外的负荷')
        if mid=='2042423':notes.append('两队周中杯赛；布兰官网另列多名伤病球员，门户清单不完整')
        if mid=='2042428':notes.append('阿森纳同11场：加权实际进球1.50、xG1.97，原小球判断需要复核')
        if mid=='2042417':notes.append('xG仅主2客1场；两队官网清单各6人不可用；开球16:00已由俱乐部核实')
        if mid=='2042415':notes.append('开球15:00已由大阪钢巴官网核实；不采用ESPN较早一小时的时间')
        if mid=='2042436':notes.append('另补12条杯赛历史，11条可确认90分钟范围；本版原预测仍留空')
        notes.append('首发未获俱乐部确认；天气预报已取得' if cur.get(mid,{}).get('weather_forecast') else '首发未获俱乐部确认')
        rows.append(f'<tr data-id="{mid}"><th>{h(r["number"])}<br>{h(r["home"])}—{h(r["away"])}</th>{"".join(srows)}<td>{h("；".join(notes))}</td></tr>');wide.append(dict(match_id=mid,number=r['number'],home=r['home'],away=r['away'],both_sides_5plus_xg=both,sides=data,notes=notes))
    write(D/'coverage-by-fixture.json',wide)
    totals=dict(fixtures=25,fixtures_both_sides_at_least5_xg=sum(r['both_sides_5plus_xg'] for r in wide),understat_own_xg_observations=coverage['xg_own_team_observations'],fotmob_own_xg_observations=fc['own_matched_xg_observations'],sporttery_listed_injury_records=coverage['listed_injury_suspension_records'],cross_competition_team_schedules=50,espn_historical_events=coverage['unique_historical_event_matches'],espn_verified_red_timelines=coverage['red_timeline_verified_matches'],espn_onfield_red_matches=coverage['matches_with_on_field_red'],understat_shot_verified_matches=coverage['unique_shot_quality_matches'],fotmob_shot_verified_matches=fc['shot_quality_sum_verified_matches'],weather_forecasts=fc['current_weather_forecasts'],confirmed_current_xi=0,kickoff_discrepancies_resolved_with_clubs=2,extra_cup_history=fc['extra_cup_history'],extra_cup_90verified=fc['extra_cup_normal90'],probabilities_changed=False,collected_at=dt.datetime.now(TZ).isoformat())
    write(D/'summary.json',totals)
    (D/'REPORT.md').write_text('''# 2026-11-01逐场数据补充

本轮面向今日25场、50支球队实际抓取数据。23场的两队各至少取得5场可匹配xG。Understat279条、FotMob249条为球队历史观察行，不是528个独立比赛；同一历史比赛涉及双方时只储存一个比赛事件对象。所有xG、射门、红牌和球员记录均对应具体比赛，不读取联赛均值作为输入。

## 已取得

- 25场的伤停端点、580条球员摘要；门户伤停清单163条、覆盖21场。它不是163名已由俱乐部确认缺阵的球员。
- 50支球队跨赛事近期赛程，可识别周中杯赛、欧战；日期差是日历天数，不是精确休息小时。
- ESPN465场历史事件，464场红牌时间线通过交叉校验，66场含已判定在场红牌；463场完整实际历史首发。均为赛后补采，不伪称赛前快照。
- Understat240场射门质量明细通过逐射门xG总和核验；23场取得合规的红牌前xG分段。FotMob另170场射门明细通过总和核验，保留射门位置、球员、门将、xG与射正后xG字段，不与Understat数值混成一个来源。
- 韩职另取34场500历史详情及7条红牌事件。部分技术表有占位0，射门统计不直接入模；红牌是否在场仍需独立核查。
- 25场天气预报及预计/上一场阵容。当前俱乐部确认首发0场；lastStarting11、predicted、预计首发均不升级成确认首发。天气风速单位未核验，不用于数值修正。
- 巴西杯额外12条杯赛历史，11条确认90分钟范围，1条含额外时段风险而排除90分钟试算；原发布版024继续留空。

## 原判断遗漏了什么

1. 格罗宁根—斯巴达：斯巴达俱乐部确认周中杯赛踢120分钟后点球出局，格罗宁根也刚踢杯赛。原同赛事历史没有这些负荷；120分钟是球队比赛时长，不代表每名球员都踢满。
2. 布兰—莫尔德：跨赛事记录显示两队周中有杯赛；布兰官网明确有近期及长期伤病、无停赛，并公布当地13:15发布阵容。门户只列少数人，不能把空名单当全员健康。
3. 利物浦—阿森纳：阿森纳同11场匹配历史的加权实际进球1.50、xG1.97，实际失球0.64、xGA1.05。这要求重新验证原小球侧。数值只是同样本描述，不是新概率。
4. 珀斯—阿德莱德：官网两队不可用名单各6人，阿德莱德周中另有亚冠二级比赛。当前冻结窗口中可匹配xG仅主2客1，尚不足稳定融合。
5. 町田—大阪钢巴、珀斯—阿德莱德：ESPN比其他源早一小时；已用两家俱乐部官网分别确认北京时间15:00、16:00。原官方赛程无需改动。

## 数值入口要求

进球与xG来自同一批比赛，不能当两票独立证据相加。首发预计、伤停传闻、空记录和0值分别保留。新的来源数据必须先在相同球队历史上比较融合比例与缺失覆盖，再验证0–1、5+、6+。本轮只增加事实与研究数据，没有手工调高或压低今天概率。

主要文件：fixture-context.json、coverage-by-fixture.json、normalized-history.json、fotmob-normalized-history.json、club-verified-facts.json、kickoff-resolution.json、summary.json。原始响应及抓取时间、SHA256在raw/，由单独原始数据压缩包交付；Git仓库只发布标准化数据、报告与复现脚本。

每场数据覆盖与不足详见context.html。源端未提供的字段仍为空，不声称已经补全所有基本面。

以上仅为公开信息整理后的娱乐分析，不构成任何购彩建议，请理性参考。
''',encoding='utf-8')
    page='''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>逐场数据补充 · 11月1日</title><style>*{box-sizing:border-box}body{margin:0;background:#f1f5fa;color:#192f49;font:14px/1.75 'Microsoft YaHei',sans-serif}main{max-width:1500px;margin:auto;padding:25px}a{color:#2856ac}h1{font-size:30px}h2{font-size:21px;margin-top:28px}.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:12px}.cards p{background:white;padding:18px;border:1px solid #dce5ef;border-radius:8px}.cards b{display:block;font-size:26px}.scroll{overflow:auto;max-height:75vh;border:1px solid #dce5ef}table{border-collapse:separate;border-spacing:0;width:100%;min-width:1300px;background:white}th,td{padding:12px;border:1px solid #e6edf5;text-align:left;vertical-align:top}thead th{background:#eaf0f8;position:sticky;top:0;z-index:3}tbody th{position:sticky;left:0;z-index:2;background:#fff;min-width:190px}small{color:#61748b}.note{color:#61748b}li{margin:10px 0}@media(max-width:600px){main{padding:15px}h1{font-size:25px}.cards{grid-template-columns:1fr 1fr}.cards p{padding:12px;font-size:12px}.cards b{font-size:22px}}</style><main><p><a href="index.html">返回原预测</a> · <a href="review.html">昨日复盘</a> · <a href="data/enrichment/20261101/REPORT.md">完整说明</a></p><h1>这次补到了哪些单场数据</h1><p>今日25场、50支球队。所有来源保留抓取记录；只增补事实，没有改写09:36冻结的概率。下面“主/客”对应各队自己的历史。</p><section class="cards"><p>双方各至少5场xG<b>23/25场</b>澳超仅主2客1；巴西杯另列研究历史</p><p>门户列出的伤停记录<b>163条</b>需要俱乐部核实，空清单不等于健康</p><p>核验过红牌时间线<b>464场</b>其中66场确认有在场红牌</p><p>确认的当前首发<b>0场</b>预计阵容、上一场首发均不冒充确认</p></section><h2>三条会影响原判断的新证据</h2><ul><li><b>015 格罗宁根—斯巴达：</b>斯巴达<a href="https://www.sparta-rotterdam.nl/sparta-in-het-hoge-noorden-tegenover-fc-groningen/">官网确认</a>周中杯赛踢120分钟后点球出局；格罗宁根也刚踢杯赛。这个负荷没有进入原先仅看联赛的计算。</li><li><b>011 布兰—莫尔德：</b><a href="https://www.brann.no/nyheter/for-kampen-brann-molde-2026h">布兰官网</a>明确列出多名近期及长期伤病。两队均有周中杯赛；不能只因历史进球多就把疲劳和阵容略过。</li><li><b>016 利物浦—阿森纳：</b>阿森纳同11场匹配样本的加权实际进球1.50、xG1.97；实际失球0.64、xGA1.05。原小球倾向需要重新验证，尚不能据此规定加多少进球。</li></ul><h2>25场覆盖表</h2><p>xGF/xGA是同一来源、已匹配球队历史的加权描述，未匹配场次不补零，也不与其他来源拼平均。日期为北京时间。伤停列是门户条数；跨赛事最近一战用于核查负荷，未当成新的进球率。</p><div class="scroll"><table><thead><tr><th>比赛</th><th>主队xG覆盖</th><th>主队xGF/xGA</th><th>主队伤停条数</th><th>主队最近一战</th><th>客队xG覆盖</th><th>客队xGF/xGA</th><th>客队伤停条数</th><th>客队最近一战</th><th>核查说明</th></tr></thead><tbody>'''+''.join(rows)+'''</tbody></table></div><h2>仍然不能直接进入概率的部分</h2><p>逐场数据已取得不等于缺阵系数已验证。实际进球与xG、射门与机会数互相关联，不能重复加分；红牌要区分是否在场、发生时间和比赛状态；天气是预报，非比赛实况。当前所有比赛仍是低置信研究观察。</p><p>原始数据包另附；<a href="data/enrichment/20261101/summary.json">覆盖汇总</a> · <a href="data/enrichment/20261101/coverage-by-fixture.json">逐场结构化数据</a> · <a href="data/enrichment/20261101/club-verified-facts.json">俱乐部核实记录</a> · <a href="data/enrichment/20261101/verification.json">验证结果</a></p><p class="note">仅90分钟总进球，不含加时和点球。以上仅为公开信息整理后的娱乐分析，不构成任何购彩建议，请理性参考。</p></main></html>'''
    (P/'context.html').write_text(page,encoding='utf-8')
    with (D/'coverage.csv').open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.writer(f);w.writerow(['编号','主队','客队','来源','主队xG场数','客队xG场数','主xGF','主xGA','客xGF','客xGA','备注'])
        for x in wide:w.writerow([x['number'],x['home'],x['away'],x['sides']['home']['source'],x['sides']['home']['xg_rows'],x['sides']['away']['xg_rows'],x['sides']['home']['weighted_xgf'],x['sides']['home']['weighted_xga'],x['sides']['away']['weighted_xgf'],x['sides']['away']['weighted_xga'],'；'.join(x['notes'])])
    print(json.dumps(totals,ensure_ascii=True))
if __name__=='__main__':main()
