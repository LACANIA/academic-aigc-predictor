# 学术 AIGC 预测

**Academic AIGC Predictor** 是一个面向学术论文修改流程的 AIGC 风险预检工程，利用宿主已有的大语言模型、本地论文解析和真实检测经验，预测论文在 Turnitin AI Writing（图灵）检测中可能出现的高亮区域及文档级比例。

开发这个项目的初始目标，是尽可能提供近似、接近 Turnitin 官方检测表现的预估，让作者在正式付费检测之前，先了解哪些连续叙述和重点段落值得检查，并结合原始研究、数据、引用和上下文有针对性地修改文章。作者可以在多轮修改中先使用预检，在稿件达到合适状态后再进行正式检测，从而减少“每修改一次就付费检测一次”的开支。

目前已经实现可安装的 Skill、PDF / TeX / DOCX 解析、历史版本差分、全文分析输入和 Markdown 报告生成。接近官方检测表现是持续验证的研发目标，当前预测仍有明显误差，不能保证正式检测只需一次或一定达到某个阈值。预测比例表示对检测行为的研究性估计，不表示论文真实由 AI 生成的比例。

## 当前发布状态：知识库尚未随包提供

**当前仓库提供程序、Skill、预测协议和配置模板，尚未提供可直接使用的知识配置及配套知识库，下载安装后还不能直接完成完整预检。** `config.example.json` 只是模板，不包含实际案例和规则。

目前使用者需要自行准备有授权的论文及对应的真实 Turnitin 检测报告，先核对版本，再将可追溯的高亮、未高亮案例和经验规则整理为现有接口要求的本地知识文件，并填写路径及 SHA-256 配置。已有兼容且有授权的知识库可以直接配置使用，无需重新收集材料。材料保留在本地，无需提交本仓库；未发表论文不建议公开。

当前没有自动导入任意论文或报告、自动学习或自动校准功能。仅把文件放入文件夹，不会生成有效知识库，也不会自动改变模型判断；本地使用和对照结果仍需核查，不能称为已完成统计校准。知识文件的字段与约束见下文“配置私有检测经验”和安装包内的 `INSTALL_WINDOWS.md`。

**后续计划补齐经过授权和内容审查的可分发基础知识包、案例整理与导入指引，以及默认配置加载流程，逐步实现下载即可预检。** 这些内容目前尚未交付，完成后将随新版本说明；补齐知识不等于预测准确性已经通过验证。原私有论文及完整检测报告不会作为默认公开资料。

## 使用流程

```text
论文 PDF / DOCX / PDF+TeX
          ↓
本地解析、来源记录与版本核对
          ↓
宿主 LLM 阅读全文，结合许可的历史检测经验分析
          ↓
实验性整体比例、主观范围、重点疑似高亮段落
          ↓
作者核对研究内容并修改论文，再进行预检
          ↓
在合适的稿件阶段进行正式 Turnitin 检测
```

预检报告用于辅助作者安排修改和检测时机。具体修改应当提高论证、表达、引用和数据说明的准确性，保留真实 AI 使用披露；本工程不自动改写原稿，也不把预测结果当作作者身份结论。

## 已实现功能

| 功能 | 当前实现 |
|---|---|
| PDF 输入 | 提取正文、章节及来源位置，记录双栏、公式和阅读顺序问题 |
| PDF+TeX 输入 | 先核对两个版本，再优先使用 TeX 组织连续正文；静态读取，不编译源码 |
| DOCX 输入 | 读取段落、表格、OMML 数学对象、图注和声明，使用段落编号追溯 |
| 模式 B：新论文预检 | 不提供旧报告，按已确认的论文家族过滤同家族案例 |
| 模式 A：历史差分预测 | 使用用户明确指定的旧版报告，结合新旧正文变化预测新稿 |
| 全文判断 | 由宿主 LLM 阅读完整上下文，提出研究性比例及主观范围 |
| 重点区域 | 输出原文摘录、章节、判断依据、反例和不确定因素 |
| 报告生成 | 校验输入绑定与引文，生成 `PRECHECK_REPORT.md` |

当前发布包为 `RC1-DOCX-PORTABLE-0.1.0`，内置协议为 `practical-whole-document-0.1.0`。目前通过 Codex Skill 调用，Skill 名称保持为 `academic-aigc-precheck-portable`；仓库名称不限定宿主，其他宿主适配与验收单独开展。

## 工程结构

```text
academic-aigc-predictor/
├── .agents/skills/academic-aigc-precheck-portable/
│   ├── SKILL.md                    # 宿主调用流程
│   ├── manage.py                   # 安装、校验、卸载
│   ├── INSTALL_WINDOWS.md          # 冻结版本的安装说明
│   ├── requirements.txt            # Python 依赖
│   ├── config.example.json         # 私有知识配置模板
│   ├── MANIFEST.json               # 文件校验清单
│   ├── references/                 # 全文协议与输入说明
│   ├── scripts/precheck.py         # doctor / prepare / finish
│   └── runtime/tap/                # 解析、知识读取及报告模块
└── dist/
    └── academic-aigc-precheck-RC1-DOCX-PORTABLE-build02.zip
```

Python 负责解析、版本核对、输入准备和报告校验；宿主 LLM 负责全文分析与预测。`prepare` 不产生检测百分比，`finish` 也不会自行调用一个检测模型。工程没有训练独立分类器，不调用额外付费模型 API 或 Turnitin 在线接口；宿主自身的订阅、额度或服务费用仍适用。

## Windows 安装

### 1. 准备环境与获取代码

需要 Python **3.11 及以上**、PyMuPDF **>=1.24,<2**。DOCX、TeX、JSON 和报告处理使用 Python 标准库，无需安装 Word 或 TeX 编译器。仓库现公开提供源码和安装包，下面使用 Git 克隆，无需 GitHub 登录。

```powershell
git clone https://github.com/LACANIA/academic-aigc-predictor.git
Set-Location academic-aigc-predictor

$repoDir = (Get-Location).Path
$skillSource = Join-Path $repoDir '.agents\skills\academic-aigc-precheck-portable'
$bundle = Join-Path $repoDir 'dist\academic-aigc-precheck-RC1-DOCX-PORTABLE-build02.zip'
py -3 --version
```

如果 `py -3` 指向低于 3.11 的解释器，请换用已经安装的兼容 Python。后续虚拟环境也应使用该解释器创建。

### 2. 检查发布包并建立独立 Python 环境

发布 ZIP 包含23个原始文件，SHA-256 应为：

```text
5e0cb505f676fe93e19bfb406919c7cdf98ebac6392f91fda0966fd31a2ba5d5
```

```powershell
$expectedHash = '5e0cb505f676fe93e19bfb406919c7cdf98ebac6392f91fda0966fd31a2ba5d5'
$actualHash = (Get-FileHash -LiteralPath $bundle -Algorithm SHA256).Hash.ToLowerInvariant()
if ($actualHash -ne $expectedHash) { throw '发布包 SHA-256 不一致，请停止安装。' }

$runtimeDir = Join-Path $env:LOCALAPPDATA 'AcademicAigcPredictor\venv'
if (Test-Path -LiteralPath $runtimeDir) { throw '虚拟环境目录已存在，请确认后复用或另选新目录。' }
py -3 -m venv $runtimeDir
if ($LASTEXITCODE -ne 0) { throw '虚拟环境创建失败。' }
$pythonEnv = Join-Path $runtimeDir 'Scripts\python.exe'
& $pythonEnv -m pip install -r (Join-Path $skillSource 'requirements.txt')
if ($LASTEXITCODE -ne 0) { throw '依赖安装失败。' }
```

已经完成本机安装的用户可以复用原兼容虚拟环境，无需为了仓库改名重装。上面的网络依赖安装步骤要求能够访问 Python 包源；已验证的离线依赖复用环境也可以继续使用。

### 3. 安装为用户级 Skill

```powershell
$installedSkill = Join-Path $env:USERPROFILE '.agents\skills\academic-aigc-precheck-portable'
if (Test-Path -LiteralPath $installedSkill) { throw '同名 Skill 已存在，请先校验和备份，勿直接覆盖。' }

& $pythonEnv (Join-Path $skillSource 'manage.py') check-bundle --bundle $bundle
if ($LASTEXITCODE -ne 0) { throw '发布包成员校验失败。' }
& $pythonEnv (Join-Path $skillSource 'manage.py') install --bundle $bundle --dest $installedSkill
if ($LASTEXITCODE -ne 0) { throw 'Skill 安装失败。' }
& $pythonEnv (Join-Path $installedSkill 'manage.py') verify --dest $installedSkill
& $pythonEnv (Join-Path $installedSkill 'scripts\precheck.py') doctor
```

用户级安装位置为 `~/.agents/skills/academic-aigc-precheck-portable`，可在其他项目中使用，目录规则见 [OpenAI 官方 Skill 文档](https://learn.chatgpt.com/docs/build-skills)。如果界面没有显示新 Skill，可刷新或重新启动会话。请避免同时保留多个内容不同的同名 Skill。已有目录内容完全相同时可以校验后复用；存在用户修改时应完整备份。

## 配置私有检测经验

**完整预检需要单独配置有授权的本地知识文件。** 仓库和安装 ZIP 不包含原35例真实案例、7条私有规则、论文原稿或正式 Turnitin 报告。仅克隆仓库并安装依赖，可以检查软件环境；缺少知识时，完整 `prepare` 会明确停止。

将模板复制到安装目录和 Git 仓库以外的私有位置：

```powershell
$configDir = Join-Path $env:USERPROFILE '.config\academic-aigc-predictor'
New-Item -ItemType Directory -Path $configDir -Force | Out-Null
$knowledgeConfig = Join-Path $configDir 'knowledge.json'
if (Test-Path -LiteralPath $knowledgeConfig) { throw '知识配置已存在，请核对后复用。' }
Copy-Item -LiteralPath (Join-Path $installedSkill 'config.example.json') -Destination $knowledgeConfig
```

按真实文件位置编辑配置，结构如下；示例中的路径和哈希需要替换，不能直接作为有效知识使用：

```json
{
  "schema_version": "portable-knowledge-1",
  "root": "<已授权本地知识根目录>",
  "cases_file": "knowledge/cases.json",
  "rules_file": "knowledge/rules.md",
  "cases_sha256": "<案例文件实际SHA-256>",
  "rules_sha256": "<规则文件实际SHA-256>",
  "known_titles": {},
  "known_sources": {},
  "engineering_test_only": false
}
```

`cases_file`、`rules_file` 必须是 `root` 内部的相对路径。使用 `Get-FileHash -Algorithm SHA256` 计算真实哈希，并填入小写十六进制值。已有正式配置可直接复用。知识接口会检查文件身份、案例结构及七条规则卡片；缺失、路径越界或哈希不符时会拒绝读取，不能使用合成测试案例代替真实经验。不要将私有配置、知识文件、输入包或输出报告提交到本仓库。

## 在对话中使用

安装和私有配置完成后，向 Codex 提供准确文件路径、Python 路径、knowledge 配置和新的输出目录即可。可以把这些本机参数另存为私有使用说明，每次调用时要求先读取该说明，避免重复输入。

### 模式 B：新论文

```text
$academic-aigc-precheck-portable
分析这份论文：<Manuscript.docx 或 paper.pdf 的完整路径>。
使用 Python：<专用虚拟环境中的 python.exe>。
使用知识配置：<knowledge.json 的完整路径>。
先确认论文家族，再按新论文模式阅读全文，输出研究性比例、主观范围、重点疑似高亮段落和判断依据，将报告保存到新的私有目录。
```

PDF+TeX 输入时，再提供同稿 `.tex` 的完整路径，要求先核对版本。只有 PDF 时可以正常使用，解析限制会记录在报告中。

### 模式 A：参考旧报告预测修订稿

```text
$academic-aigc-precheck-portable
参考旧版 Turnitin 报告：<old-report.pdf 的完整路径>，分析修订稿：<新稿 PDF 或 DOCX 的完整路径>。
如有同稿 TeX：<main.tex 的完整路径>。
使用指定的 Python 和私有 knowledge 配置，核对家族和版本后，分析保留、改写与新增内容，给出最新研究性比例、相对历史值的变化、可能继续高亮或改变状态的段落，并生成 PRECHECK_REPORT.md。
```

模式 A 只读取用户明确指定的旧报告，不搜索其他检测文件。旧高亮状态不会自动成为新稿标签。希望评价预测误差时，应先保存预测，再提供最新正式报告。

## 命令行工作流

下面的变量沿用安装步骤；实际运行时，填写当前论文路径、经核查的家族标识，以及尚未使用的新目录。每次修改后的论文应生成独立输入和报告。

```powershell
$cli = Join-Path $installedSkill 'scripts\precheck.py'

# DOCX，新论文模式
& $pythonEnv $cli prepare --docx '<Manuscript.docx>' --family '<confirmed-family>' --knowledge $knowledgeConfig --output '<new-input-dir>'

# PDF，新论文模式
& $pythonEnv $cli prepare --pdf '<paper.pdf>' --family '<confirmed-family>' --knowledge $knowledgeConfig --output '<new-input-dir>'

# PDF+TeX，先核对版本
& $pythonEnv $cli prepare --pdf '<paper.pdf>' --tex '<main.tex>' --family '<confirmed-family>' --knowledge $knowledgeConfig --output '<new-input-dir>'

# DOCX 或 PDF + 明确提供的旧报告，历史差分模式
& $pythonEnv $cli prepare --docx '<Manuscript.docx>' --history '<old-report.pdf>' --family '<confirmed-family>' --knowledge $knowledgeConfig --output '<new-input-dir>'
& $pythonEnv $cli prepare --pdf '<paper.pdf>' --history '<old-report.pdf>' --family '<confirmed-family>' --knowledge $knowledgeConfig --output '<new-input-dir>'
```

`prepare` 成功后会生成 `model_input.json`、`whole_document.md` 和来源/版本记录。宿主按照 Skill 中的全文协议读取完整输入和允许的案例，保存真实分析 JSON，然后执行：

```powershell
& $pythonEnv $cli finish --packet '<new-input-dir>\model_input.json' --prediction '<host-output.json>' --output '<new-report-dir>'
```

输出的 `PRECHECK_REPORT.md` 包含整体研究性预测、主观范围、重点摘录、依据和限制。仅运行命令行 `prepare/finish` 不会自动产生模型判断；手工填写模拟百分比只能用于格式测试，必须明确标记 `ENGINEERING_TEST_ONLY`。

## 当前工程验证与准确性边界

当前冻结版本已经验证仓库外运行、用户级 Codex 发现、独立 Python 模块加载、PDF / DOCX / PDF+TeX 输入、两种模式准备、显式私有知识读取，以及 `finish` 的输入绑定、引文和报告校验。发布与本机安装阶段完整测试结果为 **403 passed，1 xfailed**；这些结果说明对应工程检查通过。

文档级预测已有少量真实报告对照，仍存在明显低估、局部误报和遗漏；同一家族不同版本的经验也不能直接推广到新论文。主观范围没有统计置信度保证，接近某一次官方比例也不能证明局部解释正确。全新环境下宿主自主完成整条工作流，以及跨论文预测准确性，仍需继续验证。

PDF 的双栏与公式可能影响阅读顺序，TeX 与 PDF 可能存在版本差异，DOCX 的线性化数学表达可能丢失语义且没有可靠 PDF 页码。出现这些情况时，报告应说明影响，不能补写原文。作者应结合报告的具体证据和实际误差，决定正式付费检测的时机。

## 隐私与数据

解析脚本在本地处理用户明确提供的文件，不自动上传到额外检测服务，也不搜索其他论文或报告。宿主 LLM 会接收获准进入对话上下文的正文，仍适用宿主服务的数据政策。请将论文、检测报告、私有案例、knowledge 配置和预检输出保存在仓库之外。

本项目为非官方工具，与 Turnitin 没有官方隶属关系。仓库为 Public，尚未指定开源许可证；代码访问权限不等同于论文、正式报告或私有知识的再分发授权。

## 常见问题与卸载

| 提示或情况 | 处理方式 |
|---|---|
| `KNOWLEDGE_REQUIRED / MISSING / HASH` | 核对显式配置、授权路径和实际哈希，禁止用测试知识替代 |
| `HISTORY_IDENTITY_MISMATCH` | 核对旧报告与新稿的家族、标题和版本，避免错误关联 |
| `MATERIAL_MISMATCH` | 核对 PDF 与 TeX 是否来自同一稿件版本 |
| `OUTPUT_EXISTS` | 使用新输出目录，保留原输入和报告 |
| `ImportError` | 使用已安装 requirements 的同一 Python 环境 |
| Skill 未显示 | 核对用户级安装路径，并刷新或重新启动会话 |
| `ENGINEERING_TEST_ONLY` | 当前材料为格式验证，模拟数字没有真实检测意义 |

卸载前先验证，修改过的安装会拒绝自动删除，应先备份并核对：

```powershell
& $pythonEnv (Join-Path $installedSkill 'manage.py') verify --dest $installedSkill
& $pythonEnv (Join-Path $installedSkill 'manage.py') uninstall --dest $installedSkill
```

卸载只移除经过校验的 Skill 文件，不删除私有知识、原论文或报告。专用 Python 环境和私有配置如需清理，应在确认目录身份后单独处理。
