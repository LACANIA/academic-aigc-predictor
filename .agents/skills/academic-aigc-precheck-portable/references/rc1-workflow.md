# RC1 practical workflow and mode permissions

RC1 organizes existing practical-whole-document-0.1.0 judgment; it adds no detector weights, outcome correction, or new behavioral rules. Prepare performs deterministic extraction, finish validates and renders, the host supplies the actual prediction.

## Inputs and identity

Choose A only with `--history` supplied by the user, otherwise B. Do not search for manuscripts or old reports. A checks exact normalized title identity and known family conflicts before associating the historical observation. This conservative gate can reject legitimate title-changing revisions; request identity clarification rather than bypass it. It establishes family association, not identical text versions, which A expects to differ. PDF+TeX material mismatch remains a separate blocking gate. PDF-only is supported with explicit limitations.

Known development titles are identity metadata, with no scores or prediction parameters. An unknown family requires an explicit confirmed family ID. When a new title might be a renamed same-family version, verify with the user; the software cannot establish semantic independence for arbitrary papers.

## A: historical differential prediction

Read the latest full text, historical_blocks/history_blocks, historical_alignment and historical_baseline in the packet. Only the explicitly authorized old report is a baseline. Historical scores and target-family cases from that old report are permitted, overriding the generic practical new-paper prohibitions. The target's latest score and labels remain forbidden. Old geometric states, including partial and ambiguous coverage, are weak evidence, never prefilled latest predictions. A suppressed old score remains null; no exact delta is computed.

Use the unchanged practical whole-document reasoning: compare retained old highlighters, altered old text, retained old unmarked text and new/unmatched content before proposing a number. Text similarity is not behavioral probability. Do not infer decline from revision, nor force proximity to the old score. Provide key continuing-highlight excerpts and `changing_regions` with paragraph_id, exact_quote, old_id, historical_comparison and uncertainty. Exact source quotations are required; comparison reasons are host judgments.

The output schema remains practical-whole-document-0.1.0. Set target_official_result_seen=false and target_family_cases_seen=true. The user report derives predicted delta arithmetically from the saved center and exact old observation; it is not an actual detector change or a scoring formula.

## B: new paper

No historical report access or automatic local discovery. Exclude own family and source hash through the existing case selector. Read complete text and allowed cards, then use the existing practical judgment. Set both exposure flags false. There is no reliable cross-paper accuracy claim.

## Output and provenance

Default report: title/files, A/B mode, uncalibrated center/range, A baseline/delta, key quoted passages with reasons and counterexamples, parsing/version issues, evidence-condition limitations. Detailed JSON, geometry and matching artifacts stay in the private output directory. Unassessed passages are not negative labels. Null estimates need concrete reasons; an empty excerpt list is allowed only for a justified numerical abstention.

An optional user threshold changes presentation only, not the host score method; a center or subjective range below it does not guarantee a pass. Do not edit a paper or remove true AI disclosure.

Freeze source hashes, method and actual host results for a validation run. RC1 functional checks may replay existing frozen outputs for rendering, but cannot be described as new predictions or accuracy evidence. Old protocol files, command entrypoints and frozen experiments stay available separately.
