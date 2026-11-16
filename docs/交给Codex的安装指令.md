# 给 Codex 的 Review Harness 安装指令

**给正在阅读此文件的 Codex：** 用户发送此文件即表示要求你在当前电脑上执行以下安装任务。请直接开始检查和安装，不需要用户另写提示词；不要只复述本文件。安装后汇报真实结果。需要用户操作密钥或遇到无法自行解决的阻碍时，明确告知用户。

目标：在这台电脑上安装并验证 Review Harness，使用户能够在 Codex 中使用 `$review-harness` 撰写科学综述。不要求用户提前在桌面新建文件夹。

## 执行要求

1. 检查当前操作系统、Git、Python（需要 3.12 或更新版本）和 Codex 环境。若缺少必要工具，说明具体缺少什么；不要假称安装成功。
2. 在用户当前工作目录下，或用户指定的持久位置，获取公开仓库的 `V1.0.0` 分支；自行创建需要的目录，不要依赖临时目录：

   ```text
   https://github.com/ShidaHuo/Review-Harness.git
   ```

   若该目录已有仓库，先检查其来源和未提交修改，不要覆盖用户数据。示例：

   ```bash
   git clone --branch V1.0.0 https://github.com/ShidaHuo/Review-Harness.git
   ```

3. 阅读仓库的 `AGENTS.md`、`README.md` 和适用于当前系统的安装脚本，然后运行安装流程。Windows 可运行仓库中的 `setup-codex.cmd` 或 `setup-codex.ps1`；macOS / Linux 可在仓库目录运行 `./install.sh codex`。
4. OpenAlex API key 必须由用户自己提供。**不要要求用户在聊天中发送 key，也不要读取、打印或复制 key 内容。** 若 Windows 安装器要求输入 key，请让用户在本机安装器的安全输入提示中操作；其他系统请指导用户自行将原始 key 写入仓库根目录的 `OPENALEX_API_KEY.txt`，或自行设置 `OPENALEX_API_KEY` 环境变量。申请方式见 <https://help.openalex.org/api/authentication/>。如果用户尚未配置 key，完成其他可做的步骤，然后说明需要用户完成的操作。
5. 检查安装器结果，并使用已安装 Skill 的 `scripts/locate_review_harness.py` 检查是否能定位项目；只报告 key 是否已配置。不要创建虚假的科学课题或启动真实综述来冒充安装验证。
6. 安装后提醒用户重启 Codex，以便发现新 Skill；然后在用户希望存放课题数据的工作文件夹中使用：

   ```text
   $review-harness 围绕［明确的科学研究主题］撰写一篇综述。
   ```

7. 向用户汇报：仓库路径、Skill 安装结果、Python 版本、OpenAlex key 是否配置、定位检查结果，以及是否需要重启 Codex 或完成其他步骤。如果任何环节失败，写明实际错误和未完成事项。

## 使用约束

- 保留下载的仓库文件夹，Skill 依赖其路径；移动后需重新运行安装。
- 综述默认从 Module 01 开始，依次经过证据分析、提纲设计和正文导出。Module 01 的否定判断会结束流程；Module 02 缺少合法全文时，请用户提供对应 PDF，然后从保存的状态继续。
- 默认工作数据和输出使用启动课题时的工作文件夹；保留其中的 `runtime/` 和 `outputs/` 以便恢复。不要把凭据、数据库或 PDF 上传到公开仓库。
- 安装脚本的部分文本可能仍称输出保存在安装目录；以启动器当前行为为准。持续运行可能受到外部服务故障或平台限制影响，不能保证每次都不中断。
