---
id: 5da32acc-0608-54ae-bb1e-972d98af67d7
key: a1_bandit_deal
title: A Gentleman's Agreement
summary: Brandt listens, head tilted, and when you finish he laughs aloud.
location: greywood
characters:
- captain_brandt
on_enter:
- op: set_flag
  flag: BRANDT_ALLY
- op: give
  item: ration
  qty: 2
variants:
- id: fe73c194-e582-52f3-aad2-431d3af7b86c
  label: Default
choices:
- id: 87c07467-bec1-5aad-a99b-32e7198f89f8
  label: Continue toward the fen
  outcomes:
  - key: default
    target: a1_woods_exit
layout:
  x: 1920.0
  y: 170.0
prose:
- variant: fe73c194-e582-52f3-aad2-431d3af7b86c
  text: |-
    Brandt listens, head tilted, and when you finish he laughs aloud. "The reeve? Pay *me*? Gods. All right. If he'll pardon my men, I'll tell you what the road won't."

    He tells you where the fen's causeway begins, where the leeches nest, and which of the islands has a hag on it. He gives you two rations from his own pack and half a smile.

    "Tell Hale I kept the road safe," he says. "And that I'm owed."
  summary: Brandt listens, head tilted, and when you finish he laughs aloud.
  inputs_hash: e1a6ccf25b8fe234f48d0ae2daebeeb6fa2de2341ededb055f00f15cf9a6f5db
---
Peaceful route. BRANDT_ALLY is a codeword for the epilogue.
