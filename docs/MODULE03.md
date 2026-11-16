# Module 03：综述写作大纲设计与自动迭代

## 入口

Module 03只接受Module 02自动选择的最佳视角。`start-module03`验证Module 02为`perspectives_ready`且对应分支为`selected_for_module03`。每个视角仍对应一个独立大纲run，未选分支作为审计记录保留。

## 输入证据

- 所选视角的完整JSON和差异性、完整性、成熟性评分；
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

## 版本和Agent自检

`import-outline`保存不可变版本，状态进入`awaiting_outline_evaluation`。完整大纲必须在聊天中显示，然后由Agent检查：所选视角覆盖、与已有综述差异、层级完整性、章节平衡、证据支撑、逻辑递进、读者收获和过渡。

若存在具体缺陷，`save-outline-evaluation --decision revise --rationale "<缺陷和修改要求>"`将状态设为`revision_requested`。Agent读取上一版和自检理由，保存新版本并再次检查。

全部质量门通过后，`save-outline-evaluation --decision approved --rationale "<通过理由>"`冻结最新版并自动创建或恢复Module 04 manuscript run。Agent不询问用户，且必须立即继续Module 04。

## 跨运行时行为

DeepSeek Harness、Kiro Crew、Codex和未知运行时均使用相同的Agent自动自检与SQLite版本历史。人工批准不再是流程门；真实机构登录等凭据步骤仍由用户完成。

## 禁止内容

Module 03不得生成摘要、引言正文、章节正文、投稿参考文献表、图表、Word或LaTeX。
