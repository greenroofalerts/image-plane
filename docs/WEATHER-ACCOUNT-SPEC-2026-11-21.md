# Roof weather account — upgrade spec (21 Nov 2026)

Lee, 21 Nov 2026: "evaluate the wording that ChatGPT did that was so good for reasoning model
interp of the weather context for that roof type that draws upon findings and next visit
recommendations, I was happy with it but welcome ideas on how to improve that part - maybe
going beyond image plane?"

Owner of the GRA code: the Codex GRA chat (12 Nov rule). This file is the spec only. It
changes no code.

Base text: Lee's own brief, `macminia:~/gra-work-records/handoffs/laptop-close-20261112/WEATHER-NARRATIVE-CORRECTION.md`.
Keep everything it already says. The ChatGPT original was not found on Mini A or the laptop
(it may be in ChatGPT's own history).

## 1. What runs today, and why it must change
The live roof page (`weatherAccount.js`) picks fixed sentences by plant type. Fixed sentences
cannot connect this month's weather to this roof's findings. The upgrade: a model writes from
an evidence pack, and a checker refuses any sentence the pack does not support.

## 2. The evidence pack (one per roof, per account)
Each item names its source. A missing item is written as missing, never guessed.

| Item | Source |
|---|---|
| Rain and temperature this month, against the normal for the month | GRA `postcode_weather_history` |
| Forecast and how far ahead it reaches | the forecast source in use; never past its horizon |
| Planting type | GRA `sites` planting field |
| Establishment (age since install) | `sites.date_installed` = the balance invoice date |
| Depth, shade, irrigation | GRA site fields |
| Last visit: findings and recommendations | the latest visit record (Lee's words first) |
| What was done (seeding, irrigation kit, feed) | invoice lines from the Xero mirror |
| What the photos show | image plane labels: bare areas (drought), bare areas (overwatering), moss encroachment, plant threats with confidence |

## 3. Rules per planting type (the model must apply them)
Written from the honesty boxes (`Dropbox/Collateral`, sedum and meadow only).
- Sedum: over-watering harms more than drought. Dry spells alone are not a reason to water.
- Meadow (shingle counts as meadow, Lee 21 Nov): seed set and cut timing decide the next visit.
- Riverbed and hay base: no written rules yet. The account says so instead of inventing them.

## 4. Fixed shape — four parts, every time
1. What happened (measured).
2. What is changing (forecast, within its horizon).
3. What it means for this roof (inferred, citing pack items).
4. What to do and when (a window and a reason: after seed set, before the dry spell, a spring feed).
Each sentence carries its kind: seen, measured, forecast or inferred.

## 5. The checker
Refuse the account when a sentence: names a number not in the pack; claims a forecast past the
horizon; gives generic advice not tied to this roof; or contradicts Lee's last-visit words.
A refused account shows nothing new; the previous approved account stays.

## 6. Golden set
Three contrasting roofs, written once and approved by Lee, become the standard each new
account is checked against. Suggested: a sedum roof with a drought finding, a meadow roof
near seed set, a young roof under 1 year.

## 7. Beyond the image plane — the biggest gain
What grows on a roof records its moisture history. Plant ID threats and bare-area labels from
the image plane feed part 3. This closes Lee's 9 July chain: plant ID, then conditions, then
weather match, then recommendation, then timing.
