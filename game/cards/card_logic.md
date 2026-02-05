---
relations:
  at:
    subject_types: [character]
    object_types: [location]
    max_per_subject: 1
  has:
    subject_types: [character]
    object_types: [item]
    max_per_subject: 0
  knows:
    subject_types: [character]
    object_types: [character]
    max_per_subject: 0

derived_rules:
  - when:
      edges:
        - subject_id: player
          relation: has
          object_id: rusty_key
        - subject_id: player
          relation: at
          object_id: tavern
    allow_action: open_backdoor
---

Global card logic and constraints.
