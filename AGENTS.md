# TCM Agents — 古中医 AI 多智能体协作系统知识库

**Generated:** 2026-04-15
**Commit:** bc754b4
**Branch:** main

## OVERVIEW

基于 OpenClaw 的中医 AI 多智能体系统，4 个专家（text-analyzer → syndrome-reasoner → formula-architect → case-simulator）通过 JSON 协议协同工作，实现从古籍阅读到临床决策的完整链条。

## STRUCTURE

```
tcm-agents/
├── skills/                      # 4个独立Agent定义
│   ├── tcm-text-analyzer/      # v5.0.0 ✅ (唯一完整实现)
│   ├── tcm-syndrome-reasoner/  # v0.1.0 🔲
│   ├── tcm-formula-architect/  # v0.1.0 🔲
│   └── tcm-case-simulator/    # v0.1.0 🔲
├── data/ancient-books/         # 701本中医古籍全文
├── protocol/                   # JSON数据交换协议
├── examples/                   # 解析示例
└── docs/                      # 架构文档
```

## WHERE TO LOOK

| Task | Location | Notes |
|------|----------|-------|
| 伤寒明理论精读 | skills/tcm-text-analyzer/SKILL.md | v5.0.0 完整实现 |
| 六经辨证模板 | skills/tcm-syndrome-reasoner/SKILL.md | 待完善 |
| 方剂解构模板 | skills/tcm-formula-architect/SKILL.md | 待完善 |
| 医案推演模板 | skills/tcm-case-simulator/SKILL.md | 待完善 |
| 数据搜索 | data/ancient-books/tcm-search.py | 全文检索脚本 |
| NER识别 | data/ancient-books/tcm_ner.py | 命名实体识别 |
| Agent协议 | protocol/exchange-format.md | JSON字段定义 |

## CODE MAP

| Symbol | Type | Location | Role |
|--------|------|----------|------|
| tcm-text-analyzer | SKILL.md | skills/tcm-text-analyzer/ | 核心Prompt专家 |
| tcm-syndrome-reasoner | SKILL.md | skills/tcm-syndrome-reasoner/ | 六经辨证 |
| tcm-formula-architect | SKILL.md | skills/tcm-formula-architect/ | 方剂解构 |
| tcm-case-simulator | SKILL.md | skills/tcm-case-simulator/ | 医案推演 |

## CONVENTIONS

- **SKILL.md**: 每个skill的核心Prompt文件，含Objective/Rules/Workflow/Output Format
- **JSON Exchange**: Agent间传递格式 = JSON字段 + detailed_report_md
- **隔离Reference**: 每个skill有独立的references/目录
- **版本标签**: v5.0.0=完整 ✅，v0.1.0=模板 🔲

## ANTI-PATTERNS (THIS PROJECT)

- **不修改古籍原文**: 输入原文保持原貌，不做现代标点或删改
- **无幻觉条文号**: 条文号必须100%确认，不确定则只给篇章名
- **单一职责**: 每个Agent只管一个环节，不越界

## UNIQUE STYLES

- **成无己体系**: tcm-text-analyzer专攻《伤寒明理论》的对举修辞分析
- **四维病机拆解**: 病位/病性/气机演变/鉴别金指标
- **仲景经文溯源**: 每一处医理必须追溯到《伤寒论》原文

## COMMANDS

```bash
# 搜索古籍关键词
python data/ancient-books/tcm-search.py "关键词"

# NER实体识别
python data/ancient-books/tcm_ner.py
```

## NOTES

- docs/目录目前为空，架构文档待创建
- 无CI/CD配置，纯文本分析项目
- 依赖OpenClaw框架运行
