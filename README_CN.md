# TextRPG 中文使用文档

基于 LangChain + LangGraph 的 AI 文字交互 RPG 引擎，支持卡牌体系、规则引擎、长期记忆、Overlay 作弊层，以及可下载卡牌资源包（card packs）。

## 快速开始（CLI）

1) 激活 conda 环境：
```
conda activate E:\TextRPG\.conda\envs\TextRPG-py311
```

2) 安装依赖：
```
pip install -r requirements.txt
```

3) 启动游戏：
```
python -m game.main
```

如果没有设置 `OPENAI_API_KEY`，会自动使用 mock LLM 模式，保证可运行。

## 启动 UI（Streamlit）

```
streamlit run ui/app.py
```

UI 提供三个页面：Play（游玩）、Pack Manager（资源包管理）、Card Designer（卡牌设计）。

## 卡牌与规则

- 内置卡牌在 `game/cards/`。
- 每张卡牌是 `.md` 文件，使用 YAML frontmatter + 正文描述。
- 全局规则定义在 `game/cards/card_logic.md`（关系约束、派生动作等）。

## 资源包（Card Packs）

资源包安装目录：
```
game/cards_packs/<pack_id>/<version>/
```

Zip 包内必须包含 `pack.json`（或 `pack.yaml`）与 `cards_root` 目录，目录结构需与内置卡牌一致。

冲突优先级：
```
overlay > 存档动态状态 > 启用的 pack > 内置 cards
```

### UI 管理

在 Pack Manager 页面中可：
- 列出已安装 packs
- 从 URL 下载安装
- 上传本地 zip 安装
- 启用/禁用/删除
- 导出为 zip

## 卡牌制作教程

### 1) 卡牌基础格式

每张卡牌是 `.md` 文件，由 YAML frontmatter + 正文构成：

```
---
id: bartender
type: character
tags: [npc]
initial_relations:
  - subject_id: bartender
    relation: at
    object_id: tavern
hooks: []
---

The bartender polishes glasses and watches the room with a knowing gaze.
```

必填字段：
- `id`：全局唯一字符串
- `type`：`character | item | location | event | memory` 之一
- `tags`：字符串数组

可选字段：
- `initial_relations`：初始关系边（subject_id, relation, object_id）
- `hooks`：字符串数组（自由扩展）

### 2) 目录结构

内置卡牌位于：
```
game/cards/
  characters/
  items/
  locations/
  events/
  memories/
```

示例：
- `game/cards/characters/bartender.md`
- `game/cards/items/rusty_key.md`
- `game/cards/locations/tavern.md`

### 3) 关系与规则

关系合法性由 `game/cards/card_logic.md` 决定，例如：
- `at`：character -> location（每个角色只能有一个）
- `has`：character -> item（可多个）

如果要新增关系类型，需要同步修改 `card_logic.md`。

### 4) 使用 UI 制作

启动 UI：
```
streamlit run ui/app.py
```

进入 **Card Designer**：
- 选择一个 pack（或先创建新的 pack）
- 选择类型并填写卡牌 id
- 编辑 YAML frontmatter 和正文
- 点击 **Save Card**

### 5) Overlay（可选）

如果想通过文件直接修改运行时状态，在：
```
game/cards/_overlay/
```

新建 overlay 文件，格式示例：
```
---
kind: overlay_ops
priority: 10
ops:
  - type: AddEdge
    subject_id: player
    relation: has
    object_id: rusty_key
    confidence: 0.9
    source: overlay
---
```

每回合开始会读取 overlay ops 并合并到本回合操作中。

## Overlay 作弊/后台管理

Overlay ops 文件放在：
```
game/cards/_overlay/
```

示例格式：
```
---
kind: overlay_ops
priority: 10
ops:
  - type: AddEdge
    subject_id: player
    relation: has
    object_id: rusty_key
    confidence: 0.9
    source: overlay
---
```

每回合开始会加载 overlay ops，并与 LLM 生成的 ops 合并后统一校验与执行。

### CLI 管理命令（可选）
```
/give player rusty_key
/teleport player tavern
/set bartender.mood angry
```

## 存档与状态镜像

存档路径：
```
data/saves/slot_001/
```

每回合结束会导出状态镜像到：
```
data/saves/slot_001/state_snapshot/
```

镜像文件以实体 id 命名，内容包含属性与关系边。

## 开发脚本
```
scripts/dev_install.sh
scripts/run_cli.sh
scripts/run_ui.sh
```

## 测试
```
pytest
```


## 自定义 UI 卡牌（新增）

支持在卡牌包中加入 `type: ui` 的卡牌，系统会自动在 Play 页面渲染为可拖拽、可缩放的浮窗，并支持多卡并存。

建议格式：

```md
---
id: quest_tracker_main
type: ui
tags: [ui, quest]
ui_schema:
  panel_id: quest_tracker_main
  title: 任务推进
  panel_type: quest_tracker
  visible_by_default: true
  layout:
    x: 24
    y: 120
    width: 360
    height: 320
  sections:
    - title: 可推进任务
      attr_prefix: quest.
      empty_text: 暂无可推进任务
---

可在正文补充说明。
```

说明：
- `panel_type` 可用：`quest_tracker`、`relation_board`、`facts_list`。
- `sections` 会由 UI 更新 agent 按回合实时刷新。
- Play 页面侧栏新增面板总开关，每个面板可独立显示/隐藏。
