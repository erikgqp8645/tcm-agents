# TCM Case Simulator — 古今医案推演专家

**Parent:** ../AGENTS.md
**Version:** v0.1.0 🔲 (模板状态)

## OVERVIEW

接收前方剂推荐结果，在古今医案库中寻找类似案例进行对比验证，给出临床决策建议。是整个Agent链条的最后一环。

## INPUT

接收上游JSON，核心字段：
- `formula_recommendation.primary_formula`
- `formula_deconstruction.herbs`
- `next_agent_input.syndrome`

## WHERE TO LOOK

| Task | File | Notes |
|------|------|-------|
| 系统Prompt | SKILL.md | 125行模板 |
| 参考目录 | references/ | 待创建古今医案摘要索引 |

## CONVENTIONS

- **Must**: 至少2个案例对比（一个古代，一个近现代）
- **Must**: 每个案例含出处/原文/辨证/用药/效果
- **Never**: 不得编造不存在的医案
- **Never**: 不确定时标注"待验证"

## OUTPUT FORMAT

```json
{
  "case_references": [
    {
      "case_type": "经典原文",
      "formula_used": "桂枝汤",
      "outcome": "汗出而愈"
    }
  ],
  "final_recommendation": {
    "verdict": "可用桂枝汤",
    "suggested_dosage": "桂枝9g 白芍9g..."
  }
}
```

## NOTES

- 模板状态，需完善references/
- 可利用TCM-Ancient-Books全文搜索
- Example待补充
