---
id: 9c6b3c59-56ab-59fd-8c82-b9df412ad55c
key: a2_alder
title: Brother Alder's Cell
summary: The cell is a monk's room, bare and warm, with a tiny window and a rushlight.
location: sunken_abbey
characters:
- brother_alder
variants:
- id: 3504308e-b098-55d6-85ca-19b0faf6c727
  label: Default
choices:
- id: 430531b6-7724-5937-8b62-d5243c07fbcb
  label: Ask him for the seal
  condition: flag(ALDER_TRUST)
  outcomes:
  - key: default
    target: a2_seal
- id: 2df43959-a29c-50ac-89d7-2775ab77c3ff
  label: Plead for the seal without his trust
  kind: test
  condition: not flag(ALDER_TRUST)
  test: luck
  outcomes:
  - key: success
    target: a2_seal
  - key: failure
    target: a2_alder_refuse
- id: 66884556-b8c7-59fc-929c-706afe7eea4a
  label: Leave him to his prayers
  outcomes:
  - key: default
    target: a2_cloister
layout:
  x: 4800.0
  y: 340.0
prose:
- variant: 3504308e-b098-55d6-85ca-19b0faf6c727
  text: |-
    The cell is a monk's room, bare and warm, with a tiny window and a rushlight. Brother Alder is here before you: the abbot of the Sunken Abbey, thin and pewter-eyed, kneeling at a low bench. It makes no sense, and he does not seem to think it does.

    "I told you I keep the bell," he says, without turning. "I did not say that I kept it in Marrowmere. We are not entirely where we seem to be, in this place."

    On the bench lies a bronze seal on a ribbon, carved with a bell.
  summary: The cell is a monk's room, bare and warm, with a tiny window and a rushlight.
  inputs_hash: 4f517d527236334a0452fb53d37a9f46802d79cd471afbe6e8c64d9880451347
---
The seal comes to those who earned Alder's trust in town, or the lucky.
