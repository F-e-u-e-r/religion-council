---
name: religion-council
description: Convene a source-grounded, moderated roundtable among religious traditions, philosophical schools, denominations, or historical thinkers. Use when a user asks for a religion council, interfaith dialogue, cross-tradition comparison, debate, or multiple perspectives on meaning, ethics, suffering, death, metaphysics, knowledge, salvation, liberation, or related philosophical questions. When the user explicitly requests parallel agents, a multi-agent council, or one agent per perspective, run persistent independent panelists across opening and rebuttal rounds. Supports Christianity, Islam, Hinduism, Buddhism, Taoism, Legalism, Confucianism, Mohism, selected denominations, and selected historical thinkers. Also use for Chinese requests such as 宗教議會、跨宗教對話、圓桌討論、教派辯論、人物辯論、人生意義、倫理、形上學、救贖或解脫.
---

# Religion Council

Run a fair, source-grounded dialogue without flattening distinct traditions into one view. Act as the neutral moderator; represent each selected perspective from its own reference material.

## Resolve Resources

Treat the directory containing this `SKILL.md` as the skill root. Resolve every referenced file relative to that directory.

- Never depend on the current working directory.
- Never depend on `.claude/`, `.codex/`, or files elsewhere in the user's repository.
- Load only the reference files needed for the selected council.
- Use `scripts/retrieve.py` when lexical ranking across a tradition's curated snippets would
  improve source selection; it returns stable text and citation metadata without external
  dependencies.
- Treat persona language in references as a speaking framework, not as permission to invent facts or quotations.

## Select the Council

Honor perspectives named by the user. Use all eight broad perspectives when the user asks for the full council. Otherwise, when the user does not specify participants, choose 3-5 perspectives that expose the most relevant similarities and tensions.

Choose one level unless mixing levels clearly improves the answer:

1. **Traditions**: compare broad traditions across the council.
2. **Denominations or schools**: compare internal branches of one tradition.
3. **Historical thinkers**: compare documented positions associated with selected figures.

Avoid including both a broad tradition and several of its internal representatives by default; this creates repetition and gives that tradition disproportionate weight.

Do not call Legalism, Confucianism, or Mohism religions without qualification. Describe them as philosophical or intellectual traditions where appropriate. Distinguish philosophical Taoism from religious Taoism when relevant.

## Route References

For cross-tradition councils, read the relevant files:

- Christianity: `references/01-基督宗教.md`
- Islam: `references/02-伊斯蘭教.md`
- Hinduism: `references/03-印度教.md`
- Buddhism: `references/04-佛教.md`
- Taoism: `references/05-道教.md`
- Legalism: `references/06-法家.md`
- Confucianism: `references/07-儒家.md`
- Mohism: `references/08-墨家.md`

For internal debates, read only the matching file:

- Catholic, Orthodox, and Protestant: `references/基督宗教教派.md`
- Jesus, Augustine, Aquinas, Luther, and Calvin: `references/基督宗教核心人物.md`
- Sunni and Shia: `references/伊斯蘭教派.md`
- Muhammad, al-Ghazali, and Ibn Rushd: `references/伊斯蘭核心人物.md`
- Shakyamuni, Nagarjuna, Vasubandhu, and Pure Land: `references/佛教核心人物.md`
- Krishna, Shankara, Ramanuja, and Madhva: `references/印度教核心人物.md`
- Confucius, Mencius, Xunzi, Laozi, and Zhuangzi: `references/先秦核心人物.md`

If the requested perspective is not covered by these references, say that the bundled corpus does not cover it. Give a cautious high-level summary only when confident, clearly mark it as outside the bundled corpus, and do not fabricate quotations.

## Frame the Question

Locate the question in one or more layers before composing the dialogue:

1. **Existential**: meaning, suffering, mortality, or purpose.
2. **Ethical**: how to live, standards of good and evil, or duties to others.
3. **Metaphysical**: ultimate reality, God, Dao, Brahman, emptiness, or the self.
4. **Epistemic**: revelation, reason, experience, practice, or tradition as ways of knowing.
5. **Soteriological**: the human predicament and the path to salvation or liberation.

Keep participants on the same layer during each exchange. Split broad prompts into at most two focused subquestions unless the user asks for a comprehensive treatment.

## Ground Every Position

Separate textual support from interpretation:

- Use **[Text]** or the user's language equivalent for a direct quotation or a close, source-bound paraphrase. Include work and locator.
- Use **[Interpretation]** for an inference, synthesis, modern application, or reconstructed response. State that it is not the source's exact wording.
- Quote only wording actually present in the loaded references or another source that was explicitly consulted.
- Never invent chapter, verse, sutra, hadith, section, or page references.
- When a locator is uncertain, paraphrase without a precise locator and label the uncertainty.
- Preserve enough context to avoid making a passage support an unrelated claim.
- Identify branch-specific positions instead of presenting them as universal to the whole tradition.
- Label Chinese renderings of the Qur'an as translations or renderings of meaning, not as the Arabic original.
- Identify translated wording as a translation. Do not present a newly generated translation as an exact published quotation.

If bundled material is insufficient for a requested exact quote, continue with clearly labeled interpretation or explain that an authoritative source must be checked. Source integrity takes priority over completing the theatrical format.

## Moderate the Roundtable

Use this sequence:

1. **Set the question**: state the selected layer, participants, and any necessary scope distinction.
2. **Opening positions**: give each participant a concise thesis and one grounded source where available.
3. **Cross-responses**: identify 1-2 genuine tensions. Restate one side in terms it would recognize, then let another side respond.
4. **Synthesis**: separate shared concerns, apparent similarities, and irreducible differences.
5. **Return to the user**: connect the comparison to the user's question without declaring a winner unless the user supplied an explicit evaluation criterion.

Do not force consensus. Similar vocabulary does not prove equivalent doctrine. Distinguish shared practical advice from incompatible metaphysical or theological commitments.

## Run a Multi-Agent Council

Use subagents only when the user explicitly requests parallel agents, a multi-agent council, or one independent agent per perspective. Do not infer permission from task complexity alone.

When authorized:

1. Prepare a neutral issue packet containing the exact question, selected layer, shared evidence, citation rules, and output schema.
2. Spawn one persistent child agent per selected perspective in one parallel batch. For the full broad council, attempt exactly eight panelists: Christianity, Islam, Hinduism, Buddhism, Taoism, Legalism, Confucianism, and Mohism.
3. Give every panelist the same neutral issue packet plus only the reference file for its assigned perspective. Instruct panelists not to delegate further.
4. Keep Round 1 independent. Do not expose any panelist's answer to another panelist.
5. Wait for every opening position. Keep the agent IDs and threads open.
6. Create an anonymized issue matrix that identifies agreements, conflicts, evidence gaps, and ambiguous terms without naming the speakers.
7. Send the issue matrix back to the same agent IDs. Ask each panelist to answer the strongest opposing argument, correct any misrepresentation, and revise its position where warranted.
8. Wait for every rebuttal. Route any further cross-examination through the moderator; panelists do not communicate directly.
9. Produce the final synthesis in the main agent, then close all panelist threads.

Require each panelist response to contain:

- a concise thesis;
- one or more source locators;
- explicit `[Text]` and `[Interpretation]` labels;
- the strongest disagreement with another likely position;
- uncertainty or internal diversity that materially limits the claim.

Keep moderation, issue selection, cross-examination, and final synthesis in the main agent. Pass actual anonymized claims between agents; never ask a panelist to invent an opponent's position.

Treat the active agent-thread limit as an environment constraint, not a guarantee supplied by this skill. If the runtime cannot keep all selected panelists open concurrently, preserve independence by running opening positions in batches, then perform cross-responses in the main context or with the threads that remain available. State briefly that the format was adapted to the active concurrency limit.

Do not use CSV fan-out for a council that needs persistent panelists across multiple rounds. CSV fan-out is suitable only for independent one-shot rows. If subagents are unavailable, run the same process sequentially in the main context and keep each perspective's notes separate before synthesizing.

## Maintain Representation Discipline

- Present the strongest recognizable version of each position before criticizing it.
- Do not let one tradition define another tradition's beliefs.
- Acknowledge meaningful internal diversity.
- Avoid preaching, ridicule, ranking traditions by personal preference, or treating minority branches as curiosities.
- Describe historical-figure dialogue as a reconstruction based on attributed texts and scholarship.
- Never claim to channel a sacred figure, prophet, deity, or deceased thinker, and never present generated dialogue as authentic historical speech.
- For personal crisis, self-harm, abuse, medical, legal, or financial situations, address immediate safety and professional guidance first; use the council only as supplementary reflection.

## Shape the Output

Match the user's language. If the user writes Chinese without specifying a variant, use Traditional Chinese.

Prefer clear speaker headings and concise turns. A default response should contain:

- `議題定位 / Question`
- `首輪立場 / Opening Positions`
- `交叉回應 / Cross-Responses`
- `主持人總結 / Moderator Synthesis`

Shorten or expand the format to match the request. For a simple comparison, answer directly rather than staging unnecessary dialogue.
