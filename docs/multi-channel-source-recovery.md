# Multi-channel discovery and access failure audit

Reviewed 2026-11-28. This is an engineering/source inventory, not input to production benchmarks or manually injected events.

| Publisher | Observed route | Status |
|---|---|---|
| Z.ai | https://www.zhipuai.cn/zh/research/164 | readable Chinese original, header displays 2026/11/22 16:00 without explicit timezone; do not force day to 23 |
| Z.ai | https://mp.weixin.qq.com/s/D-IZr-QaT1or_chminK8IQ | original publisher pointer found via AIHOT, direct read unavailable |
| Z.ai | https://aihot.news/items/d4hhqnlmrclsx7d6idtvq95wz | discovery index, not authoritative date/statement |
| Z.ai | https://aihot.news/items/dzf8rz0gf3la7bs8kew4l0zlz | indexed publisher social announcement, original X proof needed |
| Niji | https://nijijourney.com/zh/blog/niji-8 | indexed Chinese original displays Nov 24; existing runner 403 not resolved by human web access |
| Niji | https://x.com/nijijourney/status/2125304624571986227 | public indexed announcement pointer, not fresh verified proof |
| Midjourney | https://x.com/midjourney/status/2125328040624521639 | existing independent publisher availability record already persisted via documented official embed |
| Midjourney | https://updates.midjourney.com/ | access-code page, not a usable public release feed |

AIHOT's public documentation supports RSS, HTML list, JSON list, X, WeChat and external adapters. X/WeChat adapters need paid providers; do not import these dependencies. Its public service terms https://aihot.news/terms limit public mirrors and bulk redistribution. Reuse already observed original links for discovery; do not mirror or republish its contents or bypass access limits.

Architecture: independent discovery channels -> exact model identity -> bounded independent source routes -> stage/date evidence -> separately reviewed event metrics. Source outage must not imply event outage. Do not convert article date, indexed date, social availability or catalog state into first release. This candidate reduces duplicate blocked requests and surfaces previously ignored original-channel pointers; it does not claim two missing benchmark events passed. Further adapter proof, same-stage benchmark and actual runner verification remain required.
