# TCM Syndrome Reasoner — 六经辨证临床专家

**Parent:** ../AGENTS.md
**Version:** v0.1.0 🔲 (模板状态)

## OVERVIEW

接收tcm-text-analyzer输出的病机分析，将症状映射到《伤寒论》六经辨证体系（太阳/阳明/少阳/太阴/少阴/厥阴），推演病势传变走向。

## INPUT

接收上游JSON，核心字段：
- `analysis.zheng_tags`
- `analysis.meridian_affiliation`
- `analysis.pathogenesis_keywords`
- `source_tracing`

## WHERE TO LOOK

| Task | File | Notes |
|------|------|-------|
| 系统Prompt | SKILL.md | 109行模板 |
| 参考目录 | references/ | 待创建 |

## CONVENTIONS

- **Must**: 明确判定六经归属（主经+兼经）
- **Must**: 分析病势走向（当前在何经，有无传变趋势）
- **Never**: 不得用现代医学术语替代六经概念
- **Never**: 不确定时标记"待定"而非猜测

## OUTPUT FORMAT

```json
{
  "syndrome_diagnosis": {
    "meridian_primary": "太阳",
    "meridian_secondary": ["少阳"],
    "syndrome_type": "太阳中风证"
  },
  "transformation_prediction": {
    "current_stage": "太阳表证",
    "trend": "若失治，可传阳明"
  },
  "next_agent_input": {
    "target_skill": "tcm-formula-architect"
  }
}
```

## NOTES

- 模板状态，需完善references/目录
- 依赖上游tcm-text-analyzer输出
- Example待补充
