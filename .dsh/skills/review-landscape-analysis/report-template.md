# <研究主题> · 综述格局与最新研究分析

> 执行分支：<exact_review_anchored / adjacent_review_fallback / no_related_reviews>
> 综述检索日期：<system date>；研究论文窗口：<time anchor minus 6 months or Module 01 window> 至 <system date>。

## A｜相关综述

### 01｜<论文名称>

- 相关层级：完整主题综述/邻近主题综述（关键词回退）
- 相关度与匹配关键词：
- 发表时间：
- 发表期刊：
- Nature Index期刊：是/否/暂无法核验
- 引用次数：<count>（截至 <date>，OpenAlex）
- 论文链接：
- Full-text访问：开放获取PDF/学校SSO授权PDF/学校未订阅/许可限制/仅摘要/其他
- 做综述的原因：
- 综述结构：
- 未来发展趋势：
- 证据等级：全文/仅摘要/元数据

按发表时间从新到旧编号。优先列出完整主题综述。若没有同时锚定全部核心关键词的完整主题综述，先明确报告这一结论，再列出按重要关键词相关度选出的全部邻近主题综述（最多5篇）。这些邻近综述必须继续接受与完整主题综述相同的全文访问、综述原因、结构、未来趋势、TrendClaim、时间锚点和研究对照分析，不得停在题名/摘要筛选。没有合法开放PDF时先记录`login_required`，再用编号纯文本询问是否由用户在学校官方页面登录、确认学校未订阅，或按摘要继续。不要在聊天中收集学校账号、密码或MFA，也不要从摘要猜测全文结构。

## B｜时间锚点、趋势基线与TrendClaims

- 时间锚点：<最新相关综述；可以只有摘要>
- 趋势基线：<最新且有注册PDF和未来趋势证据的综述；可以与时间锚点不同>

列出标准化TrendClaim的id、名称、说明及来源综述。没有相关综述时明确进入`no_related_reviews`，本节不虚构趋势。

## C｜研究论文与趋势关系

- 统计窗口：
- Module 01复用论文数：
- 缺口补检论文数：
- 查询完整性：

### 与TrendClaim相符

列出论文、TrendClaim id和依据。

### 对TrendClaim的延伸

列出论文、TrendClaim id、延伸内容和新增价值。

### 综述之外的新研究

列出论文、新方向及为何不匹配任何TrendClaim。没有相关综述时，相关研究统一从此分支分析。

## D｜目前值得开展的综述视角

### 视角 01｜<候选题目>

- 核心问题：
- 与前述综述的相同点：
- 与前述综述的不同点：
- 新增研究证据：
- 建议边界：
- 风险与限制：

提出3–5个有实质差异的视角，按推荐程度排序。

## E｜用户视角选择

After 3–5 perspectives are saved, every runtime presents one numbered plain-text option per perspective and waits for an explicit reply.

Example labels:

- 视角1｜<短标题>
- 视角2｜<短标题>
- ……

选择一个视角会将对应分支标记为`selected_for_module03`，并创建或恢复该视角独立的Module 03大纲设计run。DeepSeek Harness在真实子Session中继续；Kiro Crew或Codex没有可见分支时在逻辑分支中继续。用户返回Parent后仍可选择其他视角，各大纲版本互不覆盖。

Module 02不写正文。

## 输出要求

- 对话只显示简报：综述数、两个锚点、TrendClaim数、三类论文数及候选视角。
- 完整逐篇内容保存为Markdown和结构化工件，向用户提供路径。
