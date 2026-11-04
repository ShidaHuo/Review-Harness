# Research Review Harness：当前唯一工作流规范

> 版本：v0.11
> 日期：2026-11-03
> 状态：Module 01至Module 04已实现；Module 04按冻结大纲直接生成约15,000字Markdown综述后结束当前MVP任务。

## 跨运行时入口

每个新流程先执行`python runtime_adapter.py`。适配器只改变批处理编排和聊天分支实现，不改变检索口径、证据状态机或写作边界。所有运行时统一使用编号纯文本选择。DeepSeek Harness使用Workflow和Session fork；Kiro Crew使用Python核心及必要的批处理；Codex使用Python核心。原生会话能力不可用时保留SQLite逻辑分支，不得假装创建真实聊天fork。

## 总入口

用户输入“围绕X写一篇综述”只启动Harness，不授权直接写正文。

```text
用户主题
→ Module 01选题可行性评估
→ 用户选择继续/结束
→ Module 02综述格局与最新研究分析
→ 用户选择写作视角
→ Module 03生成分级写作大纲，逐节说明写作逻辑和安排原因
→ 用户反复提出修改，直至明确满意并冻结大纲
→ Module 04在根Agent同一上下文中按冻结大纲直接撰写约15,000字综述，标注图表位置并保存为.md文件
→ MVP任务结束
```

任何路径都不得在Module 01或02生成摘要、引言、正文、详细提纲、图表、Word或LaTeX。Module 03只允许生成和迭代分级写作大纲，不得撰写正文或生成投稿文件。

## Module 01：Research Topic Feasibility Assessment

- 解析完整主题和上位技术。
- Python为标准化主题保存唯一查询计划；所有运行时只能按`query_id`执行，不得提交查询字符串。
- 每个持久化步骤后调用`module01-next`；`create-run`会自动恢复同一标准化主题最新的未完成run，所有命令都返回`next_action`和`must_continue`。当`must_continue=true`时必须在同一轮持续执行，不能在检索或语义筛选中途停止。
- 只检索系统日期前两年的研究型论文。
- 最多3条完整主题查询和3条上位技术查询；每条1页、最多50条。
- 只访问元数据、题名和摘要，不下载或解析PDF。
- 去重并保存语义标签。
- 自动读取Skill内置的177条Nature Index本地目录并附加不可变快照，不再访问Nature网页。
- 输出动态主题统计、期刊、热度、成熟度、综述写作价值和建议。
- 在完整报告后显示编号纯文本：`1. 继续`、`2. 结束`。
- 结束保存`rejected`并终止；继续保存`approved`并进入Module 02。

## Module 02：Review Landscape and Post-Review Research Analysis

- 复用Module 01的TopicProfile、语义确认论文和Nature Index快照。
- 用Python从冻结Module 01计划派生的typed和untyped review-intent查询发现综述。优先采用同时锚定全部核心关键词的综述；若不存在，先明确报告未发现完整主题综述，再纳入并完整分析相关度最高的全部合格邻近综述，最多5篇。
- 每个持久化步骤后调用`module02-next`；在返回`blocking_user_input=false`时持续执行，禁止用中间进度提前结束。
- 先做题名/摘要筛选，只有纳入综述进入PDF阶段。
- PDF优先合法开放版本；没有开放PDF时必须进入`login_required`并显示编号选择。用户只在学校官方页面输入凭据；Codex无认证浏览器时可手动下载合法PDF并登记。学校无订阅或用户选择摘要继续后才允许降级。
- 有PDF才能声称全文证据并提取结构、原因和未来趋势。
- 将未来趋势归一为TrendClaim。
- 分开选择时间锚点和全文趋势基线。
- 没有相关综述时仍根据研究簇生成3–5个首篇综述视角。
- 先规划查询复用，只补检Module 01失败、未覆盖或截断的查询。
- 将研究论文分为趋势相符、趋势延伸、新方向或排除。
- 输出对话简报和完整证据工件。
- 保存3–5个视角，建立可重建的编号纯文本选择和逻辑分支。
- 用户选择任一视角后创建或恢复该视角独立的Module 03大纲run；返回Parent仍可选择其他视角。

## Module 03：Review Outline Design and Iteration

- 只使用所选视角和Module 02已持久化证据，不新增文献检索。
- 输出类似`1`、`2.1`、`2.1.1`的层级大纲。
- 每节必须给出目的、写作逻辑、关键问题、安排原因、具体证据内容、读者收获和章节衔接；内部ID不得直接显示给用户。
- 每次修改保存不可变新版本，不覆盖历史。
- 每轮完整展示后询问“满意，冻结大纲 / 继续修改”。
- 用户明确满意后冻结最新版并自动启动Module 04；不得生成正文、参考文献稿、图表、Word或LaTeX。

## Module 04：Direct Review Manuscript Writing

- 只接受`outline_approved`的Module 03 run。
- 由当前根Agent在一个连续上下文中直接生成完整中文综述，不再按章节拆分写作，也不再进入Module 05自我评审。
- 目标约15,000字，接受范围13,500–16,500字。
- 必须保留冻结大纲的全部标题层级，并使用Module 02范围内的相关证据提高完整性。
- 至少标注一处图和一处表的位置、标题及具体建议内容。
- 通过`import-manuscript`一次提交完整稿件，Python检查字数、冻结标题、证据范围、图表位置及内部ID。
- `export-module04`输出`outputs/final/<module04_run_id>-review.md`并记录SHA-256。
- 返回`MVP任务完成`并停止；当前不存在Module 05。

## 当前有效扩展

- Skills：`.dsh/skills/research-topic-evaluation/`、`.dsh/skills/review-landscape-analysis/`、`.dsh/skills/review-outline-design/`、`.dsh/skills/review-outline-export/`
- Workflows：`workflows/module02-review-landscape/`
- Session fork插件：`plugin/perspective-branches/`（真实调用DeepSeek Harness `sessionController.fork()`；安装后可用）
- Python核心：`src/review_harness/`
- 数据契约：`schemas/`

## 明确不存在

- Module 05及之后的扩展Skill或Workflow；
- Module 01或Module 02自动正文生成授权；
- Module 01 PDF处理；
- 在聊天中收集学校账号、密码、MFA或Cookie；
- 使用历史输出作为当前规范。
