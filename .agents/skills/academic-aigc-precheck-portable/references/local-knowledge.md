# 本地知识库构建 · local-knowledge-0.1.0

此功能整理真实检测观测，不训练独立模型，不校准百分比。用户提供有权处理的论文和对应正式报告，资料、图像和生成配置均留在用户指定的私有目录。不要将本地知识目录放入 Skill 或公开 Git 仓库。

## 输入与命令

使用已经安装 PyMuPDF 的 Python。以下 `<cli>` 是已安装 Skill 的 `scripts/precheck.py`，`<workspace>` 是新建的本地知识目录。输出已有时不会覆盖。文件夹输入由宿主仅查看直属文件名、确认配对后转换为明确的文件参数；脚本不自动递归搜索。

```powershell
<python> <cli> knowledge init --output <workspace>
<python> <cli> knowledge import --workspace <workspace> --paper <paper.pdf> --report <report.pdf> --family <confirmed-family> --render
# paper 也支持 DOCX；仅 PDF 可以另加 --tex <main.tex>。
<python> <cli> knowledge review --workspace <workspace> --decisions <review.json>
<python> <cli> knowledge build --workspace <workspace>
<python> <cli> knowledge verify --workspace <workspace>
```

init 复制公开的原七条规则，生成空案例文件和本机 knowledge.json。此时 ready_for_prepare=false，不能把空库当作已经可预测。import 不需要已有知识库，它复用静态 PDF/DOCX/TeX 解析，核对标题和双向正文词元匹配（固定 .98 口径），保存报告坐标和候选标签。该版本筛查不认证全部公式或排版等价，复核时仍需确认同版本。标题无法核对或正文匹配不足时停止，不读取其他文件替代。

## 复核与证据

每次导入返回 import_id，以及 imports/<id>/ 下的 import.json、geometry.json、REVIEW.md、review.template.json。加 --render 可生成报告正文页 PNG，红框表示候选文字范围，原蓝色标记仍保留。原论文与报告不复制进发布包；原路径及 SHA 留在本地导入记录中。

从 review.template.json 另存 review.json，再完成真实核查：

- reviewer 填实际执行者或宿主身份；same_version_confirmed 仅在实际核对后设为 true。
- review_method 为 pdf_visual_check 或 manual_pdf_coordinates，不能将程序推断描述成人工确认。
- 每个候选 action 保持 skip，或明确选择 reject / accept。未列出的候选仍为 pending。
- accept 必须填写 confirmed_label（highlighted / unmarked / partial / uncertain）、具体 note 和对应全部 evidence_pages。
- confirmed_label 与几何候选不同且不是 uncertain 时，还需要填写至少20字符的 geometry_override_reason，记录实际页面证据；不能静默把 partial 扩展为完整高亮。
- 没有唯一精确词元对应的候选不能接受。几何状态为不确定时，只有实际核查报告后才能确认标签；无法核查则 skip。
- 只有部分覆盖时保留 partial，不能自动扩展为完整高亮。unmarked 不表示人工写作，也不证明属于官方检测分母。

review 记录操作者声明和哈希，不具备独立证明操作者实际看过页面的能力。宿主必须诚实记录工具支持和实际操作。不要为了完成流程而自动填写全部 accept。

## 生成和使用

build 仅采纳明确接受的案例，保存版本化 generations/<hash>/cases.json，更新 knowledge.json 中的相对路径、哈希和家族身份。旧生成版本和复核记录保留。同家族同一报告的相同文字/标签去重，不同报告中的相反标签分别保存并统计冲突；不按案例数量生成检测概率。

verify 核查导入快照、几何/图像、复核、原始输入哈希和活跃配置是否一致。原稿或报告变化后应重新导入，不修改旧证据。新增复核后如果配置尚未 build，generation_current=false。锁文件防止并发写入；进程异常留下 .write.lock 时，先确认没有活动写入者并保留现场，再处理，程序不会自动删除不明锁。

生成后把 workspace/knowledge.json 传给现有 prepare --knowledge；预测协议、全文判断和 finish 不改变。新论文模式排除目标家族及自身来源，只有一个家族的库在分析同家族论文时可能没有可用外部案例，需要如实说明。

## 当前范围

高亮提取复用原固定 cyan 矢量 profile，并结合文字重叠与形状判断。其他颜色、扫描报告、部分模板及复杂断行未获得通用支持，不能将未识别颜色当作阴性；未发现任何兼容高亮时自动几何状态全部保留不确定。没有 OCR、TeX 编译、宏执行、网络请求或额外模型 API。单个文件上限64MiB、报告上限200页、版本筛查正文上限60000本地词元。

合成工程材料只能以 knowledge init --engineering-test 创建独立测试库；标记会传播到 prepare 和报告，模拟标签及百分比不代表真实检测观测。日常库不得用这些材料替代真实案例。当前工程验证不证明新库的预测效果，也不保证正式检测通过。未来 DSH 可复用相同 CLI/JSON 接口，模型侧调用需另行验收。
