# TCM-Agent Exchange Protocol v1.0

## 概述

TCM-Agent 生态系统中各 Skill 之间的数据交换协议。所有 Agent 间传递的数据必须遵循此格式。

## 设计原则

- **JSON 为框架，Markdown 为内容** — 兼顾机器可解析性和人类可读性
- **向后兼容** — 新版本必须能处理旧版本的输出
- **最小化冗余** — 只传递必要的元数据和分析结果

## 交换格式 (Exchange Format)

### 输入格式 (Input)

```json
{
  "version": "1.0",
  "source_skill": "tcm-text-analyzer",
  "timestamp": "2025-04-14T16:00:00+08:00",
  "task": "analyze",
  "input_text": "悸。伤寒悸者．何以明之．悸者心忪是也．",
  "context": {
    "book": "伤寒明理论",
    "chapter": "悸",
    "author": "成无己"
  }
}
```

### 输出格式 (Output)

```json
{
  "version": "1.0",
  "source_skill": "tcm-text-analyzer",
  "timestamp": "2025-04-14T16:05:00+08:00",
  "status": "success",

  "input_text": "悸。伤寒悸者．何以明之．悸者心忪是也．",

  "analysis": {
    "zheng_tags": ["心悸辨证", "水饮为悸", "少阳禁令"],
    "summary": "成无己将悸二分为气虚与停饮，加一层汗下后挟邪之悸",
    "meridian_affiliation": ["太阳", "少阴", "少阳"],
    "formulas_mentioned": ["小建中汤", "四逆散", "茯苓甘草汤"],
    "herbs_mentioned": ["桂枝", "甘草", "茯苓"],
    "pathogenesis_keywords": ["气虚", "停饮", "水停心下", "叉手自冒心"],
    "differentiators": {
      "qi_deficiency_vs_water_retention": "悸而烦(气虚) vs 饮水多(停饮)",
      "simple_vs_post_sweating": "单纯气虚较轻 vs 汗下后挟邪更重"
    }
  },

  "source_tracing": [
    {
      "reference_id": "ref-001",
      "source_book": "伤寒论",
      "chapter": "辨太阳病脉证并治中",
      "clause_number": "102",
      "original_text": "伤寒二三日，心中悸而烦者，小建中汤主之。",
      "confidence": "high",
      "relation": "成无己原文逐字引用"
    }
  ],

  "detailed_report_md": "## [原文段落]\n...\n## [深度病理拆解矩阵]\n...\n## [仲景经文溯源]\n..."
}
```

## 字段定义

### 必填字段 (Required)

| 字段 | 类型 | 说明 |
|------|------|------|
| `version` | string | 协议版本号 |
| `source_skill` | string | 输出此数据的 Skill 名称 |
| `timestamp` | string | ISO 8601 格式时间戳 |
| `status` | string | `success` / `error` / `partial` |
| `input_text` | string | 原始输入文本 |
| `analysis.zheng_tags` | string[] | 下游标识标签 |
| `analysis.summary` | string | 一句话总结 |
| `detailed_report_md` | string | 完整 Markdown 报告 |

### 可选字段 (Optional)

| 字段 | 类型 | 说明 |
|------|------|------|
| `analysis.meridian_affiliation` | string[] | 六经归属 |
| `analysis.formulas_mentioned` | string[] | 提及的方剂 |
| `analysis.herbs_mentioned` | string[] | 提及的药物 |
| `analysis.pathogenesis_keywords` | string[] | 病机关键词 |
| `analysis.differentiators` | object | 鉴别诊断要点 |
| `source_tracing` | array | 经文溯源结果 |
| `context` | object | 输入上下文信息 |

### source_tracing 子字段

| 字段 | 类型 | 说明 |
|------|------|------|
| `reference_id` | string | 唯一标识符 |
| `source_book` | string | 出处书名 |
| `chapter` | string | 篇章名 |
| `clause_number` | string | 条文号（可选，不确定时为空） |
| `original_text` | string | 原文内容 |
| `confidence` | string | `high` / `medium` / `low` |
| `relation` | string | 与当前文本的关系说明 |

## Agent 间数据流转

```
用户输入古文
     │
     ▼
┌─────────────────────┐
│ tcm-text-analyzer   │  输出: 分析报告 JSON
│ 古籍训诂与医理专家   │  zheng_tags: ["太阳表虚证"]
└────────┬────────────┘
         │ JSON 传递
         ▼
┌─────────────────────┐
│ tcm-syndrome-reasoner│  输出: 辨证推理 JSON
│ 六经辨证临床专家      │  meridian: "太阳"
└────────┬────────────┘
         │ JSON 传递
         ▼
┌─────────────────────┐
│ tcm-formula-architect│  输出: 方剂解构 JSON
│ 仲景方剂解构专家      │  formula: "桂枝汤"
└────────┬────────────┘
         │ JSON 传递
         ▼
┌─────────────────────┐
│ tcm-case-simulator  │  输出: 医案对比 JSON
│ 古今医案推演专家      │  similar_cases: [...]
└─────────────────────┘
```

## 错误处理

当 Skill 处理失败时，输出：

```json
{
  "version": "1.0",
  "source_skill": "tcm-text-analyzer",
  "timestamp": "2025-04-14T16:05:00+08:00",
  "status": "error",
  "error": {
    "code": "PARSE_FAILED",
    "message": "无法识别古文格式",
    "input_text": "..."
  }
}
```

## 版本演进

| 版本 | 日期 | 变更 |
|------|------|------|
| 1.0 | 2025-04-14 | 初始版本 |
