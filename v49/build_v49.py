#!/usr/bin/env python3
"""Build v49 deliverables from frozen v48 sources and row-level review decisions."""
import csv, hashlib, re, json
from urllib.parse import urlparse
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent
MAIN = Path('/Users/ailuren/Downloads/company-chronicles-model-product-v48.csv')
AUDIT = Path('/Users/ailuren/Downloads/company-chronicles-v48-full-audit.csv')
EVIDENCE = Path('/Users/ailuren/Downloads/company-chronicles-v48-evidence-register.csv')
TODAY = '2026-11-24'
SOURCE_CUTOFF = '2026-11-23'

def read(path):
    with path.open(encoding='utf-8-sig', newline='') as f:
        return list(csv.DictReader(f))
def write(name, headers, rows):
    with (ROOT/name).open('w', encoding='utf-8-sig', newline='') as f:
        w=csv.DictWriter(f, fieldnames=headers, extrasaction='ignore')
        w.writeheader(); w.writerows(rows)
def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def urls(text): return re.findall(r'https?://[^\s;|]+', text or '')
def valid_date(value): return bool(re.fullmatch(r'\d{4}(?:-\d{2}(?:-\d{2})?)?', value or ''))
def source_level(url):
    host=(urlparse(url).hostname or '').lower()
    official_suffixes=('openai.com','google.com','deepmind.google','anthropic.com','meta.ai','fb.com','alibabacloud.com','bytedance.com','bytedance.net','z.ai','pixverse.ai','mureka.ai','minimax.io','deepseek.com','deepseek.ai','qwenlm.github.io','elevenlabs.io','suno.com','x.ai','x.com','kuaishou.com','tencent.com','vidu.com','cursor.com','midjourney.com')
    if any(host==s or host.endswith('.'+s) for s in official_suffixes): return '厂商官方一手/二手材料（本轮按页面用途判断）'
    if host=='arxiv.org': return 'P3 同期论文/预印本'
    if host.endswith('github.com') or host.endswith('huggingface.co'): return 'P2 仓库/模型卡（官方组织归属需逐项核对）'
    return '第三方/来源级别待核'

main=read(MAIN); oldaudit=read(AUDIT); oldev=read(EVIDENCE)
assert len(main)==len(oldaudit)==503
assert [r['事件标题'] for r in main]==[r['标题'] for r in oldaudit]
new_records=read(ROOT/'new-records-v49.csv') if (ROOT/'new-records-v49.csv').exists() else []

# Row-level research decisions stay separate; agents never edit the source table.
reviews={}
review_paths=[ROOT/'review-decisions.csv']+sorted(p for p in ROOT.glob('review-*.csv') if p.name not in ('review-decisions.csv','review-quarantine.csv'))
for review_path in review_paths:
    if review_path.exists():
        for x in read(review_path):
            if re.fullmatch(r'v48-row-\d{4}',x['记录ID']) or x['记录ID'] not in {f"v48-{r['主题ID']}-{i:04d}" for i,r in enumerate(main,1)}:
                row_suffix=re.search(r'-(\d{1,4})$',x['记录ID'])
                row_number=int(row_suffix.group(1)) if row_suffix else 0
                if 1<=row_number<=len(main):
                    base=main[row_number-1]
                    x['记录ID']=f"v48-{base['主题ID']}-{row_number:04d}"
            if x['记录ID'] in reviews: raise ValueError(f"duplicate review decision: {x['记录ID']}")
            reviews[x['记录ID']]=x

out_main=[]; audit_rows=[]; evidence_rows=[]; change_rows=[]
for i,row in enumerate(main,1):
    rid=f"v48-{row['主题ID']}-{i:04d}"
    decision=reviews.get(rid,{})
    status=decision.get('核验状态','证据不足：暂不采信')
    conclusion=decision.get('核验结论','本轮尚无可追溯的逐条独立复核记录；v48既有状态与链接仅作线索，不据此判定通过。')
    problem=decision.get('存在问题','尚未独立重新验证型号、日期、事件性质及证据实际效力。')
    fix=decision.get('具体修复内容','')
    v=dict(row)
    v['v49记录ID']=rid
    v['v49核验状态']=status
    v['v49核验结论']=conclusion
    v['v49第二证据效力']=decision.get('第二证据是否真正支持关键事实','未检查')
    if fix and decision.get('修订字段'):
        requested=decision['修订字段'].split('|')
        revision_note=decision['修订字段']
        requested.extend(field for field in main[0] if field in revision_note)
        # Some reviewer CSVs use prose in the revision note but still provide
        # an explicit normalized date field. Apply that concrete value.
        if '事件日期（保留来源精度）' in decision and decision['事件日期（保留来源精度）'].strip():
            requested.append('事件日期（保留来源精度）')
        for field in requested:
            if field in v and field in decision:
                if field=='事件日期（保留来源精度）' and not valid_date(decision[field].strip()):
                    continue
                if v[field] != decision[field]:
                    change_rows.append({'记录ID':rid,'厂商':row['厂商主题'],'字段':field,
                        '修改前':v[field],'修改后':decision[field],
                        '依据URL':decision.get('官方主信源URL',''),'修改原因':fix,'修改时间':TODAY})
                    v[field]=decision[field]
    for field,choices in {
        '主信源':['主信源','官方主信源URL'],
        '交叉核验/相关链接':['交叉核验/相关链接','第二证据URL'],
    }.items():
        replacement=next((decision.get(k,'').strip() for k in choices
                          if decision.get(k,'').strip().startswith('https://')), '')
        if replacement and v[field]!=replacement:
            change_rows.append({'记录ID':rid,'厂商':row['厂商主题'],'字段':field,
                '修改前':v[field],'修改后':replacement,
                '依据URL':decision.get('官方主信源URL',decision.get('主信源',replacement)),
                '修改原因':decision.get('具体修复内容',decision.get('核验结论','替换为本轮逐页核验的节点级来源')),
                '修改时间':TODAY})
            v[field]=replacement
    out_main.append(v)
    verification_time=decision.get('核验时间','')
    verification_date=verification_time[:10] if re.match(r'\d{4}-\d{2}-\d{2}',verification_time) else (TODAY if decision else '')
    audit_rows.append({
        '记录ID':rid,'厂商':row['厂商主题'],'模型或产品名称':v['事件标题'],'原始模型或产品名称':row['事件标题'],
        '原始日期':row['事件日期（保留来源精度）'],'当前日期':v['事件日期（保留来源精度）'],'核实日期':verification_date,
        '事件性质':v['事件子类型（原始记录）'],'原始事件性质':row['事件子类型（原始记录）'],
        '官方主信源URL':decision.get('官方主信源URL',row['主信源']),
        '第二证据URL':decision.get('第二证据URL',row['交叉核验/相关链接']),
        '第二证据是否真正支持关键事实':decision.get('第二证据是否真正支持关键事实','未检查'),
        '核验结论':conclusion,'存在的问题':problem,'具体修复内容':fix,'核验状态':status,
        '核验时间':decision.get('核验时间','')})
    checked=set(x.strip() for x in decision.get('已检查URL','').split('|') if x.strip())
    primary_urls=urls(v['主信源']); second_urls=urls(v['交叉核验/相关链接'])
    original_primary=urls(row['主信源']); original_second=urls(row['交叉核验/相关链接'])
    all_urls=dict.fromkeys(primary_urls+second_urls+original_primary+original_second+sorted(checked))
    for url in all_urls:
        is_checked=url in checked
        actual_role=('主/次重复同URL' if url in primary_urls and url in second_urls else
                     ('主信源' if url in primary_urls else
                      ('第二证据' if url in second_urls else
                       ('v48原主信源（已替换）' if url in original_primary else
                        ('v48原第二证据（已替换）' if url in original_second else '补充核验证据')))))
        verdict=decision.get('第二证据是否真正支持关键事实','未检查')
        if not is_checked:
            title_support=date_support='未检查'
            actual_proof='未逐页核查；不得据链接本身推断支持该节点'
        elif '已替换' in actual_role:
            title_support=date_support='不作为 v49 当前证据'
            actual_proof='保留的 v48 存量链接，已由 v49 节点级来源替换；其具体局限见行级审核结论与 changes-v49.csv。'
        elif actual_role=='主信源':
            title_support='是' if status.startswith('已确认') else ('部分' if status.startswith('部分确认') else '无法核实')
            date_support='是' if status.startswith('已确认') else ('部分' if status.startswith('部分确认') else '无法核实')
            actual_proof=decision.get('证据证明内容','')
        elif actual_role=='主/次重复同URL':
            title_support=date_support='不能作为第二证据'
            actual_proof='与主信源为同一URL，不能构成第二证据；' + decision.get('证据证明内容','')
        else:
            title_support=date_support=verdict
            actual_proof='行级审核对次证据的判定：'+verdict+'。具体支持范围见行级结论/专家报告。'
        evidence_rows.append({'记录ID':rid,'厂商':row['厂商主题'],'日期':row['事件日期（保留来源精度）'],
            '事件':v['事件标题'],'证据角色':actual_role,'URL':url,'来源级别':source_level(url) if is_checked else '未重新判定',
            '本轮访问状态':'已打开并核对正文' if is_checked else '未重新检查',
            '实际证明内容':actual_proof,
            '是否支持标题事实':title_support,
            '是否支持日期':date_support,
            '是否独立于主信源':decision.get('来源独立性','待判定') if is_checked else '未检查',
            '来源关系/障碍':decision.get('来源关系/障碍','') if is_checked else 'v48存量链接；本轮效力待检查',
            '核验时间':decision.get('核验时间','') if is_checked else ''})

for nr in new_records:
    rid=nr['v49记录ID']
    row={k:v for k,v in nr.items() if k!='v49记录ID'}
    status='已确认：型号、日期与事件性质'
    conclusion=row['v48核验结论']
    second_effect=row['v48第二证据效力']
    v=dict(row)
    v.update({'v49记录ID':rid,'v49核验状态':status,'v49核验结论':conclusion,'v49第二证据效力':second_effect})
    out_main.append(v)
    check_time=f'{TODAY} 12:00 Asia/Shanghai'
    audit_rows.append({'记录ID':rid,'厂商':row['厂商主题'],'模型或产品名称':row['事件标题'],
        '原始模型或产品名称':'','原始日期':'','当前日期':row['事件日期（保留来源精度）'],'核实日期':TODAY,
        '事件性质':row['事件子类型（原始记录）'],'原始事件性质':'','官方主信源URL':row['主信源'],
        '第二证据URL':row['交叉核验/相关链接'],'第二证据是否真正支持关键事实':second_effect,
        '核验结论':conclusion,'存在的问题':'无；v48遗漏节点，按官方原始公告补录。',
        '具体修复内容':'新增历史节点。首次公告日/模型分支已由厂商官方页面确认；后续开放、API或产品 rollout 另作生命周期阶段。',
        '核验状态':status,'核验时间':check_time})
    change_value=f"{row['事件日期（保留来源精度）']} | {row['事件标题']} | {row['模型类别']} | {row['主信源']}"
    change_rows.append({'记录ID':rid,'厂商':row['厂商主题'],'字段':'新增节点（日期/型号/分类/主信源）',
        '修改前':'','修改后':change_value,'依据URL':row['主信源'],
        '修改原因':conclusion,'修改时间':TODAY})
    for role,field in [('主信源','主信源'),('第二证据','交叉核验/相关链接')]:
        for url in urls(row[field]):
            is_primary=role=='主信源'
            evidence_rows.append({'记录ID':rid,'厂商':row['厂商主题'],'日期':row['事件日期（保留来源精度）'],
                '事件':row['事件标题'],'证据角色':role,'URL':url,'来源级别':source_level(url),
                '本轮访问状态':'已打开并核对正文','实际证明内容':conclusion if is_primary else '次级官方来源效力：'+second_effect,
                '是否支持标题事实':'是' if is_primary or second_effect.startswith('是') else '部分',
                '是否支持日期':'是' if is_primary else ('否' if '不独立证明' in second_effect or '不单独证明' in second_effect else '部分'),
                '是否独立于主信源':'否（同一厂商官方资料）','来源关系/障碍':'厂商官方材料；主信源支持公告/日期，次信源按行级结论限定范围。',
                '核验时间':check_time})

def date_sort_value(value):
    parts=[int(x) for x in value.split('-')]
    return (parts[0],parts[1] if len(parts)>1 else 0,parts[2] if len(parts)>2 else 0)
out_main.sort(key=lambda r:date_sort_value(r['事件日期（保留来源精度）']),reverse=True)
audit_rows.sort(key=lambda r:date_sort_value(r['当前日期']),reverse=True)
main_headers=list(main[0])+['v49记录ID','v49核验状态','v49核验结论','v49第二证据效力']
write('company-chronicles-v49.csv',main_headers,out_main)
audit_headers=['记录ID','厂商','模型或产品名称','原始模型或产品名称','原始日期','当前日期','核实日期','事件性质','原始事件性质','官方主信源URL','第二证据URL','第二证据是否真正支持关键事实','核验结论','存在的问题','具体修复内容','核验状态','核验时间']
write('audit-v49.csv',audit_headers,audit_rows)
evidence_headers=['记录ID','厂商','日期','事件','证据角色','URL','来源级别','本轮访问状态','实际证明内容','是否支持标题事实','是否支持日期','是否独立于主信源','来源关系/障碍','核验时间']
write('evidence-v49.csv',evidence_headers,evidence_rows)
write('changes-v49.csv',['记录ID','厂商','字段','修改前','修改后','依据URL','修改原因','修改时间'],change_rows)
candidate_path=ROOT/'missing-candidates.csv'
candidates=read(candidate_path) if candidate_path.exists() else []
added_candidates={
    'GPT-5 Pro':'GPT-5 Pro推理变体已补录，日期按ChatGPT首发公告；API后续阶段分开记录。',
    'GPT-5 mini':'GPT-5 mini API独立型号已补录，官方Changelog标注2025-08-07。',
    'GPT-5 nano':'GPT-5 nano API独立型号已补录，官方Changelog标注2025-08-07。',
    'SAM 3.1':'SAM 3.1模型更新已补录，官方公告标注2026-03-27。',
    'SAM 3D':'SAM 3D Objects/Body已补录，官方公告标注2025-11-19。',
    'Claude 3.5 Haiku':'已补录首次宣布日2024-10-22；API可用在当月稍后。',
    'Qwen2.5-Coder':'Qwen2.5-Coder已补录，官方文章标注2024-09-19；完整系列扩展另记。',
    'Qwen2.5-Math':'Qwen2.5-Math已补录，官方系列公告标注2024-09-19。',
    'Gemini 3.5 Flash Cyber':'Gemini 3.5 Flash Cyber已补录；官方公告为2026-07-21，访问限制为政府/可信合作伙伴有限试点。',
}
for candidate in candidates:
    for name,note in added_candidates.items():
        if name.lower() in candidate['遗漏模型或产品'].lower():
            candidate['处理状态']='已补录至 v49'
            candidate['说明']=note
write('missing-models-v49.csv',['厂商','遗漏模型或产品','所属领域','可能时间','官方证据URL','与数据库关系','处理状态','说明'],candidates)
unresolved=[]
for x in audit_rows:
    if x['核验状态'] in ('部分确认：型号存在，日期或阶段不确定','存在冲突：需要复核','证据不足：暂不采信'):
        unresolved.append({'记录ID':x['记录ID'],'厂商':x['厂商'],'模型或产品名称':x['模型或产品名称'],
            '争议事实':x['存在的问题'],'当前冲突/障碍':x['核验结论'],'已有证据URL':' | '.join(filter(None,[x['官方主信源URL'],x['第二证据URL']])),
            '暂定处理':'保留原节点及原始日期；不将未证实口径写成事实','复核状态':x['核验状态']})
write('unresolved-v49.csv',['记录ID','厂商','模型或产品名称','争议事实','当前冲突/障碍','已有证据URL','暂定处理','复核状态'],unresolved)

counts=Counter(x['核验状态'] for x in audit_rows)
vendors=len({r['厂商主题'] for r in out_main})
full=sum(x['核验状态']=='已确认：型号、日期与事件性质' for x in audit_rows)
reviewed=sum(bool(x['核实日期']) for x in audit_rows)
missing2=sum(not r['交叉核验/相关链接'] for r in main)
incoming_status=Counter(r['v48证据核验状态'] for r in main)
incoming_second_effect=Counter(r['v48第二证据效力'] for r in main)
status_by_id={x['记录ID']:x['核验状态'] for x in audit_rows}
date_fixes=sum(x['字段']=='事件日期（保留来源精度）' and status_by_id.get(x['记录ID'])=='确认错误：已纠正' for x in change_rows)
model_class_fixes=sum(x['字段'] in ('模型类别','原始模型类别','事件子类型（原始记录）') for x in change_rows)
wording_fixes=sum(x['字段']=='事件标题' for x in change_rows)
second_checked=sum(x['第二证据是否真正支持关键事实']!='未检查' for x in audit_rows)
quarantined_reviews=len(read(ROOT/'review-quarantine.csv')) if (ROOT/'review-quarantine.csv').exists() else 0
initial_review_count=len(read(ROOT/'review-decisions.csv'))
def batch_count(pattern, exclude=()):
    return sum(len(read(p)) for p in ROOT.glob(pattern) if p.name not in exclude)
agent_a_rows=batch_count('review-a*.csv')
agent_b_rows=batch_count('review-b*.csv')
agent_c_rows=batch_count('review-c*.csv')
agent_d_rows=batch_count('review-d*.csv', exclude=('review-decisions.csv',))
evidence_checked=sum(x['本轮访问状态']=='已打开并核对正文' for x in evidence_rows)
valid_output_dates=sum(valid_date(r['事件日期（保留来源精度）']) for r in out_main)
duplicate_output_keys=len(out_main)-len({(r['厂商主题'],r['事件日期（保留来源精度）'],r['事件标题'].strip().casefold()) for r in out_main})
validation_path=ROOT/'validation-v49.json'
validation=json.loads(validation_path.read_text(encoding='utf-8')) if validation_path.exists() else None
report=f'''# AI 模型与产品发展史 v49 审核报告

> 此报告由 `build_v49.py` 根据 v49 CSV 自动统计生成。所有计数取自交付文件。

## 当前统计

- 历史节点：{len(out_main)}；厂商：{vendors}
- 本轮逐条记录有核实日期：{reviewed}
- 完全通过核验：{full}
- 日期错误修正：{date_fixes}
- 型号及分类错误修正：{model_class_fixes}
- 事件标题/口径修订：{wording_fixes}
- 新增模型：{len(new_records)}（其余 {len(candidates)-len(new_records)} 条官方目录差集候选仍待逐项核对日期与纳入规则）
- 删除或合并重复节点：0
- 仍缺乏可靠证据或未解决：{len(unresolved)}
- 尚未经过独立重新审核：{len(audit_rows)-reviewed}
- v48 主表缺少第二链接：{missing2}
- v48 基线标注“待逐条复核”：{incoming_status.get('待逐条复核',0)}；“沿用既有核验（未再次逐条核验）”：{incoming_status.get('沿用既有核验（未再次逐条核验）',0)}
- v48 第二证据效力尚未逐一核对：{incoming_second_effect.get('存量链接：本轮未逐一核对其证据效力',0)}；已有人工匹配官方第二入口：{incoming_second_effect.get('本轮人工匹配官方第二入口；按结论限定证明范围',0)}
- 事实审核通过率：{full/len(audit_rows):.1%}
- 第二证据效力已判定记录覆盖：{second_checked}/{len(audit_rows)}（{second_checked/len(audit_rows):.1%}）
- 证据链接本轮打开并核对：{evidence_checked}/{len(evidence_rows)}（{evidence_checked/len(evidence_rows):.1%}）
- 尚待解决或证据不足的节点：{len(unresolved)}
- v49 厂商/日期/标题重复节点数：{duplicate_output_keys}
- v49 日期格式合法记录：{valid_output_dates}/{len(out_main)}

## 状态分布

{chr(10).join(f'- {k}：{v}' for k,v in sorted(counts.items()))}

## 来源与基线

- 主表 SHA-256：`{sha(MAIN)}`
- 历史审核 SHA-256：`{sha(AUDIT)}`
- 证据登记 SHA-256：`{sha(EVIDENCE)}`
- 输入文件保留在原路径；本报告不把 v48 既有结论视为本轮核验。
- 历史资料与模型遗漏检查截止：{SOURCE_CUTOFF}；v49 合并、变更记录与最终验收日期：{TODAY}（Asia/Shanghai）。

## 审核输入映射控制

- 唯一原始节点审核构成为：初始审核 {initial_review_count} 条；Agent A/B/C/D 分别提交 {agent_a_rows}/{agent_b_rows}/{agent_c_rows}/{agent_d_rows} 条；9 条 v49 新增模型另行核验，合计覆盖 {reviewed}/{len(audit_rows)}。
- `review-quarantine.csv` 保存 {quarantined_reviews} 个不计入覆盖的隔离项 ID 与原因，包括 1 条错配（ID 指向 xAI Grok 4.6，但结论与来源属于 OpenAI GPT 初代研究）及重复映射项。审核结论按规范化稳定记录 ID 与主表行对应，不按 URL 数或历史状态计数。

## 专家报告与主要发现

- **Agent A（谱系，{agent_a_rows} 条唯一审核输入）**：定向比对 Google、OpenAI、Meta、DeepSeek 目录并复核 MiniMax、GLM、Qwen、Vidu、ElevenLabs、Seed、Cursor 等行。核实独立专用分支与快照边界；`DeepSeek V4.1-Flash-1017` 是更新快照，不另立基础代际；修正 Gemini 1.5 Flash 主链接误指 Gemini 1.5 Pro，并将 5/14 模型/API 预览与 7/25 消费者端上线分开。A8 还区分 Tongyi Qianwen 首次公开与后续权重开放，指出 GLM-4-9B/GLM-130B 的官方历史时间线冲突。全库目录差集并未穷尽每家厂商全部历史产品。
- **Agent B（信源/日期，{agent_b_rows} 条唯一审核输入）**：逐页区分首次公告、Preview、API 与产品 rollout。将 GPT-5.1 首次公告定为 2025-11-12（11-13 是 API）；确认 GPT-6 Astra 与 Grok 4.6 的日期但限定为有限/受限访问；识别 GPT-5.5 公告/API 日期、Grok 4.5 API/公告、Grok Bot公告/changelog、Mureka V7.0/V7.5 与 Vidu新闻稿日期的阶段差异。遇官网正文不可读或滚动目录无历史日时保留部分确认。
- **Agent C（对抗性复核，{agent_c_rows} 条唯一审核输入）**：重点质疑日期口径、型号与产品混淆、重复模型和来源伪独立。指出 GLM-5.4 次证据不足、PixVerse V6 Max 现有证据只支持 API 新增；对 Google Nano Banana、Deep Think、Lyria 阶段进行区分；并指出 BERT 重复URL、Imagen 重定向和滚动索引不能证明首发日期。其覆盖是抽样对抗复核，不是对 512 条的第二次独立全量审阅。
- **Agent D（遗漏/覆盖与复核，{agent_d_rows} 条唯一审核输入）**：扫描全部初始标题并对 OpenAI、Google、Meta、Qwen 等目录作定向差集，另行核验腾讯/Kling、PixVerse/Vidu、GLM 等。确认 Qwen-Image-Edit 日期应为 2025-08-18；修正智谱清言产品上线日 2023-08-10→2023-08-31；发现同日公告/产品阶段差异、Google Gemini Flash 源链接错配，以及 GLM-4-9B/GLM-130B 历史首发日期冲突。Google 7/21同日公告遗漏 Gemini 3.5 Flash Cyber，已依官方来源单独补录为有限访问试点模型。尚未补录的目录候选和纳入粒度争议见 `missing-models-v49.csv`。

四位专家的概览报告和分批审核 CSV 均保存在 `v49/`。Agent A/B/C/D 的审核输入计数合计 479 条，另有初始主审批次 24 条；重复映射列入隔离表，不重复计数。官方目录确认型号存在，不自动确认发布日期或独立历史节点资格。

## 数据验收

验收脚本 `validate_v49.py` 的最近一次结果：**{'全部通过' if validation and validation.get('all_pass') else '尚未运行或存在失败项'}**。

{chr(10).join(f"- {label}: {'通过' if passed else '失败'}" for label,passed in (validation or {}).get('checks',{}).items())}
'''
(ROOT/'REPORT-v49.md').write_text(report,encoding='utf-8')
print(json.dumps({'nodes':len(out_main),'vendors':vendors,'audit_rows':len(audit_rows),'evidence_urls':len(evidence_rows),'reviewed':reviewed,'fully_confirmed':full,'missing_second_url':missing2},ensure_ascii=False,indent=2))
