# Faceless Video Resource Pack

Compiled 2026-10-27 for the Brogrammers group. Star counts and download numbers are what the GitHub / Hugging Face pages showed on that date.

## 0. TL;DR

**What you're building (from the chat):** an automated, faceless YouTube pipeline. Topic in, finished MP4 out, with as little manual work as possible. Abhishek already has a Rust + Kokoro stickman pipeline (`tdf-studio`) running offline. The open problems are *visual variety*, *script quality*, *render time*, and *not getting flagged by YouTube*.

**Main findings**

1. **The biggest risk is policy, not tech.** YouTube's July 2026 update names "generic or repetitive" content as a reason to lose monetization. That is almost certainly the "monotonous design" flag Abhishek hit. Fixing visual and story variety is the priority (section 7).
2. **Don't change the stack, fill the gaps.** Kokoro (136M downloads, Apache-2.0) is the safest TTS. The gaps are variety, script quality and Hindi.
3. **Remotion has a licensing catch.** Free only for for-profit teams of up to 3, and automated video generation may fall under a paid tier. Abhishek's Rust renderer avoids this. HyperFrames (Apache-2.0) is the other no-fee option (section 3).
4. **Steal designs from four repos** (section 2): `codex-stickman-pipeline` (resumable stages, budget guards), `stickman-animation-studio` (character bible, setting and pose library), `claude-faceless-shorts-creator` (Shorts structure, QA, SFX library), `youtube-shorts-factory` (how to adapt a viral video without copying).
5. **Script quality is the weak link.** Local 7B models gave "sub-level" scripts. The free API options all have catches (section 5).
6. **Language choice is a revenue decision.** Hindi CPM is roughly $0.5–0.75 against a global average of about $3, and English for US viewers pays several times more (section 7). Kokoro's best voices are English.
7. **Brain-rot / ragebait is the highest-risk idea.** It hits two of YouTube's three demonetization buckets (section 7).
8. **I couldn't open most of the links directly** (the three X posts, the YouTube channel, Tubelab, the ChatGPT share and the private repo are all blocked or private; the Skillry link I reached through its public GitHub repo). Section 1 lists what I need from you to fill those gaps.

I ran none of this code. The sandbox blocks Hugging Face and most hosts. "Proven" below means *the bros ran it*, *very widely adopted*, or *maintainers' docs say so*.

---

## 1. Links from the chat: what I could and couldn't open

| Link | Status | What I did instead / what I need |
|---|---|---|
| x.com/0xrux/status/2082157640767930842 | ❌ blocked | Not found via search either. **Paste the tweet text or a screenshot.** |
| x.com/flxrnc/status/2105311836190978392 | ❌ blocked | Piyush said "isme sab hai, Claude ko de do". **Paste the text.** |
| x.com/jiangjiangling/status/2114684810191126548 | ❌ blocked | Piyush said it's for making shorts. **Paste the text.** Related, unconfirmed: `ninestonelee/youtube-shorts-factory` and `jjjiwjet/ai-shorts-skill` (section 2). |
| skillry.dev/ai-videos/opus-5-5 | ❌ site blocked, ✅ repo read | It maps to the public repo `yihui-dev/awesome-opus5-5-videos` (MIT, 703 prompts). The **prompts are free on GitHub**. I couldn't see what the $19 on Skillry buys. |
| youtube.com/@sticklyhonest | ❌ blocked | Search found nothing on it. **Send its top 5 video titles, lengths and view counts.** |
| tubelab.net | ❌ blocked | Pricing and alternatives from reviews (section 6). |
| chatgpt.com/share/6ae036ad… | ❌ blocked | **Paste Abhishek's output** if it's worth keeping. |
| github.com/abhishek-admin/tdf-studio | ❌ private | Invite is pending for `piyusharma4`: accept at `github.com/abhishek-admin/tdf-studio/invitations`. This session can't see it either. |

Also found while chasing the X links: Tejas Rane's post "I had AI watch 418 viral AI videos and turned it into a free skill" (x.com/tejas3732/status/2114625483648491940). Its repo is covered in section 2.

---

## 2. Ready-made pipelines and skills (reference designs)

📘 = I read the README. Stars as shown on 2026-10-27.

### 2a. Stickman / explainer pipelines (closest to what you're building)

| Repo | What it is | Stack | Worth stealing | Caveat |
|---|---|---|---|---|
| [CatbearLang/codex-stickman-pipeline](https://github.com/CatbearLang/codex-stickman-pipeline) 📘 MIT | Topic → narrated 1080p stickman explainer | LLM → Edge TTS / ElevenLabs → faster-whisper alignment → AI stills (~1 per 12 s) → FFmpeg (Ken Burns, crossfades, ducked music, −14 LUFS) | Idempotent stages (`script → voice → align → stills → compose → verify`), content-hash image cache, **budget guards and pre-spend quality gates**, resumable jobs, offline test suite | Stills + camera moves only, "not rigged animation" |
| [miang20/stickman-animation-studio](https://github.com/miang20/stickman-animation-studio) 📘 | Free-first, code-drawn stickman episodes | Pillow, NumPy, FFmpeg, Kokoro; 24 fps | **Episode JSON with a character bible** (stable IDs, outfits), 10 settings, pose library (walk, run, panic, celebrate…), explicit `motion` per scene | 0 stars, no license stated. Variation comes only from the script, which is exactly the monotony risk |
| [sg9215/stickman-video-skill](https://github.com/sg9215/stickman-video-skill) 📘 MIT | Agent skill for stickman videos | PIL → ffmpeg pipe, 1080p30 | 10-segment IK rig, 20+ actions, **camera vocabulary** (pan, zoom, roll, shake, impact punch, follow cam), 11 environments | 1 star, unproven |
| [saiedpod-bot/Stickman-Studio](https://github.com/saiedpod-bot/Stickman-Studio) 📘 MIT | Script → YouTube | Gemini 2.5 Flash, Imagen, edge-tts, ffmpeg, Streamlit; optional Veo clips | Character reference image for scene consistency; OAuth YouTube uploader | README says "~$0.02/video" but its own rate card ($0.02 per Imagen image) means cost scales with image count |

### 2b. Shorts and faceless pipelines

| Repo | What it is | Worth stealing | Caveat |
|---|---|---|---|
| [gyoridavid/short-video-maker](https://github.com/gyoridavid/short-video-maker) 📘 MIT, 1.4k★ | **Remotion + Kokoro + Whisper.cpp captions + Pexels footage**, REST + MCP API, Docker, n8n-ready, CPU only | Closest open-source match to your stack. Captions and word timing done right | English only, stock footage only. A stock-clip montage is the "generic" pattern YouTube targets |
| [hassancs91/claude-faceless-shorts-creator](https://github.com/hassancs91/claude-faceless-shorts-creator) 📘 MIT, 283★ | Three tracks: code-only Remotion, AI-clip character, paper-collage | **Six-beat Shorts structure:** HOOK → SETUP → QUIZ → REVEAL → TWIST → seamless LOOP. Frame 0 doubles as thumbnail. Word-exact captions. **Library-first SFX** (catalogue and reuse). Phone-size frame QA. `brand.md` style contract | Uses ElevenLabs (paid) and fal.ai |
| [ninestonelee/youtube-shorts-factory](https://github.com/ninestonelee/youtube-shorts-factory) 📘 (Korean) | Reference Short → forensic analysis → **adapt ≥30%** → produce | Analysis axes: hook structure, narrative arc, emotion curve, open loops, payoff. Adaptation keeps the emotional structure and swaps characters, places, props and the twist. **Cost tiers by emotion:** climax = premium model (~$1.20/clip), mid = cheap (~$0.05), establishing = free Ken Burns | Works best with the separate `rfn-video-pipeline` tool; the repo is a Claude skill, not standalone |
| [jjjiwjet/ai-shorts-skill](https://github.com/jjjiwjet/ai-shorts-skill) 📘 | Remotion + Google Flow images + **Voicebox** TTS; pixel and comic themes | Shows **themed visual templates** (font, caption style, motion) as a variety lever | Korean-focused; uses the Claude-in-Chrome extension |
| [harry0703/MoneyPrinterTurbo](https://github.com/harry0703/MoneyPrinterTurbo) 📘 MIT, ~135k★ | Topic → LLM script → TTS → stock clips → subtitles | Supports many LLMs and TTS engines (Edge, Kokoro, Chatterbox, ElevenLabs…) | Stock-montage output. No Hindi mentioned |
| [haidrrrry/claude-remotion-skill](https://github.com/haidrrrry/claude-remotion-skill), [digitalsamba/claude-code-video-toolkit](https://github.com/digitalsamba/claude-code-video-toolkit) | Claude skills for Remotion video | Found via search, 📰 not read | Unverified |

### 2c. Skills and prompt libraries for Claude Code

| Resource | What it gives you | Notes |
|---|---|---|
| [remotion-dev/skills](https://github.com/remotion-dev/skills) 📘 | Official Remotion agent skills: best-practices, markup, captions, render, docs, multimedia… | `npx skills add remotion-dev/skills`. Works with Claude Code, Codex, Kimi Code, Cursor |
| [tejas3732/viral-video-playbook](https://github.com/tejas3732/viral-video-playbook) 📘 MIT | Skill distilled from 418 viral AI videos; includes `tools/analyze_video.py` (free Gemini key) to break down **your own reference videos** | `npx skills add tejas3732/viral-video-playbook`. Findings below |
| [yihui-dev/awesome-opus5-5-videos](https://github.com/yihui-dev/awesome-opus5-5-videos) 📘 MIT, ~11.7k★ | 703 prompts that make videos as code (Canvas, SVG, GSAP, Three.js, one HTML file) | No stickman entry. 16 "explainer" prompts and 58 motion-graphics prompts |
| [heygen-com/hyperframes](https://github.com/heygen-com/hyperframes) 📘 Apache-2.0, ~73k★ | HTML → MP4 framework with agent skills and ~450 ready blocks | Section 3 |

**What the 418-video analysis found** (Gemini-watched, so rank-order only; its scores run generous, median 9/10). These are *motion-graphics* videos, not narrated stickman, so use them for Shorts:
- 53% open with a visual surprise in the first 3 s. Typical length is about 30 s, with cuts on the beat around 120 BPM.
- Structure: hook → build → drop → showcase → end card. 46% have no call to action.
- Top complaint: text too fast to read (42%).
- Only 12% have voiceover (28% of explainers), so **voice-led videos are the less crowded lane**.
- Prompts that specified music, SFX, aspect ratio, fonts and motion style scored higher.

**Deterministic-frame technique** (from the `@0xKarmi` and `@BuildFastWithAI` prompts in the Opus repo). This is the same idea as Abhishek's Rust renderer:
- Every frame is a pure function of its frame number: `draw(f)`. No clocks, no randomness.
- Render in a headless engine, encode with ffmpeg, then run automated checks: a smoke test for defects, and a **seam check comparing frame 0 with the last frame** for loops.
- `@BuildFastWithAI`'s prompt used "Rust + SVG via **fframes** where every frame is a function". I couldn't find an `fframes` repo. A 2022 conference talk mentions an `fframes.studio` Rust project; 📰 unverified.

---

## 3. Rendering engines (and the render-time problem)

**Chat data points:** Rust pipeline, 1-min short in 9 min end to end (CPU laptop). 5.5-min stickman long-form in 54 min. An earlier long-form render inside Antigravity took 49 min on CPU (the engine wasn't named in the chat). Piyush has office GPUs available (see section 8 before using them).

| Engine | License | Notes |
|---|---|---|
| **Your Rust renderer** | yours | Already works and is offline. Component options: [resvg](https://github.com/linebender/resvg) (Apache/MIT, 4.2k★, static SVG → pixels, built on tiny-skia) plus an ffmpeg pipe. I found **no public benchmark** of Rust vs Remotion, so measure per-frame raster time and encode time separately |
| **Remotion** | Free for for-profit orgs up to 3 people. Larger teams or automated video products need a paid tier (📰 snippets: "Automators" about $0.01/render, $100/mo minimum, and a license change is planned for Remotion 5.0) | Verify at remotion.dev/docs/license before commercial use. Most agent skills target it |
| **HyperFrames** (HeyGen) | Apache-2.0, no per-render fees | HTML/GSAP/SVG/Lottie/Three.js, headless-Chrome frame seeking plus FFmpeg, deterministic output. Node 22+. Has a `remotion-to-hyperframes` skill. Same class of renderer as Remotion, so no speed claim |
| **Motion Canvas** | MIT, 19.5k★ | TypeScript generators; built for **explainer-style vector animation synced to voice-over**. Live editor. Maintenance not confirmed |
| **Revideo** | MIT, 4.1k★ | Motion Canvas fork with headless `renderVideo()` API, audio support, **parallel rendering across workers**. Maintenance not confirmed |
| `rusvid`, `aniy`, `svg-to-video` | various | Small Rust / SVG animation crates found via search. 📰 Last releases around 2022–2023 for rusvid. Treat as inspiration |

**Ideas to test for render time** (my suggestions, not verified here):
- Animate "on twos" at 12–15 fps, then duplicate frames up to 24/30 fps at encode.
- Cache static backgrounds per scene (miang20's repo does this).
- Split a video into scene chunks and render them in parallel across cores, then concat.
- Draft at 720p, final at 1080p (also miang20's advice).
- Try a hardware encoder if a GPU is available.

---

## 4. Voice (TTS), including Hindi

| Model | Evidence | License | Hindi | Notes |
|---|---|---|---|---|
| **[Kokoro-82M](https://huggingface.co/hexgrad/Kokoro-82M)** | ✅ Abhishek ran it. 📘 136M downloads, 7.3k likes | Apache-2.0 | 4 voices (2F, 2M) but the model card warns non-English is "absent or thin" | Best English voices: `af_heart` (grade A), `af_bella` (A−). **Chunk text to 100–200 tokens**: it is weak under ~20 tokens and rushes over ~400 |
| [kokoro-onnx](https://github.com/thewh1teagle/kokoro-onnx) | 📘 2.8k★ | MIT | Check VOICES.md | ~300 MB, ~80 MB quantized, near real-time on M1. Easy to call from Rust via ONNX |
| [Kokoros](https://github.com/lucasjinreal/Kokoros) (Rust) | 📘 833★ | Apache-2.0 | None | OpenAI-compatible server, word-level timestamps. Last dated update in the README is July 2025, so check activity |
| **[Chatterbox](https://github.com/resemble-ai/chatterbox)** | 📘 24M downloads | MIT | **Yes: Multilingual V3 (23+ languages) and a dedicated Hindi pack** | Clone from a ~10 s clip. Turbo 350M, Nano 110M (3× realtime on 8 CPU cores, English). **Every output carries an imperceptible Perth watermark** |
| **[Voicebox](https://github.com/jamiepine/voicebox)** | 📘 58.7k★ | MIT | Via Chatterbox Multilingual | Local studio with 8 engines (Kokoro, Chatterbox, Qwen3-TTS…), voice cloning, REST API on port 17493, **MCP server** for Claude Code. Linux has no prebuilt binary yet (build from source). Used by `ai-shorts-skill` |
| [Qwen3-TTS](https://huggingface.co/Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice) | 📘 1.9M downloads (1.7B CustomVoice) | Apache-2.0 | Not in the 0.6B Base card's language list; check the 1.7B card | 0.6B Base clones voices; 1.7B VoiceDesign designs them from a text description |
| [Indic Parler-TTS](https://huggingface.co/ai4bharat/indic-parler-tts) | 📘 | Apache-2.0, **gated** (accept terms on HF) | Yes, 22 Indic languages | 938M params, so slower |
| **Sarvam Bulbul v3** | 📰 | Paid API | Yes | Docs: ₹30 per 10k characters, ₹100 free credit for new users (one page says 1,000 credits; check your dashboard). A 5.5-min script is roughly 4.8k characters, **about ₹15** (my estimate). Piyush has a free API key |
| Edge TTS | 📘 used by 3 of the pipelines above | Unofficial Microsoft endpoint, no key | Hindi voices exist (from memory; verify) | Free and decent, but not an official API |
| Voxtral-4B-TTS | 📘 | **CC-BY-NC (non-commercial)** | Yes | Skip for a monetized channel |

**Unverified claim:** Anuj suggested "Cactus TTS". Cactus's README lists only speech-to-text models (Whisper, Parakeet) and LLMs; search found a Cactus speech-to-text model, no TTS. **Ask Anuj which model he meant.**

**Word-level timestamps** (for captions and for cutting scenes on spoken words): `faster-whisper` (CatbearLang, MoneyPrinterTurbo), `whisper.cpp` (short-video-maker), Edge word boundaries, or Kokoros' timestamp TSV. `@remotion/captions` handles display.

**Voice cloning:** your own voice or voices you have rights to. Cloning someone else's voice for a channel is a legal and ethical problem.

---

## 5. Scripts and LLMs

Local 7B was "sub-level". The same 2026 comparison pages disagree on numbers, so **check each dashboard**.

| Option | What the sources say | Catch |
|---|---|---|
| **OpenRouter `:free` models** ([OpenRouter's own comparison](https://openrouter.ai/blog/tutorials/free-llm-apis-compared/)) | 20 requests/min; 50 requests/day with no credits, 1,000/day after a $10 top-up | Some free models' providers train on prompts |
| **Groq free tier** | Open-weight models such as gpt-oss-120b; about 30 req/min, 1,000/day | Llama 3.3 70B and 3.1 8B were retired on 16 Aug 2026, so old tutorials break |
| **Cerebras** | Reported as having no permanent free tier since 16 Jul 2026 ($5 credit, needs a verified payment method) | Conflicting sources |
| **Gemini (AI Studio free tier)** | Flash models free within per-project limits | Free-tier content may be used to improve Google products. Abhishek's account was asked for a ₹1000 prepaid top-up |
| **Claude via OpenRouter / API** | Anuj's pick for scripts | Paid. Piyush mentioned Opus 5.5 office credits (see section 8) |

**Practical split:** pay for the best model on the *script and storyboard only* (a 5-min script is a few thousand tokens, so cents). Use free or local models for everything else (image prompts, metadata, QA).

**Piyush's channel-reverse-engineering prompt** (from the chat, reusable as is):

```
I want to start a faceless YouTube channel in the [niche] niche.
Here is a channel that is already winning: [paste channel name or a few
of their top video titles].

Break down WHY their videos work:
- the hook style in the first 10 seconds
- the average video length
- the pacing and script rhythm
- how the title and thumbnail are built
- the exact structure of the story from start to finish

Then write me a brand new video in that SAME shape, on this fresh topic:
[your topic]. Keep the structure that works, but the story, characters,
and details must be 100% original. Give me the full script, a title,
and a thumbnail idea.
```

Pair it with the `youtube-shorts-factory` axes (open loops, emotion curve, payoff design) and a real transcript (`youtube_transcript_api` or `yt-dlp`) rather than just titles.

---

## 6. Visual variety (fixing the "monotonous design" flag)

Methods found, cheapest first. Mix several inside one channel, as Anuj suggested.

1. **Character bible + setting library + pose library.** Stable character IDs, 10+ settings, named poses, explicit `motion` per scene (`stickman-animation-studio`). This is Abhishek's "render SVGs for different emotions and stitch them", already specified as JSON.
2. **Camera vocabulary.** Pan, zoom, roll, shake, impact punch, follow cam (`stickman-video-skill`). Cheap and changes the feel of every scene.
3. **Themed templates.** Different font, caption style and motion per series (`ai-shorts-skill` pixel vs comic). One channel, several visual "formats".
4. **Cost tiers by emotion.** Ken Burns still for establishing shots (free), cheap AI clip for action (~$0.05), premium only for the climax (~$1.20) (`youtube-shorts-factory`).
5. **AI stills with a character reference.** Generate a character sheet first, then reference it per scene. Nano Banana workflows describe front view first, then side and back by reference. 📰 Nothing specific to stick figures, so test whether simple line art holds identity.
6. **Open video models for hero shots**, if you have a GPU: Wan 2.2 (Apache-2.0; 8 GB with the 5B GGUF), HunyuanVideo 1.5 (14 GB), LTX-2.3 (native audio, 16 GB+ quantized). 📰 VRAM figures from vendor blogs.
7. **Library-first sound design** (`claude-faceless-shorts-creator`): catalogue SFX and music cues so audio improves over time and every video is not mixed from scratch.
8. **Structure variety:** rotate between formats (story, countdown, myth-busting, "what if"). Seamless-loop Shorts for the short format.

**Open-Higgsfield** (Anuj mentioned an "open-higgsfield repo"): [Anil-matcha/Open-Higgsfield-AI](https://github.com/Anil-matcha/Open-Higgsfield-AI) (MIT, 31.6k★) is a studio *front end*. Cloud generation runs through **Muapi.ai with an API key**, so it is not free or local. Local mode exists only in the desktop app (stable-diffusion.cpp for images, or your own Wan2GP install for video). It has no stickman feature. If Anuj meant a different repo, ask him for the link.

---

## 7. Channel strategy, niche research and YouTube policy

### 7a. YouTube policy (the real constraint)

📰 from TechCrunch coverage and explainers (I couldn't open YouTube's help page, so read [YouTube channel monetization policies](https://support.google.com/youtube/answer/1311392) yourself before committing):

- **July 2026 update:** non-monetizable content is split into three buckets: (1) **generic or repetitive** (cookie-cutter AI, CGI or template output, and tutorials copying what is already common), (2) **off-putting or distressing** content built to upset or manipulate viewers, (3) **AI personas on sensitive topics** (finance, legal, health).
- Enforcement is **per channel, on monetization**, not video removal. Too much of any bucket and the channel can't monetize.
- AI itself isn't the trigger. YouTube's own examples of OK AI use include editing scripts and visualizing a character the creator invented.
- Jan 2026 crackdown reportedly hit 16 AI-slop channels with 35M subscribers and 4.7B views combined (📰 one news site, treat as approximate).
- Piyush's note ("same skeleton, new body") matches the guidance: copy the *structure*, never the story or visuals.

**What this means for the plan**
- "10 YouTube channels × 10 strategies" multiplies channel-level risk. **Prove one channel first.**
- A fixed intro, outro, voice, background and animation set across every video is the "template" signature. Variety work in section 6 is monetization insurance.
- Brain-rot / ragebait (the "NPC is awake", "999999 aura" idea) hits buckets 1 and 2 directly, and Italian-brainrot characters are in an IP dispute ([NPR, Aug 2026](https://www.npr.org/2026/08/19/nx-s1-5867638/artificial-intelligence-brainrot-memes-copyright-spyder-tung-tung-sahur)). **Highest risk of the ideas discussed.**
- AI-persona "experts" on money or health content can't monetize. Avoid those niches with this format.

### 7b. Language and audience

Hindi CPM is roughly $0.5–0.75 against a global average of about $3 (📰 agency blogs, directional only). One source puts English content for US viewers at ₹650–₹3,300 per 1,000 views against ₹50–₹200 for India-targeted content. That supports Anuj's "America ka dalal bano", and Kokoro's strongest voices are English.

### 7c. Finding niches and outliers

| Tool | Price (📰, vendor-written comparisons, mid-2026) | Notes |
|---|---|---|
| TubeLab | $178.80/yr, credit-metered | Cheapest dedicated outlier tool; Piyush found it paid |
| 1of10 | Free tier: outlier search and 3 tracked channels | Best free starting point I found |
| vidIQ | Free plan, metered (150 searches) | |
| OutlierKit | from $29/mo | |
| Social Blade | Free stats | No outlier research |

**DIY free method (my suggestion):** YouTube Data API v3 `search` + `videos.list` to find videos whose views far exceed the channel's subscribers, then run them through the analysis prompt above and `analyze_video.py` (Gemini). Check that Hindi and English niches are not already saturated before building anything.

### 7d. Uploading

- Per Google's docs, `videos.insert` uploads from **unverified API projects created after 28 Jul 2020 are locked to private** until the project passes an audit. Plan to upload manually at first, or apply for the audit.
- Quota cost per upload is reported inconsistently (1, 100 or 1,600 units). Check your Cloud Console.
- Disclosure: sources say labelling AI content doesn't reduce reach or eligibility. Check the current "altered or synthetic content" rules for realistic content; obvious cartoons are a lower-risk case but verify.

---

## 8. Risks and things to decide

1. **Remotion licensing** (section 3). Three friends may fit the free tier today, but a monetized, automated pipeline may not. Keep the Rust renderer as the primary path or use HyperFrames.
2. **Employer resources.** The chat mentions office Opus credits and office GPUs for this project. Using an employer's compute or credits for a personal monetized side project can breach acceptable-use and IP-assignment terms. Check before running anything on them.
3. **Open-Higgsfield isn't free** (section 6), and Cactus TTS isn't confirmed (section 4).
4. **Music licensing.** Use YouTube Audio Library, CC0, or properly attributed CC-BY (for example Kevin MacLeod). Avoid unlicensed tracks to dodge Content ID claims.
5. **Fact accuracy.** Auto-generated explainers can state wrong facts. CatbearLang's README itself recommends human review before publishing.
6. **Cloning a channel.** Reuse structure, never visuals, characters or story beats. `sticklyhonest` has been studied for inspiration, but "clone the whole channel" (Anuj) should not mean copying it.
7. **Gemini free tier privacy:** fine for public scripts, not for anything private.

---

## 9. Suggested shortlist

**Adopt now (proven by you or by wide adoption)**
- Kokoro-82M for English voice, with sentence chunking. `kokoro-onnx` if you want it callable from Rust.
- Your Rust + SVG renderer, with the ideas in section 3 for speed.
- ffmpeg + faster-whisper / whisper.cpp for word timestamps.
- Pexels (free API) only as B-roll, never the whole video.

**Copy the design, not the code**
- CatbearLang: resumable idempotent stages, budget ledger, quality gates before spend.
- miang20: character bible and setting/pose library in JSON.
- hassancs91: six-beat structure, phone-size QA, SFX library.
- youtube-shorts-factory: structured adaptation (≥30% change) and emotion-based cost tiers.

**Try next, in this order**
1. Test Chatterbox Multilingual (Hindi) via Voicebox, and Sarvam, on one 60-second Hindi script to decide whether Hindi is worth it.
2. Run `viral-video-playbook` and `analyze_video.py` on 3 reference videos in your chosen niche.
3. Add 2–3 camera moves and 3 background themes to the renderer, then re-test whether videos feel distinct.
4. Benchmark one scene: Rust vs HyperFrames vs Remotion, measuring raster and encode time separately.
5. Hero shots with Wan 2.2 or LTX-2.3 *only* if a GPU is legitimately available.

**Parked / avoid**
- Brain-rot / ragebait formats.
- 10 channels at once.
- Voxtral-4B-TTS (non-commercial), and MoneyPrinterTurbo-style stock montages as the whole video.

---

## 10. What I need from you

1. Text or screenshots of the three X posts (section 1).
2. Top 5 videos of `@sticklyhonest`: titles, lengths, views.
3. Abhishek's ChatGPT share output, if useful.
4. Accept the `tdf-studio` invite so a future session can read the code (this session would also need the repo added).
5. Anuj: which "Cactus" TTS model, which "open-higgsfield" repo, and which "DeepSeek harness" skill rebuild he meant.
6. Decision: English/US-audience or Hindi first?

---

## Appendix: quick-start commands

```bash
# Official Remotion skills for Claude Code / Codex
npx skills add remotion-dev/skills

# Viral-video benchmarks and reference analysis
npx skills add tejas3732/viral-video-playbook
# or: /plugin marketplace add tejas3732/viral-video-playbook
#     /plugin install viral-video-playbook@viral-video-playbook

# HyperFrames (HTML → MP4)
claude plugin marketplace add heygen-com/hyperframes
npx hyperframes init my-video && npx hyperframes preview && npx hyperframes render

# Kokoro (Python)
pip install "kokoro>=0.9.4" soundfile   # also needs espeak-ng

# Chatterbox
pip install chatterbox-tts

# Short-video-maker (Remotion + Kokoro + Whisper.cpp + Pexels), Docker recommended
# see https://github.com/gyoridavid/short-video-maker for the image names

# Korean-style Shorts skill using Voicebox
git clone https://github.com/jjjiwjet/ai-shorts-skill ~/.claude/skills/remotion-flow-shorts
```

## Sources

Primary (READMEs / model cards read): [awesome-opus5-5-videos](https://github.com/yihui-dev/awesome-opus5-5-videos) · [viral-video-playbook](https://github.com/tejas3732/viral-video-playbook) · [claude-faceless-shorts-creator](https://github.com/hassancs91/claude-faceless-shorts-creator) · [youtube-shorts-factory](https://github.com/ninestonelee/youtube-shorts-factory) · [ai-shorts-skill](https://github.com/jjjiwjet/ai-shorts-skill) · [remotion-dev/skills](https://github.com/remotion-dev/skills) · [HyperFrames](https://github.com/heygen-com/hyperframes) · [Chatterbox](https://github.com/resemble-ai/chatterbox) · [Kokoro](https://github.com/hexgrad/kokoro) · [Kokoros](https://github.com/lucasjinreal/Kokoros) · [kokoro-onnx](https://github.com/thewh1teagle/kokoro-onnx) · [Voicebox](https://github.com/jamiepine/voicebox) · [Open-Higgsfield-AI](https://github.com/Anil-matcha/Open-Higgsfield-AI) · [Cactus](https://github.com/cactus-compute/cactus) · [short-video-maker](https://github.com/gyoridavid/short-video-maker) · [MoneyPrinterTurbo](https://github.com/harry0703/MoneyPrinterTurbo) · [codex-stickman-pipeline](https://github.com/CatbearLang/codex-stickman-pipeline) · [stickman-animation-studio](https://github.com/miang20/stickman-animation-studio) · [Stickman-Studio](https://github.com/saiedpod-bot/Stickman-Studio) · [stickman-video-skill](https://github.com/sg9215/stickman-video-skill) · [resvg](https://github.com/linebender/resvg) · [Revideo](https://github.com/redotvideo/revideo) · [Motion Canvas](https://github.com/motion-canvas/motion-canvas) · Hugging Face model cards ([Kokoro-82M](https://huggingface.co/hexgrad/Kokoro-82M), [chatterbox](https://huggingface.co/ResembleAI/chatterbox), [indic-parler-tts](https://huggingface.co/ai4bharat/indic-parler-tts)).

Secondary (search snippets, not opened in full): [TechCrunch, 20 Jul 2026](https://techcrunch.com/2026/07/20/youtube-clarifies-policies-around-ai-slop-and-upsetting-videos/) · [YouTube monetization policy help page](https://support.google.com/youtube/answer/1311392) · [OpenRouter free LLM API comparison](https://openrouter.ai/blog/tutorials/free-llm-apis-compared/) · [Sarvam pricing docs](https://docs.sarvam.ai/api/pricing.md) · [Remotion pricing](https://www.remotion.dev/docs/pricing) · [YouTube Data API videos.insert](https://developers.google.com/youtube/v3/docs/videos/insert) · [1of10 vs TubeLab](https://1of10.com/blog/1of10-vs-tubelab/) · [TubeLab review](https://outlierkit.com/blog/tubelab-reviews-features-alternatives) · [YouTube CPM in India](https://upgrowth.in/youtube-cpm-in-india-complete-guide/) · [Geo TV on the Jan 2026 crackdown](https://www.geo.tv/latest/648023-in-fresh-crackdown-on-ai-brainrot-content-youtube-discards-over-47-billion-views) · [open-source video model roundups](https://www.thundercompute.com/blog/best-open-source-ai-video-generation-models) · [Nano Banana consistent-character guide](https://lilys.ai/en/notes/consistent-characters-20251101/consistent-characters-nano-banana).
