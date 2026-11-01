# 公开模型研究后的单场模型

研究目的：学习可检验的方法，不照搬会使用联赛共同先验的拟合流程。每场仍只读取两队自己的历史记录；历史对手候选只读取所遇对手个人的更早比赛。方法参数可以相同，输入数据和逐场估计不共用。

|参考|借鉴／检验|没有照搬|
|---|---|---|
|[Dixon & Coles (1997)](https://doi.org/10.1111/1467-9876.00065)|time decay and team attack/defence structure|whole-population joint fitting; fixed-rate low-score correction does not change 3+ probability|
|[penaltyblog model documentation](https://penaltyblog.readthedocs.io/en/latest/models/overview.html)|benchmark distribution families on identical fixtures|hierarchical league-wide priors and claims of automatic improvement|
|[Stan posterior predictive sampling](https://mc-stan.org/docs/2_36/stan-users-guide/posterior-prediction.html)|account for parameter uncertainty; own-sample moment matching tested as approximation|claiming a full Bayesian posterior without fitting one|
|[Gneiting & Raftery (2007)](https://doi.org/10.1198/016214506000001437)|proper probability scores and calibration checks|choosing only on a selected win count|
|[Forecasting: Principles and Practice](https://otexts.com/fpp3/toolbox.html)|time-ordered evaluation and pre-target inputs|randomly mixing future and earlier observations|

Dixon–Coles在两队强度固定时仅修正总进球0、1、2中的若干结构，3+概率不变，因此不能仅换这个名称就声称大球预测改进。我们没有拟合其全联赛共同强度与主场参数。
新增两个候选：按本场两队自身样本方差与有效样本量作负二项矩匹配；按两队自身历史比赛节奏作精确加权泊松混合。前者是预测不确定性的近似，不冒充完整贝叶斯后验；后者可能把比赛随机噪声也混入强度，须通过开发样本决定是否采用。
十种候选只在7月—9月28日355个共同样本比较，选中own_uncertainty。10月未用于选参数，但此前已经查看过10月表现，因此这轮仍不是新盲测。

|区间|模型|同场数|Brier3↓|Brier4↓|对数损失↓|高概率组平均|高概率组实际3+|
|---|---|---:|---:|---:|---:|---:|---:|
|last30|old_venue6|214|0.26144|0.22883|1.96655|69.3%|54.9%|
|last30|slow_own_blend|214|0.24660|0.21785|1.91902|68.2%|60.7%|
|last30|own_uncertainty|214|0.24672|0.21770|1.91821|67.8%|59.8%|
|last20|old_venue6|179|0.26310|0.22653|1.97391|69.5%|53.3%|
|last20|slow_own_blend|179|0.24840|0.21753|1.92733|68.1%|59.7%|
|last20|own_uncertainty|179|0.24839|0.21728|1.92630|67.7%|58.7%|

即使评分改善，仍不能把模型输出称为真实命中率。网页只展示每场的总进球倾向与逐队解释，完整概率、样本和全部失败留在数据文件中供核查。
所有资料取目标日期至少两天前；当前首发和伤停只作单独核查，不对历史回放作事后补写。