# TCM Text Analyzer — 伤寒明理论精读专家

**Parent:** ../AGENTS.md
**Version:** v5.0.0 ✅

## OVERVIEW

以成无己"对举"修辞为切入点，对《伤寒明理论》原文进行四维病机拆解（病位/病性/气机演变/鉴别金指标），并精准追溯至《伤寒论》《金匮要略》原始条文。

## STRUCTURE

```
tcm-text-analyzer/
├── SKILL.md                    # 核心Prompt (62行)
└── references/
    └── 伤寒论-条文索引.md
```

## WHERE TO LOOK

| Task | File | Notes |
|------|------|-------|
| 系统Prompt | SKILL.md | Objective/Rules/Workflow完整 |
| 条文索引 | references/伤寒论-条文索引.md | 溯源依据 |

## CONVENTIONS

- **四维分析Must**: 每次拆解必须包含病位/病性/气机演变/鉴别金指标
- **溯源Must**: 必须设立`# 仲景经文溯源`环节
- **Never幻觉**: 条文号无100%把握时只给篇章名

## OUTPUT FORMAT

```markdown
**[原文段落]**：...

**[深度病理拆解矩阵]**：
- 🔴 **对比组：[概念A] vs [概念B]**

**[仲景经文溯源 (Source Tracing)]**：
- 📜 **溯源点1**：
  - **出处**：《伤寒论》[篇名/第x条]
  - **仲景原文**："..."
  - **印证解说**：...

**[下游提取标识(Zheng)]**：...
```

## EXAMPLE

- `examples/伤寒明理论-悸.md` — 悸篇完整解析示例

## NOTES

- 防幻觉机制：不确定条文号时不编造
- 输入原文保持原貌
