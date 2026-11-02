# 学术 AIGC 预测

**Academic AIGC Predictor** 是一个面向学术论文修改流程的 AIGC 风险预检工程，利用宿主已有的大语言模型、本地论文解析和真实检测经验，预测论文在 Turnitin AI Writing（图灵）检测中可能出现的高亮区域及文档级比例。

开发这个项目的初始目标，是尽可能提供近似、接近 Turnitin 官方检测表现的预估，让作者在正式付费检测之前，先了解哪些连续叙述和重点段落值得检查，并结合原始研究、数据、引用和上下文有针对性地修改文章。作者可以在多轮修改中先使用预检，在稿件达到合适状态后再进行正式检测，从而减少“每修改一次就付费检测一次”的开支。

目前已经实现可安装的 Skill、PDF / TeX / DOCX 解析、历史版本差分、全文分析输入和 Markdown 报告生成。接近官方检测表现是持续验证的研发目标，当前预测仍有明显误差，不能保证正式检测只需一次或一定达到某个阈值。预测比例表示对检测行为的研究性估计，不表示论文真实由 AI 生成的比例。

## 当前版本：0.2.0 已支持本地知识库构建

**现在可以下载安装后，用自己的论文和对应 Turnitin 报告建立本地知识库，再用于后续论文预检。** 本版本提供初始化、配对导入、页面复核、案例生成和配置校验五个命令，并内置公开的七条通用经验规则。构建过程在本地进行，不需要把论文、报告或案例上传本仓库。

**模式 B：直接预检论文。** 提供需要分析的 PDF 或 DOCX，可选同版本 TeX，使用已经配置好的本地知识库，由 Codex 阅读全文，给出实验性检测比例、主观范围和重点疑似高亮段落。这个模式无需提供待检论文的旧报告，也无需从知识库中选择一份报告作为基准。

**模式 A：参考旧报告预测修订稿。** 如果同一篇论文已经做过正式检测，可以明确提供旧版 Turnitin 报告和修订稿，结合旧高亮及文字变化估计新稿，报告同时说明相对历史结果的预期变化。只有明确提供旧报告用于差分预测时，才使用这个模式；旧高亮不会自动成为新稿标签。

**第一次使用时，已有知识配置、案例和规则文件，就先核对本机路径并直接预检；尚未准备知识库，则先用自己的论文与对应报告建立本地案例。** 建库时每篇论文分别与自己的报告配对，无需选择全局基准。待预测版本的正式结果应在预测保存后再提供，用于核查误差。

这里的“建库”是整理可追溯的检测观测，没有训练独立模型权重，不会自动提高或校准百分比。后续仍计划补充经过授权与审查的公共真实案例。当前几何提取沿用固定 cyan 矢量 profile，扫描报告、其他颜色和部分模板可能无法可靠识别；版本匹配或标签不明确时应停止或保留不确定性。

规则原文见[七条经验规则](docs/turnitin-behavior-rules.md)；其中 E01 等私有证据编号暂未公开，规则仍为有限样本假设。[本地建库完整说明](.agents/skills/academic-aigc-precheck-portable/references/local-knowledge.md)解释复核字段、证据和限制。原0.1.0 ZIP 与版本标签继续保留，0.2.0 使用新的独立包。

## 后续真实案例与社区贡献

**随时欢迎大家贡献不涉及隐私、具有公开分享权限的真实检测案例、论文文本或文本库，共同帮助项目积累更丰富的数据，探索更有参考价值的预测能力。** 不同学科、不同写作风格的高亮与未高亮案例，以及预测失败的记录，都可以帮助我们检验现有判断、发现局限。可以通过 [Issue](https://github.com/LACANIA/academic-aigc-predictor/issues) 讨论资料和提交方式，或通过 Pull Request 提交有权公开的内容。

贡献时请注明来源、版本和允许使用的范围，并清除个人信息及未获授权的内容。仅有论文文本的资料可以作为文本参考；要作为真实检测标签案例，还需要对应版本的报告证据。新增资料经核查后再纳入参考库，数据增加是否改善预测，需要通过后续验证确认。

后续案例库将优先考虑已经公开且允许分享相关文本的论文，以及贡献者有权分享的真实检测记录。每条候选案例应登记论文来源与版本、报告时间、对应原文和上下文、真实高亮状态、可追溯证据及分享范围。原文、高亮证据和版本无法可靠对应时，应保留未知，不能根据语言风格编造标签。

社区可以通过 Issue 或 Pull Request 参与程序修复、资料规范和案例审查。请先说明可公开的材料范围，再提交获准分享的内容；未发表原稿、账号信息和完整私有报告不应直接放入公开讨论或附件。合成示例只用于工程测试，不作为真实检测经验。新增案例在审核和版本登记后再纳入候选知识包，保留正例、反例及失败记录。当前支持本地导入与复核，不会自动接受社区提交或训练模型。

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

当前发布包为 `RC1-DOCX-PORTABLE-0.2.0`，内置协议为 `practical-whole-document-0.1.0`。目前通过 Codex Skill 调用，Skill 名称保持为 `academic-aigc-precheck-portable`；仓库名称不限定宿主，其他宿主适配与验收单独开展。

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
│   ├── scripts/precheck.py         # doctor / knowledge / prepare / finish
│   └── runtime/tap/                # 解析、知识读取及报告模块
├── docs/                          # 公开七条规则
├── tests/                         # 合成本地建库测试
├── requirements-dev.txt           # 可选测试依赖
└── dist/
    └── academic-aigc-precheck-portable-0.2.0.zip
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
$bundle = Join-Path $repoDir 'dist\academic-aigc-precheck-portable-0.2.0.zip'
py -3 --version
```

如果 `py -3` 指向低于 3.11 的解释器，请换用已经安装的兼容 Python。后续虚拟环境也应使用该解释器创建。

### 2. 检查发布包并建立独立 Python 环境

0.2.0 发布 ZIP 包含26个文件，SHA-256 应为：

```text
c622e5951201e8ea667fdf84b4925ec01402d30057f40656a9e062e43d0cd679
```

```powershell
$expectedHash = 'c622e5951201e8ea667fdf84b4925ec01402d30057f40656a9e062e43d0cd679'
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

## 安装后的第一次使用

### 已经收到知识配置、案例和规则三个文件

如果你已经收到一套允许使用的知识文件，可以直接配置，无需重新提供论文和检测报告来建库。三个文件通常是 `knowledge.json`、案例 JSON 和规则 Markdown；实际文件名以配置中的登记为准。

1. 将这三个文件保存在自己的本地资料目录，放在 GitHub 仓库和 Skill 安装目录之外。
2. 让 Codex 读取你明确提供的 `knowledge.json`，检查 `root` 是否指向这台电脑上的知识目录，`cases_file` 和 `rules_file` 是否对应目录中的真实文件。后两项应使用知识目录以内的相对路径，文件也可以位于其子目录。
3. 案例和规则的 SHA-256 必须与配置一致。仅移动文件不会改变哈希；出现不一致时先确认文件来源和完整性，不要为了通过检查直接改写哈希。
4. 提供需要预检的论文路径，明确使用模式 B，并指定新的报告目录。程序准备输入后，由 Codex 阅读全文、分析并生成报告。

配置 JSON 记录的是路径和文件身份，单独一个配置文件不能代替案例与规则。它也不会自动告诉其他电脑你的文件存放位置，因此首次使用需要核对本机路径。已经配置成功后，可以把 Python 和知识配置路径保存为本机使用说明，后续调用时继续使用。

首次可以直接向 Codex 发送下面这段话，把尖括号内容换成自己的路径：

```text
$academic-aigc-precheck-portable
这是我第一次使用，已经安装好 Skill，并收到一套有权使用的知识文件。
Python 路径：<安装依赖的 python.exe 完整路径>
知识配置：<knowledge.json 完整路径>
知识文件目录：<案例和规则所在的本地目录>
待预检论文：<论文 PDF 或 DOCX 完整路径>
报告输出目录：<尚未使用的新目录>

请先核对本机知识路径、文件哈希及论文家族，然后使用模式 B 进行全文预检，生成 PRECHECK_REPORT.md。
本次没有提供旧报告作为差分基准，请不要让我选择模式 A 的报告，也不要搜索其他检测文件。
遇到配置错误时指出具体问题；正常情况下继续完成全文分析和报告。
```

如果有对应的 TeX，再附上同版本源码路径即可。收到知识文件后也应确认其中的论文摘录可以在当前宿主中使用，不要把别人的未发表材料上传公开仓库。

### 尚未准备知识文件

如果手里只有论文和真实报告，请按下一节先建立本地知识库；初始化会生成配置，经过配对、复核和构建后才能用于完整预检。当前版本没有预装可直接使用的公共真实案例库，只有一份待检测论文时，仍然缺少运行完整流程所需的案例资料。

### 后续什么时候使用模式 A

当你有同一篇论文的旧版检测报告，并且希望根据旧稿高亮和修订内容预测新稿时，再明确指定模式 A、旧报告路径和新稿路径。**待预测版本自身的正式报告应在预测保存以后再提供**，用于核对误差。知识库里的其他报告无需逐次指定为基准。

## 建立自己的本地知识库

安装后无需手工编写首次配置。使用已经安装依赖的 Python 初始化一个新私有目录，程序会复制公开规则并生成本机 knowledge.json。下面沿用前文的安装变量。

```powershell
$cli = Join-Path $installedSkill 'scripts\precheck.py'
$knowledgeRoot = Join-Path $env:USERPROFILE '.local\share\academic-aigc-predictor\knowledge'
& $pythonEnv $cli knowledge init --output $knowledgeRoot
& $pythonEnv $cli knowledge verify --workspace $knowledgeRoot
```

初始 ready_for_prepare=false 是正常状态。将论文与对应报告放在自己选择的本地资料文件夹，向 Codex 明确说明配对关系和家族标识；不要把最新待预测结果混入预检输入。脚本按明确路径处理一对文件，宿主只查看指定资料文件夹直属文件名，不递归搜索。

```powershell
& $pythonEnv $cli knowledge import --workspace $knowledgeRoot --paper '<paper.pdf>' --report '<report.pdf>' --family '<confirmed-family>' --render
# --paper 也可以是 DOCX；PDF 可另外提供 --tex '<main.tex>'。
```

命令返回 import_id、REVIEW.md 和 review.template.json 路径；--render 生成报告正文页面图像。先查看真实页面和原文对应，再将模板另存为 review.json，填写实际复核者、同版本确认、明确接受/拒绝/跳过、真实标签、具体依据和页码。改变自动几何候选标签时，还需说明 geometry_override_reason；未核查的项目保持 skip。脚本记录复核声明，无法独立证明操作者确实看过页面，宿主不得虚构人工确认。

```powershell
& $pythonEnv $cli knowledge review --workspace $knowledgeRoot --decisions '<review.json>'
& $pythonEnv $cli knowledge build --workspace $knowledgeRoot
& $pythonEnv $cli knowledge verify --workspace $knowledgeRoot
$knowledgeConfig = Join-Path $knowledgeRoot 'knowledge.json'
```

build 只将明确接受的案例写入版本化本地案例文件，自动生成路径、SHA-256 和家族身份登记。verify 显示 ready_for_prepare=true 后，将 knowledgeConfig 传给现有 prepare。新论文模式排除目标自身及同家族案例；只用一个家族建库，再分析同家族论文时，可能没有可用的其他家族参考。已知旧报告的修订稿应明确使用历史差分模式。

也可以在对话中请求：

```text
$academic-aigc-precheck-portable
为“<本地论文及报告文件夹>”建立本地知识库，输出到“<新私有知识目录>”。
使用“<Python完整路径>”，仅查看该文件夹直属文件，确认每一对论文与报告及其家族。
先生成候选和复核页面，实际核查后再加入知识库，无法确认的案例保留未知或跳过。
最后生成并校验 knowledge.json，不上传我的论文、报告或案例。
```

已有兼容的 portable-knowledge-1 配置仍可通过 --knowledge 使用。若需要手工配置，原[JSON模板](.agents/skills/academic-aigc-precheck-portable/config.example.json)继续提供；root、cases_file、rules_file 和哈希必须与本机真实文件对应。完整格式及复核说明见 [local-knowledge.md](.agents/skills/academic-aigc-precheck-portable/references/local-knowledge.md)。

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

既有版本已验证仓库外运行、用户级 Codex 发现、独立 Python 模块加载、PDF / DOCX / PDF+TeX 输入、两种模式准备、显式私有知识读取，以及 `finish` 的输入绑定、引文和报告校验。原有测试为 **403 passed，1 xfailed**；本次新增本地建库测试 **27 passed**，并从实际0.2.0 ZIP在研发仓库外安装，完成15条命令的合成建库和预检工程验收。所有模拟材料都标记 ENGINEERING_TEST_ONLY，没有重新预测真实论文。测试说明对应工程检查通过，不代表预测准确性。

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

## 开发测试

公开仓库 tests/ 包含27项本地知识库合成测试，不依赖开发者私有论文。原研发403项测试包含本地研究资产，未随公开包分发。

```powershell
python -m pip install -r .agents/skills/academic-aigc-precheck-portable/requirements.txt -r requirements-dev.txt
python -m pytest -q tests
```

这些测试不调用真实检测服务或模型 API。合成报告和标签仅用于工程检查，不能作为真实检测经验。最新安装包见 [0.2.0 发布页](https://github.com/LACANIA/academic-aigc-predictor/releases/tag/v0.2.0)。
