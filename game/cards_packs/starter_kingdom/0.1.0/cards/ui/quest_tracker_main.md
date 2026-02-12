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

此面板会自动读取 world attrs 中以 `quest.` 开头的键值并展示，便于在游玩中追踪任务推进。
