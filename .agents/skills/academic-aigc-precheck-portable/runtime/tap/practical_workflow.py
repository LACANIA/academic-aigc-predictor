"""RC1 routing/report adapter. Existing host prediction method stays unchanged."""
from pathlib import Path
import json
import pymupdf
from . import practical
from .audit import overview_observation
from .behavior import history_context,align_history
from .contrastive import case_card
from .precheck import preprocess_pdf,canonical_hash
from .knowledge import load

RELEASE='academic-aigc-precheck-RC1'
# Identity metadata only, with no observed percentages or prediction parameters.
TITLES={}

def prepare(root,pdf,tex=None,family=None,history=None,threshold=None):
    for path in [pdf]+([tex] if tex else [])+([history] if history else []):
        if not Path(path).is_file():raise FileNotFoundError('Missing explicitly supplied file: '+str(path))
    if threshold is not None and (isinstance(threshold,bool) or not 0<=threshold<=100):raise ValueError('Threshold must be between0 and100')
    target=preprocess_pdf(Path(pdf),'identity')
    if target['source_kind']!='standalone_pdf':raise ValueError('Target must be a manuscript, not a detector report')
    known=next((f for t,f in load(root)['known_titles'].items() if practical.tokens(t)==practical.tokens(target['title'] or '')),None)
    if known and family and known!=family:raise ValueError('Target family conflicts with known title identity')
    family=known or family
    if not family:raise ValueError('Confirm the target family and supply --family before using reference cases')
    private,packet=practical.prepare(root,Path(pdf),Path(tex) if tex else None,family)
    if packet is None:return private,None
    packet.update(release=RELEASE,mode='new_paper',target_family=family,
        input_files={'pdf':Path(pdf).name,'tex':Path(tex).name if tex else None},decision_threshold=threshold,
        known_development_source=bool(known) or packet.get('known_development_source',False))
    if history is not None:
        old,labels=history_context(Path(history),'history',include_uncertainty=True)
        if old['source_hash']==target['source_hash']:raise ValueError('History is the target itself')
        # Conservative identity gate: title changes require separate human identity review.
        if practical.tokens(old['title'] or '')!=practical.tokens(packet['title'] or ''):raise ValueError('HISTORY_IDENTITY_MISMATCH: title/family association not established')
        with pymupdf.open(history) as pdfdoc:
            observations=[o for i in range(min(2,len(pdfdoc))) if (o:=overview_observation(pdfdoc[i].get_text(),i+1))]
        if len(observations)!=1:raise ValueError('Historical official observation missing or ambiguous')
        cases=load(root)['cases']
        selected=[c for c in cases if c['evidence']['report_sha256']==old['source_hash']]
        if any(c['family_id']!=family for c in selected):raise ValueError('HISTORY_IDENTITY_MISMATCH: known report family differs')
        if private['tex']:
            candidates=[{'paragraph_id':b['paragraph_id'],'normalized_text':b['text']} for b in private['tex']['blocks'] if b['kind'] in practical.BODY and b['prose_text']]
        else:
            candidates=[{'paragraph_id':p['paragraph_id'],'normalized_text':p['normalized_text']} for p in private['pdf']['paragraphs'] if p['analysis_candidate']]
        packet.update(mode='history_diff',history_reference_authorized=True,
            historical_baseline=dict(observations[0],report_sha256=old['source_hash']),
            historical_cases=[case_card(c) for c in selected],
            history_blocks=[{'old_id':p['paragraph_id'],'page':p['pdf_page'],'section':p['section'],'text':p['normalized_text'],
                'old_geometry_weak_label':labels.get(p['paragraph_id'])} for p in old['paragraphs']],
            historical_alignment=align_history(candidates,old,labels),
            family_reference_policy='Only user-designated old-report evidence; never inherited latest labels.')
        private['history']={'source_path':str(Path(history).resolve()),'old':old,'labels':labels,'observations':observations}
        packet['input_files']['history']=Path(history).name
        packet['input_limitations']+=['Historical title equality supports family association only, not identical versions. Old geometry and lexical best matches are weak evidence, never latest labels.']
    packet.pop('packet_hash');packet['packet_hash']=canonical_hash(packet);private['packet']=packet
    return private,packet

def report(packet,result):
    practical.validate(packet,result)
    history=packet.get('mode')=='history_diff';n=result['research_guess_percent'];iv=result.get('subjective_interval')
    rows=[f"# 学术论文 AIGC 实验性预检\n\n{packet['title']}",
        f"模式：{'A · 历史差分预测' if history else 'B · 全新论文预检'}；输入：{packet['input_mode']}；版本核查：{packet['version_status']}。",
        '输入文件：'+('；'.join(f'{k}: {v}' for k,v in packet.get('input_files',{}).items() if v) or '见原冻结输入清单'),
        f"**研究性预测：{str(n)+'%' if n is not None else '未给出数值'}；主观范围：{str(iv[0])+'%–'+str(iv[1])+'%' if iv else '未给出'}。** 未经统计校准，预测检测器标记比例，不衡量真实AI生成比例，不保证正式检测通过。"]
    if history:
        baseline=packet['historical_baseline'];old=baseline['observed_score']
        delta=f'{n-old:+g}个百分点' if n is not None and old is not None else '无法精确计算'
        rows += [f"历史官方显示：{baseline.get('display_value',str(old)+'%' if old is not None else '隐藏低分')}；相对历史的预测变化：{delta}。旧分数是观测，新分数是研究猜测。",
            '模式A依赖明确旧报告，只有有限同家族开发对照，不能当作跨论文准确率。']
    else:rows+=['模式B排除目标自身及同家族案例，跨论文可靠性尚未充分验证。']
    if packet.get('known_development_source'):rows+=['本输入属于已知开发家族，当前输出不能作为独立盲测证据。']
    threshold=packet.get('decision_threshold')
    if threshold is not None:
        relation='中心低于该阈值' if n is not None and n<threshold else '中心达到或高于该阈值' if n is not None else '未给出中心，无法比较'
        rows += [f'用户目标阈值：{threshold}%；{relation}。主观范围没有覆盖保证，此比较不能作通过承诺。']
    rows += [result['overall_rationale']]
    if n is None:rows += ['拒绝数值原因：'+result['abstain_reason']]
    rows+=['## 重点疑似高亮文字']
    blocks={b['paragraph_id']:b for b in packet['blocks']}
    for r in result['likely_highlights']:
        b=blocks[r['paragraph_id']]
        rows += [f"### {b['section']}\n\n> {r['exact_quote']}",r['rationale']+'\n\n反例或局限：'+r['uncertainty'],
            f"来源：{b['source_file']}；PDF页{b['pdf_pages']}"+(f"；源码行{b['source_line_start']}–{b['source_line_end']}" if 'source_line_start' in b else '')+'。']
    if history and result.get('changing_regions'):
        rows+=['## 可能改变标记的区域']
        for r in result['changing_regions']:
            uid=r.get('paragraph_id');quote=r.get('exact_quote','')
            if uid not in blocks or not quote or quote not in blocks[uid]['text']:raise ValueError('Changing region must quote exact latest text')
            rows += [f"- {uid}：{r.get('historical_comparison','')} {r.get('uncertainty','')}"]
    rows+=['## 解析及可靠性限制','\n'.join('- '+s for s in packet['input_limitations']+result['uncertainty_factors']),
        '## 学术表达核查','\n'.join('- '+s for s in result['writing_checks']),
        '详细JSON、坐标、对齐和日志单独保存。摘录没有穷举全文，未摘录文字不自动视为阴性；未改写原稿或删除真实AI使用披露。']
    return '\n\n'.join(rows)+'\n'
