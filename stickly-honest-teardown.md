# Stickly Honest: teardown and our own version

Source: a phone screenshot of the channel's Videos tab (29 Oct 2026), showing 26 of its 60 videos. I couldn't watch any video, so everything about narration and editing is inferred from thumbnails, titles and lengths.

## 1. What the channel is

- **Tagline:** "the world's bitter truths, drawn in ink." 4.28K subscribers, 60 videos.
- **Audience:** Bangladesh and Bengal. Titles are in English, often followed by Bangla text.
- **Pace:** the 26 visible videos span about one month, so roughly 6 uploads a week. That is pipeline speed, not hand animation.

## 2. Look

- **Style:** pen-and-ink crosshatching on cream paper, black ink plus **one red accent** (red-and-white gamcha checks, red walls, red text). Very consistent across every thumbnail.
- **Characters:** caricatures, not stick figures. A recurring everyman in a lungi and gamcha, desi uncles, aunties, students. Big heads, expressive faces.
- **Backgrounds:** dense and detailed: Dhaka streets, houses, rickshaws, rain, crowds.
- **Thumbnails:** a 2–4 word question in bold caps (black and red) top-left, one striking image, split-screen "vs" layouts.
- **How it's probably made:** the consistency and level of detail point to an AI image generator locked to one style prompt and character set, then still images with pans and zooms, narration and music. A 7–11 minute video would need about 40–70 illustrations.

## 3. What performs (from the view counts)

| Format | Examples | Views | Length |
|---|---|---|---|
| **"What if" alternate history, often "in 2026"** | British Never Came 110K · Bengal Won Palashi 92K · Mughals in 2026 35K · Bengal Never Divided 18K · Pakistan Never Split 8.4K | **Best** | 7–9 min |
| **"Why do we…" culture explainer** | Parents Pay Twice for Same Lesson 74K · Why Bangalis Eat Like This 28K · Orange Beards 6.1K · Surnames 3.3K (1 day old) | Strong | 7–13 min |
| **Then / today / future** | Bangali vs Rain: 1,000 years ago, today, 2050 · 1.6K | Middling | 8 min |
| **Short relatable desi comedy** | Wedding vs Marriage, "When are you getting married?", Betting app, Mosquito, Road crossing, BCS | **263–2.2K** | 2–4 min |
| **Generic global topics** | President becomes a monk 1.2K · No coffee or tea 587 | **Flopped** | 8 min |

**Takeaways**
1. The channel moved from 3-minute comedy (low views) to **7–11 minute explainers**, and views jumped 10–100×. Long form is what works here.
2. **Identity plus history wins.** "Our people, our history, what if" beats universal topics. The two global topics flopped even with the same art style.
3. **Questions as titles**, with a specific hook such as "in 2026" or "paid twice".
4. Being small (4K subs) with 100K-view videos means the algorithm is pushing the format, not the brand.

## 4. Our version: same proven skeleton, a different body

### Market (pick one)
- **A. India, in English (recommended to test first).** Much bigger audience than Bengal, the bros know the culture, and the identity hook still works. Kokoro's English voices are strong, and English India content earns more than Hindi.
- **B. Global English, US-heavy.** Highest RPM, but the generic-topic flops above are a warning: we would still need a strong identity anchor ("Why Americans…", "What if Rome never fell").

### Look (deliberately not theirs)
| | Stickly Honest | Ours |
|---|---|---|
| Medium | Static AI ink illustrations | **Animated** characters that move, plus animated maps, timelines and charts |
| Paper / ink | Cream paper, black + red | **Notebook look:** ruled paper, blue ballpoint ink, yellow highlighter |
| Host | Unnamed everyman | **A named recurring narrator character**, who appears in every episode and on thumbnails |
| Signature device | Split-screen "vs" | **A drawn timeline bar** at the top that fills chapter by chapter; maps that redraw themselves for "what if" |

### Pipeline (hybrid)
1. **Backgrounds:** AI-generated in one fixed notebook-doodle style prompt, made once and reused across episodes (street, village, palace, office, train, classroom, map table). Needs an image model: the Gemini image API, or Flux/SDXL on a GPU.
2. **Characters:** our code rig (`demo-short/stickman.py`), upgraded to the narrator design with outfits, drawn over the backgrounds so they actually move.
3. **Maps and data:** drawn in code (borders redrawing, arrows, counters, charts). This is where "what if" episodes come alive and static channels can't compete.
4. **Script:** an AI model writes the script and scene list, then **a human fact-checks** before rendering.
5. **Voice and assembly:** Kokoro, captions, music and SFX, as in the demo.

## 5. Episode ideas (India, English)

**What if (their best format)**
- What If India Had Never Been Colonised? (India in 2026)
- What If the Indus Valley Civilisation Never Collapsed?
- What If Chandragupta Maurya's Empire Never Broke Up?
- What If Mumbai Had Stayed Seven Islands?
- What If the Railways Never Came to India?

**Why do we… (culture explainers)**
- Why Do Indian Parents Pay for Tuition AND School?
- Why Is Every Indian Wedding Like a Small War?
- Why Do Indians Hang Lemon and Chillies on Doors?
- Why Does Every Indian Dad Love the Same Car?
- Why Is Chai Everywhere in India? (the honest history)

**Then / now / 2050**
- Indian Commute: 500 Years Ago, Today and 2050
- Indian Summer: How Did We Survive Before AC?

## 6. Risks specific to this format
- **Partition, India–Pakistan, religion and caste are high-risk.** Alternate-history takes on them can spark backlash, attract misinformation reports, and hurt monetization. Start with lower-temperature what-ifs (empires, inventions, cities). **Avoid surname-origin videos in India**: surnames map to caste.
- **Accuracy:** "what if" is speculation, but the "what actually happened" half must be correct. Fact-check every script before rendering.
- **Don't copy their look or titles.** Same skeleton (question title, "in 2026" hook, 7–10 minutes, identity angle), our own visuals, character and topics.
