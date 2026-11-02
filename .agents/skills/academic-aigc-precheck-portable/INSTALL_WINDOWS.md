# Windows独立安装与使用

## 0.2.0：本地知识库构建

本版本增加 [本地建库流程](references/local-knowledge.md)，内置公开的七条规则，不分发原35例私有案例。安装后先运行 `scripts/precheck.py knowledge init --output <新私有目录>`，再通过 `knowledge import` 明确提供论文、对应报告和家族标识；`--render` 可生成复核页面。完成实际页面复核并提交 decisions 后，运行 `knowledge build` 和 `knowledge verify`，生成可供 prepare 使用的本机 knowledge.json。空库不能运行完整预检，没有自动训练或百分比校准。

0.2.0 安装包与原 build02 分开保存，manage.py 仅接受本版本包。已有同名安装时先校验与备份，不能直接覆盖；原安装器可在确认内容未修改后卸载，私有知识不删除，再使用新包安装。本次公开发布没有自动更新任何用户原安装。

## 运行条件

Python 3.11及以上、PyMuPDF>=1.24,<2。DOCX静态解析、TeX读取、JSON和报告生成使用Python标准库；不需要Word、TeX编译器、OCR、外部检测服务或额外模型API。宿主Codex负责阅读全文及给出实验性判断，Python没有独立AI分类器。建议使用虚拟环境。

```powershell
py -3 -m venv <venv-dir>
<venv-dir>/Scripts/python.exe -m pip install -r <unpacked-skill>/requirements.txt
<venv-dir>/Scripts/python.exe <unpacked-skill>/manage.py check-bundle --bundle <release.zip>
```

## 安装位置

项目级安装到目标工作目录的 .agents/skills/academic-aigc-precheck-portable；用户级可使用用户目录的 .agents/skills/academic-aigc-precheck-portable。请先核对发布包SHA-256；不要覆盖已有同名目录。当前官方参考：[Build skills](https://learn.chatgpt.com/docs/build-skills)。Codex发现规则与本机实际结果应分别核查，静态格式检查不代表宿主已发现。

```powershell
<python> <unpacked-skill>/manage.py install --bundle <release.zip> --dest <target-workspace>/.agents/skills/academic-aigc-precheck-portable
<python> <installed-skill>/manage.py verify --dest <installed-skill>
<python> <installed-skill>/scripts/precheck.py doctor
```

在目标目录启动Codex，明确调用 $academic-aigc-precheck-portable；若未出现，重新加载或重启后核查。不要覆盖原 academic-aigc-precheck 或 academic-aigc-precheck-docx。

## 私有知识配置

复制config.example.json到安装目录以外的私有位置。root指定合法本地知识根目录；cases_file和rules_file必须是该目录以内的相对路径。分别填写SHA-256；known_titles/known_sources可填写已经授权的家族身份登记。不要把规则、35例索引、报告或账号信息添加到发布包中。

案例格式沿用RC1案例索引：顶层cases列表，含case_id、family_id、text、label、section、text_type、context、observable_features、similarities_and_differences、unsupported_inferences及evidence.report_sha256。规则文件必须提供原有R01至R07卡片。配置缺失、身份哈希不符或内容不完整将停止完整prepare；不会静默替代成另一套评分。没有这些资料时，doctor仍可检查软件，但不能声称完成RC1等价预检。

## 输入与报告

```powershell
<python> <installed-skill>/scripts/precheck.py prepare --docx <paper.docx> --family <family-id> --knowledge <private-config.json> --output <new-dir>
<python> <installed-skill>/scripts/precheck.py prepare --pdf <paper.pdf> --family <family-id> --knowledge <private-config.json> --output <new-dir>
<python> <installed-skill>/scripts/precheck.py prepare --pdf <paper.pdf> --tex <main.tex> --family <family-id> --knowledge <private-config.json> --output <new-dir>
<python> <installed-skill>/scripts/precheck.py prepare --docx <paper.docx> --history <old-report.pdf> --family <family-id> --knowledge <private-config.json> --output <new-dir>
<python> <installed-skill>/scripts/precheck.py prepare --pdf <paper.pdf> --history <old-report.pdf> --family <family-id> --knowledge <private-config.json> --output <new-dir>
<python> <installed-skill>/scripts/precheck.py finish --packet <new-dir>/model_input.json --prediction <host-output.json> --output <report-dir>
```

没有history时为模式B，有明确history时为模式A。PDF和DOCX二选一；TeX只配PDF。宿主必须按协议实际分析后保存输出；finish仅校验并呈现。不要把人工构造的格式JSON当作真实预测。DOCX无可靠页码，数学提示不认证等价性；PDF/TeX不一致时阻止联合预测。

## 常见问题

KNOWLEDGE_REQUIRED/MISSING/HASH：提供合法显式配置，重新核对授权文件及哈希，不通过复制私有资料到安装包解决。ImportError：使用已安装requirements的同一Python。OUTPUT_EXISTS：指定新目录，不覆盖旧实验。HISTORY_IDENTITY_MISMATCH：核对家族和标题，不用其他报告替代。MATERIAL_MISMATCH：核对PDF与TeX版本。ENGINEERING_TEST_ONLY：仅供工程测试，不作实测或作者身份判断。缺失图片文字和复杂公式只能披露，不能补造。

## 卸载

```powershell
<python> <installed-skill>/manage.py verify --dest <installed-skill>
<python> <installed-skill>/manage.py uninstall --dest <installed-skill>
```

卸载仅移除有安装标记且哈希一致的该候选目录，私有知识和输入输出均不删除。若文件被改动或有额外文件，自动卸载拒绝，请先备份并核查。虚拟环境若由用户另行创建，可在确认目录身份后单独处理；卸载工具不会自动删除它。

本插件给出未经校准的Turnitin检测行为假设，不验证真实AI作者身份，也不能保证正式检测分数。公开包不带私有知识，工程测试中的模拟数字没有实际检测意义。DSH原生适配不属于此版本。
