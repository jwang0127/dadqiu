# 独立模型实验 v4

本目录不会修改网站、生产模型或data中的原始预测。详细结论见REPORT.md；最终决定在results/decision.json。

从仓库根目录运行，Python 3.10+、仅标准库：

```sh
python experiments/team_v4/test_engine.py
python experiments/team_v4/run.py
python experiments/team_v4/report.py
python experiments/team_v4/predict.py examples/historical_case.json --replay
```

研究重算必须显式--replay。前向模式必须提供--manifest，manifest含captured_at、match_id、source_paths（head/all/venue原始响应）、source_sha256、normalized_case_sha256、team_identity_verified、period_90_verified、venue_status_verified。文件路径相对manifest所在目录。每个历史进失球必须能在原始响应中匹配。核实标记依赖可信上游，不构成独立来源认证。

preregistered-plan.json已冻结候选、目标和数据哈希；同样协议允许复算，改目标须另建实验，不覆盖本轮登记。所有10月成绩都是已查看数据上的回顾性结果，不是新盲测。

结果含逐月选择、全部候选、覆盖不足、分箱校准、AP、每日前20%与前五、按日期分块1500次bootstrap、今日冻结数据重算和全部10月预测。opponent_histories.json只按个人球队和赛事ID组织更早记录，不包含联赛平均或共同先验。
