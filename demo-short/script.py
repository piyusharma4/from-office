"""Narration for the demo short: "The Spotlight Effect".

Each entry is (scene_id, line, pause_after_seconds). The renderer maps scene_id
to a drawing function; the audio step turns each line into its own clip so
scene cuts land exactly on sentence boundaries.

Fact source: Gilovich, Medvec & Savitsky (2000), "The spotlight effect in social
judgment", Journal of Personality and Social Psychology 78(2). Students wearing
a Barry Manilow T-shirt estimated ~50% of peers noticed; the real figure was ~23%.
"""

TITLE = "The Spotlight Effect"
VOICE = "af_heart"
SPEED = 0.95
LEAD_IN = 0.35

LINES = [
    ("spill",    "You just spilled coffee all over yourself.", 0.15),
    ("stare",    "And you're sure the whole room saw it.", 0.25),
    ("nobody",   "Honestly? Almost nobody did.", 0.30),
    ("title",    "Psychologists call this the spotlight effect.", 0.30),
    ("shirt",    "In a famous Cornell study, students walked into a room wearing a seriously uncool T-shirt.", 0.15),
    ("guess",    "They guessed half the room would notice.", 0.20),
    ("actual",   "The real number? Roughly one in four.", 0.40),
    ("truth",    "Here's the honest truth.", 0.20),
    ("spots",    "Everyone is standing in their own spotlight,", 0.05),
    ("worries",  "way too busy worrying about themselves to judge you.", 0.30),
    ("movie",    "You're the main character only in your own movie.", 0.15),
    ("everyone", "And so is everyone else.", 0.90),
]
