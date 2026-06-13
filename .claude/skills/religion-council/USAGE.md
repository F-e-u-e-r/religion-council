# 議會使用說明

## 三層架構
- **操作手冊層**:`SKILL.md` — 大家共用的提問架構、引用紀律、防斷章取義守則、圓桌流程。
- **議會成員層**:`../../agents/council-*.md` — 1 個主持人 + 三個層次:
  - **傳統層(8 家)**:基督宗教、伊斯蘭教、印度教、佛教、道教、法家、儒家、墨家。跨傳統對照。
  - **第一層·教派 debate**:基督宗教=天主教/東正教/新教(`references/基督宗教教派.md`);伊斯蘭教=遜尼/什葉(`references/伊斯蘭教派.md`)。
  - **第二層·人物 debate**(教派/學派內代表人物):
    - 基督宗教:耶穌(源頭)、奧古斯丁、阿奎那、路德、加爾文(`references/基督宗教核心人物.md`)
    - 伊斯蘭教:穆罕默德(源頭)、安薩里、伊本·魯世德(`references/伊斯蘭核心人物.md`)
    - 佛教:釋迦牟尼、龍樹、世親、淨土宗(`references/佛教核心人物.md`)
    - 印度教:克里希納、商羯羅、羅摩奴闍、摩陀婆(`references/印度教核心人物.md`)
    - 先秦:孔子、孟子、荀子、老子、莊子(`references/先秦核心人物.md`)
- **工具層**:`scripts/retrieve.py` — v0.1 解析 references 並作詞彙排序,未來換成向量檢索,對外契約不變。

## 怎麼開一場議會
在本專案資料夾(`religion/`)啟動 Claude Code,然後對主對話說,例如:
> 「用議會討論:人生有沒有意義?請佛教、道教、儒家三家先各自陳述,再交叉辯論。」

主對話會把任務交給 **council-moderator**,由它立題、調度各 `council-<傳統>` 成員、轉述彼此論點、最後收斂分歧。也可以直接點名要哪幾家。

**第一層·教派 debate** 範例:
> 「天主教、東正教、新教對『人怎樣得救』看法為何不同?」
> 「遜尼與什葉對『先知之後誰該領導』的分歧是什麼?」

**第二層·人物 debate** 範例:
> 「儒家內部對人性的看法一致嗎?請孔子、孟子、荀子各自說明,再交叉辯論。」
> 「老子和莊子的道有何不同?」
> 「龍樹與世親對『空』與『識』的爭論是什麼?」
> 「吠檀多裡梵與個我是一是二?請商羯羅、羅摩奴闍、摩陀婆各自申辯。」
> 「解脫該靠自力還是他力?請淨土宗與禪/上座部對話。」
> 「信仰與理性會衝突嗎?請安薩里與伊本·魯世德辯論。」
> 「人靠信心還是善功得救?請路德、加爾文與阿奎那對話。」

一般不必同時叫學派層(如 council-confucianism)與其人物層(council-confucius 等),以免重複。

## Claude 主持 + Codex 議員

專案根目錄的 `.mcp.json` 會註冊 `religion-council-controller`。在 Claude Code 的 `/mcp`
批准後,可以說:

> 「請由 Claude 擔任主持人,用 Codex 作八個獨立議員。首輪收齊才做匿名 issue matrix,
> 第二輪必須回到原本相同 threadId,最後再綜合。」

主持人會依序使用 `debate_start`、`debate_collect`、`debate_reply`;失敗時先用
`debate_retry`,並以 `debate_status` 檢查 barrier。八家名冊位於
`orchestrator/panelists/religion-8.json`;通用 30 人範例位於
`orchestrator/panelists/thirty-member-example.json`。

## 注意
- subagent 在 session 啟動時載入;若新增/改動成員,**重開 session** 才生效(skill 與 references 的內容變動則會即時反映)。
- v0.1 只用 `references/` 的精選經文片段做詞彙檢索。要擴充語料,先加進對應 persona 檔;規模變大再接向量庫(改寫 `scripts/retrieve.py` 的 `retrieve()`,保持輸出 metadata 契約)。
- 引用紀律是這套系統的核心價值:沒出處的具體引文一律標〔詮釋〕或要求補出處,《古蘭經》一律標「釋義」。

## 下一步可擴充
1. 把各 persona 的經文片段擴充成小型語料庫(仍放 references/)。
2. 接向量庫:切分 → 嵌入 → 建庫,改寫 `retrieve.py`,輸出帶「傳統/教派/書卷/章節/語言/版本/分類」metadata。
3. 需要 agent 點對點自主協調時,再評估升級到較重的 Agent Teams(目前主持人編排已足夠)。
