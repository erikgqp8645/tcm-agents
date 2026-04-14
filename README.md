# TCM Agents — 古中医 AI 多智能体协作系统

<p align="center">
  <b>Traditional Chinese Medicine Multi-Agent Collaboration System</b>
  <br>
  <i>从古籍阅读到临床推演，四个 AI 专家协同工作</i>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/version-1.0.0-blue" alt="Version">
  <img src="https://img.shields.io/badge/license-MIT-green" alt="License">
  <img src="https://img.shields.io/badge/agents-4-purple" alt="Agents">
  <img src="https://img.shields.io/badge/TCM--Classic-伤寒论-orange" alt="TCM">
</p>

---

## 这是什么？

**TCM Agents** 是一套基于 [OpenClaw](https://github.com/openclaw/openclaw) 的中医 AI 多智能体协作系统。

它将中医研读与临床推演拆解为 **4 个高度独立的 AI 专家**，每个专家专注于一个环节，通过标准化的数据格式协同工作，完成从"古籍阅读"到"临床决策"的完整链条。

## 系统架构

```
用户输入（古文 / 症状 / 医案）
         │
         ▼
┌─────────────────────┐
│ tcm-text-analyzer   │  v5.0.0 ✅
│ 古籍训诂与医理专家   │  对举鉴别 · 病机拆解 · 经文溯源
└────────┬────────────┘
         │ JSON Exchange
         ▼
┌─────────────────────┐
│ tcm-syndrome-reasoner│  v0.1.0 🔲
│ 六经辨证临床专家      │  六经归经 · 病势推演 · 传变预判
└────────┬────────────┘
         │ JSON Exchange
         ▼
┌─────────────────────┐
│ tcm-formula-architect│  v0.1.0 🔲
│ 仲景方剂解构专家      │  方证对应 · 君臣佐使 · 用量法度
└────────┬────────────┘
         │ JSON Exchange
         ▼
┌─────────────────────┐
│ tcm-case-simulator  │  v0.1.0 🔲
│ 古今医案推演专家      │  案例对比 · 风险评估 · 决策建议
└─────────────────────┘
```

## 四大专家

| Skill | 角色 | 状态 | 核心能力 |
|-------|------|------|---------|
| **tcm-text-analyzer** | 古籍训诂与医理专家 | ✅ v5.0.0 | 四维病理拆解、仲景经文溯源、防幻觉机制 |
| **tcm-syndrome-reasoner** | 六经辨证临床专家 | 🔲 模板 | 六经归经、病势传变推演 |
| **tcm-formula-architect** | 仲景方剂解构专家 | 🔲 模板 | 方证对应、君臣佐使解析 |
| **tcm-case-simulator** | 古今医案推演专家 | 🔲 模板 | 案例对比、临床决策建议 |

## 设计原则

### 1. 单一职责 (Single Responsibility)

每个 Agent 只管一件事。训诂的不管辨证，辨证的不管开方，开方的不管找案例。互不越界。

### 2. 标准数据流 (Standard Data Flow)

Agent 之间通过 **JSON + 内嵌 Markdown** 格式传递数据：
- **JSON 字段** → 机器可解析（下一个 Agent 直接读取）
- **detailed_report_md** → 人类可读（保留完整分析报告）

详见 [protocol/exchange-format.md](protocol/exchange-format.md)。

### 3. 隔离的参考库 (Isolated References)

每个 Skill 有自己的 `references/` 目录：
- `tcm-text-analyzer` → 伤寒论/金匮要略条文索引
- `tcm-syndrome-reasoner` → 六经辨证条文对照
- `tcm-formula-architect` → 方剂组成与药物归经
- `tcm-case-simulator` → 古今医案摘要

### 4. 严格的环境门控 (Gating)

所有 Skill 均为纯文本分析，不需要 shell 执行权限。

## 数据输入

本系统可以利用以下数据源：

| 数据源 | 说明 | 位置 |
|--------|------|------|
| **TCM-Ancient-Books** | 701 本中医古籍全文 | `../TCM-Ancient-Books/` |
| **全文搜索工具** | 关键词/正则/组合搜索 | `../TCM-Ancient-Books/tcm-search.py` |
| **NER 数据集** | 中医命名实体识别 | `../TCM-NER-Dataset/` |

## 快速开始

### 作为 OpenClaw Skill 使用

```bash
# 克隆到 OpenClaw skills 目录
cd ~/.openclaw/workspace/skills
git clone https://github.com/your-username/tcm-agents.git

# 按需启用各个 skill
# tcm-text-analyzer 已可用（v5.0.0）
# 其他 skill 的 SKILL.md 模板已就位，可逐步完善
```

### 作为独立 Prompt 使用

每个 skill 的 `SKILL.md` 都可以直接作为 LLM 的 System Prompt 使用：

1. 复制 `skills/tcm-text-analyzer/SKILL.md` 的内容
2. 粘贴到 ChatGPT / Claude / 其他 LLM 的 System Prompt
3. 发送《伤寒明理论》原文即可

## 目录结构

```
tcm-agents/
├── README.md                          # 本文件
├── LICENSE                            # MIT 协议
├── CHANGELOG.md                       # 版本更新日志
├── CONTRIBUTING.md                    # 贡献指南
├── docs/
│   └── architecture.md                # 系统架构详解
├── protocol/
│   └── exchange-format.md             # Agent 间数据交换协议
├── skills/
│   ├── tcm-text-analyzer/             # v5.0.0 ✅
│   │   ├── SKILL.md                   # 核心 Prompt
│   │   └── references/
│   │       └── 伤寒论-条文索引.md
│   ├── tcm-syndrome-reasoner/         # v0.1.0 🔲
│   │   └── SKILL.md
│   ├── tcm-formula-architect/         # v0.1.0 🔲
│   │   └── SKILL.md
│   └── tcm-case-simulator/           # v0.1.0 🔲
│       └── SKILL.md
└── data/                              # 共享数据（不纳入仓库）
    ├── shanghan-lun/
    ├── jingui-yaolue/
    ├── huangdi-neijing/
    └── ancient-refs/
```

## 贡献

欢迎贡献！特别是：

1. **完善 tcm-text-analyzer 的示例** — 添加更多《伤寒明理论》篇章的解析
2. **补全其他三个 Skill** — 从模板变为可用版本
3. **校验溯源结果** — 确保条文号和原文准确无误

详见 [CONTRIBUTING.md](CONTRIBUTING.md)。

## 许可证

[MIT License](LICENSE)
