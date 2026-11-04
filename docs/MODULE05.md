# Module 05：稿件评价、具体修订与DOCX导出

## 输入

- Module 04完成的Markdown综述；
- Module 03冻结大纲和所选视角；
- Module 02中既有同主题/邻近综述分析和研究证据。

## 评价维度

只评价：

1. 综述视角是否清楚、一致并贯穿全文；
2. 与此前同主题或邻近综述相比是否存在实质差异；
3. 章节、论点、比较、过渡和结论的逻辑；
4. 在声明范围内的内容完整性。

不评价格式、图表、参考文献格式或引用准确度。

## 具体性要求

评价必须指出具体章节、具体问题、具体改法和验收标准。每项修改使用`R1`、`R2`等内部编号，并形成有优先级的修订清单。禁止只写“加强逻辑”“增加细节”等无法直接执行的意见。

## 修改

Agent按全部评价项直接修改完整稿件，并提交：

- 完整修订Markdown；
- 已处理的全部修订ID；
- 每项修改的位置和实际改动。

Python检查修订项是否全部覆盖、正文是否异常缩短/膨胀、章节层级是否保留，以及是否残留内部证据ID。

## 输出

最终确定性输出：

```text
outputs/final/<module05_run_id>-final-review.md
outputs/final/<module05_run_id>-final-review.docx
```

DOCX由Python标准库生成，不依赖Microsoft Word或`python-docx`。完成后状态为`mvp_complete`，当前不存在Module 06。
