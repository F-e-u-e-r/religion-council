# Corpus & RAG Roadmap · 典籍語料與 RAG 藍圖

[English](#english) · [繁體中文](#繁體中文)

> This documents the **corpus seed** (the `01–08` folders) and how it feeds the retrieval
> roadmap. For the user-facing skill, start at the [README](../README.md).

---

## English

### Where the corpus lives

| Layer | Path | Role |
|---|---|---|
| **Runtime snippets** | `references/<tradition>.md` | The hand-picked, cited quotations the personas actually speak from today (Phase 0). |
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
  "version": "通行本", "category": "宗教經典" }
```

Phase 0 parses the cited bullets in the selected `references/` file and applies deterministic
lexical ranking. The **shape is already fixed.** As long as future phases honor it, `SKILL.md`
and all 34 voices keep working unchanged. This is the seam the whole
[roadmap](../README.md#roadmap) turns on.

### RAG ingestion notes (for Phases 2–3)

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

---

## 繁體中文

### 語料分佈

| 層 | 路徑 | 角色 |
|---|---|---|
| **執行期片段** | `references/<傳統>.md` | persona 今日實際引用的精選、附出處引文(第 0 階段)。 |
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
  "version": "通行本", "category": "宗教經典" }
```

第 0 階段會解析所選 `references/` 檔中的附出處條目,並作可重現的詞彙排序;**回傳形狀已固定**。
只要未來階段守住它,`SKILL.md` 與 34 個聲音都不必改。這正是整個
[發展藍圖](../README.md#發展藍圖)的樞紐。

### RAG 收錄實務(第 2–3 階段用)

1. **先固定版本/譯本。** 同一典籍不同譯本用語差異極大,混用會嚴重影響檢索品質。
2. **善用既有結構切分。** 聖經(書/章/節)、古蘭經(章/節)天然適合 chunk;佛典、道藏、諸子需
   自訂切分策略。
3. **版權注意。** 古代原典無版權問題,但**現代譯本與註釋多數仍受版權保護**;建議優先採用公有
   領域或開放授權版本(見 [DISCLAIMER.md](../DISCLAIMER.md))。
4. **metadata 設計。** 至少標註:傳統/教派/典籍類別/書卷/章節/語言/版本——即 `retrieve.py`
   的欄位。
5. **跨傳統去重。** 如《周易》在多傳統共用,需處理重複收錄。
6. **分類標籤。** 區分「宗教經典」與「哲學思想著作」,方便日後過濾與分眾檢索。
