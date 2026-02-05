---
kind: overlay_ops
priority: 10
ops:
  - type: SetAttr
    entity_id: player
    key: strength
    value: "5"
    source: overlay
  - type: SetAttr
    entity_id: player
    key: agility
    value: "5"
    source: overlay
  - type: SetAttr
    entity_id: player
    key: vitality
    value: "5"
    source: overlay
  - type: SetAttr
    entity_id: player
    key: intellect
    value: "5"
    source: overlay
  - type: SetAttr
    entity_id: player
    key: willpower
    value: "5"
    source: overlay
  - type: SetAttr
    entity_id: player
    key: charisma
    value: "5"
    source: overlay
  - type: SetAttr
    entity_id: player
    key: hero_talent_level
    value: "1"
    source: overlay
  - type: SetAttr
    entity_id: player
    key: hero_talent_node
    value: "awakening_1"
    source: overlay
  - type: SetAttr
    entity_id: player
    key: affinity_lord_alric
    value: "0"
    source: overlay
  - type: SetAttr
    entity_id: player
    key: affinity_guard_captain_lyra
    value: "0"
    source: overlay
  - type: SetAttr
    entity_id: player
    key: affinity_guild_master_bram
    value: "0"
    source: overlay
  - type: SetAttr
    entity_id: player
    key: affinity_blacksmith_hugo
    value: "0"
    source: overlay
  - type: SetAttr
    entity_id: player
    key: affinity_tavern_keeper_mira
    value: "0"
    source: overlay
  - type: SetAttr
    entity_id: player
    key: affinity_apothecary_selene
    value: "0"
    source: overlay
  - type: SetAttr
    entity_id: player
    key: affinity_witch_elowen
    value: "0"
    source: overlay
  - type: SetAttr
    entity_id: player
    key: affinity_weapon_master_kael
    value: "0"
    source: overlay
  - type: AddEdge
    subject_id: player
    relation: has
    object_id: iron_sword
    confidence: 0.9
    source: overlay
  - type: AddEdge
    subject_id: player
    relation: has
    object_id: linen_cloak
    confidence: 0.9
    source: overlay
  - type: AddEdge
    subject_id: player
    relation: has
    object_id: travel_rations
    confidence: 0.9
    source: overlay
  - type: AddEdge
    subject_id: player
    relation: has
    object_id: city_map
    confidence: 0.9
    source: overlay
---
初始化玩家属性、好感度与起始物品。
