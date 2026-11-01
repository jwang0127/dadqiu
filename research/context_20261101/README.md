# 11月1日逐场补采

数据目录：data/enrichment/20261101。原始raw/通过独立压缩包交付，未提交Git，以免原始响应重复增加仓库体积。

离线复核：将原始包解压并把其data/enrichment/20261101/raw复制到仓库相同位置，安装requirements-daily.txt后执行：

```text
python research/context_20261101/normalize_expanded.py
python research/context_20261101/normalize_fotmob.py
python research/context_20261101/build_context_report.py
```

采集脚本包含2026-11-01固定赛事身份，是本次研究脚本，不能直接当未来每日通用程序。历史xG与实际首发均为赛后回收；本次并未学习缺阵系数或将新特征用于发布概率。

raw-manifest.json提供原始响应URL、接收时间和SHA256。source_500与Sporttery的比赛编号不相同；代码逐场保留映射。FotMob的阶段id与primaryId分别保留，韩职常规赛和争冠组属于同球队赛季历史，但不假设阶段效应已验证。不同供应商xG不混作同一尺度。
