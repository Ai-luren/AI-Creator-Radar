#!/usr/bin/env python3
"""Validate v49 CSV completeness, dates, duplicates, vendor range, encoding, and joins."""
import csv, json, re
from datetime import date
from pathlib import Path

ROOT=Path(__file__).resolve().parent
BASE=Path('/Users/ailuren/Downloads/company-chronicles-model-product-v48.csv')
NEW=ROOT/'new-records-v49.csv'
def read(path):
    with path.open(encoding='utf-8-sig',newline='') as f:
        return list(csv.DictReader(f))
def parse_date(v):
    if re.fullmatch(r'\d{4}',v): return date(int(v),1,1)
    if re.fullmatch(r'\d{4}-\d{2}',v): return date.fromisoformat(v+'-01')
    if re.fullmatch(r'\d{4}-\d{2}-\d{2}',v): return date.fromisoformat(v)
    raise ValueError(v)

files=['company-chronicles-v49.csv','audit-v49.csv','evidence-v49.csv','changes-v49.csv','missing-models-v49.csv','unresolved-v49.csv']
outputs={name:read(ROOT/name) for name in files}
main=read(BASE); new_records=read(NEW) if NEW.exists() else []
current=outputs['company-chronicles-v49.csv']; audit=outputs['audit-v49.csv']
allowed_statuses={'已确认：型号、日期与事件性质','部分确认：型号存在，日期或阶段不确定','存在冲突：需要复核','确认错误：已纠正','证据不足：暂不采信'}
vendors={r['厂商主题'] for r in main}; current_vendors={r['厂商主题'] for r in current}
bad_dates=[]
for i,r in enumerate(current,1):
    try: parse_date(r['事件日期（保留来源精度）'])
    except Exception: bad_dates.append((i,r['事件日期（保留来源精度）']))
keys=[(r['厂商主题'],r['事件日期（保留来源精度）'],r['事件标题'].strip().casefold()) for r in current]
ids=[r['记录ID'] for r in audit]
audit_by_id={r['记录ID']:r for r in audit}
mapping=[]
old_by_id={f"v48-{r['主题ID']}-{i:04d}":r for i,r in enumerate(main,1)}
new_ids={r['v49记录ID'] for r in new_records}
current_ids=[r.get('v49记录ID','') for r in current]
for r in current:
    rid=r.get('v49记录ID','')
    a=audit_by_id.get(rid)
    if not a or a['厂商']!=r['厂商主题'] or a['模型或产品名称']!=r['事件标题'] or a['当前日期']!=r['事件日期（保留来源精度）']:
        mapping.append(rid)
encoding_errors=[]
for name in files:
    try: (ROOT/name).read_text(encoding='utf-8-sig')
    except UnicodeDecodeError: encoding_errors.append(name)
change_keys={(r['记录ID'],r['字段'],r['修改前'],r['修改后']) for r in outputs['changes-v49.csv']}
unlogged_changes=[]
for rid,old in old_by_id.items():
    new=next((r for r in current if r.get('v49记录ID')==rid),None)
    if new is None: unlogged_changes.append((rid,'missing from v49')); continue
    for field in old:
        if old[field]!=new[field] and (rid,field,old[field],new[field]) not in change_keys:
            unlogged_changes.append((rid,field))
bad_statuses=sorted({r['核验状态'] for r in audit if r['核验状态'] not in allowed_statuses})
post_cutoff=[]
for i,r in enumerate(current,1):
    try:
        if parse_date(r['事件日期（保留来源精度）'])>date(2026,11,23): post_cutoff.append(i)
    except Exception: pass
checks={
 'expected_node_count_includes_additions':len(current)==len(main)+len(new_records),
 'expected_20_vendors':len(current_vendors)==20,
 'vendor_whitelist_preserved':current_vendors==vendors,
 'all_dates_legal':not bad_dates,
 'no_duplicate_vendor_date_title':len(keys)==len(set(keys)),
 'audit_one_to_one_and_consistent':len(audit)==len(current) and len(ids)==len(set(ids)) and not mapping,
 'stable_record_ids_unique_and_complete':len(current_ids)==len(set(current_ids)) and set(current_ids)==set(old_by_id)|new_ids,
 'audit_status_enum_valid':not bad_statuses,
 'all_substantive_changes_logged':not unlogged_changes,
 'records_within_2026_11_23_cutoff':not post_cutoff,
 'all_outputs_utf8_readable':not encoding_errors,
 'v48_source_still_present':BASE.exists(),
 'expected_output_files_present':all((ROOT/name).is_file() for name in files),
}
result={'checks':checks,'all_pass':all(checks.values()),'counts':{
 'nodes':len(current),'original_v48_nodes':len(main),'new_nodes':len(new_records),'vendors':len(current_vendors),'audit_rows':len(audit),
 'evidence_rows':len(outputs['evidence-v49.csv']),'change_rows':len(outputs['changes-v49.csv']),
 'missing_candidates':len(outputs['missing-models-v49.csv']),'unresolved_rows':len(outputs['unresolved-v49.csv']),
 'invalid_dates':len(bad_dates),'duplicate_keys':len(keys)-len(set(keys))},
 'details':{'invalid_dates':bad_dates[:10],'audit_mapping_errors':mapping[:10],'encoding_errors':encoding_errors,
 'invalid_status_values':bad_statuses,'unlogged_changes':unlogged_changes[:10],'post_cutoff_rows':post_cutoff}}
(ROOT/'validation-v49.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps(result,ensure_ascii=False,indent=2))
if not result['all_pass']: raise SystemExit(1)
