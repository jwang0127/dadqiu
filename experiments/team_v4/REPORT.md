# 单场总进球模型：十项问题审查与独立优化实验

**网站、原始逐场概率及生产模型均未改动。** 新代码和结果仅位于experiments/team_v4。

本轮广泛检索论文、研究机构与开源项目官方文档，采用12个一手来源。没有借用联赛均值、联赛大球率、共同联赛先验、盘口或外部推荐。参考文献启发候选设计，不意味着完整复刻论文中的联合模型。

## 十项问题、实施与真实状态

|编号|问题及证据|怎么处理|结果与边界|参考|
|---|---|---|---|---|
|1|**历史来源时间与输入证明不够严格**：既有回放事后取数，且推断接口不核对原始响应与标准化记录|新增live_contract：抓取早于开球、原始SHA与case SHA、原始球队身份和逐条进失球一致性校验；90分钟与场地状态未经上游核实则拒绝前向模式|校验实现并测试；无法补造历史时点，过往仍标为回顾性|[Forecast evaluation pitfalls and best practices](https://link.springer.com/article/10.1007/s10618-022-00894-5)|
|2|**只看一个时间切片，重复看10月容易事后挑模型**：10月已在前轮查看，不能重新宣称盲测|预登记候选与目标；6—10月逐月只用此前资料选模，留两天隔离；网站和现版冻结|流程已实现；真正新盲测仍需未来新数据|[Alan Turing Institute: rolling-origin evaluation](https://alan-turing-institute.github.io/tea-techniques/techniques/rolling-origin-evaluation/)|
|3|**选模目标没有对准极小球和高进球**：原版主要按8档对数损失选模，不能代表0–1和5+/6+抓取效果|新目标为三端Brier均值加0.01倍完整分布对数损失；另报AP、分箱、每日前20%与前五及覆盖数|评价与选模目标已修复；不以排序第一冒充强机会|[Evaluating Probabilistic Classifiers: The Triptych](https://arxiv.org/abs/2301.10803)|
|4|**加权方差未作小样本修正**：原公式的加权二阶矩直接除有效样本量|加入1−Σ归一化权重平方的修正，保留原版作消融；不误用频数权重公式|实现和数学检验通过；准确率未证明改善，不自动替换|[NumPy weighted covariance normalization](https://numpy.org/doc/stable/reference/generated/numpy.cov.html)|
|5|**同一交锋重复进入双方历史却被当成独立**：2466个目标中有1347个包含共享历史交锋，合计1778个共享引用|按context_match_id对齐交锋，核对镜像进失球；用同一HC对角与交叉项估算强度协方差|实现并通过完全重合样本检验；统计近似仍需前向检验|[Statsmodels cluster covariance](https://www.statsmodels.org/dev/generated/statsmodels.stats.sandwich_covariance.cov_cluster.html)|
|6|**跨赛季和长间隔记录可能不代表现状**：1047个目标的原始近期12条输入包含旧赛季记录|比较旧赛季权重0/0.25/0.5/1与长间隔降权；不使用联赛回退|排除会靠丢失大量难场而显得更好的方案；其余保留消融结果|[Koopman and Lit: dynamic football model](https://rss.onlinelibrary.wiley.com/doi/abs/10.1111/rssa.12042)|
|7|**12场窗口、180天衰减和主客权重固定**：原参数未按此次两端目标进行独立开发期比较|比较8/12/20场、45/90/180/365天与其他主客权重0.25/0.5/0.75/1；训练期覆盖缺失即不准入|开发期选中20场，10月稳定性不通过，暂不替换|[Scikit-learn TimeSeriesSplit](https://scikit-learn.org/stable/modules/generated/sklearn.model_selection.TimeSeriesSplit.html)|
|8|**一场极端比分可能抬高均值**：887个目标的原始近期12条中有7+总进球记录；这不代表记录错误|比较两档Huber稳健均值；保留真实极端比赛和验证标签，不把高比分删掉|已测试；不因10月某个候选较好而事后更换赢家|[Scikit-learn HuberRegressor](https://scikit-learn.org/stable/modules/generated/sklearn.linear_model.HuberRegressor.html)|
|9|**没有充分区分此前对手强弱**：进攻均值可能来自不同防守能力的历史对手|使用实际遇到的对手个人、更早的自身失球记录作受限比例校正，测试25%/50%融合；日期严格早于那次交锋|实现并检查时间隔离；没有证明稳定胜出，不替换|[Koopman and Lit: dynamic football model](https://rss.onlinelibrary.wiley.com/doi/abs/10.1111/rssa.12042)|
|10|**一个负二项近似未验证能否同时覆盖两端**：参数估计方差与实际比赛波动不同，零球机制也未单独检验|比较自身过程过度离散、经验分布混合和零点hurdle；各项保持概率和为1，混合后均值与原强度明确区分|候选与分布检查完成；完整贝叶斯、射门质量和阵容机制仍未实现|[Statsmodels hurdle count models](https://www.statsmodels.org/v0.14.6/examples/notebooks/generated/count_hurdle.html)|

十项并不等于十项都带来准确率提升。输入、验证、数学一致性问题可以修复；预测方法只能经过比较后保留或拒绝。未证明改善的方案没有被包装为升级。

## 如何防止调到答案上

先写preregistered-plan.json，再计算30个方案（原版加29个改动方案）。开发期为4月1日—9月28日，原版可预测的1465场作为覆盖准入基准。候选必须覆盖全部训练基准场次，且完整分布对数损失不比原版差超过0.02，再按预登记目标选最小值。
逐月滚动验证：每月第一天之前至少两天的数据才可用来选模。6、7、8、9、10月分别评估；不随机打乱比赛。不在10月结果出来之后再选一个10月表现最好的候选。
研究设计和过往版本均已接触部分10月结果，因此本轮从头到尾都是回顾性实验，不会成为新的真正盲测。预登记只防止本轮根据结果继续换目标，不能消除过去看过答案的事实。

## 选中的方案，实际上有没有更好

开发期选中 `window_20`：只把每队窗口从12场扩到20场，保留原来的其他主要参数。这里没有把全部实验修正强行叠加。

|比较范围|同场数|原版目标损失↓|候选目标损失↓|结果|
|---|---:|---:|---:|---|
|6—10月滚动合计|975|0.152962|0.152063|小幅改善|
|last30|277|0.155563|0.155964|变差|
|last20|237|0.158164|0.158008|改善|

该目标＝(0–1球Brier＋5+球Brier＋6+球Brier)/3＋0.01×8档对数损失。它不是命中率。

|近30天，277个共同场次|原版Brier↓|候选Brier↓|原版AP↑|候选AP↑|
|---|---:|---:|---:|---:|
|0–1球|0.154593|0.155345|0.247|0.235|
|5球以上|0.151621|0.151469|0.266|0.261|
|6球以上|0.102267|0.102724|0.186|0.183|

候选减原版的30天目标损失差为0.000401，按比赛日期分块自助法95%区间[-0.001366, 0.002492]，跨过0，不能认定稳定优于原版。

**决定：不提升到生产模型。** 保留现版预测器；把更严格的输入合同、滚动选模、两端指标、覆盖准入和可检验候选作为研究基础。网站内容与现有概率保持原样。

## 每类方法的消融，失败也保留

|方法家族|仅开发期选中的代表|10月目标损失↓|
|---|---|---:|
|baseline|v3|0.155563|
|combined|combo_180_1|0.155790|
|distribution|empirical_0.1|0.155756|
|opponent_strength|opponents_0.25|0.156473|
|outlier|huber_2|0.155113|
|overlap_covariance|cluster|0.155594|
|regime|season_0.5|0.155163|
|time_window_venue|window_20|0.155964|
|weighted_variance|unbiased|0.155573|

部分稳健/赛季方案10月得分好于原版，但开发期并未胜出；不能看完10月再选它当赢家。当前赛季限定候选缺失了大量原版可预测目标，因此不能以更少、更容易的场次宣称胜出。

## 数据与测试

校验2466个目标；本批没有发现不合法目标。共享历史引用1778次，涉及1347个目标；这些是跨目标的引用数量，不是1778场新增独立比赛。1047和887同样是目标数量，不是独立事件数。
7组对抗性测试通过，包含重复/错误赛事/布尔或负数进球、镜像冲突、未来行、过期age、标签和价格注入、零样本与全零进球、对手历史时点、真实源内容SHA、原始历史与标准化记录对应、前向时间戳及不确定性重合样本校验。
live_contract是来源与转换一致性检查，不是加密的第三方取证。90分钟与中立场的核实标记仍须由可信上游给出，缺少时拒绝前向模式；它无法把事后抓取变成真正历史快照。
results/today-recomputed.json只是对原冻结输入的实验重算，不是重新发布的赛前预测，也没有回填网站。

## 还没有解决的现实限制

仍缺少全覆盖、可回放的逐场xG、射门质量、红牌分钟、首发和球员分钟；稳健均值不能代替这些数据。没有假装收集到这些字段，也未手工给伤停加减进球。完整贝叶斯后验、教练更换和中立场机制没有通过本轮完成。
下一步应固定方案与阈值，采集新的开赛前原始响应、身份/90分钟/场地证明和结果快照，再检验0–1、5+、6+的校准与排序；不能继续反复修改到同一批10月样本上。

## 全部一手来源

- [Forecast evaluation pitfalls and best practices](https://link.springer.com/article/10.1007/s10618-022-00894-5)：time-of-availability, data leakage and honest retrospective labels。
- [Alan Turing Institute: rolling-origin evaluation](https://alan-turing-institute.github.io/tea-techniques/techniques/rolling-origin-evaluation/)：repeated earlier-only model selection with date embargo。
- [Evaluating Probabilistic Classifiers: The Triptych](https://arxiv.org/abs/2301.10803)：separate calibration, discrimination and proper probability scores。
- [NumPy weighted covariance normalization](https://numpy.org/doc/stable/reference/generated/numpy.cov.html)：analytic-weight finite-sample denominator; frequency weights are not reliability weights。
- [Statsmodels cluster covariance](https://www.statsmodels.org/dev/generated/statsmodels.stats.sandwich_covariance.cov_cluster.html)：group observations by original fixture; own covariance plug-in is an approximation, not library regression CRV。
- [Koopman and Lit: dynamic football model](https://rss.onlinelibrary.wiley.com/doi/abs/10.1111/rssa.12042)：time-varying individual team strength and opponent attack/defence motivation; no whole-league latent fit copied。
- [Scikit-learn TimeSeriesSplit](https://scikit-learn.org/stable/modules/generated/sklearn.model_selection.TimeSeriesSplit.html)：earlier-only tuning and explicit gap; implemented on dates rather than irregular row-count splits。
- [Scikit-learn HuberRegressor](https://scikit-learn.org/stable/modules/generated/sklearn.linear_model.HuberRegressor.html)：bounded-residual robust location candidate; custom weighted location rather than a copied regression fit。
- [Scikit-learn average precision](https://scikit-learn.org/stable/modules/generated/sklearn.metrics.average_precision_score.html)：threshold-grouped average precision alongside Brier and prevalence。
- [Statsmodels hurdle count models](https://www.statsmodels.org/v0.14.6/examples/notebooks/generated/count_hurdle.html)：separate zero mass and positive counts; own-sample sensitivity candidate, not a fitted full hurdle regression。
- [Stan posterior predictive uncertainty](https://mc-stan.org/docs/stan-users-guide/posterior-prediction.html)：distinguish parameter uncertainty from future match count variation; no full Bayesian claim。
- [StatsBomb: what shot-quality inputs represent](https://blogarchive.statsbomb.com/articles/soccer/understanding-statsbomb-radars/)：document remaining gap: no uniform shot-quality, minutes or lineups available in this sample。

以上仅为公开信息整理后的娱乐分析，不构成任何购彩建议，请理性参考。