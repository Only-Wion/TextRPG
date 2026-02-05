from pathlib import Path

root = Path(r'E:\TextRPG\game\cards_packs\starter_kingdom\0.1.0')
files = {}

files['pack.json'] = """{
  \"pack_id\": \"starter_kingdom\",
  \"name\": \"新手王国：城镇·森林·海洋\",
  \"version\": \"0.1.0\",
  \"author\": \"TextRPG Team\",
  \"description\": \"包含城镇、森林、海洋三大区域的完整开箱即玩卡牌包。\",
  \"requires\": \"0.1.0\",
  \"entrypoints\": {\n    \"start_location\": \"tavern\"\n  },
  \"cards_root\": \"cards\"
}
"""

files['README.md'] = """# 新手王国卡牌包

开箱即玩卡牌包，包含城镇、森林与海洋三大区域。

包含内容：
- 18 张地点卡（城镇/森林/海洋）
- 16 张人物卡（城镇 NPC、森林与海洋首领）
- 30 张物品卡（城镇/森林/海洋各 10）
- 5 张势力卡、6 张系统卡、13 张任务卡
- Overlay 初始化主角属性与好感度
"""

files['cards/locations/tavern.md'] = """---
id: tavern
type: location
tags: [城镇, 社交, 酒馆]
---
温暖的酒馆，传闻与委托在此流转。
"""
files['cards/locations/lord_manor.md'] = """---
id: lord_manor
type: location
tags: [城镇, 城主府]
---
城主府高踞城中，秩序森严。
"""
files['cards/locations/adventurers_guild.md'] = """---
id: adventurers_guild
type: location
tags: [城镇, 工会]
---
冒险者登记、休整与接取任务的大厅。
"""
files['cards/locations/blacksmith_shop.md'] = """---
id: blacksmith_shop
type: location
tags: [城镇, 锻造]
---
炽热的炉火里传来铁锤声。
"""
files['cards/locations/tailor_shop.md'] = """---
id: tailor_shop
type: location
tags: [城镇, 服装]
---
出售斗篷、制服与旅装的店铺。
"""
files['cards/locations/apothecary.md'] = """---
id: apothecary
type: location
tags: [城镇, 医药]
---
药草与药剂的香气弥漫。
"""
files['cards/locations/residential_district.md'] = """---
id: residential_district
type: location
tags: [城镇, 居民区]
---
窄巷与低矮房屋，居民安居之地。
"""
files['cards/locations/guard_barracks.md'] = """---
id: guard_barracks
type: location
tags: [城镇, 护卫队]
---
护卫队的训练场与军械库。
"""
files['cards/locations/forest_gate.md'] = """---
id: forest_gate
type: location
tags: [森林, 边境]
---
进入森林前的最后检查点。
"""
files['cards/locations/woodland_trail.md'] = """---
id: woodland_trail
type: location
tags: [森林, 小径]
---
树影下的小径，脚印与低语交织。
"""
files['cards/locations/ancient_tree_altar.md'] = """---
id: ancient_tree_altar
type: location
tags: [森林, 圣地]
---
巨大的古树与沉默的祭坛。
"""
files['cards/locations/witch_cabin.md'] = """---
id: witch_cabin
type: location
tags: [森林, 女巫]
---
女巫的小屋，四周种满草药。
"""
files['cards/locations/swamp_edge.md'] = """---
id: swamp_edge
type: location
tags: [森林, 沼泽]
---
湿冷的沼泽边缘，雾气缭绕。
"""
files['cards/locations/dragon_border.md'] = """---
id: dragon_border
type: location
tags: [森林, 危险]
---
焦黑的树干与巨爪痕迹，提示巨龙领地。
"""
files['cards/locations/port_docks.md'] = """---
id: port_docks
type: location
tags: [海洋, 港口, 城镇]
---
港口码头，船只往来，消息与货物交汇。
"""
files['cards/locations/nearshore_isle.md'] = """---
id: nearshore_isle
type: location
tags: [海洋, 岛屿]
---
近海小岛，有隐蔽海湾与浅滩礁群。
"""
files['cards/locations/storm_belt.md'] = """---
id: storm_belt
type: location
tags: [海洋, 危险]
---
风暴海域，雷云与狂浪常年不散。
"""
files['cards/locations/deep_sea_isle.md'] = """---
id: deep_sea_isle
type: location
tags: [海洋, 传说]
---
深海孤岛，武器大师隐居之所。
"""

files['cards/characters/lord_alric.md'] = """---
id: lord_alric
type: character
tags: [城镇, 城主府, NPC]
initial_relations:
  - subject_id: lord_alric
    relation: at
    object_id: lord_manor
hooks:
  - "好感度30+：开放城中档案。"
  - "好感度60+：特殊委托。"
---
城主阿尔里克重视秩序与责任。
"""
files['cards/characters/guard_captain_lyra.md'] = """---
id: guard_captain_lyra
type: character
tags: [城镇, 护卫队, NPC]
initial_relations:
  - subject_id: guard_captain_lyra
    relation: at
    object_id: guard_barracks
hooks:
  - "好感度20+：护卫队训练许可。"
  - "好感度50+：护卫队装备折扣。"
---
护卫队队长莉拉严谨而可靠。
"""
files['cards/characters/guild_master_bram.md'] = """---
id: guild_master_bram
type: character
tags: [城镇, 工会, NPC]
initial_relations:
  - subject_id: guild_master_bram
    relation: at
    object_id: adventurers_guild
hooks:
  - "好感度20+：开放B级任务。"
  - "好感度60+：稀有合同与导师指点。"
---
工会会长布拉姆欣赏有潜力的新人。
"""
files['cards/characters/blacksmith_hugo.md'] = """---
id: blacksmith_hugo
type: character
tags: [城镇, 商人, NPC]
initial_relations:
  - subject_id: blacksmith_hugo
    relation: at
    object_id: blacksmith_shop
hooks:
  - "好感度20+：维修小折扣。"
  - "好感度50+：解锁定制升级。"
---
铁匠雨果崇尚好钢与实干。
"""
files['cards/characters/tavern_keeper_mira.md'] = """---
id: tavern_keeper_mira
type: character
tags: [城镇, 商人, NPC]
initial_relations:
  - subject_id: tavern_keeper_mira
    relation: at
    object_id: tavern
hooks:
  - "好感度20+：每日免费情报。"
  - "好感度50+：引荐隐秘联系人。"
---
酒馆老板米拉掌握城中大小消息。
"""
files['cards/characters/apothecary_selene.md'] = """---
id: apothecary_selene
type: character
tags: [城镇, 商人, NPC]
initial_relations:
  - subject_id: apothecary_selene
    relation: at
    object_id: apothecary
hooks:
  - "好感度20+：赠送基础药剂。"
  - "好感度50+：解锁高级配方。"
---
药师赛琳专注草药与疗愈。
"""
files['cards/characters/tailor_ines.md'] = """---
id: tailor_ines
type: character
tags: [城镇, 商人, NPC]
initial_relations:
  - subject_id: tailor_ines
    relation: at
    object_id: tailor_shop
hooks: []
---
裁缝伊妮丝擅长制作旅行服与制服。
"""
files['cards/characters/guard_elite_roland.md'] = """---
id: guard_elite_roland
type: character
tags: [城镇, 护卫队, NPC]
initial_relations:
  - subject_id: guard_elite_roland
    relation: at
    object_id: guard_barracks
hooks: []
---
护卫队精英罗兰沉稳强悍。
"""
files['cards/characters/guild_adventurer_kai.md'] = """---
id: guild_adventurer_kai
type: character
tags: [城镇, 工会, NPC]
initial_relations:
  - subject_id: guild_adventurer_kai
    relation: at
    object_id: adventurers_guild
hooks: []
---
冒险者凯热爱高风险的探索。
"""
files['cards/characters/witch_elowen.md'] = """---
id: witch_elowen
type: character
tags: [森林, 女巫, NPC]
initial_relations:
  - subject_id: witch_elowen
    relation: at
    object_id: witch_cabin
hooks:
  - "好感度20+：基础魔药。"
  - "好感度60+：稀有酿剂与解除诅咒。"
---
女巫艾洛温研究森林的古老魔法。
"""
files['cards/characters/forest_dragon_thorne.md'] = """---
id: forest_dragon_thorne
type: character
tags: [森林, 巨龙, 首领]
initial_relations:
  - subject_id: forest_dragon_thorne
    relation: at
    object_id: dragon_border
hooks: []
---
森林巨龙索恩以烈火统治森林。
"""
files['cards/characters/wolf_alpha_garruk.md'] = """---
id: wolf_alpha_garruk
type: character
tags: [森林, 妖兽, 首领]
initial_relations:
  - subject_id: wolf_alpha_garruk
    relation: at
    object_id: woodland_trail
hooks: []
---
狼王加鲁克守护狩猎领地。
"""
files['cards/characters/spider_matriarch_nyra.md'] = """---
id: spider_matriarch_nyra
type: character
tags: [森林, 妖兽, 首领]
initial_relations:
  - subject_id: spider_matriarch_nyra
    relation: at
    object_id: swamp_edge
hooks: []
---
蛛母妮娅在沼泽边缘织起密网。
"""
files['cards/characters/weapon_master_kael.md'] = """---
id: weapon_master_kael
type: character
tags: [海洋, 大师, NPC]
initial_relations:
  - subject_id: weapon_master_kael
    relation: at
    object_id: deep_sea_isle
hooks:
  - "好感度20+：武器训练许可。"
  - "好感度60+：传奇锻造。"
---
武器大师凯尔铸造绝世兵器。
"""
files['cards/characters/sea_dragon_morwen.md'] = """---
id: sea_dragon_morwen
type: character
tags: [海洋, 巨龙, 首领]
initial_relations:
  - subject_id: sea_dragon_morwen
    relation: at
    object_id: storm_belt
hooks: []
---
海洋巨龙莫文掌控深海与风暴。
"""
files['cards/characters/pirate_lord_vega.md'] = """---
id: pirate_lord_vega
type: character
tags: [海洋, 海盗, 首领]
initial_relations:
  - subject_id: pirate_lord_vega
    relation: at
    object_id: nearshore_isle
hooks: []
---
海盗头目维加以强者为尊。
"""

files['cards/items/iron_sword.md'] = """---
id: iron_sword
type: item
tags: [城镇, 武器, 常见]
---
结实的铁剑，适合新手与护卫。
"""
files['cards/items/leather_armor.md'] = """---
id: leather_armor
type: item
tags: [城镇, 护甲, 常见]
---
轻便皮甲，防护与灵活兼顾。
"""
files['cards/items/healing_potion.md'] = """---
id: healing_potion
type: item
tags: [城镇, 消耗品]
---
基础治疗药剂，缓解轻伤。
"""
files['cards/items/guard_badge.md'] = """---
id: guard_badge
type: item
tags: [城镇, 关键道具]
---
护卫队徽章，象征执勤权限。
"""
files['cards/items/guild_token.md'] = """---
id: guild_token
type: item
tags: [城镇, 关键道具]
---
冒险者工会的身份徽记。
"""
files['cards/items/travel_rations.md'] = """---
id: travel_rations
type: item
tags: [城镇, 消耗品]
---
远行干粮，适合巡逻与探索。
"""
files['cards/items/city_map.md'] = """---
id: city_map
type: item
tags: [城镇, 工具]
---
城镇与周边地形的详细地图。
"""
files['cards/items/lockpick_set.md'] = """---
id: lockpick_set
type: item
tags: [城镇, 工具]
---
开锁工具，可应付简单锁具。
"""
files['cards/items/linen_cloak.md'] = """---
id: linen_cloak
type: item
tags: [城镇, 装备]
---
轻薄披风，适合旅行与微寒。
"""
files['cards/items/copper_coins.md'] = """---
id: copper_coins
type: item
tags: [城镇, 货币]
---
一小袋铜币，足够日常花销。
"""
files['cards/items/moonleaf_herb.md'] = """---
id: moonleaf_herb
type: item
tags: [森林, 草药]
---
银月草，常用于安神药剂。
"""
files['cards/items/thornroot.md'] = """---
id: thornroot
type: item
tags: [森林, 草药]
---
荆根，常见于解毒配方。
"""
files['cards/items/crystal_moss.md'] = """---
id: crystal_moss
type: item
tags: [森林, 材料]
---
水晶苔，微光闪烁并蕴含魔力。
"""
files['cards/items/wolf_fang.md'] = """---
id: wolf_fang
type: item
tags: [森林, 材料]
---
狼牙，锋利且可作饰件。
"""
files['cards/items/spider_silk.md'] = """---
id: spider_silk
type: item
tags: [森林, 材料]
---
坚韧蛛丝，可织轻甲或绳索。
"""
files['cards/items/boar_tusk.md'] = """---
id: boar_tusk
type: item
tags: [森林, 材料]
---
野猪獠牙，质硬可作材料。
"""
files['cards/items/witch_essence.md'] = """---
id: witch_essence
type: item
tags: [森林, 炼金]
---
女巫精华，用于高级魔药。
"""
files['cards/items/forest_dragon_scale.md'] = """---
id: forest_dragon_scale
type: item
tags: [森林, 稀有]
---
森林巨龙鳞片，能强化护甲。
"""
files['cards/items/glowing_mushroom.md'] = """---
id: glowing_mushroom
type: item
tags: [森林, 草药]
---
夜间发光的蘑菇，可制照明药剂。
"""
files['cards/items/ancient_seed.md'] = """---
id: ancient_seed
type: item
tags: [森林, 遗物]
---
古树之种，触手温热。
"""
files['cards/items/coral_shard.md'] = """---
id: coral_shard
type: item
tags: [海洋, 材料]
---
珊瑚碎片，可用于锻造与饰品。
"""
files['cards/items/salt_pearl.md'] = """---
id: salt_pearl
type: item
tags: [海洋, 稀有]
---
盐海珍珠，商人争相收购。
"""
files['cards/items/sea_serpent_scale.md'] = """---
id: sea_serpent_scale
type: item
tags: [海洋, 材料]
---
海蛇鳞片，耐腐蚀且坚韧。
"""
files['cards/items/barnacle_ore.md'] = """---
id: barnacle_ore
type: item
tags: [海洋, 材料]
---
藤壶矿石，适合锻造与合金。
"""
files['cards/items/stormglass.md'] = """---
id: stormglass
type: item
tags: [海洋, 稀有]
---
风暴玻璃，闪电之力凝结而成。
"""
files['cards/items/tidewood_plank.md'] = """---
id: tidewood_plank
type: item
tags: [海洋, 材料]
---
潮木木板，常用于船体修补。
"""
files['cards/items/anchor_chain_link.md'] = """---
id: anchor_chain_link
type: item
tags: [海洋, 材料]
---
锚链链节，沉重而坚固。
"""
files['cards/items/pirate_medallion.md'] = """---
id: pirate_medallion
type: item
tags: [海洋, 关键道具]
---
海盗徽章，象征黑水交易。
"""
files['cards/items/island_relic.md'] = """---
id: island_relic
type: item
tags: [海洋, 遗物]
---
岛屿遗物，刻有未知符文。
"""
files['cards/items/abyssal_iron.md'] = """---
id: abyssal_iron
type: item
tags: [海洋, 稀有]
---
深渊铁，沉重且极适合锻造。
"""

files['cards/factions/faction_lordship.md'] = """---
id: faction_lordship
type: faction
tags: [势力, 城镇]
---
城主府统领城镇与护卫队。
优势：行政权限、城市资源、政治支持。
"""
files['cards/factions/faction_city_guard.md'] = """---
id: faction_city_guard
type: faction
tags: [势力, 城镇]
---
城市护卫队负责治安与防御。
优势：巡逻薪资、训练资源、装备渠道。
"""
files['cards/factions/faction_adventurers_guild.md'] = """---
id: faction_adventurers_guild
type: faction
tags: [势力, 城镇]
---
冒险者工会组织探索与委托。
优势：任务权限、冒险等级、共享情报。
"""
files['cards/factions/faction_forest.md'] = """---
id: faction_forest
type: faction
tags: [势力, 森林]
---
森林势力由森林巨龙与妖兽统治。
优势：稀有材料、原始魔力与隐秘路径。
"""
files['cards/factions/faction_sea.md'] = """---
id: faction_sea
type: faction
tags: [势力, 海洋]
---
海洋势力由海洋巨龙与岛屿势力掌控。
优势：航线与海域遗物资源。
"""

files['cards/systems/system_affinity.md'] = """---
id: system_affinity
type: system
tags: [系统]
---
好感度记录在玩家属性中：affinity_<npc_id>（0-100）。
通过任务、赠礼、关键选择提升。阈值解锁折扣、情报或特殊物品。
"""
files['cards/systems/system_inventory.md'] = """---
id: system_inventory
type: system
tags: [系统]
---
物品栏使用关系：player has <item_id>。
消耗品可被移除，装备可在叙事中提供加成。
"""
files['cards/systems/system_attributes.md'] = """---
id: system_attributes
type: system
tags: [系统]
---
基础属性：力量、敏捷、体质、智力、意志、魅力。
勇者天赋成长使用 hero_talent_level 与 hero_talent_node。
"""
files['cards/systems/system_quests.md'] = """---
id: system_quests
type: system
tags: [系统]
---
任务卡写明触发条件、目标、奖励与后续钩子。
完成任务可更新属性、物品与好感度。
"""
files['cards/systems/system_combat.md'] = """---
id: system_combat
type: system
tags: [系统]
---
战斗结果取决于属性、装备与叙事位置。
力量与体质偏近战，敏捷用于闪避，智力影响战术判断。
"""
files['cards/systems/system_exploration.md'] = """---
id: system_exploration
type: system
tags: [系统]
---
探索可发现资源与任务。森林与海洋风险更高。
魅力用于交涉，智力用于解谜与线索推理。
"""

files['cards/quests/quest_join_guard.md'] = """---
id: quest_join_guard
type: quest
tags: [任务, 城镇, 护卫队]
---
触发：在 guard_barracks 与护卫队队长对话。
目标：完成基础训练并宣誓加入护卫队。
奖励：guard_badge，SetAttr(player.affiliation, city_guard)，好感度+10（guard_captain_lyra）。
后续：quest_patrol_residential。
"""
files['cards/quests/quest_join_guild.md'] = """---
id: quest_join_guild
type: quest
tags: [任务, 城镇, 工会]
---
触发：在 adventurers_guild 与工会会长对话。
目标：登记并完成简单委托。
奖励：guild_token，SetAttr(player.affiliation, adventurers_guild)，好感度+10（guild_master_bram）。
后续：quest_tavern_rumors。
"""
files['cards/quests/quest_patrol_residential.md'] = """---
id: quest_patrol_residential
type: quest
tags: [任务, 城镇, 护卫队]
---
触发：加入护卫队后。
目标：巡逻 residential_district 并报告异常。
奖励：copper_coins，好感度+5（guard_captain_lyra）。
后续：quest_blacksmith_delivery。
"""
files['cards/quests/quest_tavern_rumors.md'] = """---
id: quest_tavern_rumors
type: quest
tags: [任务, 城镇]
---
触发：加入工会后。
目标：在酒馆收集三条传闻。
奖励：city_map，好感度+5（tavern_keeper_mira）。
后续：quest_apothecary_collect。
"""
files['cards/quests/quest_blacksmith_delivery.md'] = """---
id: quest_blacksmith_delivery
type: quest
tags: [任务, 城镇]
---
触发：与铁匠雨果对话。
目标：交付 barnacle_ore 或 forest_dragon_scale。
奖励：装备强化，好感度+10（blacksmith_hugo）。
后续：quest_drive_wolves。
"""
files['cards/quests/quest_apothecary_collect.md'] = """---
id: quest_apothecary_collect
type: quest
tags: [任务, 城镇, 森林]
---
触发：与药师赛琳对话。
目标：从森林采集 moonleaf_herb 与 thornroot。
奖励：healing_potion x2，好感度+10（apothecary_selene）。
后续：quest_forest_herbs。
"""
files['cards/quests/quest_forest_herbs.md'] = """---
id: quest_forest_herbs
type: quest
tags: [任务, 森林]
---
触发：获得 forest_gate 的探索许可。
目标：收集 glowing_mushroom 与 crystal_moss。
奖励：SetAttr(player.intellect, +1)，好感度+5（witch_elowen）。
后续：quest_meet_witch。
"""
files['cards/quests/quest_drive_wolves.md'] = """---
id: quest_drive_wolves
type: quest
tags: [任务, 森林]
---
触发：巡逻报告或工会请求。
目标：击退 wolf_alpha_garruk 或驱逐狼群。
奖励：wolf_fang，SetAttr(player.strength, +1)。
后续：quest_altar_investigation。
"""
files['cards/quests/quest_meet_witch.md'] = """---
id: quest_meet_witch
type: quest
tags: [任务, 森林]
---
触发：携带 witch_essence 或稀有草药。
目标：在 witch_cabin 会见女巫并请求酿剂。
奖励：witch_essence 配方，好感度+10（witch_elowen）。
后续：quest_altar_investigation。
"""
files['cards/quests/quest_altar_investigation.md'] = """---
id: quest_altar_investigation
type: quest
tags: [任务, 森林]
---
触发：任一森林探索线。
目标：调查 ancient_tree_altar 并带回 ancient_seed。
奖励：SetAttr(player.willpower, +1)，hero_talent_node = awakening_2。
后续：quest_sea_permit。
"""
files['cards/quests/quest_sea_permit.md'] = """---
id: quest_sea_permit
type: quest
tags: [任务, 海洋, 城镇]
---
触发：与城主或护卫队队长对话。
目标：在 port_docks 取得出海许可。
奖励：SetAttr(player.affiliation, sea_explorer)，好感度+5（lord_alric）。
后续：quest_isle_scout。
"""
files['cards/quests/quest_isle_scout.md'] = """---
id: quest_isle_scout
type: quest
tags: [任务, 海洋]
---
触发：取得出海许可。
目标：侦察 nearshore_isle 并带回 island_relic。
奖励：stormglass，SetAttr(player.agility, +1)。
后续：quest_find_weapon_master。
"""
files['cards/quests/quest_find_weapon_master.md'] = """---
id: quest_find_weapon_master
type: quest
tags: [任务, 海洋]
---
触发：收集稀有海洋材料。
目标：抵达 deep_sea_isle 会见 weapon_master_kael。
奖励：开放传奇锻造，好感度+10（weapon_master_kael）。
后续：无。
"""

files['cards/_overlay/init_state.md'] = """---
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
"""

for rel, content in files.items():
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content.strip() + '\n', encoding='utf-8')

print(f'Wrote {len(files)} files under {root}')
