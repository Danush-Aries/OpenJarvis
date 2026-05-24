"""Text preprocessing for natural Jarvis speech patterns.

Transforms written text into conversational speech that sounds like
Marvel's Jarvis — measured, British, with natural cadence and
contractions. Designed to work with any TTS backend (edge-tts, ElevenLabs).

Key transformations:
  - Expands/smartens contractions for natural flow
  - Inserts natural pauses at sentence boundaries
  - Converts written punctuation into speech-friendly form
  - Maintains the sophisticated but conversational Jarvis tone
  - Adjusts pacing/tone based on emotional state
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# Contraction patterns — convert formal writing into natural speech
# The TTS will read these naturally as contractions.
# ---------------------------------------------------------------------------

# (pattern, replacement) — ordered so longer matches come first
_CONTRACTIONS: List[Tuple[re.Pattern, str]] = [
    # "I am" -> "I'm"
    (re.compile(r"\bI am\b", re.IGNORECASE), "I'm"),
    # "I have" -> "I've"
    (re.compile(r"\bI have\b", re.IGNORECASE), "I've"),
    # "I will" -> "I'll"
    (re.compile(r"\bI will\b", re.IGNORECASE), "I'll"),
    # "I would" -> "I'd"
    (re.compile(r"\bI would\b", re.IGNORECASE), "I'd"),
    # "you are" -> "you're"
    (re.compile(r"\byou are\b", re.IGNORECASE), "you're"),
    # "we are" -> "we're"
    (re.compile(r"\bwe are\b", re.IGNORECASE), "we're"),
    # "they are" -> "they're"
    (re.compile(r"\bthey are\b", re.IGNORECASE), "they're"),
    # "it is" -> "it's"
    (re.compile(r"\bit is\b", re.IGNORECASE), "it's"),
    # "that is" -> "that's"
    (re.compile(r"\bthat is\b", re.IGNORECASE), "that's"),
    # "there is" -> "there's"
    (re.compile(r"\bthere is\b", re.IGNORECASE), "there's"),
    # "here is" -> "here's"
    (re.compile(r"\bhere is\b", re.IGNORECASE), "here's"),
    # "what is" -> "what's"
    (re.compile(r"\bwhat is\b", re.IGNORECASE), "what's"),
    # "who is" -> "who's"
    (re.compile(r"\bwho is\b", re.IGNORECASE), "who's"),
    # "do not" -> "don't"
    (re.compile(r"\bdo not\b", re.IGNORECASE), "don't"),
    # "does not" -> "doesn't"
    (re.compile(r"\bdoes not\b", re.IGNORECASE), "doesn't"),
    # "did not" -> "didn't"
    (re.compile(r"\bdid not\b", re.IGNORECASE), "didn't"),
    # "cannot" -> "can't"
    (re.compile(r"\bcannot\b", re.IGNORECASE), "can't"),
    # "will not" -> "won't"
    (re.compile(r"\bwill not\b", re.IGNORECASE), "won't"),
    # "would not" -> "wouldn't"
    (re.compile(r"\bwould not\b", re.IGNORECASE), "wouldn't"),
    # "should not" -> "shouldn't"
    (re.compile(r"\bshould not\b", re.IGNORECASE), "shouldn't"),
    # "could not" -> "couldn't"
    (re.compile(r"\bcould not\b", re.IGNORECASE), "couldn't"),
    # "have not" -> "haven't"
    (re.compile(r"\bhave not\b", re.IGNORECASE), "haven't"),
    # "has not" -> "hasn't"
    (re.compile(r"\bhas not\b", re.IGNORECASE), "hasn't"),
    # "was not" -> "wasn't"
    (re.compile(r"\bwas not\b", re.IGNORECASE), "wasn't"),
    # "were not" -> "weren't"
    (re.compile(r"\bwere not\b", re.IGNORECASE), "weren't"),
    # "is not" -> "isn't"
    (re.compile(r"\bis not\b", re.IGNORECASE), "isn't"),
    # "are not" -> "aren't"
    (re.compile(r"\bare not\b", re.IGNORECASE), "aren't"),
    # "let us" -> "let's"
    (re.compile(r"\blet us\b", re.IGNORECASE), "let's"),
    # "that will" -> "that'll"
    (re.compile(r"\bthat will\b", re.IGNORECASE), "that'll"),
]

# ---------------------------------------------------------------------------
# Cadence punctuation — insert natural speech rhythms
# ---------------------------------------------------------------------------

# Sentences that are too long get broken up with a comma or pause marker
_LONG_SENTENCE_THRESHOLD = 120  # characters — insert a break if longer

# Words that suggest a natural pause should follow
_PAUSE_TRIGGERS = re.compile(
    r"\b(however|therefore|nevertheless|meanwhile|furthermore|additionally|"
    r"consequently|specifically|essentially|importantly|interestingly|"
    r"alternatively|notably|ultimately|incidentally)\b",
    re.IGNORECASE,
)

# ---------------------------------------------------------------------------
# Main preprocessing
# ---------------------------------------------------------------------------


def preprocess_for_speech(text: str) -> str:
    """Preprocess text to sound like natural Jarvis speech.

    Applies in order:
      1. Apply contractions for natural flow
      2. Break up long sentences
      3. Normalize pauses and punctuation
      4. Clean up whitespace

    Args:
        text: Raw LLM response text.

    Returns:
        Text optimized for natural TTS delivery.
    """
    if not text:
        return text

    result = text

    # 1. Apply contractions
    result = _apply_contractions(result)

    # 2. Add natural cadence — break up long compound sentences
    result = _adjust_cadence(result)

    # 3. Clean up whitespace and normalize punctuation
    result = _cleanup(result)

    return result


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _apply_contractions(text: str) -> str:
    """Replace formal word pairs with natural contractions."""
    for pattern, replacement in _CONTRACTIONS:
        text = pattern.sub(replacement, text)
    return text


def _adjust_cadence(text: str) -> str:
    """Insert natural pauses and break up long sentences.

    The key to not sounding like you're reading every word is having
    natural variation in pacing. We insert:
      - Pauses after transition words (however, therefore...)
      - Breaks in sentences over threshold length
      - Commas before connecting clauses
    """
    # Insert pauses after transition words — but only if not already followed by a comma
    def _add_pause(m: re.Match) -> str:
        word = m.group(1)
        # Check if the next non-whitespace char after the word is already a comma
        rest = text[m.end():].lstrip()
        if rest.startswith(","):
            return word  # Already has comma — don't add another
        return word + ","
    text = _PAUSE_TRIGGERS.sub(_add_pause, text)

    # Break up sentences that are too long
    # Only work on sentences between 120-300 chars that don't already have commas
    sentences = re.split(r"(?<=[.!?])\s+", text)
    adjusted = []
    for sent in sentences:
        sent = sent.strip()
        if len(sent) > _LONG_SENTENCE_THRESHOLD and "," not in sent:
            # Find natural break points — after conjunctions or at clause boundaries
            # Look for "and", "but", "or", "so", "because", "which", "that"
            break_points = list(
                re.finditer(
                    r"\b(and|but|or|so|because|which|where|however|"
                    r"although|while|since|unless|though)\b",
                    sent[50:],  # Only look after the first 50 chars
                )
            )
            # Take the first break point and add a comma before it
            # Only if it's not too close to the end
            for bp in break_points:
                pos = bp.start() + 50
                if pos < len(sent) - 30:  # Not too close to end
                    sent = sent[:pos] + "," + sent[pos:]
                    break

        adjusted.append(sent)

    text = " ".join(adjusted)
    return text


def _cleanup(text: str) -> str:
    """Clean up whitespace and normalize punctuation for speech.

    Multiple spaces, awkward punctuation spacing, etc.
    """
    # Remove multiple spaces (but keep single spaces)
    text = re.sub(r"  +", " ", text)

    # Fix punctuation spacing (space before comma/period)
    text = re.sub(r'\s+([,.!?;:])', r'\1', text)

    # Ensure single space after sentence-ending punctuation
    text = re.sub(r'([.!?])([A-Za-z])', r'\1 \2', text)

    # Ensure space after commas that don't have one
    text = re.sub(r',(\S)', r', \1', text)

    # Normalize ellipses to exactly three dots with space before and after
    text = re.sub(r'\.{3,}', "...", text)
    text = re.sub(r'\s+\.\.\.', " ...", text)
    text = re.sub(r'\.\.\.\s+', "... ", text)

    # Remove leading/trailing whitespace
    text = text.strip()

    return text


# ---------------------------------------------------------------------------
# Emotional adjustment — adapt delivery based on soul emotional state
# ---------------------------------------------------------------------------


def adjust_for_emotion(
    text: str,
    emotional_context: Optional[Dict[str, Any]] = None,
) -> str:
    """Adjust speech pacing and tone based on the soul\'s emotional state.

    Called after ``preprocess_for_speech()`` to further tailor delivery:

    - **High frustration** (> 0.5): shorter sentences, more direct, removes
      enthusiasm markers for a clipped, professional tone.
    - **Positive mood** (valence > 0.3): slightly warmer, adds measured
      enthusiasm markers like "certainly", "of course".
    - **Low arousal / calm**: more cadence pauses for a measured, deliberate
      delivery.
    - **Neutral / default**: no adjustment beyond standard preprocessing.

    Args:
        text: Already preprocessed text (from ``preprocess_for_speech()``).
        emotional_context: Dict from ``EmotionalState.get_emotional_context()``.
                           If None or empty, returns text unchanged.

    Returns:
        Text adjusted for current emotional delivery.
    """
    if not emotional_context:
        return text

    frustration = emotional_context.get("frustration", 0.0)
    valence = emotional_context.get("valence", 0.0)
    arousal = emotional_context.get("arousal", 0.0)
    mood = emotional_context.get("mood", "neutral")

    result = text

    # ── High frustration → clipped, direct, professional ──────────
    if frustration > 0.5:
        # Strip enthusiasm markers
        result = re.sub(
            r"\b(wonderful|excellent|fantastic|amazing|brilliant|delightful|splendid)\b",
            "fine",
            result,
            flags=re.IGNORECASE,
        )
        # Reduce exclamation marks to periods
        result = result.replace("!", ".")
        # Break long sentences at conjunctions for shorter delivery
        result = re.sub(
            r"(,?\s+)(and|but|or|so|because|however|although)(\s+[^.]{40,}\.)",
            r".\2\3",
            result,
        )
        # Remove unnecessary pleasantries at end
        result = re.sub(
            r"\s*(if you (?:would like|need|have any (?:more )?(?:questions|concerns))|let me know if).*?$",
            "",
            result,
            flags=re.IGNORECASE,
        )

    # ── Positive mood → warm, slightly enthusiastic ──────────────
    elif valence > 0.3 and mood in ("happy", "excited", "calm"):
        # Add measured warmth to sentence starts
        warm_prefixes = {
            "i will": "I will",
            "i have": "I have",
            "i am": "I am",
            "the": "The",
            "you": "You",
            "your": "Your",
        }
        # Only apply to sentences that don't already have warmth markers
        sentences = re.split(r"(?<=[.!?])\s+", result)
        warm_sentences = []
        for i, sent in enumerate(sentences):
            sent = sent.strip()
            # On the first sentence or after a long stretch, add
            # "Certainly" or "Of course" for acknowledgement turns
            if i == 0 and len(sent) < 80 and not sent.startswith(("Yes", "No", "I" ,"Of course", "Certainly")):
                if sent.endswith("."):
                    sent = f"Certainly, {sent[0].lower() + sent[1:]}"
            warm_sentences.append(sent)
        result = " ".join(warm_sentences)

    # ── Low arousal / calm → more cadence pauses ─────────────────
    if arousal < -0.2:
        # Insert light pauses after transition words more liberally
        result = re.sub(
            r"\b(and then|so then|after that|next|then)\b",
            lambda m: m.group(1) + ",",
            result,
            flags=re.IGNORECASE,
        )

    return result


# ---------------------------------------------------------------------------
# Direct test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    # Test with some Jarvis-style responses
    test_cases = [
        "Good morning sir. I have completed the analysis you requested. All systems are functioning within normal parameters.",
        "I am running a full diagnostic on the Mark III suit. The power core is operating at 98% efficiency and the repulsor systems are fully calibrated.",
        "It appears there is an anomaly in the reactor core. However I do not believe it is a cause for immediate concern. I would recommend scheduling a maintenance cycle within the next 72 hours.",
        "Yes, sir. I have taken the liberty of preparing the documents you will need for the Stark Industries board meeting. They are ready for your review whenever you are.",
        "Shall I order your usual from the workshop? Coffee, black, no sugar. I have also taken the liberty of rescheduling your 3 o'clock meeting. You seemed preoccupied with the new thruster calculations.",
    ]

    print("=" * 60)
    print("Jarvis Speech Style Preprocessor")
    print("=" * 60)

    for i, case in enumerate(test_cases, 1):
        print(f"\n--- Test {i} ---")
        print(f"  Original: {case}")
        processed = preprocess_for_speech(case)
        print(f"  Processed: {processed}")
        print()
