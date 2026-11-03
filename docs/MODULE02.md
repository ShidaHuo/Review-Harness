# Module 02：综述格局与最新研究分析

## 跨运行时状态驱动

DeepSeek Harness、Kiro Crew和Codex在创建Module 02后都必须重复调用`module02-next`。该命令返回唯一下一动作及`blocking_user_input`。当值为`false`时，Agent必须执行动作并再次调用，不得把中间进度作为最终输出。没有合法PDF时降级到摘要/元数据证据并继续。只有真实SSO、已保存检查点的提供方失败，或`render_outputs_and_select_perspective`可以暂停。

Python在`perspectives_ready`之前拒绝渲染最终报告，在研究分类正式完成之前拒绝保存视角。Module 01研究查询和Module 02研究补检只接受冻结`query_id`；Module 02综述查询由Python从冻结的直接主题查询确定性派生。

## 入口

Module 01 用户选择“结束”时保存 `rejected` 并终止。用户选择“继续”时保存 `approved`，加载 `review-landscape-analysis` Skill，然后创建 Module 02 run。数据库门禁不接受缺失决定、自定义文本或拒绝决定。

## 阶段 A：相关综述

优先检索并纳入同时锚定全部核心关键词的完整主题综述。若没有，必须先明确报告“未发现同时锚定全部核心关键词的完整主题综述”，再根据冻结TopicProfile中的重要技术对象、机制、材料、器件、方法和应用关键词，对候选进行0–1相关度评分，并纳入全部最高相关的合格邻近综述，最多5篇。邻近综述必须逐篇显示匹配关键词，不能表述成完整主题综述；同时必须继续完成全文状态、原因、结构、未来趋势、TrendClaim、时间锚点、后续研究比较和视角分析。OpenAlex负责题名与摘要范围的元数据发现和引用次数快照，并通过游标分页尽可能取全；单条查询最多10页、每页100条，超出时必须标记为截断。Nature Index身份只读取Module 01附加的Skill本地目录快照，不访问Nature网页。

每篇综述保存：题名、发表日期、期刊、Nature Index状态、引用次数及观察日期、稳定链接、全文访问状态、PDF路径与哈希、写作原因、结构、未来趋势、证据等级和证据URL。

全文获取顺序为合法开放版本优先。没有开放PDF时必须保存`login_required`并显示编号选择：`1. 我将在学校官方页面登录并下载PDF`、`2. 学校没有订阅，跳过全文`、`3. 不使用学校权限，按摘要继续`。有受信任认证浏览器时，用户直接在学校页面登录；Codex等没有认证浏览器的运行时，由用户在普通浏览器登录并把合法PDF放入系统建议的`runtime/institutional-pdfs/`路径。Agent不得接触学工号、密码、MFA或Cookie。学校认证成功但没有订阅时保存`institution_not_subscribed`；用户不使用学校权限时保存`skipped`。`login_required`未解决前，Python拒绝综述分析和锚点确定。

HTTP下载、本地PDF校验和本地解析不消耗模型Token；等待用户完成SSO也不消耗模型Token。只有Agent参与决策，或解析后的文本/图像进入模型请求时才消耗Token。应优先发送摘要、目录、引言、结论和展望片段，而不是整篇PDF。

## 阶段 B：锚点后研究

选择最新纳入综述，其发表日期记为 D。研究窗口为 D 前6个日历月至当前系统日期。先导入 Module 01 窗口内论文，再用相同的完整主题和上位技术查询补检。

每篇研究论文分类为：

- `trend_consistent`：直接实现或验证综述明确提出的趋势；
- `trend_extension`：在材料、方法、器件、应用、规模或评价上实质扩展该趋势；
- `new_direction`：相关但未被综述趋势覆盖；
- `excluded`：语义复核后不相关。

## 阶段 C：候选综述视角

生成3–5个候选视角。每个视角必须有研究证据，并说明与已有综述的相同点、实质差异、建议边界和重叠风险。优先使用趋势延伸和综述外新方向作为差异化依据。

## Runtime-neutral orchestration

- `runtime_adapter.py`: detects DeepSeek Harness, Kiro Crew, Codex, or an unknown host and selects only the interaction/orchestration layer.
- Skill: defines execution rules, evidence boundaries, and report format for every runtime.
- DeepSeek Harness：原生Workflow、有界Subagent、编号纯文本选择和真实Session fork插件。
- Kiro Crew：Python核心及必要的`workflow_run`/`spawn_run`，使用编号纯文本选择。
- Codex：Python核心、有界本地/根Agent批次和编号纯文本选择。
- Python CLI: approval gate, OpenAlex retrieval, deduplication, dates, anchors, persistence, and report rendering in every runtime.

If a runtime has no genuine persistent visible-session API, keep reconstructable SQLite logical perspective branches and state that no real chat fork exists.

## 输出

最终报告包括：逐篇综述档案、锚点后论文的三类分析，以及按推荐程度排序的候选综述视角。Module 02 完成后停止，不自动开始正文写作。

## 优化后的复用与分支

- TopicProfile、Module 01研究论文、语义标签和Nature Index快照均按Module 01 run复用。
- `plan-module02-research`逐条输出`reuse_module01`、`already_supplemented`或`supplement`；只有`supplement`可以发起新API请求。
- 时间锚点采用最新相关综述，趋势基线采用最新且有注册PDF及未来趋势证据的综述，两者可以不同。
- 没有相关综述时不报错：使用Module 01两年窗口，跳过趋势相符/延伸，相关研究作为`new_direction`候选，并形成可能的首篇主题综述视角。
- 综述趋势先归一为TrendClaim，再与研究论文对照，避免论文与每篇综述逐对比较。
- 综述默认每批5篇、研究论文每批25篇交给Subagent。
- 对话默认显示`render-module02-summary`简报，`render-module02-report`保存完整逐篇工件。
- 简报之后必须显示编号纯文本视角选择。即使持久Session fork插件未安装，也可从逻辑分支重建相同编号列表；但不得声称已创建真实聊天fork。

Module 01严格停留在题名、元数据和摘要层，不下载、解析、OCR或向模型传入PDF。所有全文访问只在用户批准后的Module 02执行。

## 视角选择与聊天分支

Module 02无论是否找到相关综述，都必须生成3–5个视角。`save_perspectives`会为每个视角创建持久逻辑分支记录，并把Parent保持为`perspectives_ready`。

插件对每个视角真实调用DeepSeek Harness官方`sessionController.fork()`，并返回持久Session ID。重建时传入已有Session ID可避免重复fork；部分失败时先保存成功映射，只重试缺失视角。插件只建会话和命名，不发送提示、不启动写作。

Agent把插件返回的rank/session id映射通过`attach-perspective-sessions`写入SQLite，然后使用编号纯文本列出各视角。用户选择后调用`select-perspective`，对应逻辑分支变为`selected_for_module03`，并创建或恢复该视角的Module 03大纲run。DeepSeek Harness在对应真实子Session中继续；Kiro Crew或Codex没有真实分支时使用SQLite逻辑分支。用户返回Parent后仍可选择其他视角，已有大纲版本不会被覆盖。

Module 02本身不得生成大纲、正文、图表或投稿文件。Module 03只负责分级写作大纲及其迭代，不负责正文写作。
