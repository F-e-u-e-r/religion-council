# Corpus & RAG Roadmap · 典籍語料與 RAG 藍圖

[English](#english) · [繁體中文](#繁體中文)

> This documents the **corpus seed** (the `01–08` folders) and how it feeds the retrieval
> roadmap. For the user-facing skill, start at the [README](../README.md).

---

## English

### Where the corpus lives

| Layer | Path | Role |
|---|---|---|
| **Runtime snippets** | `references/<tradition>.md` | The hand-picked, cited quotations the personas actually speak from today (A0). |
| **Corpus seed** | `01-基督宗教/ … 08-墨家/` | Per-tradition `典籍清單.md` (canon list + RAG version notes) and `思想概要.md` (thought summary) — planning material for the fuller corpus. |
| **Retrieval seam** | `skills/religion-council/scripts/retrieve.py` | The stable contract between the corpus and the personas. |

The eight traditions, and how they're classified:

| # | Folder | Category | A religion? |
|---|---|---|---|
| 01 | Christianity 基督宗教 | religion | yes |
| 02 | Islam 伊斯蘭教 | religion | yes |
| 03 | Hinduism 印度教 | religion | yes |
| 04 | Buddhism 佛教 | religion | yes |
| 05 | Taoism 道教 | religion | yes |
| 06 | Legalism 法家 | Pre-Qin political philosophy | no |
| 07 | Confucianism 儒家 | philosophical / ethical system | disputed |
| 08 | Mohism 墨家 | Pre-Qin school of thought | no (though 〈天志〉〈明鬼〉 carry a notion of Heaven's will) |

The first five have an explicit canon/scripture concept. The last three are essentially
**philosophical schools, not religions** — the corpus carries them for their textual value but
tags them distinctly (`category`: `宗教經典` vs `哲學思想著作`).

### The retrieval contract

Everything the personas need from the corpus flows through one function,
`retrieve.retrieve(tradition, query, k)`, which returns records shaped like:

```json
{ "text": "…snippet…", "tradition": "buddhism", "school": "漢傳",
  "work": "般若波羅蜜多心經", "locator": "全經", "language": "zh-Hant",
  "version": "通行本", "category": "宗教經典", "label": "Text",
  "evidence_type": "quotation", "verbatim": true }
```

A0 parses the cited bullets in the selected `references/` file and applies deterministic
lexical ranking. Parenthetical locator notes are not treated as denominations unless they contain
an explicit, recognized school marker. Every parsed bullet is source-bound `[Text]`; the additive
`evidence_type` and `verbatim` fields distinguish a direct quotation from a close, cited summary.
The core retrieval keys are stable. As long as future phases honor them, `SKILL.md` and all 36
voices keep working unchanged. This is the seam the whole
[roadmap](../README.md#roadmap) turns on.

### The retrieval envelope and contract version

`retrieve.retrieve(...)` keeps returning the bare list above for every existing caller.
The B1 retrieval-to-evidence adapter instead consumes a **versioned envelope** from
`retrieve_envelope(tradition, query, k)`:

```json
{ "contract_version": "religion-council/retrieval/v1", "records": [ … ] }
```

Shape negotiation trusts **only** `contract_version` (`RETRIEVAL_CONTRACT_VERSION`); the
per-record `version` field is the *source edition* (e.g. `通行本`), not the API contract.
Each record's `text` **is** the canonical bytes the B1 adapter content-addresses into an
immutable snapshot — `artifact_id = sha256(UTF-8(NFC(text)))`, newlines normalized to LF,
spans as byte offsets — so identity is backend-independent and needs no `source_file`
(which vanishes under A3); A2/A3 may add `artifact_ref` + `content_hash` + a `span`
(`byte_offset` + `byte_length`, since an `artifact_ref` unit can be larger than the quote
and the same wording can recur) for the edition-backed tier (see
[ADR 0003](adr/0003-retrieval-evidence-adapter.md)).
Per [ADR 0006](adr/0006-retriever-fork-contract.md) the portable and project retrievers are now
**forked**: they share one retrieval-envelope contract — proven by the conformance suite in
`tests/retrieval_contract/` — rather than byte-parity. Byte-identical parity is retained only as a
narrow same-artifact check between the two **portable** `retrieve.py` copies (`skills/` ↔
`.claude/skills/`); the project retriever (`orchestrator/project_retrieve.py`) is bound by the
contract, not by byte-parity, and MAY later use an index/RAG backend over the same envelope. See
[ADR 0003](adr/0003-retrieval-evidence-adapter.md) and
[ADR 0006](adr/0006-retriever-fork-contract.md).

### Retrieval field contract

Every record returned by `retrieve.retrieve(...)` carries the fields below. Classifying
them does **not** change the return shape; it only records what future phases may rely on. The two
**portable** `retrieve.py` copies stay byte-identical (a narrow same-artifact check in
`tests/test_retrieve.py`); cross-implementation consistency with the project retriever is enforced
by the contract suite in `tests/retrieval_contract/` ([ADR 0006](adr/0006-retriever-fork-contract.md)).

| Field | Classification | Notes |
|---|---|---|
| `text` | contractual | The snippet. Personas speak from this. |
| `tradition` | contractual | Canonical tradition key. |
| `school` | contractual | Branch/school, or the tradition default. |
| `work` | contractual | Cited work title. |
| `locator` | contractual | Chapter/verse/section locator (or a fallback note). |
| `language` | contractual | Language of the snippet. |
| `version` | contractual | Edition/version tag of the source. |
| `category` | contractual | `宗教經典` vs `哲學思想著作`. |
| `label` | contractual | Evidence-usage marker; currently always `Text`. |
| `evidence_type` | optional contractual | Additive: `quotation` vs `source-bound-summary`. |
| `verbatim` | optional contractual | Additive: `true` only for a verbatim quotation. |
| `topic` | optional contractual | Parsed `〔topic〕` tag; supplementary. |
| `representation_kind` | optional contractual (A1 curated) | Present only when the `presentation.json` sidecar marks the record (e.g. `published-translation`). Curator-declared, carried-not-trusted; never inferred. |
| `rendering_mode` | optional contractual (A1 curated) | e.g. `meaning-rendering` for a Chinese Qur'an rendering, so B2/renderer present it with a rendering marker. Curated; never inferred. |
| `provenance` | optional contractual (A1 curated) | Object: translator / edition / source-language note for a rendering. |
| `rights` | optional contractual (A1 curated) | Per-snippet rights note (satisfies the A1 rights gate). |
| `source_file` | implementation metadata | Absolute path; may change. Do not depend on it. |
| `source_line` | implementation metadata | Parse position; seeds the file-based legacy occurrence id (`occ/v1-corpus-stable`, ADR 0005) and stable tie-breaking. Not Artifact identity. |

The A1 curated fields (introduced in v0.8.0) come from an optional
`references/presentation.json` sidecar, merged by `retrieve.py` onto a record by exact
`(tradition, work, locator)`. The sidecar is additive: an absent, unparseable, or
structurally-invalid file leaves retrieval unchanged, and a field whose value has the wrong type
is dropped at merge (pure-stdlib type-checking; enum-membership is checked in the test suite,
since the portable retriever must not import `policy_enums`). Only entries already marked as
renderings in the reference prose are curated (nothing is inferred). `representation_kind` /
`rendering_mode` remain declared, carried-not-trusted — B2 still span-verifies and the renderer
still shows a rendering marker.

**Contractual** fields are the stable seam every persona and future retriever must
keep. **Optional contractual** fields are additive and stable but supplementary — safe
to use, not load-bearing for the persona contract. **Implementation metadata** is
internal to the A0 file parser and may change without notice; downstream code must
not depend on it. In particular, `source_file` / `source_line` never participate in
**Artifact** identity — the B1 adapter mints that from immutable, content-addressed snapshots,
not from live line numbers (see [ADR 0003](adr/0003-retrieval-evidence-adapter.md)). They DO,
however, seed the file-based legacy **occurrence**-identity scheme (`occ/v1-corpus-stable`), so
for a given snapshot they must stay stable; network/dynamic retrieval must not depend on them and
mints an order-independent occurrence id instead — or fails closed (see
[ADR 0005](adr/0005-stable-occurrence-identity.md)).

`label` is an evidence-usage marker (see [ADR 0001](adr/0001-quote-admissibility-policy.md)),
not an authority or quality score, and a present-in-record value does not by itself
make wording quote-admissible.

### RAG ingestion notes (for A2–A3)

> **Gate:** no index/hybrid/vector/RAG backend is adopted until a candidate clears the retrieval
> benchmark in [benchmarks/retrieval-v1.md](benchmarks/retrieval-v1.md) *and* preserves the ADR 0006
> envelope contract + ADR 0005 stable identity. The notes below are ingestion guidance for that work,
> not a decision to do it.

1. **Pin a version/translation first.** The same text in different translations diverges
   wildly; mixing them wrecks retrieval quality.
2. **Use existing structure to chunk.** The Bible (book/chapter/verse) and Qur'an
   (sūrah/āyah) chunk naturally; Buddhist canon, the Daozang, and the 諸子 need custom
   splitting.
3. **Mind copyright.** Ancient originals are public domain, but **most modern translations and
   annotations are not.** Prefer public-domain or openly licensed editions (see
   [DISCLAIMER.md](../DISCLAIMER.md)).
4. **Design metadata.** At minimum: tradition / denomination / text category / book / chapter
   / language / version — exactly the `retrieve.py` fields.
5. **De-duplicate across traditions.** Shared texts (e.g. the *Yijing*) need handling so they
   aren't ingested twice.
6. **Tag the category.** Separate `宗教經典` from `哲學思想著作` so they can be filtered later.

**Rights gate (tiered).** A1 (curated excerpts) requires per-snippet provenance,
edition/translator, and a rights note. A2 (full-text storage + redistribution) requires an
operational rights review — rights basis, jurisdiction notes, `redistributable = true`, and
a review date — before any text unit enters the distributable corpus; material that has not
cleared full redistribution stays in a restricted/private store.

---

## 繁體中文

### 語料分佈

| 層 | 路徑 | 角色 |
|---|---|---|
| **執行期片段** | `references/<傳統>.md` | persona 今日實際引用的精選、附出處引文(A0)。 |
| **語料種子** | `01-基督宗教/ … 08-墨家/` | 各傳統的 `典籍清單.md`(核心典籍+RAG 版本備註)與 `思想概要.md`(思想摘要)——擴充語料的規劃材料。 |
| **檢索介面** | `skills/religion-council/scripts/retrieve.py` | 語料與 persona 之間的穩定契約。 |

八大傳統與分類:

| 編號 | 資料夾 | 類別 | 是否為宗教 |
|------|--------|------|-----------|
| 01 | 基督宗教(Christianity) | 宗教 | 是 |
| 02 | 伊斯蘭教(Islam) | 宗教 | 是 |
| 03 | 印度教(Hinduism) | 宗教 | 是 |
| 04 | 佛教(Buddhism) | 宗教 | 是 |
| 05 | 道教(Taoism) | 宗教 | 是 |
| 06 | 法家(Legalism) | 先秦政治哲學 | 否 |
| 07 | 儒家(Confucianism) | 哲學/倫理體系 | 學界有爭議 |
| 08 | 墨家(Mohism) | 先秦哲學/思想流派 | 否(惟〈天志〉〈明鬼〉帶神意色彩) |

- 前五項是**宗教**,有明確「經典/聖典」概念。
- 後三項本質是**先秦哲學/思想流派**,並非宗教:法家是政治哲學;儒家是否為「儒教」學界有爭議,
  但四書五經體系明確;墨家為先秦思想流派,〈天志〉〈明鬼〉帶神意色彩,可在 metadata 標註。
- 對 RAG 而言重點是「文本語料」,故一併納入;但**分類標籤須區分「宗教經典」與「哲學思想著作」**。

### 檢索契約

persona 對語料的需求全部走同一個函式 `retrieve.retrieve(tradition, query, k)`,回傳如下形狀的
紀錄:

```json
{ "text": "…片段…", "tradition": "buddhism", "school": "漢傳",
  "work": "般若波羅蜜多心經", "locator": "全經", "language": "zh-Hant",
  "version": "通行本", "category": "宗教經典", "label": "Text",
  "evidence_type": "quotation", "verbatim": true }
```

A0 階段會解析所選 `references/` 檔中的附出處條目,並作可重現的詞彙排序。括號內的出處備註
只有在含明確、已登錄的教派標記時才會成為 `school`;所有解析條目均為有來源約束的 `[Text]`,
再以附加欄位 `evidence_type` 與 `verbatim` 區分逐字引文和附出處摘要。核心檢索欄位保持穩定;
只要未來階段守住它們,`SKILL.md` 與 36 個聲音都不必改。這正是整個
[發展藍圖](../README.md#發展藍圖)的樞紐。

### 檢索 envelope 與 contract version

`retrieve.retrieve(...)` 對既有呼叫者仍回傳上面的純 list。B1 的檢索→證據 adapter 改為消費
`retrieve_envelope(tradition, query, k)` 回傳的**版本化 envelope**:

```json
{ "contract_version": "religion-council/retrieval/v1", "records": [ … ] }
```

shape negotiation 只信 `contract_version`(`RETRIEVAL_CONTRACT_VERSION`);每筆紀錄的
`version` 欄位是**來源版本/edition**(如 `通行本`),不是 API 契約。每筆紀錄的 `text` 即 B1
adapter content-address 成不可變 snapshot 的 canonical bytes(`artifact_id =
sha256(UTF-8(NFC(text)))`,換行正規化為 LF,span 為 byte offset),故 identity 與後端無關、不需
`source_file`(A3 下不存在);A2/A3 可另帶 `artifact_ref` + `content_hash` + `span`
(`byte_offset` + `byte_length`,因 `artifact_ref` 單元可大於引文且相同文字可能重複出現)供 edition-backed
層(見 [ADR 0003](adr/0003-retrieval-evidence-adapter.md))。依
[ADR 0006](adr/0006-retriever-fork-contract.md),可攜版與專案版檢索器現已**分叉**:兩者共用同一份
檢索 envelope 契約(由 `tests/retrieval_contract/` 的 conformance suite 保證),而非位元組 parity。
位元組 parity 僅保留為兩份**可攜** `retrieve.py` 副本(`skills/` ↔ `.claude/skills/`)之間的窄同源檢查;
專案版檢索器(`orchestrator/project_retrieve.py`)受契約約束而非位元組 parity,日後可在同一 envelope 上
改用 index/RAG 後端。見 [ADR 0003](adr/0003-retrieval-evidence-adapter.md) 與
[ADR 0006](adr/0006-retriever-fork-contract.md)。

### 檢索欄位契約

`retrieve.retrieve(...)` 回傳的每筆紀錄都帶有下列欄位。此分類**不**更動回傳形狀,只為每個
欄位分類,讓後續階段知道哪些可依賴。兩份**可攜** `retrieve.py` 保持位元組相同(`tests/test_retrieve.py`
的窄同源檢查);與專案版檢索器的跨實作一致性則由 `tests/retrieval_contract/` 的契約 suite 保證
([ADR 0006](adr/0006-retriever-fork-contract.md))。

| 欄位 | 分類 | 說明 |
|---|---|---|
| `text` | 契約 | 片段本體,persona 據此發言。 |
| `tradition` | 契約 | 傳統的正規鍵。 |
| `school` | 契約 | 派別/學派,或傳統預設值。 |
| `work` | 契約 | 所引典籍名稱。 |
| `locator` | 契約 | 章節/出處定位(或退而求其次的備註)。 |
| `language` | 契約 | 片段語言。 |
| `version` | 契約 | 來源版本標記。 |
| `category` | 契約 | `宗教經典` 與 `哲學思想著作` 之分。 |
| `label` | 契約 | 證據使用標記;目前恆為 `Text`。 |
| `evidence_type` | 可選契約 | 附加:`quotation` 與 `source-bound-summary`。 |
| `verbatim` | 可選契約 | 附加:僅逐字引文為 `true`。 |
| `topic` | 可選契約 | 解析得到的 `〔主題〕` 標籤,屬補充。 |
| `representation_kind` | 可選契約(A1 curated) | 僅當 `presentation.json` sidecar 標註該筆時出現(如 `published-translation`)。由 curator 宣告、carried-not-trusted,絕不臆測。 |
| `rendering_mode` | 可選契約(A1 curated) | 如古蘭經中文釋義為 `meaning-rendering`,供 B2/renderer 以釋義標記呈現。Curated,絕不臆測。 |
| `provenance` | 可選契約(A1 curated) | 物件:譯者/版本/來源語言備註。 |
| `rights` | 可選契約(A1 curated) | 每片段的權利備註(滿足 A1 rights gate)。 |
| `source_file` | 實作 metadata | 絕對路徑,可能變動,不應依賴。 |
| `source_line` | 實作 metadata | 解析位置;為檔案式 legacy occurrence id(`occ/v1-corpus-stable`,ADR 0005)的輸入並用於穩定排序;非 Artifact identity。 |

A1 curated 欄位(v0.8.0 引入)來自選用的 `references/presentation.json` sidecar,由
`retrieve.py` 依精確 `(tradition, work, locator)` merge;為附加性質:檔案缺漏、無法解析或
結構無效則檢索不變,且值型別錯誤者於 merge 時丟棄(純 stdlib 型別檢查;enum 成員檢查在測試套件,
因 portable retriever 不得 import `policy_enums`)。僅標註 reference prose 中已標明為釋義/翻譯者
(絕不臆測)。`representation_kind` / `rendering_mode` 仍為宣告、carried-not-trusted——B2 仍
span 驗證,renderer 仍顯示釋義標記。

**契約**欄位是每個 persona 與未來檢索器都必須守住的穩定介面;**可選契約**欄位為附加且穩定的
補充欄位,可用但非 persona 契約的承重點;**實作 metadata** 屬 A0 階段檔案解析器的內部細節,
可能隨時變動,下游不得依賴。尤其 `source_file` / `source_line` 不參與 **Artifact** identity
——B1 adapter 由不可變、content-addressed 的 snapshot 鑄造,而非依賴 live 行號(見
[ADR 0003](adr/0003-retrieval-evidence-adapter.md));但它們確實是檔案式 legacy **occurrence**
identity scheme(`occ/v1-corpus-stable`)的輸入,故對同一 snapshot 須維持穩定。網路/動態檢索
不得依賴它們,改鑄造與順序無關的 occurrence id,否則 fail closed(見
[ADR 0005](adr/0005-stable-occurrence-identity.md))。

`label` 是證據使用標記(見 [ADR 0001](adr/0001-quote-admissibility-policy.md)),不是權威
或品質分數;欄位中有值本身並不使該用語成為可引用。

### RAG 收錄實務(A2–A3 用)

> **Gate:** 在候選後端通過 [benchmarks/retrieval-v1.md](benchmarks/retrieval-v1.md) 的檢索 benchmark
> 並保住 ADR 0006 envelope 契約與 ADR 0005 穩定 identity 之前,不採用任何 index/hybrid/vector/RAG 後端。
> 以下為該工作的收錄指引,而非「要做」的決定。

1. **先固定版本/譯本。** 同一典籍不同譯本用語差異極大,混用會嚴重影響檢索品質。
2. **善用既有結構切分。** 聖經(書/章/節)、古蘭經(章/節)天然適合 chunk;佛典、道藏、諸子需
   自訂切分策略。
3. **版權注意。** 古代原典無版權問題,但**現代譯本與註釋多數仍受版權保護**;建議優先採用公有
   領域或開放授權版本(見 [DISCLAIMER.md](../DISCLAIMER.md))。
4. **metadata 設計。** 至少標註:傳統/教派/典籍類別/書卷/章節/語言/版本——即 `retrieve.py`
   的欄位。
5. **跨傳統去重。** 如《周易》在多傳統共用,需處理重複收錄。
6. **分類標籤。** 區分「宗教經典」與「哲學思想著作」,方便日後過濾與分眾檢索。

**Rights gate(分層)。** A1(精選 excerpt)要求每片段具 provenance、edition/譯者與 rights note;
A2(全文儲存與再分發)在任何 text unit 進入可分發 corpus 前,需 operational rights review——
rights basis、jurisdiction notes、`redistributable = true` 與 review date;未通過完整再分發審查者,
僅能留在 restricted/private store。
