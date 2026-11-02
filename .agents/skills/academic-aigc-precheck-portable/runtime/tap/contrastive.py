"""Only unchanged case-selection/card functions needed by practical input."""
def forbidden_keys(value):
    if isinstance(value,dict):
        return [k for k in value if k in {'source_path','report_path','observed_score','official_score','detector_probability'}]+[k for v in value.values() for k in forbidden_keys(v)]
    if isinstance(value,list):return [k for v in value for k in forbidden_keys(v)]
    return []

def select_cases(cases,family,source_hash,mode):
    if mode not in {'new_paper','development_diagnostic'}:raise ValueError('Unknown mode')
    return [c for c in cases if mode=='development_diagnostic' or
            (c['family_id']!=family and source_hash not in {c.get('document_sha256'),c['evidence']['report_sha256']})]

def case_card(c):
    card={k:c[k] for k in ['case_id','family_id','text','label','section','text_type','context','observable_features','similarities_and_differences','unsupported_inferences']}
    if forbidden_keys(card):raise ValueError('Score/path leaked through case context')
    return card
