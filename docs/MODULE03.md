# Module 03：综述写作大纲设计与迭代

## 入口

Module 03只接受Module 02中已经选择的视角。`start-module03`验证Module 02为`perspectives_ready`且对应分支为`selected_for_module03`。每个视角对应一个独立大纲run；再次进入同一视角时恢复原run，选择其他视角时创建另一run。

## 输入证据

- 所选视角的完整JSON；
- Module 02纳入综述；
- TrendClaim；
- `trend_consistent`、`trend_extension`和`new_direction`研究论文；
- Module 02范围和风险说明。

Module 03不执行新的文献检索。

## 大纲内容

大纲使用`1`、`2.1`、`2.1.1`形式，包含3–10个连续一级章节，最大四级，并包含Introduction和Future Perspective/Outlook一级章节。

每一级章节都必须说明：

- 本节目的；
- 有顺序的写作逻辑；
- 关键问题；
- 这样安排的原因；
- Module 02证据内容：内部保留ID用于审计，但向用户显示论文/综述题名及其具体结果、论点或趋势，不显示裸编号；
- 预期读者收获；
- 与前后章节的衔接。

只有标题列表不是合格大纲。

## 版本和反馈

`import-outline`保存不可变版本，状态进入`awaiting_outline_feedback`。完整大纲必须在聊天中显示，然后提供：

1. 满意，冻结大纲
2. 继续修改

选择继续修改后，用户用自由文本说明具体变化，`save-outline-feedback --decision revise`保存原始反馈，状态进入`revision_requested`。Agent读取上一版和反馈，保存新版本。该循环没有固定次数。

选择满意后，`save-outline-feedback --decision approved`冻结最新版并自动执行Module 04，输出最终Markdown文件。

## 跨运行时交互

- DeepSeek Harness：编号纯文本选择，在所选真实Session fork中迭代；
- Kiro Crew：编号纯文本选择，有可见会话能力时使用独立会话，否则使用逻辑分支；
- Codex：编号纯文本选择，使用SQLite逻辑分支。

三种运行时共用相同SQLite版本历史和证据门禁。

## 禁止内容

Module 03不得生成摘要、引言正文、章节正文、投稿参考文献表、图表、Word或LaTeX。
