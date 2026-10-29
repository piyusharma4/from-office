"""Episode 01: Why Do Indians Hang Lemon and Chillies on Doors?

Each entry: (scene, caption_text, pause_after[, spoken_text]). spoken_text is a
phonetic respelling for Kokoro, which reads "mirchi" as "mer-chai".
Consecutive lines with the same scene share one continuous shot.

Fact notes (checked before rendering):
- Nimbu-mirchi: one lemon plus (usually) seven green chillies on a cotton thread,
  hung at doorways of shops, homes and vehicles, commonly replaced every Saturday.
  Folk belief: wards off nazar (the evil eye) and Alakshmi, Lakshmi's sister and
  the goddess of misfortune, who likes sour and spicy food.
- The "scientific reason" forward (thread absorbs citric acid/capsaicin and the
  vapour repels insects) has no supporting studies.
- Evil-eye beliefs are found across the Mediterranean, Middle East and South Asia
  (e.g. the Turkish blue glass "nazar" bead). Indian trucks commonly carry the
  painted line "Buri nazar wale tera muh kala".
- Rituals reduce anxiety: Brooks et al. (2016), "Don't stop believing: Rituals
  improve performance by decreasing anxiety", Organizational Behavior and Human
  Decision Processes 137.
"""

TITLE = "Why Do Indians Hang Lemon and Chillies on Doors?"
VOICE = "af_heart"
SPEED = 0.95
LEAD_IN = 0.4

CHAPTERS = ["THE THING", "THE LEGEND", "THE \"SCIENCE\"", "THE TRUTH"]
CHAPTER_OF = {  # scene -> chapter index (None = no timeline bar)
    "street": None, "everywhere": None, "question": None, "title": None,
    "recipe": 0, "saturday": 0,
    "legend": 1, "visit": 1, "nazar": 1,
    "forward": 2, "verdict": 2,
    "world": 3, "brain": 3, "shop": 3,
    "end": None,
}

N = "nimboo mir chee"

LINES = [
    ("street",     "Walk past almost any shop in India, and you'll spot it.", 0.2),
    ("street",     "One lemon. A few green chillies. Hanging on a thread.", 0.35),
    ("everywhere", "On shop doors, on homes, on trucks, even on brand new cars.", 0.3),
    ("question",   "But why do we do this? And is the reason you got on WhatsApp actually true?", 0.4),
    ("title",      "Let's be honest about nimbu mirchi.", 0.6, f"Let's be honest about {N}."),

    ("recipe",     "First, the recipe.", 0.2),
    ("recipe",     "Thread one lemon and usually seven green chillies onto a cotton string.", 0.3),
    ("saturday",   "Hang it at the door, and swap it for a fresh one every Saturday.", 0.25),
    ("saturday",   "In big cities, vendors even go shop to shop on Saturday mornings, selling them ready-made.", 0.5),

    ("legend",     "Now, the legend.", 0.2),
    ("legend",     "Lakshmi, the goddess of wealth, loves sweet things.", 0.25, "Lukshmi, the goddess of wealth, loves sweet things."),
    ("legend",     "But her sister Alakshmi, the goddess of misfortune, loves sour and spicy food.", 0.35,
     "But her sister, Alukshmi, the goddess of misfortune, loves sour and spicy food."),
    ("visit",      "So the story goes: when Alakshmi arrives at your door, she eats the lemon and chillies,", 0.1,
     "So the story goes: when Alukshmi arrives at your door, she eats the lemon and chillies,"),
    ("visit",      "feels satisfied, and leaves without ever coming inside.", 0.4),
    ("nazar",      "The charm is also said to soak up nazar, the evil eye: jealous looks from people passing by.", 0.25,
     "The charm is also said to soak up nuh-zar, the evil eye: jealous looks from people passing by."),
    ("nazar",      "Which is why you never step on an old one lying on the road. All that bad luck has to go somewhere.", 0.6),

    ("forward",    "Then there's the forwarded message.", 0.2),
    ("forward",    "It says the cotton thread soaks up citric acid and capsaicin, and the smell keeps insects away.", 0.3),
    ("verdict",    "Sounds clever. But there's no real evidence for it.", 0.3),
    ("verdict",    "One small lemon isn't stopping a single mosquito. And nobody hangs one to keep out bugs.", 0.6),

    ("world",      "So what's really going on?", 0.25),
    ("world",      "Fear of the evil eye is everywhere. Turkey has its blue glass eye.", 0.15),
    ("world",      "And Indian trucks paint a rude warning on the back for anyone staring with jealousy.", 0.4),
    ("brain",      "Psychologists have found that rituals, even made-up ones, can lower anxiety before stressful moments.", 0.4),
    ("shop",       "Now think of a shopkeeper who has put their savings into one small shop.", 0.2),
    ("shop",       "Every morning is a gamble. A lemon and seven chillies make it feel a little less scary.", 0.5),

    ("end",        "So does it stop bad luck? Honestly, no.", 0.3),
    ("end",        "But it might stop the worrying. And for the price of one lemon, that's not a bad deal.", 1.4),
]
