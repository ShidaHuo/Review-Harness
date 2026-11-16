# Review Harness：Codex 安装与使用说明

Review Harness 是一个辅助撰写科学文献综述的 Codex Skill。输入研究主题后，它按选题评估、证据分析、提纲设计和正文写作四个阶段推进，最终在工作文件夹中生成 Markdown 综述。

## 1. 准备环境

- 安装 Git、Python 3.12 或更高版本，以及 Codex。
- 准备自己的 OpenAlex API key，申请和管理方式见 [OpenAlex 文档](https://help.openalex.org/api/authentication/)。
- 保持网络连接，并选择一个用于保存项目文件的工作文件夹。

请勿将 API key、学校账号、密码或验证码发送到 Codex 聊天、GitHub 或截图中。

## 2. 下载并安装

在终端运行：

```bash
git clone --branch V1.0.0 https://github.com/ShidaHuo/Review-Harness.git
cd Review-Harness
```

### Windows

在下载的 `Review-Harness` 文件夹中双击 `setup-codex.cmd`，按照提示在本地终端输入自己的 OpenAlex key。安装脚本会将 key 保存在本地项目目录的 `OPENALEX_API_KEY.txt` 中。

安装完成后重启 Codex。请保留下载的 `Review-Harness` 文件夹：全局 Skill 通过安装时保存的路径加载其中的程序。移动或删除该文件夹后，需要在新位置重新安装。

### macOS / Linux

在仓库目录执行：

```bash
chmod +x install.sh
./install.sh codex
```

然后在仓库根目录创建 `OPENALEX_API_KEY.txt`，文件只包含一行原始 key，不要加引号或 `OPENALEX_API_KEY=` 前缀。也可以配置 `OPENALEX_API_KEY` 环境变量。完成后重启 Codex。

## 3. 开始一篇综述

在 Codex 中打开一个用于该课题的工作文件夹，在聊天框输入例如：

```text
$review-harness 围绕硅通孔（TSV）检测方法撰写一篇综述。
```

建议写清专业术语和范围；缩写有多种含义时，可直接写出全称。Codex 将读取 Skill，并从 Module 01 开始。

1. **Module 01：选题评估。** 检索近两年的研究论文，展示评估报告，由 Agent 决定是否继续。如果证据不足或方向不适合，工作流会结束并说明原因。
2. **Module 02：证据分析。** 分析相关综述与近期研究，形成多个候选视角并自动选择。如果无法取得所需综述的合法全文，Codex 会列出论文，请你提供对应 PDF；无需提供机构登录凭据。提供后在同一工作文件夹、同一任务中继续。
3. **Module 03：提纲设计。** 按所选视角生成、评估并冻结提纲。
4. **Module 04：正文写作。** 根据冻结提纲和已保存证据撰写综述，标记图表位置并导出 Markdown 文件。

正常情况下无需逐阶段输入“继续”。如果因网络、服务、平台限制或会话中断而暂停，可在同一工作文件夹重新打开该任务，要求 Codex“从已保存的 Review Harness 状态继续”。流程不会保证在所有外部故障下都能不间断完成。

## 4. 查看结果和保存位置

最终论文默认位于工作文件夹的 `outputs/final/`，文件名以 Module 04 运行编号开头。`runtime/` 保存工作流数据库和检索记录；中间报告通常保存在 `outputs/`。请保留这些文件，以便恢复任务和核查证据。

安装程序中部分提示可能仍显示结果保存在安装目录；当前 Codex 启动器使用**启动任务时的工作文件夹**保存默认运行数据和输出。不要把运行数据库、论文 PDF 或 API key 上传到公开仓库。

## 5. 使用前后检查

- Codex 找不到 `$review-harness`：确认安装成功、重启 Codex，并检查安装目录是否被移动；必要时重新运行安装程序。
- 提示缺少 OpenAlex key：检查项目根目录的 key 文件或环境变量是否配置；不要在聊天中粘贴 key。
- 被要求提供 PDF：按列表通过学校、图书馆或其他合法途径获取对应全文，再交给 Codex。
- 任务提前停止：先保留工作文件夹，要求从已保存状态继续；若报错，提供不含凭据的错误信息。
- 稿件生成后，应由研究者核对参考文献、引用与原文是否一致，并复核结论。自动生成结果不替代人工学术审查。

本版本包含可选的结束检查脚本，但常规安装步骤不保证自动启用或信任该钩子；请勿把它视为持续运行的保证。
