# Season 1 trailer: what to record on the beta server

For Lorenzo or a builder, during the closed beta (about 25 Jan to 3 Feb). This turns the trailer brief
(`docs/relaunch/marketing/trailer.md`, PR #211) into takes you can tick off in two or three sessions. Once the files
exist, the trailer is cut to the same 100 BPM music and text cards as the teaser (`marketing/season1/teaser.py`).

## Before you press record

**Minecraft (Java, the recording player)**
- Video: GUI scale 3, FOV 75, render distance 16 or more, smooth lighting on, brightness 50 %, clouds fancy,
  particles all, view bobbing **off** for steady shots (on for the fight shots).
- Hide the HUD with **F1** for every scenery and establishing shot. Keep it on where the HUD is the point (hearts bar,
  coins, the shop menu).
- Chat: turn chat to "Hidden" except for shot 4 and shot 8, and only show real names of players who said yes.
- Never show **F3**, coordinates, the server IP in the menu, or a player list with real names nobody agreed to.
- Daytime, clear weather (`/time set 1000`, `/weather clear`) unless the shot says otherwise.
- Use a vanilla client. If you film with Replay Mod or a camera mod, make sure no modded UI is in frame: the trailer
  promises "no mods", so nothing should look modded.

**OBS (Windows or Mac)**
| Setting | Value |
| --- | --- |
| Canvas and output | 1920 x 1080 |
| Frame rate | 60 fps (the trailer is 30 fps; 60 gives clean slow motion on the heart steal) |
| Recording format | MKV (survives a crash), then File > Remux Recordings to MP4 |
| Encoder | NVIDIA NVENC H.264 or AMD/Apple hardware H.264; x264 if no GPU encoder |
| Rate control | CQP 16 (NVENC/AMD) or CRF 16 (x264), preset Quality; keyframe interval 1 s |
| Audio | Track 1 game audio only. No mic, no Discord, no music (the music is added in the edit) |
| Source | Game Capture (Windows) or Window Capture (Mac) of Minecraft, full screen 1920 x 1080 |
| Vertical | Optional: the free "Aitum Vertical" plugin records a 1080 x 1920 canvas at the same time. Otherwise I crop |

**Bedrock footage (the shot that sells crossplay)**
- Phone or tablet: the built-in screen recorder (iOS Control Centre, Android quick settings) at 1080p or higher.
  Turn on Do Not Disturb so no notifications appear. Landscape.
- Console: a capture card, or the console's own clip capture at 1080p 60.
- Windows Bedrock: Xbox Game Bar (Win + Alt + R) or OBS as above.

**Every take:** record 3 seconds before and after the action, and do each take twice. Name files by shot, for
example `05-auction-a.mkv`.

## The takes

Times are where each shot lands in the 45-second trailer. "Players" counts accounts in frame.

| # | Shot | Players | How to stage it | Get |
| --- | --- | --- | --- | --- |
| 1 | Not needed: the heart snatch opener is drawn (as in the teaser) | 0 | | |
| 2 | Dawn on the fresh world, players spawning together, empty hotbars | 4+ | `/time set 23000`, everyone `/spawn`, HUD on, slow pan across them | 8 s |
| 3a | Mining diamonds | 1 | Deep strip mine, torch lit, break 2 or 3 diamond ore close up, HUD off | 5 s |
| 3b | Crop farm harvest | 1 | Walk a full wheat or potato row breaking it, low camera | 5 s |
| 3c | Mob grinder output | 1 | Items pouring into a hopper chest | 4 s |
| 4 | The `/shop` menu selling a stack, balance going up | 1 | HUD and chat on, sell a full stack, show the balance message or scoreboard tick | 6 s |
| 5 | Auction house bid war | 2 | Two players bid on one item; the second outbids at the last second. Record both screens if you can | 8 s |
| 6 | A rich player counting chests in a big base, smug | 1 | Walk past a wall of full chests; open one stacked with gold or diamonds | 5 s |
| 7 | Stepping out of the safe zone, a shadow behind | 2 | Player A walks past the spawn border (show the leave-zone message), Player B steps out of cover behind | 5 s |
| 8 | The drop: fight, kill, the heart transfers, hearts bar grows | 2 | Pre-arranged PvP fight outside spawn; film from the winner's view with HUD on so the extra heart shows. Film a third-person angle too (second account spectating) | 10 s |
| 9 | Phone and PC in the same fight | 2 | Same fight, Bedrock player records on the phone at the same time. I sync them on the hit sound | 6 s each |
| 10 | Weekly event: supply drop lands, players race in | 4+ | Trigger the drop event, film from above, then from one runner | 8 s |
| 11 | Border closing, boss rising, final crowd fight | 6+ | Staged finale rehearsal: `/worldborder set` shrinking, boss spawned by staff, everyone fights | 10 s |
| 12 | Not needed: the end card is drawn | 0 | | |
| B1 | Bonus for TikTok: "POV: your friend on a phone just stole your heart" | 2 | Shot 9 from the Java player's side, losing the heart | 6 s |
| B2 | Bonus: the spawn and safe zone from the air | 0 | Fly a slow circle over spawn at sunset, HUD off | 10 s |

Where a shot is staged (all of them, in a closed beta), the YouTube description says so, as the old trailer did.

## Hand-off

Put the remuxed MP4s in a shared folder (or `/mnt/project-files/marketing/footage/` from the Claude Duet project)
and tell me. I'll cut a 45 s 16:9 trailer plus 30 s and 15 s vertical cut-downs.

## Edit notes (for me, or anyone cutting it)

- Music: `marketing/music.py`, 100 BPM, a bar every 2.4 s. Cut on the downbeat. Trailer: 19 bars = 45.6 s with the
  impact (CTA) on the end card and the lift (crash, doubled hats) on shot 8's heart steal.
- Text cards: the teaser's styles (Pixelify Sans in bone with an ink outline, gold plate for SEASON 1, heart red
  only for hearts and PvP). Times, dates and ports in Atkinson Bold, because Pixelify's 5 and 2 read badly.
- Opener and end card: reuse `teaser.py`'s heart snatch (first 2.4 s) and end card (last 4.8 s).
- Slow motion: only shot 8, 50 % from the 60 fps source, for the heart transfer.
- Vertical cut: crop 9:16 around the action, keep text inside x 60 to 940 and y 220 to 1500 (TikTok, Reels and
  Shorts buttons sit on the right and bottom).
- Colour: no grading beyond a small saturation lift; the game should look like the game.
- Exports: 1920 x 1080 30 fps H.264 CRF 18 with AAC 192k at -14 LUFS for YouTube and the site; 1080 x 1920 for
  TikTok, Shorts and Reels; a 1280 x 720 thumbnail from `kit.py thumb --bg frame.png`.
