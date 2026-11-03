# Module 04：冻结大纲Markdown导出

## 入口

用户在Module 03选择`1. 满意，冻结大纲`后，最新版大纲状态变为`outline_approved`，并自动启动Module 04。未批准的大纲不能进入本模块。

## 执行

Module 04不调用模型，也不检索文献。它确定性执行：

1. 读取最新版已批准大纲；
2. 将内部证据ID展开为题名和具体证据内容；
3. 删除“满意/继续修改”的反馈提示；
4. 添加冻结版本、批准时间和MVP完成状态；
5. 原子写入`outputs/final/<module03_run_id>-approved-outline-vNN.md`；
6. 在SQLite的`module04_exports`中保存绝对路径、版本和SHA-256；
7. 返回`MVP任务完成`并停止。

`run-module04`可用于中断恢复，同一批准版本重复执行是幂等的。

## 当前MVP终点

Module 04完成后不再运行其他模块。它不生成综述正文、参考文献稿、图表、Word或LaTeX。
