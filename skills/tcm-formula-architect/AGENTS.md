# TCM Formula Architect — 仲景方剂解构专家

**Parent:** ../AGENTS.md
**Version:** v0.1.0 🔲 (模板状态)

## OVERVIEW

接收六经辨证结果，解析方证对应关系与君臣佐使配伍原理，给出精准的方剂选择与用药法度。将"诊断"转化为"处方"。

## INPUT

接收上游JSON，核心字段：
- `syndrome_diagnosis.meridian_primary`
- `syndrome_diagnosis.syndrome_type`
- `clinical_indicators.key_symptoms`
- `next_agent_input.recommended_formulas`

## WHERE TO LOOK

| Task | File | Notes |
|------|------|-------|
| 系统Prompt | SKILL.md | 145行模板 |
| 参考目录 | references/ | 待创建方剂条文对照表 |

## CONVENTIONS

- **Must**: 方证对应分析（为什么选这个方，不选那个方）
- **Must**: 解构君臣佐使（每味药的角色和作用）
- **Must**: 用量法度（原方剂量、煎服法、加减法）
- **Never**: 不得随意加减药物

## OUTPUT FORMAT

```json
{
  "formula_recommendation": {
    "primary_formula": "桂枝汤",
    "selection_basis": "太阳中风证..."
  },
  "formula_deconstruction": {
    "herbs": [
      {"name": "桂枝", "role": "君", "dosage_original": "三两"}
    ]
  },
  "preparation": {
    "decoction_method": "以水七升，微火煮取三升"
  }
}
```

## NOTES

- 模板状态，需完善references/
- 汉制一两约等于现代3g
- Example待补充
