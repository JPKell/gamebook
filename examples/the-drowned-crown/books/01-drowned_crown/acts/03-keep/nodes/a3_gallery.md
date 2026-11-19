---
id: ad338f6f-1ba7-564c-8afa-d34750346e48
key: a3_gallery
title: The Gallery of Portraits
summary: 'The gallery is a long room hung with painted portraits: kings and queens, in gold and crimson,
  each holding a bell.'
location: hollow_keep
characters:
- king_oswin
- lady_isolde
variants:
- id: 342ec37c-fb62-5e58-a6a9-8522cff378be
  label: Default
- id: 2223e3f3-b68e-5a6a-aa0d-8cbe9d4354ea
  label: Ghost-friend
  condition: flag(GHOST_FRIEND)
  priority: 10
choices:
- id: c0702af6-4108-5675-bb16-b99f8f9b7ad3
  label: Study the riddle door
  outcomes:
  - key: default
    target: a3_riddle_door
- id: cc6601e8-8b07-5d9e-9c61-1bc6aa42a3ab
  label: Climb to the throne room
  outcomes:
  - key: default
    target: a3_throne_stair
- id: 03240fa4-cce0-5617-9e41-cb9e8010866b
  label: Go back to the hall
  outcomes:
  - key: default
    target: a3_aldous_down
layout:
  x: 7680.0
  y: 170.0
prose:
- variant: 342ec37c-fb62-5e58-a6a9-8522cff378be
  text: |-
    The gallery is a long room hung with painted portraits: kings and queens, in gold and crimson, each holding a bell. The last portrait is of a young man with a worried, kind face and a circlet on his brow, and beside him a dark-eyed woman in a wedding dress. Isolde.

    At the end, a heavy door is carved with three interlocking rings, and over it, in gold: *WHAT IS THE CROWN'S TRUE NAME?* The tall doors to the throne room stand to the left, wide and guarded by nothing.
  summary: 'The gallery is a long room hung with painted portraits: kings and queens, in gold and crimson,
    each holding a bell.'
  inputs_hash: bb2cb5a8a4f22c8a463358ad569db4146f72b6102ecf6a20c715283bf17dca04
- variant: 2223e3f3-b68e-5a6a-aa0d-8cbe9d4354ea
  text: |-
    The gallery is a long room hung with painted portraits: kings and queens, each holding a bell. The last is of a young man with a worried, kind face, and beside him a dark-eyed woman in a wedding dress. You know her face. You have held her shard.

    Isolde's painted eyes follow you down the room, and you could almost swear her lips move. *The door,* she seems to say. *Say what he never would.*

    At the far end, a carved door asks its question in gold. The tall doors to the throne room stand open to the left.
  summary: 'The gallery is a long room hung with painted portraits: kings and queens, each holding a bell.'
  inputs_hash: 3c652a31934f51cd3daf19a830589da5ddb076c62d1033380a41e7b641743244
---
The gallery. Ghost-friends get a whispered hint at the answer.
