"""Narrative background generation, character naming, and title/role assignment."""

from __future__ import annotations

import random

from planetfall.engine.models import (
    Character,
    ColonizationAgenda,
    Loyalty,
    SubSpecies,
)


# --- Narrative background generation ---


def build_character_background_prompt(
    char: Character,
    other_characters: list[Character],
    agenda: ColonizationAgenda,
    colony_name: str = "the colony",
) -> str:
    """Build a Claude API prompt to generate a character's narrative background.

    Uses the character's rolled traits (motivation, prior experience, class,
    sub-species) and the rest of the crew for interpersonal context.
    """
    # Crew context
    crew_lines = []
    for c in other_characters:
        if c.name == char.name:
            continue
        parts = [f"{c.name} ({c.char_class.value})"]
        if c.background_motivation:
            parts.append(f"motivated by {c.background_motivation.lower()}")
        if c.background_prior_experience:
            parts.append(f"formerly {c.background_prior_experience.lower()}")
        crew_lines.append(", ".join(parts))
    crew_text = "\n".join(f"  - {l}" for l in crew_lines) if crew_lines else "  None yet."

    subspecies_note = ""
    if char.sub_species != SubSpecies.STANDARD:
        subspecies_note = f"\nSUB-SPECIES: {char.sub_species.value} (non-human traits affect personality and worldview)"

    events_text = ""
    if char.background_notable_events:
        events_str = " → ".join(char.background_notable_events)
        events_text = f"\nNOTABLE EVENTS (in chronological order): {events_str}"

    prompt = f"""Write a 5-7 sentence narrative background for a character in a gritty frontier sci-fi colony game.
This is for internal use as a personality reference when narrating scenes — make it vivid and specific.

CHARACTER: {f"{char.title} " if char.title else ""}{char.name}
CLASS: {char.char_class.value}{subspecies_note}
{f"TITLE: {char.title}" + chr(10) if char.title else ""}ROLE: {char.role or char.char_class.value}
MOTIVATION: {char.background_motivation or 'Unknown'}
PRIOR EXPERIENCE: {char.background_prior_experience or 'None — fresh recruit'}{events_text}
LOYALTY: {char.loyalty.value}
COLONIZATION AGENDA: {agenda.value}
COLONY: {colony_name}

CREWMATES:
{crew_text}

Write a brief personality sketch: who they are, why they joined this mission, and one distinctive trait or habit.
Reference their motivation and prior experience naturally — don't just list them.
Weave their notable events into the backstory as defining moments that shaped who they are.
Keep it grounded, no purple prose. This person is real, flawed, and interesting.
Do NOT include their name at the start — just the description.
Do NOT use em dashes (—). Use commas, periods, semicolons, or colons instead."""
    return prompt


def generate_character_background_local(
    char: Character,
    other_characters: list[Character] | None = None,
) -> str:
    """Generate a rich template-based narrative background (no API needed).

    Also sets title (rank) and role if not already set.
    Builds a 4-6 sentence background from layered lookup tables keyed on
    prior experience, motivation, class, loyalty, and sub-species.
    """
    # Generate title based on class + prior experience
    # Experienced characters always get a title; inexperienced have a chance
    if not char.title:
        _class_titles = {
            "scientist": ["Dr.", "Prof.", "Dr."],
            "scout": ["Cpl.", "Sgt.", "Lt.", "Pvt."],
            "trooper": ["Sgt.", "Cpl.", "Lt.", "Capt.", "Pvt."],
        }
        # Prior experience overrides when there's a clear match
        _exp_title_override = {
            "Army": {"trooper": "Sgt.", "scout": "Cpl."},
            "Researcher": {"scientist": "Dr."},
            "Unity Agent": {"scientist": "Agent", "scout": "Agent", "trooper": "Agent"},
            "Bug Hunter": {"trooper": "Specialist", "scout": "Specialist"},
            "Enforcer": {"trooper": "Cpl.", "scout": "Cpl."},
            "Fleet Officer": {"trooper": "Lt.", "scout": "Lt.", "scientist": "Lt."},
        }
        cls_val = char.char_class.value
        exp = char.background_prior_experience
        experienced = bool(exp)

        if experienced:
            # Experienced characters always get a title
            override = _exp_title_override.get(exp, {}).get(cls_val)
            if override:
                char.title = override
            else:
                pool = _class_titles.get(cls_val, [])
                char.title = random.choice(pool) if pool else ""
        else:
            # Inexperienced: ~40% chance of a junior title
            if random.random() < 0.4:
                _junior_titles = {
                    "scientist": ["Dr."],
                    "scout": ["Pvt."],
                    "trooper": ["Pvt.", "Cpl."],
                }
                pool = _junior_titles.get(cls_val, [])
                if pool:
                    char.title = random.choice(pool)

    # Generate role if not set
    if not char.role:
        _role_map = {
            "scientist": [
                "Head of Research", "Chief Medical Officer", "Xeno-botanist",
                "Lab technician", "Field biologist", "Data analyst",
                "Environmental scientist", "Geologist", "Comms officer",
                "Epidemiologist",
            ],
            "scout": [
                "Expedition lead", "Point scout", "Recon specialist",
                "Pathfinder", "Survey lead", "Perimeter watch",
                "Cartographer", "Forward observer", "Navigation officer",
            ],
            "trooper": [
                "Head of Security", "Fire team leader", "Heavy weapons specialist",
                "Weapons sergeant", "Breach specialist", "Tactical officer",
                "Combat engineer", "Armorer", "Quartermaster",
            ],
        }
        roles = _role_map.get(char.char_class.value, ["Crew member"])
        char.role = random.choice(roles)

    exp = char.background_prior_experience
    mot = char.background_motivation
    cls = char.char_class.value

    # --- Layer 1: Origin story (2 sentences based on prior experience) ---
    _origins: dict[str, list[str]] = {
        "Army": [
            f"Spent six years in a Unity ground division before mustering out with a bad knee and a chest full of campaign ribbons. Transferred to colonial service because garrison life felt like slow death — {cls} duty on the frontier at least keeps the blood moving.",
            f"Served three combat tours on the inner-rim border wars, the kind that never make the newsfeeds. When the armistice came there was nothing left for a career soldier, so signing on as a colony {cls} was the only door still open.",
            f"Rose through the ranks fast in a Unity mechanized unit, but a friendly-fire incident that killed two squadmates ended any hope of further promotion. Took a colony {cls} posting to get as far from that memory as possible.",
        ],
        "Freelancer": [
            f"Worked freelance contracts across a dozen systems — salvage ops, private security, courier runs that didn't ask questions. Landed the {cls} gig when a contact passed along the colony charter and the signing bonus was too good to ignore.",
            f"Built a reputation running independent jobs in the outer sectors, the kind where you bring your own gear and don't expect backup. Took the colony {cls} contract after a job went bad on Meridian Station and burning that port meant needing new horizons.",
            f"Freelanced for years, picking up skills the hard way — a stint as a cargo hand, another as a survey temp, a third running comms for a mining outfit. The colony {cls} role is the first real commitment in a career defined by walking away.",
        ],
        "Researcher": [
            f"Held a fellowship at the Cygnus Institute studying xenobiology before funding cuts shuttered the entire department. Signed on as a colony {cls} because field data from an uncharted world was worth more than any lab simulation.",
            f"Published three papers on frontier ecology that nobody read before abandoning academia for applied work. The colony {cls} posting promised real specimens and real danger — exactly what the lab could never offer.",
            f"Spent years in a Unity research lab analyzing soil samples from survey probes, dreaming of seeing the source. When the colony expedition posted a {cls} opening, it felt like the universe finally answering a decade of grant applications.",
        ],
        "Trader": [
            f"Ran a small trading loop between three fringe systems, making thin margins on medical supplies and machine parts. Lost the ship to a creditor, kept the instincts — reading people, spotting value, knowing when to cut and run. The colony {cls} role pays steady, which is novel.",
            f"Made and lost two small fortunes trading rare minerals before the market collapsed. Signed on as a {cls} because the colony needed someone who understood supply chains, and because starting over somewhere nobody knows your debts has its appeal.",
        ],
        "Orphan/Utility program": [
            f"Raised in a Unity Utility Program facility on a mid-rim station — no family name, no homeworld, just a service number and a bunk assignment. Trained as a {cls} because the program said that's where the aptitude scores pointed, and nobody asked for a second opinion.",
            f"Grew up in a state-run orphan program where every kid learned a trade by twelve and shipped out by sixteen. The {cls} training stuck better than most things, and the colony posting was the first time anyone offered a choice instead of an assignment.",
        ],
        "Unity Agent": [
            f"Worked Unity Intelligence for eight years — counter-insurgency, asset recruitment, the kind of work that doesn't leave a paper trail. Reassigned to colonial {cls} duty after a mission went sideways on Helos IV, which Unity calls 'a lateral move' and everyone else calls exile.",
            f"Spent years running operations for Unity's frontier security division, tracking separatist cells and monitoring unaligned settlements. The {cls} posting on a colony world is officially a 'field liaison role,' but the crew suspects there's more to it than the paperwork says.",
        ],
        "Bug Hunter": [
            f"Made a living clearing xeno-infestations from terraforming sites — twelve confirmed hive clearances across four systems, each one worse than the last. Took the colony {cls} posting because the pay was better than freelance extermination and the bugs out here haven't learned to fear humans yet.",
            f"Spent five years with a licensed extermination crew, the kind that gets called when survey teams stop reporting in. Knows what a nest smells like before you see it, how to read spoor in alien soil, and exactly how many rounds it takes to drop a brood mother. The colony needed that expertise.",
        ],
        "Administration": [
            f"Pushed requisition forms and personnel files for a mid-rim logistics hub for seven years before the monotony became unbearable. Applied for a colony {cls} position on impulse during a night shift, and was genuinely surprised when the transfer came through.",
            f"Managed supply manifests and duty rosters at a Unity waystation — competent, reliable, and slowly dying of boredom. Retrained as a {cls} and took the colony posting because even the risk of death felt better than another decade of spreadsheets.",
        ],
        "Corporate": [
            f"Came up through a megacorp's colonial development division, where 'resource optimization' meant squeezing every credit from frontier operations. Transferred to {cls} duty after a restructuring eliminated the entire regional office — brought sharp instincts and zero sentimentality.",
            f"Worked corporate security for a resource extraction firm, handling problems that couldn't appear on quarterly reports. The colony {cls} role is technically a demotion, but it came with full benefits and no internal affairs department breathing down the corridor.",
        ],
        "Explorer": [
            f"Logged more uncharted sectors than most survey teams see in a career, always pushing one jump further than the charts recommended. The colony {cls} posting was supposed to be a rest stop between expeditions, but the planet turned out to be far more interesting than expected.",
            f"Grew up on long-range survey ships, learning to read terrain from orbit before most kids learn to ride a bike. Took the {cls} role because this world has blank spots on every map, and blank spots are the only thing that still makes the heart rate climb.",
        ],
        "Adventurer": [
            f"Has a string of close calls across six systems — a collapsed mine on Vega III, a hull breach off the Kepler drift, a bar fight on Meridian that left a scar and a good story. Signed on as a {cls} because the colony brochure promised 'unprecedented challenges,' which is corporate-speak for exactly the kind of trouble that keeps life interesting.",
            f"Never stayed in one place longer than a standard year, always chasing the next frontier, the next rush. The colony {cls} gig is the longest commitment to date, and there's a running bet among the crew on how long it lasts.",
        ],
        "Records Deleted": [
            f"Official service record shows a blank where the last five years should be — redacted by someone with enough clearance to make it permanent. Whatever happened before the colony {cls} posting, the skills are real: steady hands, sharp eyes, and a habit of checking sight lines when entering a room.",
            f"Nobody knows the real story and the file is sealed at a classification level the colony admin can't access. Shows up as a {cls} with training that doesn't match any standard program, reflexes that suggest serious field time, and a reluctance to talk about anything before the day the transport landed.",
        ],
        "Enforcer": [
            f"Worked enforcement on a mining colony where labor disputes were settled with riot gear and stun batons. Got good at reading a crowd, better at controlling one, and eventually tired of being the corporation's blunt instrument. The colony {cls} posting felt like a chance to protect something worth protecting.",
            f"Spent years as a station enforcer on the outer rim, keeping order in places where order was mostly theoretical. The scars are from the job, the cynicism is earned, and the colony {cls} role is the first gig that didn't require looking the other way.",
        ],
        "Fleet Officer": [
            f"Commanded a patrol corvette on the Unity border fleet for four years before requesting a ground posting. The official reason was 'career diversification'; the real reason was watching a refugee transport burn up on re-entry while fleet command debated jurisdiction. Colony {cls} duty means decisions have immediate consequences, which is the point.",
            f"Rose to executive officer on a fleet destroyer before a disagreement with the captain over engagement protocols ended with a transfer request and a note in the personnel file. Took the colony {cls} posting because leading a squad on the ground feels more honest than bridge politics.",
        ],
        "Access Denied": [
            f"The personnel file triggers a security flag when accessed — not redacted, not deleted, just locked behind clearance levels that don't exist in the colony's system. Whatever branch trained this {cls}, they taught tradecraft that shows in small ways: the careful habit of sitting with back to the wall, the way conversations get steered without anyone noticing.",
            f"Arrived on the colony transport with credentials that checked out and a background file that returned nothing but a classification header. The {cls} skills are undeniable — too polished for standard training, too instinctive for academy work. The crew has theories; none of them are comforting.",
        ],
    }
    _recruit_origins: list[str] = [
        f"Signed up for the colony {cls} program straight out of a Unity vocational track — no combat experience, no field time, just a passing score on the aptitude test and a willingness to ship out. The training was six weeks of compressed basics that barely scratched the surface of what the frontier actually demands.",
        f"Grew up on a mid-rim station where the most dangerous thing was a malfunctioning airlock seal. Applied for the colony {cls} posting because the recruitment vid made it look like an adventure, and because staying home meant inheriting a maintenance contract and a lifetime of recycled air.",
        f"Fresh out of a Unity technical program with top marks in theory and zero practical hours. The colony {cls} assignment is the first real posting — everything before this was simulations and classroom drills that suddenly feel laughably inadequate.",
    ]

    if exp and exp in _origins:
        origin = random.choice(_origins[exp])
    elif exp:
        origin = f"Comes from a background in {exp.lower()}, bringing unusual skills to the {cls} role. The colony posting represents a fresh start after years in a very different line of work."
    else:
        origin = random.choice(_recruit_origins)

    # --- Layer 2: Motivation sentence ---
    _motivations: dict[str, list[str]] = {
        "Curiosity": [
            "What drives them isn't duty or money — it's the need to understand. Every anomalous reading, every unclassified organism, every question without an answer pulls like gravity.",
            "The unknown isn't frightening; it's the only thing that makes getting up worthwhile. Asks more questions than the rest of the crew combined and writes everything down in a battered field journal.",
        ],
        "Personal Achievement": [
            "Carries a private scoreboard that nobody else can see — every milestone, every first, every record matters. Not competitive with the crew so much as locked in a permanent contest with their own limits.",
            "Has something to prove, though whether it's to the crew, to someone back home, or to the face in the mirror depends on the day. Pushes harder than necessary and takes shortcuts less often than expected.",
        ],
        "Loyalty": [
            "The crew comes first — before protocol, before personal safety, before common sense. It's the kind of loyalty that makes people follow you into a bad situation and occasionally the kind that creates bad situations.",
            "Treats the squad like family, which in practice means worrying too much, checking on people who don't ask for it, and holding grudges against anyone who lets the team down.",
        ],
        "Danger": [
            "Most alive when the situation is worst — when the alarms are screaming and the options are narrowing. It's not recklessness exactly, more like a fundamental inability to feel present when things are calm.",
            "Volunteers for the hard jobs, takes point without being asked, and gets restless during downtime. The crew can't decide if it's courage or a death wish, and neither can they.",
        ],
        "Independence": [
            "Chafes under authority the way most people chafe under a bad sunburn — constantly, visibly, and with occasional outbursts. Works best when given a task and left alone to figure out how.",
            "Values autonomy above comfort, rank, or approval. Follows orders when they make sense and finds creative interpretations when they don't. Command has flagged the attitude; the results keep saving it.",
        ],
        "Circumstance": [
            "Didn't choose the frontier life — it chose them, through a chain of events that started with bad luck and ended with a one-way transport ticket. Making the best of it with a pragmatism that borders on fatalism.",
            "Ended up on the colony roster through circumstances nobody bothers to explain twice. Not bitter about it, exactly, but carries the quiet weight of someone living a life they didn't plan for.",
        ],
        "Progress": [
            "Thinks in terms of infrastructure, timelines, and long-term survival curves. While others worry about today's threat, they're calculating resource yields three seasons out and planning supply routes that don't exist yet.",
            "Believes the colony can become something permanent — not just a camp, but a real settlement. That conviction shows in the way they treat every task as part of a larger blueprint only they can fully see.",
        ],
        "Adventure": [
            "Collects experiences the way some people collect currency — every close call is a story, every new sector is a chapter, and the only real failure is a boring day. The crew finds it exhausting and occasionally infectious.",
            "Treats every mission like the opening scene of a story worth telling. It makes them brave in situations that call for caution and optimistic in situations that call for realism, which is both their best and worst quality.",
        ],
        "Exploration": [
            "Drawn to the edges of the map with an intensity that goes beyond professional interest. Stares at sensor readouts of uncharted terrain the way most people stare at a fire — absorbed, reverent, slightly hypnotized.",
            "Wants to see what's over the next ridge, around the next bend, beyond the next scan horizon. It's not ambition — it's compulsion, the kind that makes for great scouts and terrible listeners when someone suggests turning back.",
        ],
        "Greater Cause": [
            "Carries a conviction that the colony matters beyond its own survival — that what they're building here serves something larger. It gives them a steadiness under pressure that the rest of the crew finds either reassuring or unnerving, depending on the day.",
            "Sees the mission in moral terms, not just operational ones. The colony isn't just a posting; it's a responsibility. That perspective makes them reliable in a crisis and occasionally insufferable during routine briefings.",
        ],
        "Escape": [
            "Took the most distant posting available, and the colony qualified. Whatever they're running from — a warrant, a debt, a person, a memory — it stays locked behind a flat expression and a refusal to discuss anything before the voyage out.",
            "The colony is the far edge of known space, which is exactly the point. Doesn't talk about before, doesn't keep personal effects from before, and gets visibly tense whenever a supply ship arrives from the inner systems.",
        ],
        "Obligation": [
            "Here because they owe someone — a debt, a promise, a life saved at a cost that hasn't been fully paid. Does the work with a grim reliability that suggests this isn't about wanting to be here but about needing to be.",
            "Carries an obligation that predates the colony charter, the kind that doesn't expire and can't be bought out. The crew doesn't know the details, but they've noticed the way duty and personal cost seem to weigh exactly equal.",
        ],
    }

    if mot and mot in _motivations:
        motivation_text = random.choice(_motivations[mot])
    elif mot:
        motivation_text = f"Motivated primarily by {mot.lower()} — it colors every decision and shapes how they approach the work."
    else:
        motivation_text = "Still figuring out why they're really here, which makes them unpredictable in ways that keep the crew guessing."

    # --- Layer 3: Personality quirk / distinctive trait ---
    _quirks: dict[str, list[str]] = {
        "scientist": [
            "Keeps a detailed specimen log in impossibly small handwriting and gets irritable when anyone touches the sample cases.",
            "Has a habit of muttering hypotheses under their breath during tense situations, which is either calming or maddening depending on who's listening.",
            "Taps the side of their scanner three times before every reading — claims it recalibrates the sensor, but it's clearly superstition.",
        ],
        "scout": [
            "Moves with an economy of motion that makes other people feel clumsy, and sleeps so lightly that a shifted boot across the room brings them fully awake.",
            "Marks every route traveled with small scratches on their gear — a personal navigation record that only makes sense to them.",
            "Has an uncanny sense for ambush terrain and a habit of stopping mid-sentence to listen to something nobody else can hear.",
        ],
        "trooper": [
            "Cleans their weapon every evening with a ritualistic focus that borders on meditation — the one time of day where the usual tension in their shoulders disappears.",
            "Counts rounds obsessively, always knows exactly how much ammunition the squad is carrying, and gets visibly uncomfortable below a threshold only they have calculated.",
            "Has a quiet ritual of touching the wall of the barracks before every deployment — won't explain it, won't skip it, and got genuinely angry the one time someone asked.",
        ],
    }

    quirk = random.choice(_quirks.get(cls, [
        "Has a habit of humming tunelessly during routine tasks — nobody's identified the song, if it even is one.",
    ]))

    # --- Layer 4: Loyalty/sub-species color ---
    loyalty_text = ""
    if char.loyalty == Loyalty.LOYAL:
        loyalty_text = random.choice([
            " The crew trusts them without hesitation — the kind of person who'd walk into fire for someone else's mistake and never mention it afterward.",
            " Deeply committed to the colony and everyone in it, to a degree that occasionally worries the people who know how costly that kind of loyalty can get.",
        ])
    elif char.loyalty == Loyalty.DISLOYAL:
        loyalty_text = random.choice([
            " Their commitment to the group runs exactly as deep as their self-interest, and the crew knows it. Useful, capable, and never quite trustworthy.",
            " Looks out for themselves first, second, and third — the colony and the crew come in somewhere around fourth. It's not malice; it's a survival instinct that never learned to include other people.",
        ])

    subspecies_text = ""
    if char.sub_species == SubSpecies.FERAL:
        subspecies_text = " The feral bloodline shows in small ways — a wider stance, a tendency to smell the air before entering a space, reflexes that operate on instinct rather than training. It makes some of the crew uneasy, which they pretend not to notice."
    elif char.sub_species == SubSpecies.HULKER:
        subspecies_text = " Built on a hulker frame — broader, heavier, and harder to stop than baseline humans. Doorways are a constant negotiation, standard-issue gear needs modification, and the ground vibrates slightly when they walk with purpose."
    elif char.sub_species == SubSpecies.STALKER:
        subspecies_text = " Stalker physiology makes them eerily silent and hard to track even in a well-lit room. The crew has learned not to startle when they appear in peripheral vision, though some never fully manage it."
    elif char.sub_species == SubSpecies.SOULLESS:
        subspecies_text = " The soulless affect is unsettling — flat voice, minimal expression, emotional responses that arrive several seconds late or not at all. Competent and reliable, in the way that a well-maintained machine is reliable."

    # --- Layer 5: Notable events summary ---
    notable_text = ""
    if char.background_notable_events:
        _event_phrases: dict[str, str] = {
            "Journey": "a journey that took them far from everything familiar",
            "Establish family": "starting a family that gave them something to fight for",
            "Betrayal": "a betrayal that taught them who could really be trusted",
            "Personal advancement": "a breakthrough that proved they were capable of more than anyone expected",
            "Disaster struck": "a disaster that leveled everything they'd built and forced a fresh start",
            "Injured": "a serious injury that left marks both visible and otherwise",
            "Joined a group": "joining a movement that shaped how they see the world",
            "Changed perspective": "a moment that changed how they see everything",
            "Went missing": "a period when nobody knew where they were — and they prefer it stays that way",
            "Did a good deed": "a selfless act that nobody asked for and few people know about",
            "Became a student": "a decision to start over as a student when most people would have settled",
            "Was framed": "being blamed for something they didn't do, which left a lasting distrust of systems",
            "Made a mistake": "a mistake that got noticed and still stings when they think about it",
            "Progressed a career": "a career breakthrough that opened doors they didn't expect",
            "Good luck": "an improbable stroke of luck that changed the trajectory of everything after",
            "Confrontation": "a confrontation with a rival that settled something important",
            "Great danger": "surviving great physical danger through a mix of skill and luck",
            "Narrow escape": "a narrow escape from a situation that should have ended them",
            "Second chance": "a second chance from someone who didn't have to give one",
            "Change of lifestyle": "a fundamental change in how they live that nobody saw coming",
        }
        phrases = [_event_phrases.get(e, e.lower()) for e in char.background_notable_events]
        if len(phrases) == 1:
            notable_text = f" Their life was marked by {phrases[0]}."
        elif len(phrases) == 2:
            notable_text = f" Their past includes {phrases[0]} and {phrases[1]}."
        else:
            notable_text = f" Before the colony, their life was shaped by {phrases[0]}, then {phrases[1]}, and finally {phrases[2]}."

    # --- Assemble ---
    text = f"{origin} {motivation_text}{notable_text} {quirk}{loyalty_text}{subspecies_text}"
    return text


def _is_unnamed(name: str) -> bool:
    """Check if a character name is a placeholder like 'Scientist 1' or 'Character 3'."""
    import re
    return bool(re.match(
        r'^(Scientist|Scout|Trooper|Character)\s+\d+$', name, re.IGNORECASE,
    ))


# Diverse sci-fi name pool for local fallback
_NAME_POOL = [
    "Kira Vasquez", "Orin Takahashi", "Maren Osei", "Dex Calloway",
    "Asha Volkov", "Renn Dubois", "Yuki Okafor", "Cade Moreno",
    "Liora Chen", "Falk Andersen", "Zuri Petrov", "Niko Ramirez",
    "Hana Bergström", "Rafe Mensah", "Ines Kowalski", "Joss Tanaka",
    "Cleo Abara", "Leif Guerrero", "Priya Johansson", "Tobias Wren",
    "Maya Idris", "Soren Reyes", "Eira Nakamura", "Cal Obi",
    "Tessa Lindgren", "Arjun Mwangi", "Nyla Ortega", "Kit Ivanova",
    "Bram Adesanya", "Sage Yamamoto", "Dara Novak", "Quinn Bakker",
]


def generate_character_names(
    characters: list[Character],
    api_key: str = "",
) -> None:
    """Generate proper names for unnamed characters (e.g. 'Scientist 1').

    Modifies characters in-place.
    """
    unnamed = [(i, c) for i, c in enumerate(characters) if _is_unnamed(c.name)]
    if not unnamed:
        return

    if api_key:
        try:
            _generate_names_api(characters, unnamed, api_key)
            return
        except Exception:
            pass

    # Local fallback
    used = {c.name for c in characters}
    pool = [n for n in _NAME_POOL if n not in used]
    random.shuffle(pool)
    for idx, (i, char) in enumerate(unnamed):
        if idx < len(pool):
            char.name = pool[idx]
        else:
            char.name = f"Colonist {i + 1}"


def _generate_names_api(
    characters: list[Character],
    unnamed: list[tuple[int, Character]],
    api_key: str,
) -> None:
    """Generate character names via a single Haiku API call."""
    import anthropic
    from planetfall.api_tracker import tracked_api_call

    lines = []
    for i, char in unnamed:
        lines.append(
            f"{i}: {char.char_class.value}, "
            f"{'experienced' if char.background_prior_experience else 'recruit'}, "
            f"sub-species: {char.sub_species.value}"
        )

    prompt = (
        "Generate realistic, diverse sci-fi character names for a frontier colony crew. "
        "Names should feel grounded (not fantasy) — mix of cultures, 2-3 syllable first names, "
        "real-world-inspired surnames. Each name should be unique. "
        "Do NOT include titles or ranks (Dr., Sgt., etc.) — just the name.\n\n"
        "Characters needing names:\n" + "\n".join(lines) + "\n\n"
        "Reply with ONLY lines in format: INDEX: First Last\n"
        "No other text."
    )

    client = anthropic.Anthropic(api_key=api_key)
    message = tracked_api_call(
        client, caller="char_names",
        model="claude-haiku-4-5-20251001",
        max_tokens=200,
        messages=[{"role": "user", "content": prompt}],
    )

    text = message.content[0].text
    for line in text.strip().split("\n"):
        line = line.strip()
        if ":" not in line:
            continue
        parts = line.split(":", 1)
        try:
            idx = int(parts[0].strip())
            name = _strip_title_from_name(parts[1].strip())
            if name and 0 <= idx < len(characters):
                characters[idx].name = name
        except (ValueError, IndexError):
            continue


def generate_character_backgrounds_api(
    characters: list[Character],
    agenda: ColonizationAgenda,
    colony_name: str = "the colony",
    api_key: str = "",
) -> None:
    """Generate narrative backgrounds, names, titles, and roles in a single API call.

    Modifies characters in-place. Falls back to local generation on failure.
    Skips any character that already has a proper name AND a narrative background.
    If ALL characters are fully specified, no API call is made.
    """
    # Check which characters still need generation
    needs_gen = [c for c in characters
                 if _is_unnamed(c.name) or not c.narrative_background]

    if not needs_gen:
        return  # All characters already have names and backgrounds

    if not api_key:
        # Local fallback — generate names first, then backgrounds/titles/roles
        generate_character_names(characters, api_key="")
        for char in characters:
            if not char.narrative_background:
                char.narrative_background = generate_character_background_local(
                    char, characters,
                )
        return

    try:
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)

        from planetfall.config import get_background_model
        model = get_background_model()

        prompt = _build_batch_background_prompt(characters, agenda, colony_name)
        from planetfall.api_tracker import tracked_api_call
        message = tracked_api_call(
            client, caller="background_gen",
            model=model,
            max_tokens=600 * len(needs_gen),
            messages=[{"role": "user", "content": prompt}],
        )
        _parse_batch_backgrounds(message.content[0].text, characters)

    except Exception:
        pass

    # Fallback: generate names for any still-unnamed, backgrounds for any still empty
    generate_character_names(characters, api_key="")
    for char in characters:
        if not char.narrative_background:
            char.narrative_background = generate_character_background_local(
                char, characters,
            )


def _build_batch_background_prompt(
    characters: list[Character],
    agenda: ColonizationAgenda,
    colony_name: str,
) -> str:
    """Build a single prompt to generate backgrounds for all characters.

    Uses ID-based format for reliable matching. Generates names for placeholder
    characters, titles (ranks) for experienced characters, roles, and detailed
    narrative backgrounds.
    """
    char_blocks = []
    for i, char in enumerate(characters):
        # Skip characters that already have a proper name AND background
        has_name = not _is_unnamed(char.name)
        has_bg = bool(char.narrative_background)
        if has_name and has_bg:
            # Include as context for inter-crew references, but mark as complete
            block = (
                f"[ID:{i}] ALREADY COMPLETE — do NOT generate output for this character.\n"
                f"  Name: {char.name} | Class: {char.char_class.value}"
                f"{f' | Title: {char.title}' if char.title else ''}"
                f"{f' | Role: {char.role}' if char.role else ''}"
            )
            char_blocks.append(block)
            continue

        subspecies_note = ""
        if char.sub_species != SubSpecies.STANDARD:
            subspecies_note = f"  Sub-species: {char.sub_species.value}\n"
        placeholder_note = " (PLACEHOLDER — generate a proper name)" if not has_name else ""
        experienced = bool(char.background_prior_experience)

        # Note which fields are already provided
        provided = []
        if has_name:
            provided.append("name")
        if char.title:
            provided.append("title")
        if char.role:
            provided.append("role")
        provided_note = f"  KEEP EXISTING: {', '.join(provided)}\n" if provided else ""

        events_line = ""
        if char.background_notable_events:
            events_str = " → ".join(char.background_notable_events)
            events_line = f"  Notable Events (chronological): {events_str}\n"

        block = (
            f"[ID:{i}]\n"
            f"  Name: {char.name}{placeholder_note}\n"
            f"  Class: {char.char_class.value}\n"
            f"{subspecies_note}"
            f"  Experienced: {'yes' if experienced else 'no (fresh recruit)'}\n"
            f"  Motivation: {char.background_motivation or 'Unknown'}\n"
            f"  Prior Experience: {char.background_prior_experience or 'None'}\n"
            f"{events_line}"
            f"  Loyalty: {char.loyalty.value}\n"
            f"{provided_note}"
            f"  Title: {char.title or '(generate)'}\n"
            f"  Role: {char.role or '(generate)'}"
        )
        char_blocks.append(block)

    roster = "\n\n".join(char_blocks)

    return f"""Generate character profiles for a gritty frontier sci-fi colony crew.
These are personality references for narrating scenes — make them vivid and specific.

COLONIZATION AGENDA: {agenda.value}
COLONY: {colony_name}

CREW:
{roster}

For each character, generate the following fields:
- NAME: Only generate a new name if marked PLACEHOLDER. Otherwise keep their existing name EXACTLY.
  Names should be realistic, diverse sci-fi names (mix of cultures, 2-3 syllable first names, real-world-inspired surnames).
- TITLE: A short rank or academic title abbreviation.
  Experienced characters MUST always have a title. Inexperienced characters MAY have a junior title.
  Choose based on class:
  Scientist: Dr., Prof.
  Scout: Pvt., Cpl., Sgt., Lt., Specialist
  Trooper: Pvt., Cpl., Sgt., Lt., Capt., Specialist
  Prior experience may influence title (e.g. Fleet Officer → Lt., Researcher → Dr., Army → Sgt.).
  Inexperienced characters may use junior ranks like Pvt. or Dr. (for scientists), or leave blank.
- ROLE: A single concise job role in the crew. One role only — do NOT combine multiple roles with "/" or "and".
  Choose from or adapt these suggested roles based on class:
  Scientist: Head of Research, Chief Medical Officer, Xeno-botanist, Lab technician, Field biologist,
    Data analyst, Environmental scientist, Geologist, Comms officer, Epidemiologist, Xenolinguist
  Scout: Expedition lead, Point scout, Recon specialist, Pathfinder, Survey lead,
    Perimeter watch, Cartographer, Terrain analyst, Forward observer, Navigation officer
  Trooper: Head of Security, Fire team leader, Heavy weapons specialist, Weapons sergeant,
    Breach specialist, Close protection, Tactical officer, Combat engineer, Armorer, Quartermaster
  You may invent similar roles that fit — the list is suggestive, not exhaustive.
- BACKGROUND: A detailed 5-7 sentence personality sketch and backstory. Include: who they are, their life before
  the colony mission (career, defining moments), why they signed up, how they relate to at least one crewmate,
  and two or three distinctive traits, habits, or quirks that make them memorable. Reference their motivation
  and prior experience naturally — weave them into the story, don't list them. Weave their notable events into
  the backstory as defining moments that shaped who they are (in the chronological order listed).
  Give enough detail that a narrator could write them convincingly in any scene.
  Keep it grounded, specific, and character-driven. No purple prose.
  Do NOT use em dashes (—). Use commas, periods, semicolons, or colons instead.

IMPORTANT:
- Do NOT generate equipment or gear.
- Do NOT restate or change their motivation or prior experience — those are already determined.
- Characters should feel interconnected — reference relationships between crewmates.
- Experienced characters MUST have a TITLE. Fresh recruits MAY have a junior title or leave it blank.
- Characters marked "ALREADY COMPLETE" should be SKIPPED entirely — do NOT output a section for them.
  They are included only as context for writing other characters' relationships.
- If a field is marked "KEEP EXISTING" (e.g. name, title, role), reproduce it EXACTLY — do not change it.
- Only generate fields marked "(generate)".

Format your response EXACTLY as (only for characters that need generation):
[ID:0]
NAME: First Last
TITLE: Rank
ROLE: Job description
Detailed background text here, 5-7 sentences with real depth and specificity.

[ID:1]
NAME: First Last
TITLE:
ROLE: Job description
Detailed background text here, 5-7 sentences with real depth and specificity."""


_TITLE_PREFIXES = (
    "Dr.", "Dr ", "Sgt.", "Sgt ", "Cpl.", "Cpl ", "Lt.", "Lt ",
    "Commander ", "Cmdr.", "Cmdr ", "Chief ", "Prof.", "Prof ",
    "Specialist ", "Agent ", "Pvt.", "Pvt ", "Capt.", "Capt ",
    "Major ", "Maj.", "Maj ", "Colonel ", "Col.", "Col ",
    "Corporal ", "Sergeant ", "Lieutenant ", "Captain ",
    "Private ", "Officer ",
)


def _strip_title_from_name(name: str) -> str:
    """Strip military/academic title prefixes from a generated name."""
    for prefix in _TITLE_PREFIXES:
        if name.startswith(prefix):
            name = name[len(prefix):].strip()
            break
    return name


def _parse_batch_backgrounds(text: str, characters: list[Character]) -> None:
    """Parse batch API response and assign names, titles, roles, and backgrounds."""
    import re
    # Split on [ID:N] headers
    sections = re.split(r'\[ID:(\d+)\]', text.strip())
    # sections = ['', '0', '\nNAME: ...\n', '1', '\nNAME: ...\n', ...]

    for i in range(1, len(sections) - 1, 2):
        try:
            idx = int(sections[i].strip())
        except ValueError:
            continue
        body = sections[i + 1].strip()
        if not body or idx < 0 or idx >= len(characters):
            continue

        char = characters[idx]
        lines = body.split('\n')
        narrative_lines = []

        for line in lines:
            stripped = line.strip()
            upper = stripped.upper()
            if upper.startswith('NAME:'):
                name = stripped[5:].strip()
                # Strip title prefixes that may have been included in the name
                name = _strip_title_from_name(name)
                if name and _is_unnamed(char.name):
                    char.name = name
            elif upper.startswith('TITLE:'):
                title = stripped[6:].strip()
                if title and not char.title:
                    char.title = title
            elif upper.startswith('ROLE:'):
                role = stripped[5:].strip()
                if role and not char.role:
                    char.role = role
            elif stripped and not upper.startswith('BACKGROUND:'):
                narrative_lines.append(stripped)

        if narrative_lines and not char.narrative_background:
            char.narrative_background = ' '.join(narrative_lines)


def generate_colony_description(
    state: "GameState",
    api_key: str = "",
) -> str:
    """Generate a narrative description of the colony founding.

    Uses the agenda, administrator, and crew backgrounds to create a
    2-3 paragraph description of the colony and its founding circumstances.
    """
    colony = state.colony
    agenda = state.settings.colonization_agenda.value.replace("_", " ").title()
    admin = state.administrator

    # Build crew summary
    crew_lines = []
    for c in state.characters:
        cls = c.char_class.value.title()
        title = f" ({c.title})" if c.title else ""
        role = f", {c.role}" if c.role else ""
        bg = f" — {c.narrative_background}" if c.narrative_background else ""
        crew_lines.append(f"- {c.name}{title}: {cls}{role}{bg}")
    crew_block = "\n".join(crew_lines)

    admin_str = ""
    if admin.name:
        history = f" ({admin.past_history})" if admin.past_history else ""
        admin_str = f"Administrator: {admin.name}{history}"

    prompt = f"""Write a 2-3 paragraph founding description for a frontier colony in a \
solo sci-fi wargame. The colony has just made planetfall on an uncharted world.

Colony name: {colony.name}
Colonization agenda: {agenda}
{admin_str}
Starting morale: {state.colony.morale}

Crew backgrounds (for context — DO NOT list individual characters):
{crew_block}

Write from a gritty, grounded perspective — not heroic, not dystopian. Focus on:
- Why this particular group was sent (the agenda shapes the mission)
- The administrator's leadership style and what it means for the crew
- The overall crew dynamics, tensions, or shared traits visible from the backgrounds
- The planet's first impressions (unknown, uncertain)

You may reference themes from the crew backgrounds that matter for the colony as a whole \
(e.g. if several crew have military backgrounds, or if there's a mix of idealists and \
pragmatists), but do NOT list individual characters by name, class, or count. \
Do NOT mention grunts, bots, or crew composition numbers.
Do NOT use game mechanics language. Write prose only, no headers or formatting.
Separate paragraphs with blank lines. Each paragraph should be 3-5 sentences.
Do NOT use em dashes (—). Use commas, periods, semicolons, or colons instead."""

    if not api_key:
        return _colony_description_local(colony.name, agenda, admin, state.characters)

    try:
        import anthropic
        from planetfall.api_tracker import tracked_api_call
        from planetfall.config import get_background_model

        client = anthropic.Anthropic(api_key=api_key)
        message = tracked_api_call(
            client, caller="colony_description",
            model=get_background_model(),
            max_tokens=800,
            messages=[{"role": "user", "content": prompt}],
        )
        text = message.content[0].text.strip()
        if text:
            return text
    except Exception:
        pass

    return _colony_description_local(colony.name, agenda, admin, state.characters)


def _colony_description_local(
    colony_name: str,
    agenda: str,
    admin: "Administrator",
    characters: list["Character"],
) -> str:
    """Template-based fallback colony description."""
    import random as _rng

    class_counts: dict[str, int] = {}
    for c in characters:
        cls = c.char_class.value.title()
        class_counts[cls] = class_counts.get(cls, 0) + 1
    comp = ", ".join(f"{v} {k}{'s' if v > 1 else ''}" for k, v in class_counts.items())

    # Agenda-specific flavor
    agenda_flavor = {
        "Scientific": (
            "The mission parameters prioritize research and discovery above all else — "
            "cataloguing alien biomes, analyzing soil composition, establishing long-term "
            "observation protocols. The corporate sponsors expect data, not profit."
        ),
        "Corporate": (
            "The corporate charter is explicit: locate exploitable resources, establish "
            "extraction infrastructure, and begin generating returns for the shareholders "
            "who funded this expedition. Everything else is secondary."
        ),
        "Unity": (
            "The Unity mandate emphasizes collective survival and social cohesion. "
            "This colony exists to prove that humanity can build something lasting on "
            "the frontier — a functioning society, not just a mining outpost."
        ),
        "Military": (
            "The military directive is clear: establish a defensible forward operating base, "
            "assess and neutralize threats, and secure the region for future colonization "
            "efforts. The crew knows how to take orders."
        ),
        "Independent": (
            "No corporate backing, no government mandate. This crew pooled resources, "
            "called in favors, and scraped together enough to fund their own expedition. "
            "They answer to nobody but themselves — which means nobody is coming to help."
        ),
        "Affinity": (
            "The colony was founded on shared ideals and mutual trust. Every member was "
            "chosen not just for their skills but for their commitment to the group's "
            "vision of what a frontier settlement could become."
        ),
    }
    agenda_text = agenda_flavor.get(agenda, f"The {agenda.lower()} mission charter defines their purpose.")

    # Admin flavor
    admin_text = ""
    if admin.name and admin.past_history:
        admin_text = (
            f"\n\nAdministrator {admin.name} — a {admin.past_history.lower()} "
            f"by background — watches the landing zone take shape from the command "
            f"module's observation port. The crew's files are memorized, the supply "
            f"manifest reviewed three times, and still the margins feel thin."
        )
    elif admin.name:
        admin_text = (
            f"\n\nAdministrator {admin.name} oversees the unloading with the quiet "
            f"focus of someone who understands that the first hours set the tone "
            f"for everything that follows."
        )

    # Character texture
    motivations = [c.background_motivation for c in characters if c.background_motivation]
    char_texture = ""
    if motivations:
        sample = _rng.sample(motivations, min(3, len(motivations)))
        motiv_text = ", ".join(m.lower() for m in sample)
        char_texture = (
            f" Among the crew, motivations vary — {motiv_text} — "
            f"but for now everyone shares the same immediate concern: "
            f"making it through the first night."
        )

    return (
        f"Colony {colony_name} touches down on uncharted soil. The drop ship's "
        f"engines cycle down for the last time — there isn't enough fuel for a return "
        f"trip, and everyone aboard knows it.\n\n"
        f"{agenda_text}{admin_text}\n\n"
        f"The first hours blur together. Perimeter stakes go in. Scanners sweep "
        f"the horizon and return data that raises more questions than it answers. "
        f"The local wildlife keeps its distance — for now. The terrain surrounding "
        f"the landing site is unmapped, the ecosystem unstudied, and the nearest "
        f"resupply point is measured in parsecs, not kilometers.{char_texture}"
    )
