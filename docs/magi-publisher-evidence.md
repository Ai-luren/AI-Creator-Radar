# MAGI-2 publisher evidence correction

The [official launch article](https://sand.ai/blog/magi-2/) uses a graphic model mark in the H1, a dated research header and a present-day launch sentence ending the model name with an em dash. The previous resolver only accepted a matching text H1 and rejected that punctuation. It had retained an identity-unresolved task despite the separate research-index date hit.

The scoped Sand.ai fallback requires exactly one H1, a matching publisher document title with the same descriptive suffix, the existing allowed source/family match, a nonconflicting publisher calendar date and affirmative same-model launch wording in the introduction. The original statement and date are retained as a separate observation, not canonical releaseEvidence. Preview and future weight release remain distinct. Resolver revision 5 makes affected unresolved tasks eligible for bounded retry. Tests are markup-shaped fixtures, not a real network acceptance result. Production runner observation and persistence remain required.

## Independent discovery channels

The official Chinese research directory (https://sandai.cn/research) was
read separately: the November 24 flagship entry links to the same original
article on sand.ai, and the August 5 preview is a separate entry. It is
configured as a bounded fallback on failed or empty English directory reads,
not a second independent publisher or a second release. Its listing date
does not become verified article-body launch evidence.

Further discovery pointers, not automatic canonical release evidence:
the MAGI product account post at https://x.com/magiai_hq/status/2125290721003680155
(public indexed representation only), the partner announcement
https://higgsfield.ai/announcing-magi-2 (service availability, not an
independent first-release date), and IT Home
https://www.ithome.com/1/032/124.htm (news report, distinct reporting date).
A public index points to a Digital Life Kazik WeChat article, but the original
WeChat article was not retrieved. Do not count the index as first-party
proof or copy its content. Official GitHub/Hugging Face preview weights
must not be confused with future flagship weights.

For other vendors, reuse this pattern: official localized directories,
public product/account updates, official repositories, partner availability,
and compliant third-party discovery indexes. Keep source rights, original
links, report versus event dates, bounded retry, and evidence grades.
The Chinese fallback is code-tested against a markup-shaped fixture; real
runner accessibility and persistence are separate acceptance requirements.
