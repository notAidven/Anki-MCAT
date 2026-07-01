#!/usr/bin/env python3
# Copyright: Ankitects Pty Ltd and contributors
# License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html
"""Builder (single source of truth) for `passage_psych_soc.json`.

ReadyMCAT P/S (Psychological, Social & Biological Foundations of Behavior)
passage-based, exam-simulating question sets. This script holds the authored
content as Python data and emits the JSON array consumed by the app, mirroring
the repo's existing `tools/build_taxonomy.py -> taxonomy.json` pattern.

Why a builder:
  * `json.dump` guarantees the emitted JSON is well formed.
  * passage/question ids and `section` are assigned mechanically here, so they
    are always consistent and unique (no hand-numbering mistakes).

All passages and questions are ORIGINAL, authored for ReadyMCAT and grounded in
free / openly-licensed sources (OpenStax Psychology 2e, OpenStax Introduction to
Sociology 3e). No copyrighted/paid question-bank content (UWorld, Kaplan,
Blueprint, AAMC paid/practice) is copied or paraphrased. The public AAMC
"What's on the MCAT Exam?" outline is used only as a coverage/format blueprint
(the category IDs already encoded in taxonomy.json). See
`passage_psych_soc_SOURCES.md`.

Run:
    python3 readymcat/content/passage_psych_soc_build.py
Then validate:
    python3 readymcat/content/passage_psych_soc_validate.py
"""

from __future__ import annotations

import collections
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "passage_psych_soc.json")

# --- Grounding sources (openly licensed) -----------------------------------
PSY = {
    "book": "OpenStax Psychology 2e",
    "url": "https://openstax.org/details/books/psychology-2e",
    "license": "CC BY 4.0",
}
SOC = {
    "book": "OpenStax Introduction to Sociology 3e",
    "url": "https://openstax.org/details/books/introduction-sociology-3e",
    "license": "CC BY 4.0",
}


def src(chapter: str, book: dict = PSY) -> dict:
    """Build a passage_source {name,url,license} from a book + chapter label."""
    return {
        "name": f"{book['book']} ({chapter})",
        "url": book["url"],
        "license": book["license"],
    }


PASSAGES: list[dict] = []

# ---------------------------------------------------------------------------
# Passage 1 - Sensation & perception: thresholds, signal detection, adaptation
# ---------------------------------------------------------------------------
PASSAGES.append({
    "passage": (
        "Researchers investigated how listeners detect faint tones and how "
        "expectations shape perception. In Experiment 1, 40 young adults sat in "
        "a soundproof booth and reported whether a brief 1000-Hz tone was present "
        "on each of 400 trials. The tone was actually presented on only half of "
        "the trials; on the rest, participants heard only background noise. "
        "Investigators varied the tone's intensity to estimate each listener's "
        "absolute threshold, defined as the intensity detected on 50% of trials. "
        "They also recorded four response categories - hits, misses, false alarms, "
        "and correct rejections - and computed a sensitivity index (d') separately "
        "from each listener's response criterion.\n\n"
        "In Experiment 2, the same listeners were told before each block whether "
        "tones would be 'rare' or 'common.' When told tones were common, listeners "
        "reported hearing a tone more often, producing more hits but also more "
        "false alarms, even though the physical stimuli were identical across "
        "blocks. Sensitivity (d') did not change between the 'rare' and 'common' "
        "blocks; only the criterion shifted.\n\n"
        "In Experiment 3, listeners judged whether two successive weights "
        "differed. The smallest detectable difference grew in proportion to the "
        "starting weight: distinguishing 102 g from 100 g was as hard as "
        "distinguishing 204 g from 200 g. Finally, when a steady tone played "
        "continuously, listeners' reported loudness declined over several minutes, "
        "though an abrupt change in intensity was noticed at once. The authors "
        "concluded that detection reflects both sensory capacity and decision "
        "processes, and that the sensory system is tuned to change rather than to "
        "constant stimulation."
    ),
    "passage_source": src("Ch. 5, Sensation and Perception"),
    "questions": [
        {
            "aamc_category": "6A",
            "subtopic": "Absolute threshold (psychophysics)",
            "stem": "The intensity 'detected on 50% of trials' corresponds to which concept?",
            "options": [
                "Difference threshold",
                "Absolute threshold",
                "Weber's constant",
                "Response criterion",
            ],
            "correct_index": 1,
            "explanation": (
                "The absolute threshold is the minimum stimulus intensity an observer can "
                "detect 50% of the time - exactly the definition used in Experiment 1. A "
                "difference threshold (just-noticeable difference) is about telling two "
                "stimuli apart, not detecting one against no stimulus. Weber's constant is the "
                "fixed ratio behind the difference threshold, and the response criterion is a "
                "decision variable, not a sensory limit."
            ),
            "difficulty": "easy",
            "cognitive_level": "comprehension",
            "subquestions": [
                {
                    "stem": "In psychophysics, a 'threshold' describes what?",
                    "options": ["A boundary of detectability", "A specific brain region", "A type of neuron"],
                    "correct_index": 0,
                    "explanation": "Thresholds mark the limits of what the senses can detect or discriminate.",
                },
                {
                    "stem": "Which threshold concerns detecting a stimulus versus no stimulus (rather than telling two apart)?",
                    "options": ["Difference threshold", "Absolute threshold"],
                    "correct_index": 1,
                    "explanation": "The absolute threshold is detection of a single stimulus against a background of none.",
                },
                {
                    "stem": "What detection rate defines the absolute threshold?",
                    "options": ["50% of the time", "100% of the time"],
                    "correct_index": 0,
                    "explanation": "By convention it is the level detected on half of the trials.",
                },
            ],
        },
        {
            "aamc_category": "6B",
            "subtopic": "Signal detection theory (sensitivity vs. bias)",
            "stem": (
                "In Experiment 2, telling listeners tones were 'common' raised both hits and "
                "false alarms while d' stayed constant. This pattern is best explained by:"
            ),
            "options": [
                "Increased sensory sensitivity",
                "A shift in the response criterion (bias)",
                "Sensory adaptation",
                "A change in the absolute threshold",
            ],
            "correct_index": 1,
            "explanation": (
                "Signal detection theory separates sensitivity (d', the ability to tell signal "
                "from noise) from the response criterion (the willingness to say 'yes'). "
                "Constant d' means sensitivity did not change; the expectation made listeners "
                "adopt a more liberal criterion, which raises hits and false alarms together. "
                "Adaptation is a decline over time, and the absolute threshold is a sensory "
                "limit, neither of which fits identical stimuli with shifting 'yes' rates."
            ),
            "difficulty": "medium",
            "cognitive_level": "application",
            "subquestions": [
                {
                    "stem": "In signal detection theory, what does d' measure?",
                    "options": ["The observer's decision bias", "The ability to distinguish signal from noise", "The loudness of the tone"],
                    "correct_index": 1,
                    "explanation": "d' indexes sensitivity - how separable signal is from noise - independent of bias.",
                },
                {
                    "stem": "If d' is unchanged but a person says 'yes' more often, what changed?",
                    "options": ["Sensitivity", "The response criterion", "The physical stimulus"],
                    "correct_index": 1,
                    "explanation": "Only the decision criterion moved; sensitivity (d') was constant.",
                },
                {
                    "stem": "A more liberal criterion increases hits. What else does it increase?",
                    "options": ["Correct rejections", "False alarms", "Misses"],
                    "correct_index": 1,
                    "explanation": "Saying 'yes' more often yields more hits AND more false alarms.",
                },
            ],
        },
        {
            "aamc_category": "6A",
            "subtopic": "Weber's law",
            "stem": (
                "Experiment 3 found the smallest detectable weight difference grew in "
                "proportion to the standard (2 g at 100 g; 4 g at 200 g). This illustrates:"
            ),
            "options": [
                "Weber's law",
                "Signal detection theory",
                "Sensory adaptation",
                "The absolute threshold",
            ],
            "correct_index": 0,
            "explanation": (
                "Weber's law states the just-noticeable difference is a constant proportion of "
                "the standard stimulus (here about 2%). Signal detection theory concerns "
                "decision processes, adaptation is a decline in response to constant "
                "stimulation over time, and the absolute threshold is detection versus none - "
                "none of which describe a constant ratio between stimuli."
            ),
            "difficulty": "medium",
            "cognitive_level": "data-analysis",
            "subquestions": [
                {
                    "stem": "A 2 g difference was detectable at 100 g and a 4 g difference at 200 g. What stays constant?",
                    "options": ["The absolute grams", "The ratio of the difference to the standard", "Nothing"],
                    "correct_index": 1,
                    "explanation": "2/100 = 4/200 = 0.02; the proportion is fixed even though the grams differ.",
                },
                {
                    "stem": "A constant ratio (jnd / standard) is the signature of which principle?",
                    "options": ["Weber's law", "The absolute threshold"],
                    "correct_index": 0,
                    "explanation": "Weber's law: the jnd is a fixed fraction of the baseline stimulus.",
                },
            ],
        },
        {
            "aamc_category": "6A",
            "subtopic": "Sensory adaptation",
            "stem": (
                "Reported loudness of a continuous tone declined over minutes, yet an abrupt "
                "change was noticed at once. This best demonstrates:"
            ),
            "options": [
                "Proactive interference",
                "Sensory adaptation",
                "A shift in response criterion",
                "The all-or-none law",
            ],
            "correct_index": 1,
            "explanation": (
                "Sensory adaptation is a decline in sensitivity to an unchanging stimulus, "
                "which is why the steady tone faded while a change was detected immediately - "
                "the system is tuned to change. Proactive interference is a memory phenomenon, "
                "a criterion shift is a decision effect, and the all-or-none law describes "
                "neuronal firing, not perceived intensity over time."
            ),
            "difficulty": "easy",
            "cognitive_level": "comprehension",
            "subquestions": [
                {
                    "stem": "What happens to the perceived intensity of an unchanging stimulus over time?",
                    "options": ["It increases", "It decreases", "It stays the same"],
                    "correct_index": 1,
                    "explanation": "Constant stimulation leads to reduced responding - sensory adaptation.",
                },
                {
                    "stem": "The sensory system responds most strongly to what?",
                    "options": ["Constant stimulation", "Change in stimulation"],
                    "correct_index": 1,
                    "explanation": "Adaptation frees the system to signal changes, which carry information.",
                },
            ],
        },
        {
            "aamc_category": "6B",
            "subtopic": "Top-down processing / perceptual expectation",
            "stem": (
                "The 'rare/common' instruction changed what listeners reported hearing. This "
                "influence of expectation best exemplifies:"
            ),
            "options": [
                "Bottom-up processing",
                "Top-down processing",
                "Transduction",
                "The all-or-none law",
            ],
            "correct_index": 1,
            "explanation": (
                "Top-down processing is perception guided by expectations, context, and prior "
                "knowledge - here, the instruction about tone frequency. Bottom-up processing "
                "is driven by the raw stimulus features (unchanged across blocks), transduction "
                "is converting a stimulus into neural signals, and the all-or-none law concerns "
                "neuronal firing."
            ),
            "difficulty": "medium",
            "cognitive_level": "application",
            "subquestions": [
                {
                    "stem": "Bottom-up processing starts from the raw stimulus; top-down processing is guided by what?",
                    "options": ["Expectations and prior knowledge", "Receptor cells", "The optic nerve"],
                    "correct_index": 0,
                    "explanation": "Top-down perception is shaped by what we expect and already know.",
                },
                {
                    "stem": "The instruction changed expectations, not the stimulus. Which process does that engage?",
                    "options": ["Bottom-up", "Top-down"],
                    "correct_index": 1,
                    "explanation": "Changing expectations while holding the stimulus constant is a top-down effect.",
                },
            ],
        },
    ],
})

# ---------------------------------------------------------------------------
# Passage 2 - Memory: levels of processing, serial position, misinformation
# ---------------------------------------------------------------------------
PASSAGES.append({
    "passage": (
        "A memory researcher tested how the way information is studied affects later "
        "recall. In Phase 1, 90 undergraduates saw a list of 30 common nouns, one every "
        "three seconds. Each word was preceded by one of three questions: whether the "
        "word was printed in capital letters (structural), whether it rhymed with a "
        "target word (phonemic), or whether it fit meaningfully into a sentence "
        "(semantic). After a filled delay, participants took a surprise free-recall "
        "test.\n\n"
        "Recall rose steadily with the depth of processing: 18% for structural, 37% for "
        "phonemic, and 65% for semantic judgments. In addition, regardless of the "
        "processing condition, words from the beginning and end of the list were "
        "recalled better than words from the middle. When recall was delayed by 30 "
        "seconds of counting backward, the advantage for the last few items disappeared, "
        "but the advantage for the first few items remained.\n\n"
        "In Phase 2, participants watched a short video of a car approaching an "
        "intersection. Afterward, half were asked, 'How fast was the car going when it "
        "passed the yield sign?' though the video actually showed a stop sign. A week "
        "later, participants who had received the misleading question were far more "
        "likely to report having seen a yield sign than participants asked a neutral "
        "question. The researchers argued that memory is not a faithful recording but is "
        "encoded selectively and reconstructed at retrieval, so that later information "
        "can alter what is 'remembered.'"
    ),
    "passage_source": src("Ch. 8, Memory"),
    "questions": [
        {
            "aamc_category": "6B",
            "subtopic": "Levels of processing (encoding)",
            "stem": (
                "The rise in recall from structural to phonemic to semantic judgments best "
                "supports:"
            ),
            "options": [
                "The sensory register of the multi-store model",
                "The levels-of-processing effect (deeper encoding aids retention)",
                "State-dependent memory",
                "Proactive interference",
            ],
            "correct_index": 1,
            "explanation": (
                "Craik and Lockhart's levels-of-processing framework holds that deeper, more "
                "meaningful (semantic) encoding produces stronger memories than shallow "
                "(structural/phonemic) encoding - exactly the ordering in the data. The "
                "sensory register concerns very brief sensory storage, state-dependent memory "
                "concerns matching internal states, and proactive interference is older "
                "learning disrupting new learning."
            ),
            "difficulty": "medium",
            "cognitive_level": "data-analysis",
            "subquestions": [
                {
                    "stem": "Which judgment required thinking about the word's meaning?",
                    "options": ["Capital letters", "Rhyme", "Sentence fit"],
                    "correct_index": 2,
                    "explanation": "Fitting a word into a meaningful sentence is semantic (deep) processing.",
                },
                {
                    "stem": "Deeper (semantic) encoding produced which level of recall?",
                    "options": ["The lowest", "The highest"],
                    "correct_index": 1,
                    "explanation": "Semantic judgments yielded 65% recall, the highest of the three.",
                },
                {
                    "stem": "In the levels-of-processing view, what best predicts retention?",
                    "options": ["Depth/meaningfulness of encoding", "The font used", "The length of the delay"],
                    "correct_index": 0,
                    "explanation": "Meaningful, deep encoding is the key driver of durable memory.",
                },
            ],
        },
        {
            "aamc_category": "6B",
            "subtopic": "Serial position effect",
            "stem": (
                "The recency advantage vanished after a 30-second distractor while the primacy "
                "advantage remained. This indicates that:"
            ),
            "options": [
                "Recency reflects long-term store; primacy reflects short-term store",
                "Recency reflects short-term memory; primacy reflects long-term memory",
                "Both reflect short-term memory",
                "Both reflect sensory memory",
            ],
            "correct_index": 1,
            "explanation": (
                "The recency effect reflects items still held in short-term/working memory, so "
                "a distractor task that prevents rehearsal erases it. The primacy effect "
                "reflects early items rehearsed into long-term memory, which survives the "
                "delay. Thus the two ends of the serial-position curve arise from different "
                "stores, ruling out the options that assign them to the same store."
            ),
            "difficulty": "hard",
            "cognitive_level": "data-analysis",
            "subquestions": [
                {
                    "stem": "Which labels the memory advantages correctly?",
                    "options": ["Primacy (first items) and recency (last items)", "Recency (first items) and primacy (last items)"],
                    "correct_index": 0,
                    "explanation": "Primacy = better recall of the first items; recency = better recall of the last items.",
                },
                {
                    "stem": "A distractor task wiped out one effect. Which, and why?",
                    "options": ["Primacy, because those items were in long-term memory", "Recency, because those items were still in short-term memory"],
                    "correct_index": 1,
                    "explanation": "Recent items sat in fragile short-term memory and were lost when rehearsal stopped.",
                },
                {
                    "stem": "The surviving primacy effect reflects items rehearsed into what?",
                    "options": ["Long-term memory", "Sensory memory"],
                    "correct_index": 0,
                    "explanation": "Early items got extra rehearsal and were consolidated into long-term memory.",
                },
            ],
        },
        {
            "aamc_category": "6B",
            "subtopic": "Misinformation effect / reconstructive memory",
            "stem": (
                "Phase 2 showed a misleading question changed what participants later reported "
                "seeing. This best illustrates:"
            ),
            "options": [
                "Proactive interference",
                "The misinformation effect (reconstructive memory)",
                "Intact source monitoring",
                "Sensory adaptation",
            ],
            "correct_index": 1,
            "explanation": (
                "Loftus's misinformation effect occurs when post-event information distorts "
                "the memory of the original event, as when 'yield sign' wording led people to "
                "'remember' a yield sign. It supports reconstructive memory. Proactive "
                "interference involves prior learning, source monitoring here failed rather "
                "than stayed intact, and adaptation is a sensory phenomenon."
            ),
            "difficulty": "easy",
            "cognitive_level": "application",
            "subquestions": [
                {
                    "stem": "Did the misleading question change the original video or the later memory report?",
                    "options": ["The original video", "The later memory report"],
                    "correct_index": 1,
                    "explanation": "The event was fixed; only the reconstructed memory of it changed.",
                },
                {
                    "stem": "Post-event misleading information altering memory is called the ___ effect.",
                    "options": ["spacing", "misinformation", "testing"],
                    "correct_index": 1,
                    "explanation": "This is the classic misinformation effect.",
                },
                {
                    "stem": "This supports the view that memory is:",
                    "options": ["A perfect recording", "Reconstructed at retrieval"],
                    "correct_index": 1,
                    "explanation": "Memories are rebuilt (and can be reshaped) each time they are retrieved.",
                },
            ],
        },
        {
            "aamc_category": "6B",
            "subtopic": "Short-term memory duration",
            "stem": (
                "That the last few items were lost after 30 seconds of counting backward "
                "(before rehearsal) reflects the limited duration of:"
            ),
            "options": [
                "Long-term memory",
                "Short-term memory without rehearsal",
                "Procedural memory",
                "Semantic memory",
            ],
            "correct_index": 1,
            "explanation": (
                "Unrehearsed short-term memory decays within roughly 15-30 seconds, so a "
                "backward-counting distractor eliminates the most recent items. Long-term, "
                "procedural, and semantic memories are durable stores and would not vanish "
                "over such a brief filled delay."
            ),
            "difficulty": "medium",
            "cognitive_level": "comprehension",
            "subquestions": [
                {
                    "stem": "Counting backward prevents what?",
                    "options": ["Encoding into sensory memory", "Rehearsal"],
                    "correct_index": 1,
                    "explanation": "The distractor blocks rehearsal that would otherwise maintain the items.",
                },
                {
                    "stem": "Without rehearsal, short-term memory is lost within about:",
                    "options": ["A few seconds to half a minute", "Several hours"],
                    "correct_index": 0,
                    "explanation": "Short-term storage is brief - on the order of seconds - without rehearsal.",
                },
            ],
        },
    ],
})

# ---------------------------------------------------------------------------
# Passage 3 - Emotion & stress: two-factor theory, appraisal, GAS/cortisol
# ---------------------------------------------------------------------------
PASSAGES.append({
    "passage": (
        "Investigators examined how bodily arousal and its interpretation combine to "
        "produce emotion. In Study 1, 120 volunteers received an injection described as "
        "a vitamin; half actually received a mild dose of adrenaline (epinephrine), "
        "which raises heart rate and produces jitteriness, and half received saline. "
        "Within each group, some were accurately told to expect arousal symptoms and "
        "others were told nothing. Each participant then waited with a confederate who "
        "acted either euphoric or irritated. Aroused participants who had not been warned "
        "about the symptoms reported emotions matching the confederate's mood - euphoria "
        "or anger - more strongly than warned participants or saline controls. "
        "Participants who could attribute their arousal to the injection were less swayed "
        "by the confederate.\n\n"
        "In Study 2, the same volunteers completed a stressful mental-arithmetic task "
        "while salivary cortisol was sampled. Cortisol rose within 20 minutes, peaked, "
        "and then declined once the task ended. Participants who appraised the task as a "
        "'challenge' showed a smaller cortisol response than those who appraised it as a "
        "'threat,' despite identical task difficulty. Reported stress correlated with "
        "threat appraisal, not with objective performance.\n\n"
        "The authors linked Study 1 to a theory holding that emotion requires both "
        "physiological arousal and a cognitive label for that arousal, and linked Study "
        "2 to a model in which the same stressor produces different physiological "
        "responses depending on how it is appraised. They noted that the cortisol time "
        "course mirrored the mobilize-then-recover pattern of the body's general response "
        "to stressors."
    ),
    "passage_source": src("Ch. 10, Emotion and Motivation; Ch. 14, Stress and Health"),
    "questions": [
        {
            "aamc_category": "6C",
            "subtopic": "Two-factor (Schachter-Singer) theory of emotion",
            "stem": (
                "Study 1 - arousal plus the confederate's mood determined the emotion, and an "
                "available attribution weakened the effect - best supports:"
            ),
            "options": [
                "The James-Lange theory",
                "The Cannon-Bard theory",
                "The Schachter-Singer two-factor theory",
                "The facial-feedback hypothesis",
            ],
            "correct_index": 2,
            "explanation": (
                "Schachter and Singer's two-factor theory holds that emotion requires "
                "physiological arousal PLUS a cognitive label drawn from context; unexplained "
                "arousal took on the confederate's mood, while participants who blamed the "
                "injection had a non-emotional label and felt less. James-Lange ties each "
                "emotion to a specific bodily pattern, Cannon-Bard says arousal and emotion "
                "occur independently and simultaneously, and facial feedback concerns "
                "expressions driving emotion."
            ),
            "difficulty": "medium",
            "cognitive_level": "application",
            "subquestions": [
                {
                    "stem": "In Study 1, what two ingredients produced the emotion?",
                    "options": ["Arousal alone", "A cognitive label alone", "Arousal plus a label from the context"],
                    "correct_index": 2,
                    "explanation": "Both arousal and an interpretation of it were needed.",
                },
                {
                    "stem": "Which theory says emotion = physiological arousal + a cognitive interpretation of it?",
                    "options": ["James-Lange", "Schachter-Singer two-factor", "Cannon-Bard"],
                    "correct_index": 1,
                    "explanation": "That is precisely the two-factor theory.",
                },
                {
                    "stem": "Why were participants who blamed the injection less emotional?",
                    "options": ["They had no arousal", "They had a non-emotional label for their arousal"],
                    "correct_index": 1,
                    "explanation": "Attributing arousal to a shot supplies a non-emotional explanation, so no emotion label is needed.",
                },
            ],
        },
        {
            "aamc_category": "6C",
            "subtopic": "Distinguishing emotion theories",
            "stem": (
                "Which result argues AGAINST a pure James-Lange account (that a specific bodily "
                "state alone determines the specific emotion)?"
            ),
            "options": [
                "Arousal was required for emotion to occur",
                "Identical adrenaline arousal produced different emotions depending on context",
                "Saline controls reported little emotion",
                "Cortisol rose during the arithmetic task",
            ],
            "correct_index": 1,
            "explanation": (
                "James-Lange proposes a one-to-one mapping from a distinct bodily pattern to a "
                "distinct emotion. Because the SAME adrenaline arousal yielded euphoria or "
                "anger depending on the confederate, bodily state alone cannot determine the "
                "emotion - context/labeling matters. The other options are consistent with "
                "arousal-based theories generally and do not challenge James-Lange "
                "specifically."
            ),
            "difficulty": "hard",
            "cognitive_level": "application",
            "subquestions": [
                {
                    "stem": "Did aroused participants receive the same physiological manipulation (adrenaline) whether they felt euphoria or anger?",
                    "options": ["Yes, an identical injection", "No, different drugs"],
                    "correct_index": 0,
                    "explanation": "The arousal manipulation was the same; only the social context differed.",
                },
                {
                    "stem": "If identical arousal yields different emotions, can a specific bodily state alone determine the emotion?",
                    "options": ["Yes", "No - context/labeling must matter"],
                    "correct_index": 1,
                    "explanation": "Same body state, different emotion means the body state is not sufficient.",
                },
            ],
        },
        {
            "aamc_category": "6C",
            "subtopic": "Cognitive appraisal of stress (Lazarus)",
            "stem": (
                "In Study 2, identical tasks produced smaller cortisol responses under "
                "'challenge' than 'threat' appraisals. This best supports:"
            ),
            "options": [
                "That stress is a purely physical stimulus",
                "Lazarus's cognitive-appraisal model of stress",
                "The exhaustion stage of the general adaptation syndrome",
                "The Yerkes-Dodson law",
            ],
            "correct_index": 1,
            "explanation": (
                "Lazarus's appraisal model holds that the stress response depends on how a "
                "person evaluates a situation (threat vs. challenge), so identical tasks can "
                "produce different physiology - exactly the result. If stress were purely "
                "physical, appraisal would not matter; the exhaustion stage concerns prolonged "
                "stress; and Yerkes-Dodson relates arousal to performance, not appraisal to "
                "cortisol."
            ),
            "difficulty": "medium",
            "cognitive_level": "data-analysis",
            "subquestions": [
                {
                    "stem": "What differed between participants with small vs. large cortisol responses?",
                    "options": ["Task difficulty", "How they appraised the task"],
                    "correct_index": 1,
                    "explanation": "Difficulty was identical; appraisal (threat vs. challenge) differed.",
                },
                {
                    "stem": "A model in which appraisal shapes the stress response is credited to:",
                    "options": ["Selye", "Lazarus", "Zajonc"],
                    "correct_index": 1,
                    "explanation": "Richard Lazarus emphasized primary/secondary appraisal in stress.",
                },
            ],
        },
        {
            "aamc_category": "6C",
            "subtopic": "General adaptation syndrome (Selye) / HPA axis",
            "stem": (
                "The cortisol pattern - rising during the task, peaking, then declining after "
                "it ended - best mirrors which phases of Selye's general adaptation syndrome?"
            ),
            "options": [
                "Alarm, then resistance/recovery",
                "Exhaustion, then alarm",
                "Resistance only, with no recovery",
                "The parasympathetic 'rest and digest' response",
            ],
            "correct_index": 0,
            "explanation": (
                "Selye's general adaptation syndrome runs alarm (rapid mobilization) -> "
                "resistance -> exhaustion; the mobilize-then-recover cortisol curve matches the "
                "alarm and subsequent resistance/recovery, not exhaustion (which follows "
                "prolonged stress). Cortisol is released via the hypothalamic-pituitary-adrenal "
                "axis, a stress (not parasympathetic) response."
            ),
            "difficulty": "medium",
            "cognitive_level": "data-analysis",
            "subquestions": [
                {
                    "stem": "The body's initial mobilization to a stressor is which stage?",
                    "options": ["Alarm", "Exhaustion"],
                    "correct_index": 0,
                    "explanation": "The alarm stage is the immediate fight-or-flight mobilization.",
                },
                {
                    "stem": "Cortisol is released during stress via which axis?",
                    "options": ["The HPA (hypothalamic-pituitary-adrenal) axis", "The corticospinal tract"],
                    "correct_index": 0,
                    "explanation": "The HPA axis drives cortisol secretion from the adrenal cortex.",
                },
            ],
        },
    ],
})

# ---------------------------------------------------------------------------
# Passage 4 - Motivation & personality: overjustification, SDT, traits
# ---------------------------------------------------------------------------
PASSAGES.append({
    "passage": (
        "A team studied what sustains effort on a task. Ninety children who already "
        "enjoyed drawing were randomly assigned to three groups. The 'expected-reward' "
        "group was promised a certificate for drawing; the 'unexpected-reward' group "
        "drew and then received the same certificate as a surprise; the 'no-reward' "
        "group simply drew. Two weeks later, during free-play periods, observers "
        "unobtrusively recorded how much each child chose to draw. Children in the "
        "expected-reward group spent about half as much free time drawing as the other "
        "two groups, whose behavior did not differ.\n\n"
        "In a second study with adults, participants worked on solvable puzzles under "
        "one of two framings. Some were told the task measured 'innate intelligence'; "
        "others were told that effort and strategy drive success. After encountering "
        "difficult items, the 'effort' group persisted longer and reported greater "
        "interest, and this difference was largest among participants who scored high on "
        "a measure of conscientiousness.\n\n"
        "The researchers interpreted the children's result as evidence that offering an "
        "expected tangible reward for an already-enjoyable activity can reduce later "
        "voluntary engagement, because the behavior becomes attributed to the external "
        "incentive. They connected the adult result to a framework distinguishing "
        "motivation that arises from within the person from motivation driven by external "
        "consequences, and noted that a stable personality dimension moderated "
        "persistence. They cautioned that rewards are not universally harmful: unexpected "
        "rewards, and rewards for dull tasks, did not undermine engagement."
    ),
    "passage_source": src("Ch. 10, Emotion and Motivation; Ch. 11, Personality"),
    "questions": [
        {
            "aamc_category": "7A",
            "subtopic": "Overjustification effect",
            "stem": "The expected-reward group's reduced later drawing best illustrates:",
            "options": [
                "Negative reinforcement",
                "The overjustification effect",
                "Secondary reinforcement",
                "Learned helplessness",
            ],
            "correct_index": 1,
            "explanation": (
                "The overjustification effect occurs when an expected external reward for an "
                "already-intrinsically-enjoyable activity undermines later intrinsic "
                "motivation - here, halving voluntary drawing. Negative and secondary "
                "reinforcement would increase behavior, and learned helplessness follows "
                "uncontrollable aversive events, neither of which applies."
            ),
            "difficulty": "medium",
            "cognitive_level": "application",
            "subquestions": [
                {
                    "stem": "The children already enjoyed drawing. What was added in the expected-reward group?",
                    "options": ["A punishment", "An expected external reward"],
                    "correct_index": 1,
                    "explanation": "An expected tangible reward was introduced for an already-enjoyable act.",
                },
                {
                    "stem": "When an expected reward makes an enjoyable behavior feel externally driven, later intrinsic motivation:",
                    "options": ["Rises", "Drops"],
                    "correct_index": 1,
                    "explanation": "Intrinsic motivation is undermined - the hallmark of overjustification.",
                },
                {
                    "stem": "This is called the ___ effect.",
                    "options": ["overjustification", "contrast"],
                    "correct_index": 0,
                    "explanation": "Over-justifying the behavior with an external reward crowds out intrinsic interest.",
                },
            ],
        },
        {
            "aamc_category": "7A",
            "subtopic": "Intrinsic vs. extrinsic motivation",
            "stem": (
                "The framework contrasting motivation 'from within the person' with motivation "
                "'driven by external consequences' is:"
            ),
            "options": [
                "Drive-reduction theory",
                "Intrinsic vs. extrinsic motivation",
                "The Yerkes-Dodson law",
                "Incentive salience",
            ],
            "correct_index": 1,
            "explanation": (
                "Doing something for its own enjoyment is intrinsic motivation; doing it for a "
                "reward or to avoid punishment is extrinsic motivation. Drive-reduction "
                "concerns reducing biological needs, Yerkes-Dodson relates arousal to "
                "performance, and incentive salience is a neuroscience concept about "
                "reward 'wanting.'"
            ),
            "difficulty": "easy",
            "cognitive_level": "comprehension",
            "subquestions": [
                {
                    "stem": "Doing something for its own enjoyment is ___ motivation.",
                    "options": ["intrinsic", "extrinsic"],
                    "correct_index": 0,
                    "explanation": "Intrinsic motivation comes from internal satisfaction.",
                },
                {
                    "stem": "Doing something to gain a reward or avoid punishment is ___ motivation.",
                    "options": ["intrinsic", "extrinsic"],
                    "correct_index": 1,
                    "explanation": "Extrinsic motivation is driven by external consequences.",
                },
            ],
        },
        {
            "aamc_category": "7A",
            "subtopic": "Trait theory (Big Five)",
            "stem": (
                "That the effort-framing benefit was largest among highly conscientious "
                "participants draws on which approach to personality?"
            ),
            "options": [
                "The psychoanalytic approach",
                "The trait (Big Five) approach",
                "The humanistic approach",
                "The behaviorist approach",
            ],
            "correct_index": 1,
            "explanation": (
                "Conscientiousness is one of the Big Five (OCEAN) traits, stable dimensions on "
                "which people differ - the trait approach. The psychoanalytic approach "
                "emphasizes unconscious conflict, the humanistic approach emphasizes "
                "self-actualization, and the behaviorist approach emphasizes learning "
                "histories rather than trait dimensions."
            ),
            "difficulty": "easy",
            "cognitive_level": "application",
            "subquestions": [
                {
                    "stem": "Conscientiousness (organized, persistent, disciplined) is one of the:",
                    "options": ["Freudian psychosexual stages", "Big Five traits", "defense mechanisms"],
                    "correct_index": 1,
                    "explanation": "Conscientiousness is a Big Five dimension.",
                },
                {
                    "stem": "Trait theories describe personality as:",
                    "options": ["unconscious conflicts", "stable dimensions on which people differ"],
                    "correct_index": 1,
                    "explanation": "Traits are enduring dimensions used to describe and predict behavior.",
                },
            ],
        },
        {
            "aamc_category": "7A",
            "subtopic": "Beliefs about ability and achievement motivation",
            "stem": (
                "That difficulty increased persistence in the 'effort' framing but not the "
                "'intelligence' framing relates most to which idea?"
            ),
            "options": [
                "Beliefs about the causes of success shape motivation (mindset)",
                "Homeostatic drive reduction",
                "The neuronal refractory period",
                "The mere-exposure effect",
            ],
            "correct_index": 0,
            "explanation": (
                "Whether people attribute success to malleable effort/strategy or to fixed "
                "ability shapes how they respond to difficulty; an effort belief sustains "
                "persistence after setbacks. Drive reduction concerns biological needs, the "
                "refractory period is a neuronal property, and mere exposure is about "
                "familiarity increasing liking."
            ),
            "difficulty": "medium",
            "cognitive_level": "application",
            "subquestions": [
                {
                    "stem": "The two groups differed in what they believed drives success: fixed intelligence vs. ___.",
                    "options": ["luck", "effort and strategy"],
                    "correct_index": 1,
                    "explanation": "The contrast was a fixed-ability belief vs. an effort/strategy belief.",
                },
                {
                    "stem": "Believing effort drives success tends to ___ persistence after failure.",
                    "options": ["increase", "decrease"],
                    "correct_index": 0,
                    "explanation": "An effort belief frames setbacks as surmountable, sustaining persistence.",
                },
            ],
        },
    ],
})

# ---------------------------------------------------------------------------
# Passage 5 - Social influence: conformity, social facilitation, bystander
# ---------------------------------------------------------------------------
PASSAGES.append({
    "passage": (
        "Researchers ran three studies of behavior in groups. In Study 1, a participant "
        "judged which of three comparison lines matched a standard line, answering aloud "
        "after several confederates. On critical trials the confederates unanimously gave "
        "an obviously wrong answer. Participants conformed to the wrong answer on about "
        "35% of critical trials, and three-quarters conformed at least once; conformity "
        "fell sharply when a single confederate broke from the majority. Most conformers "
        "later said they knew the group was wrong but did not want to stand out.\n\n"
        "In Study 2, participants completed either a simple, well-practiced task or a "
        "complex, unfamiliar task, alone or in front of an audience. An audience improved "
        "performance on the simple task but worsened it on the complex task.\n\n"
        "In Study 3, participants heard what sounded like a fellow participant having a "
        "medical emergency in another room. When participants believed they were the only "
        "witness, 85% sought help within a minute; when they believed four others were "
        "also present, only 31% did, and those who helped took longer. Interviews "
        "suggested that the presence of others reduced each individual's felt "
        "responsibility.\n\n"
        "The authors distinguished going along with a group to fit in from the effect of "
        "an audience on task performance, and linked Study 3 to a well-documented "
        "reduction in helping as the number of bystanders rises. They emphasized that "
        "these effects reflect the social situation rather than stable personality "
        "differences among the participants."
    ),
    "passage_source": src("Ch. 12, Social Psychology"),
    "questions": [
        {
            "aamc_category": "7B",
            "subtopic": "Conformity (normative social influence)",
            "stem": (
                "Participants in Study 1 conforming despite privately knowing the answer was "
                "wrong best reflects:"
            ),
            "options": [
                "Informational social influence",
                "Normative social influence",
                "Obedience to authority",
                "Group polarization",
            ],
            "correct_index": 1,
            "explanation": (
                "Normative social influence is conforming to gain acceptance or avoid "
                "standing out, which is exactly what conformers described. Informational "
                "influence is conforming because you believe the group is more accurate; "
                "obedience involves orders from an authority; and group polarization is "
                "discussion making views more extreme."
            ),
            "difficulty": "medium",
            "cognitive_level": "application",
            "subquestions": [
                {
                    "stem": "Conformers said they knew the group was wrong but did not want to stand out. Were they seeking correct information or social acceptance?",
                    "options": ["Correct information", "Social acceptance"],
                    "correct_index": 1,
                    "explanation": "Their motive was fitting in, not getting the answer right.",
                },
                {
                    "stem": "Conforming to gain acceptance / avoid disapproval is ___ social influence.",
                    "options": ["informational", "normative"],
                    "correct_index": 1,
                    "explanation": "Normative influence is about social approval.",
                },
                {
                    "stem": "Conforming because you think the group knows better (for accuracy) would instead be ___.",
                    "options": ["informational", "normative"],
                    "correct_index": 0,
                    "explanation": "Seeking accuracy from others is informational influence.",
                },
            ],
        },
        {
            "aamc_category": "7B",
            "subtopic": "Unanimity and conformity",
            "stem": (
                "Conformity 'fell sharply when a single confederate broke from the majority.' "
                "This shows conformity depends strongly on:"
            ),
            "options": [
                "The group's unanimity",
                "The difficulty of the perceptual task",
                "The participant's self-esteem",
                "The size of the monetary reward",
            ],
            "correct_index": 0,
            "explanation": (
                "Losing unanimity - even one dissenter - dramatically reduces conformity, the "
                "key manipulation here. The perceptual task was easy and unchanged, no reward "
                "was involved, and the passage attributes the drop to the broken consensus, "
                "not to self-esteem."
            ),
            "difficulty": "medium",
            "cognitive_level": "data-analysis",
            "subquestions": [
                {
                    "stem": "What changed when one confederate dissented?",
                    "options": ["The group was no longer unanimous", "The task got easier"],
                    "correct_index": 0,
                    "explanation": "A single dissenter breaks the group's unanimity.",
                },
                {
                    "stem": "A single ally / loss of unanimity ___ conformity.",
                    "options": ["increases", "reduces"],
                    "correct_index": 1,
                    "explanation": "Breaking unanimity sharply reduces conformity pressure.",
                },
            ],
        },
        {
            "aamc_category": "7B",
            "subtopic": "Social facilitation",
            "stem": (
                "Study 2's pattern - an audience helps simple tasks but hurts complex ones - is "
                "the classic finding of:"
            ),
            "options": [
                "Social loafing",
                "Social facilitation",
                "Deindividuation",
                "Groupthink",
            ],
            "correct_index": 1,
            "explanation": (
                "Social facilitation: the presence of others boosts performance on simple/"
                "well-learned tasks (the dominant response) but impairs it on complex/novel "
                "tasks. Social loafing is reduced individual effort in groups, deindividuation "
                "is loss of self-awareness in crowds, and groupthink is flawed group "
                "decision-making."
            ),
            "difficulty": "medium",
            "cognitive_level": "application",
            "subquestions": [
                {
                    "stem": "The audience improved which task and worsened which?",
                    "options": ["Improved simple; worsened complex", "Improved complex; worsened simple"],
                    "correct_index": 0,
                    "explanation": "Arousal from an audience aids dominant (well-learned) responses and hurts novel ones.",
                },
                {
                    "stem": "This audience effect on performance is called:",
                    "options": ["social loafing", "social facilitation"],
                    "correct_index": 1,
                    "explanation": "The performance-modulating presence of others is social facilitation.",
                },
            ],
        },
        {
            "aamc_category": "8C",
            "subtopic": "Bystander effect / diffusion of responsibility",
            "stem": (
                "The drop from 85% to 31% helping as more witnesses were believed present "
                "illustrates:"
            ),
            "options": [
                "Social loafing on a shared physical task",
                "The bystander effect via diffusion of responsibility",
                "Informational social influence",
                "Altruism driven by inclusive fitness",
            ],
            "correct_index": 1,
            "explanation": (
                "The bystander effect is reduced helping as group size grows, driven here by "
                "diffusion of responsibility (each person feels less personally responsible). "
                "Social loafing concerns effort on a joint task, informational influence is "
                "about accuracy, and inclusive fitness concerns helping genetic relatives - "
                "none of which the interviews indicated."
            ),
            "difficulty": "medium",
            "cognitive_level": "data-analysis",
            "subquestions": [
                {
                    "stem": "As the number of believed witnesses rose, helping:",
                    "options": ["rose", "fell"],
                    "correct_index": 1,
                    "explanation": "Helping dropped from 85% (alone) to 31% (with others believed present).",
                },
                {
                    "stem": "Each person feeling less personally responsible when others are present is called:",
                    "options": ["diffusion of responsibility", "the just-world hypothesis"],
                    "correct_index": 0,
                    "explanation": "Responsibility is spread across bystanders, so each feels less of it.",
                },
                {
                    "stem": "This reduction in helping as bystanders increase is the ___ effect.",
                    "options": ["bystander", "halo"],
                    "correct_index": 0,
                    "explanation": "It is the bystander effect.",
                },
            ],
        },
        {
            "aamc_category": "7B",
            "subtopic": "Power of the situation",
            "stem": (
                "The authors' emphasis that these effects 'reflect the social situation rather "
                "than stable personality differences' aligns with which broad claim of social "
                "psychology?"
            ),
            "options": [
                "Behavior is determined mainly by fixed traits",
                "Situations exert powerful influence on behavior",
                "The fundamental attribution error is always accurate",
                "Genetics determine conformity",
            ],
            "correct_index": 1,
            "explanation": (
                "A central lesson of social psychology is the power of the situation to shape "
                "behavior, which these three studies illustrate. The trait-only and "
                "genetic-determinism options contradict the authors' point, and the "
                "fundamental attribution error is precisely the mistake (over-attributing to "
                "disposition) these results warn against."
            ),
            "difficulty": "easy",
            "cognitive_level": "comprehension",
            "subquestions": [
                {
                    "stem": "Did the studies attribute behavior to who the people were, or to the situation?",
                    "options": ["Who they were", "The situation"],
                    "correct_index": 1,
                    "explanation": "The effects came from situational structure, not personality.",
                },
                {
                    "stem": "Over-attributing others' behavior to personality while ignoring the situation is the ___ (which these results caution against).",
                    "options": ["fundamental attribution error", "mere-exposure effect"],
                    "correct_index": 0,
                    "explanation": "The fundamental attribution error underweights situational causes.",
                },
            ],
        },
    ],
})

# ---------------------------------------------------------------------------
# Passage 6 - Attitude change: elaboration likelihood model, dissonance
# ---------------------------------------------------------------------------
PASSAGES.append({
    "passage": (
        "A study examined how persuasive messages change attitudes. Undergraduates read "
        "an editorial advocating a new campus exam policy. The message was either strong "
        "(well-reasoned arguments) or weak (superficial slogans), and was attributed "
        "either to a distinguished professor or to a first-year student. Crucially, half "
        "the participants were told the policy would take effect next year (high personal "
        "relevance) and half were told it would begin in a decade (low relevance).\n\n"
        "Among high-relevance readers, attitude change depended almost entirely on "
        "argument strength and hardly at all on the source; among low-relevance readers, "
        "the reverse held - the prestigious source mattered, but argument quality did "
        "not. A follow-up a week later showed that attitudes formed by high-relevance "
        "readers persisted and better predicted sign-up behavior than those of "
        "low-relevance readers.\n\n"
        "In a second study, participants who volunteered to argue publicly for a position "
        "they privately opposed later shifted their private attitudes toward that "
        "position - but only when they felt they had freely chosen to do so and were paid "
        "little. Those paid a large sum, or who felt coerced, showed no attitude "
        "change.\n\n"
        "The authors mapped the first study onto a dual-route model of persuasion: one "
        "route processes the substance of a message when motivation is high, while the "
        "other relies on surface cues when motivation is low. They explained the second "
        "study as the reduction of an uncomfortable inconsistency between behavior and "
        "belief, resolved by changing the belief when the behavior could not be justified "
        "by an external incentive."
    ),
    "passage_source": src("Ch. 12, Social Psychology"),
    "questions": [
        {
            "aamc_category": "7C",
            "subtopic": "Elaboration likelihood model (central route)",
            "stem": (
                "High-relevance readers' reliance on argument strength reflects which route of "
                "the elaboration likelihood model?"
            ),
            "options": [
                "The peripheral route",
                "The central route",
                "Classical conditioning",
                "The mere-exposure effect",
            ],
            "correct_index": 1,
            "explanation": (
                "In the elaboration likelihood model, motivated (here, high-relevance) "
                "recipients take the central route, effortfully evaluating argument quality. "
                "The peripheral route relies on surface cues such as source prestige. "
                "Classical conditioning and mere exposure are different attitude-formation "
                "mechanisms."
            ),
            "difficulty": "medium",
            "cognitive_level": "data-analysis",
            "subquestions": [
                {
                    "stem": "High-relevance readers were persuaded by what?",
                    "options": ["The source's prestige", "The quality of the arguments"],
                    "correct_index": 1,
                    "explanation": "They responded to argument strength, not the source.",
                },
                {
                    "stem": "Effortful processing of a message's substance is the ___ route.",
                    "options": ["central", "peripheral"],
                    "correct_index": 0,
                    "explanation": "The central route involves high elaboration on content.",
                },
            ],
        },
        {
            "aamc_category": "7C",
            "subtopic": "Elaboration likelihood model (peripheral route)",
            "stem": (
                "Low-relevance readers being swayed by the source's prestige rather than "
                "argument quality exemplifies:"
            ),
            "options": [
                "The central route",
                "The peripheral route",
                "Cognitive dissonance",
                "The foot-in-the-door technique",
            ],
            "correct_index": 1,
            "explanation": (
                "Unmotivated recipients take the peripheral route, leaning on surface cues "
                "like who delivered the message. The central route would attend to argument "
                "quality; cognitive dissonance and foot-in-the-door are separate phenomena "
                "not at issue here."
            ),
            "difficulty": "medium",
            "cognitive_level": "application",
            "subquestions": [
                {
                    "stem": "Low-relevance readers relied on a surface cue - who said it. Is that deep or shallow processing?",
                    "options": ["Deep", "Shallow"],
                    "correct_index": 1,
                    "explanation": "Using source cues instead of content is shallow processing.",
                },
                {
                    "stem": "Relying on surface cues (source, attractiveness) is the ___ route.",
                    "options": ["central", "peripheral"],
                    "correct_index": 1,
                    "explanation": "Peripheral processing uses heuristic cues.",
                },
            ],
        },
        {
            "aamc_category": "7C",
            "subtopic": "Durability of attitude change",
            "stem": (
                "That high-relevance (central-route) attitudes persisted longer and better "
                "predicted behavior supports which generalization?"
            ),
            "options": [
                "Peripheral-route attitudes are more durable",
                "Central-route attitude change is more durable and predictive of behavior",
                "Attitudes never predict behavior",
                "Source cues create the most lasting change",
            ],
            "correct_index": 1,
            "explanation": (
                "Central-route change, built on effortful processing, is generally more "
                "durable, resistant to counter-persuasion, and predictive of behavior - "
                "matching the week-later sign-up data. The other options contradict the "
                "findings or overstate the role of peripheral cues."
            ),
            "difficulty": "medium",
            "cognitive_level": "data-analysis",
            "subquestions": [
                {
                    "stem": "Which readers' attitudes better predicted later sign-up?",
                    "options": ["High-relevance (central route)", "Low-relevance (peripheral route)"],
                    "correct_index": 0,
                    "explanation": "Central-route attitudes better predicted behavior.",
                },
                {
                    "stem": "Central-route change tends to be ___ than peripheral-route change.",
                    "options": ["weaker and briefer", "stronger and longer-lasting"],
                    "correct_index": 1,
                    "explanation": "Effortful, content-based change is more enduring.",
                },
            ],
        },
        {
            "aamc_category": "7C",
            "subtopic": "Cognitive dissonance (insufficient justification)",
            "stem": (
                "Study 2's result - attitude shift only with free choice and small pay - is the "
                "signature of:"
            ),
            "options": [
                "Self-perception driven by large incentives",
                "Cognitive dissonance reduction under insufficient justification",
                "Operant reinforcement of the essay behavior",
                "Obedience to the experimenter",
            ],
            "correct_index": 1,
            "explanation": (
                "Festinger's cognitive dissonance theory predicts that freely arguing against "
                "one's beliefs for little pay creates discomfort that cannot be blamed on the "
                "reward (insufficient justification), so people change the attitude. Large pay "
                "provides sufficient external justification, eliminating dissonance. "
                "Reinforcement or obedience would not require the free-choice/low-pay pattern."
            ),
            "difficulty": "hard",
            "cognitive_level": "application",
            "subquestions": [
                {
                    "stem": "Arguing publicly against one's private belief creates an uncomfortable:",
                    "options": ["reward", "inconsistency between behavior and belief"],
                    "correct_index": 1,
                    "explanation": "That inconsistency is cognitive dissonance.",
                },
                {
                    "stem": "With little pay, the behavior cannot be blamed on money, so to reduce discomfort people change their:",
                    "options": ["behavior", "attitude"],
                    "correct_index": 1,
                    "explanation": "They bring the attitude in line with the behavior.",
                },
                {
                    "stem": "Large pay provides ___ justification, so no attitude change is needed.",
                    "options": ["insufficient", "sufficient"],
                    "correct_index": 1,
                    "explanation": "Ample external reward justifies the behavior, so dissonance is low.",
                },
            ],
        },
    ],
})

# ---------------------------------------------------------------------------
# Passage 7 - Self-concept & attribution (self-efficacy, locus, FAE)
# ---------------------------------------------------------------------------
PASSAGES.append({
    "passage": (
        "Researchers studied how people view themselves and explain behavior. In Study "
        "1, community volunteers completed a scale measuring their belief that they could "
        "organize and execute the actions needed to reach specific goals. Independently, "
        "they rated how much they felt their life outcomes were controlled by their own "
        "actions versus by luck or powerful others. Volunteers high on the first measure "
        "attempted harder tasks, persisted longer after setbacks, and reported less "
        "anxiety. Those who attributed outcomes mostly to outside forces set fewer goals "
        "and gave up sooner.\n\n"
        "In Study 2, participants read vignettes about a student who failed an exam. When "
        "explaining the student's failure, observers most often cited the student's "
        "laziness or low ability, rarely mentioning the situation (an unfair test, a "
        "family emergency). Yet when participants recalled a time they themselves had "
        "failed, they overwhelmingly cited situational causes. In a variation, "
        "participants watched a peer perform poorly under obvious time pressure; even so, "
        "most still rated the peer as low in ability.\n\n"
        "The authors linked Study 1 to two related constructs: a person's belief in their "
        "capability to succeed at specific tasks, and a general expectancy about whether "
        "outcomes are internally or externally controlled. They interpreted Study 2 as "
        "showing a systematic bias in how observers explain others' behavior, together "
        "with a divergence between how people explain their own versus others' outcomes. "
        "They stressed that these attribution tendencies operate even when situational "
        "information is clearly available."
    ),
    "passage_source": src("Ch. 11, Personality; Ch. 12, Social Psychology"),
    "questions": [
        {
            "aamc_category": "8A",
            "subtopic": "Self-efficacy (Bandura)",
            "stem": (
                "The first measure in Study 1 - belief in one's capability to execute the "
                "actions needed to reach goals - is:"
            ),
            "options": [
                "Self-esteem",
                "Self-efficacy",
                "Locus of control",
                "The self-serving bias",
            ],
            "correct_index": 1,
            "explanation": (
                "Bandura's self-efficacy is the belief in one's capability to succeed at "
                "specific tasks, which predicts effort and persistence - as observed. "
                "Self-esteem is global self-worth, locus of control is the second construct in "
                "the study, and the self-serving bias is an attribution pattern."
            ),
            "difficulty": "medium",
            "cognitive_level": "application",
            "subquestions": [
                {
                    "stem": "The measure concerned belief in one's ability to succeed at specific tasks, not overall self-worth. That is:",
                    "options": ["self-esteem", "self-efficacy"],
                    "correct_index": 1,
                    "explanation": "Task-specific capability belief is self-efficacy.",
                },
                {
                    "stem": "High self-efficacy predicted what after setbacks?",
                    "options": ["giving up sooner", "persisting longer"],
                    "correct_index": 1,
                    "explanation": "Self-efficacy supports persistence in the face of difficulty.",
                },
            ],
        },
        {
            "aamc_category": "8A",
            "subtopic": "Locus of control (Rotter)",
            "stem": (
                "Rating how much outcomes are controlled by one's own actions versus luck or "
                "powerful others measures the construct of:"
            ),
            "options": [
                "Self-efficacy",
                "Locus of control",
                "Self-concept",
                "Self-handicapping",
            ],
            "correct_index": 1,
            "explanation": (
                "Rotter's locus of control is a general expectancy about whether outcomes are "
                "internally (own actions) or externally (luck, others) controlled. "
                "Self-efficacy is task-specific capability, self-concept is one's overall "
                "self-description, and self-handicapping is creating obstacles to excuse "
                "failure."
            ),
            "difficulty": "medium",
            "cognitive_level": "comprehension",
            "subquestions": [
                {
                    "stem": "Believing you control your outcomes is a(n) ___ locus of control.",
                    "options": ["internal", "external"],
                    "correct_index": 0,
                    "explanation": "Internal locus attributes outcomes to one's own actions.",
                },
                {
                    "stem": "Believing luck or powerful others control outcomes is a(n) ___ locus of control.",
                    "options": ["internal", "external"],
                    "correct_index": 1,
                    "explanation": "External locus attributes outcomes to outside forces.",
                },
            ],
        },
        {
            "aamc_category": "8B",
            "subtopic": "Fundamental attribution error",
            "stem": (
                "Observers blaming the failing student's laziness or ability while ignoring the "
                "situation illustrates:"
            ),
            "options": [
                "The self-serving bias",
                "The fundamental attribution error",
                "The just-world hypothesis",
                "The halo effect",
            ],
            "correct_index": 1,
            "explanation": (
                "The fundamental attribution error is over-attributing others' behavior to "
                "disposition while underweighting situational causes - seen even under obvious "
                "time pressure. The self-serving bias concerns explaining one's own outcomes, "
                "the just-world hypothesis is believing people get what they deserve, and the "
                "halo effect is one trait coloring overall judgment."
            ),
            "difficulty": "medium",
            "cognitive_level": "data-analysis",
            "subquestions": [
                {
                    "stem": "In explaining someone else's behavior, observers over-weighted which kind of cause?",
                    "options": ["situational", "dispositional (personal)"],
                    "correct_index": 1,
                    "explanation": "They favored personal/dispositional explanations.",
                },
                {
                    "stem": "Over-attributing others' behavior to disposition and underweighting the situation is the:",
                    "options": ["fundamental attribution error", "mere-exposure effect"],
                    "correct_index": 0,
                    "explanation": "That is the fundamental attribution error (correspondence bias).",
                },
            ],
        },
        {
            "aamc_category": "8B",
            "subtopic": "Actor-observer bias",
            "stem": (
                "The divergence - situational explanations for one's OWN failure but "
                "dispositional explanations for OTHERS' - is:"
            ),
            "options": [
                "The actor-observer bias",
                "The fundamental attribution error alone",
                "The false-consensus effect",
                "Self-efficacy",
            ],
            "correct_index": 0,
            "explanation": (
                "The actor-observer bias is the tendency to attribute our own behavior to the "
                "situation but others' behavior to their dispositions - exactly the pattern "
                "across the two vignettes. The fundamental attribution error names only the "
                "observer side, the false-consensus effect is overestimating how many share "
                "our views, and self-efficacy is unrelated."
            ),
            "difficulty": "hard",
            "cognitive_level": "application",
            "subquestions": [
                {
                    "stem": "For their own failure, participants cited which causes, and for others' failure, which?",
                    "options": ["Situational for self; dispositional for others", "Dispositional for self; situational for others"],
                    "correct_index": 0,
                    "explanation": "Own failure -> situation; others' failure -> disposition.",
                },
                {
                    "stem": "This difference between explaining one's own versus others' behavior is the ___ bias.",
                    "options": ["actor-observer", "halo"],
                    "correct_index": 0,
                    "explanation": "It is the actor-observer asymmetry.",
                },
            ],
        },
        {
            "aamc_category": "8A",
            "subtopic": "Development of the self (Mead)",
            "stem": (
                "According to George Herbert Mead, the internalized sense of the general "
                "expectations of society - which children increasingly take into account - is:"
            ),
            "options": [
                "The 'I'",
                "The generalized other",
                "The looking-glass self",
                "The id",
            ],
            "correct_index": 1,
            "explanation": (
                "Mead's 'generalized other' is the internalized attitudes and expectations of "
                "society as a whole. The 'I' is the spontaneous, unsocialized self (contrasted "
                "with the socialized 'me'); the looking-glass self is Cooley's concept; and the "
                "id is a Freudian structure."
            ),
            "difficulty": "medium",
            "cognitive_level": "comprehension",
            "subquestions": [
                {
                    "stem": "Mead distinguished the spontaneous '___' from the socialized 'me'.",
                    "options": ["I", "superego"],
                    "correct_index": 0,
                    "explanation": "The 'I' is the impulsive, unsocialized aspect of the self.",
                },
                {
                    "stem": "The internalized attitudes of the whole community form the:",
                    "options": ["generalized other", "sick role"],
                    "correct_index": 0,
                    "explanation": "Taking the role of the generalized other reflects society's expectations.",
                },
            ],
        },
    ],
})

# ---------------------------------------------------------------------------
# Passage 8 - Stereotype threat & impression management (dramaturgy)
# ---------------------------------------------------------------------------
PASSAGES.append({
    "passage": (
        "A study tested how awareness of a negative stereotype affects performance and "
        "self-presentation. Two groups of equally qualified students took the same "
        "difficult verbal test. In the 'diagnostic' condition, the test was described as "
        "measuring underlying ability; in the 'nondiagnostic' condition, it was described "
        "as a problem-solving exercise unrelated to ability. Students from a group "
        "stereotyped as weaker in the domain scored lower than others in the diagnostic "
        "condition but scored equally in the nondiagnostic condition. Merely asking "
        "students to record their group membership before a diagnostic test reproduced "
        "the gap.\n\n"
        "In a second study, participants prepared for a mock interview. Told the "
        "interviewer valued modesty, they described themselves cautiously; told the "
        "interviewer admired confidence, the same participants emphasized their "
        "strengths. Observers who saw only one version rated the participants "
        "accordingly, and participants reported deliberately tailoring the impression "
        "they gave.\n\n"
        "The authors interpreted the first study as evidence that the fear of confirming "
        "a negative group stereotype can itself depress performance, independent of "
        "ability, and that subtle cues activate this fear. They interpreted the second as "
        "an example of managing the impression one presents to different audiences, "
        "comparing it to an actor shifting performances between a front region and a back "
        "region. They cautioned that persistent performance gaps in real settings may "
        "partly reflect such situational threats and unequal conditions rather than fixed "
        "differences in ability between groups."
    ),
    "passage_source": src("Ch. 12, Social Psychology", SOC),
    "questions": [
        {
            "aamc_category": "8B",
            "subtopic": "Stereotype threat",
            "stem": (
                "The lower scores only in the 'diagnostic' condition, erased in the "
                "'nondiagnostic' condition, best demonstrate:"
            ),
            "options": [
                "A genuine ability difference between groups",
                "Stereotype threat",
                "The mere-exposure effect",
                "Deindividuation",
            ],
            "correct_index": 1,
            "explanation": (
                "Stereotype threat is the fear of confirming a negative stereotype about one's "
                "group, which can depress performance independent of ability - hence the gap "
                "appears only when the test is framed as diagnostic of ability. A true ability "
                "difference would appear in both conditions; mere exposure and deindividuation "
                "are unrelated."
            ),
            "difficulty": "medium",
            "cognitive_level": "data-analysis",
            "subquestions": [
                {
                    "stem": "Did the stereotyped group score lower in both conditions, or only when the test was called diagnostic of ability?",
                    "options": ["Both conditions", "Only the diagnostic condition"],
                    "correct_index": 1,
                    "explanation": "The gap appeared only under the ability-diagnostic framing.",
                },
                {
                    "stem": "If ability were truly lower, the gap would appear in both conditions. Its disappearance points to a ___ cause.",
                    "options": ["genetic", "situational/psychological"],
                    "correct_index": 1,
                    "explanation": "A frame-dependent gap indicates a situational, not fixed, cause.",
                },
                {
                    "stem": "Fear of confirming a negative stereotype impairing performance is called:",
                    "options": ["stereotype threat", "the self-serving bias"],
                    "correct_index": 0,
                    "explanation": "This is stereotype threat.",
                },
            ],
        },
        {
            "aamc_category": "8C",
            "subtopic": "Impression management / self-presentation",
            "stem": (
                "Participants tailoring their self-descriptions to what each interviewer valued "
                "exemplifies:"
            ),
            "options": [
                "Cognitive dissonance",
                "Impression management (self-presentation)",
                "The actor-observer bias",
                "Social loafing",
            ],
            "correct_index": 1,
            "explanation": (
                "Impression management is controlling the impression others form of us, here "
                "by adjusting self-presentation to the audience's values. Dissonance concerns "
                "internal inconsistency, the actor-observer bias concerns attribution, and "
                "social loafing concerns reduced group effort."
            ),
            "difficulty": "easy",
            "cognitive_level": "application",
            "subquestions": [
                {
                    "stem": "Participants changed how they portrayed themselves depending on the:",
                    "options": ["audience", "weather"],
                    "correct_index": 0,
                    "explanation": "They adapted to the interviewer's stated preferences.",
                },
                {
                    "stem": "Controlling the impression others form of you is:",
                    "options": ["impression management", "groupthink"],
                    "correct_index": 0,
                    "explanation": "That is impression management / self-presentation.",
                },
            ],
        },
        {
            "aamc_category": "8C",
            "subtopic": "Dramaturgical approach (Goffman)",
            "stem": (
                "The comparison to 'an actor shifting performances between a front region and a "
                "back region' refers to whose dramaturgical approach?"
            ),
            "options": [
                "Leon Festinger",
                "Erving Goffman",
                "Stanley Milgram",
                "Jean Piaget",
            ],
            "correct_index": 1,
            "explanation": (
                "Goffman's dramaturgical approach frames social life as theater, with front "
                "stage (performing for an audience) and back stage (relaxing out of view). "
                "Festinger (dissonance), Milgram (obedience), and Piaget (cognitive "
                "development) are associated with different ideas."
            ),
            "difficulty": "medium",
            "cognitive_level": "comprehension",
            "subquestions": [
                {
                    "stem": "The 'front region' (front stage) is where we:",
                    "options": ["perform for an audience", "relax out of view"],
                    "correct_index": 0,
                    "explanation": "Front stage is the performance region.",
                },
                {
                    "stem": "This theatrical metaphor for social life is credited to:",
                    "options": ["Goffman", "Skinner"],
                    "correct_index": 0,
                    "explanation": "Erving Goffman developed the dramaturgical approach.",
                },
            ],
        },
        {
            "aamc_category": "8B",
            "subtopic": "Stereotype vs. prejudice vs. discrimination",
            "stem": (
                "The negative belief that a group is 'weaker in the domain' is best labeled a:"
            ),
            "options": [
                "prejudice (an attitude/feeling)",
                "stereotype (a cognitive belief)",
                "discrimination (a behavior)",
                "social norm",
            ],
            "correct_index": 1,
            "explanation": (
                "A stereotype is a cognitive belief/generalization about a group. Prejudice is "
                "the affective attitude (feeling) toward a group, discrimination is the "
                "behavioral act of unequal treatment, and a norm is a shared expectation for "
                "behavior."
            ),
            "difficulty": "easy",
            "cognitive_level": "comprehension",
            "subquestions": [
                {
                    "stem": "A generalized belief about a group's characteristics is a:",
                    "options": ["stereotype", "discrimination"],
                    "correct_index": 0,
                    "explanation": "Beliefs are the cognitive component: stereotypes.",
                },
                {
                    "stem": "Acting on such a belief to treat the group unfairly would be:",
                    "options": ["prejudice", "discrimination"],
                    "correct_index": 1,
                    "explanation": "Behavioral unequal treatment is discrimination.",
                },
            ],
        },
        {
            "aamc_category": "10A",
            "subtopic": "Explaining group inequality (situational vs. individual)",
            "stem": (
                "The authors' caution that real-world performance gaps 'may partly reflect "
                "situational threats and unequal conditions rather than fixed differences' is "
                "most relevant to debates about:"
            ),
            "options": [
                "The demographic transition",
                "Explanations of social inequality between groups",
                "The sick role",
                "The population pyramid",
            ],
            "correct_index": 1,
            "explanation": (
                "Attributing group gaps to unequal conditions (structural) versus fixed ability "
                "(individual) is central to explaining social inequality. The demographic "
                "transition and population pyramid concern population change, and the sick role "
                "concerns illness behavior."
            ),
            "difficulty": "medium",
            "cognitive_level": "application",
            "subquestions": [
                {
                    "stem": "Attributing group gaps to unequal conditions is a ___ explanation; attributing them to fixed ability is a(n) ___ explanation.",
                    "options": ["structural; individual", "individual; structural"],
                    "correct_index": 0,
                    "explanation": "Conditions = structural; fixed ability = individual.",
                },
                {
                    "stem": "This debate concerns the causes of:",
                    "options": ["social inequality", "sensory adaptation"],
                    "correct_index": 0,
                    "explanation": "It is about the origins of inequality between groups.",
                },
            ],
        },
    ],
})

# ---------------------------------------------------------------------------
# Passage 9 - Sociological paradigms & the institution of medicine
# ---------------------------------------------------------------------------
PASSAGES.append({
    "passage": (
        "Sociologists analyzed how a chronic illness is understood and managed in a "
        "mid-sized city. Using surveys and interviews, they documented three patterns. "
        "First, physicians and hospitals coordinated with schools and workplaces so that "
        "ill members could be temporarily excused from normal duties while being expected "
        "to seek treatment and cooperate with doctors. Second, patients with more "
        "education and income obtained diagnoses and specialist care far faster than "
        "poorer patients, who often relied on crowded clinics; the researchers traced "
        "this to differences in insurance, flexible work hours, and familiarity with "
        "medical institutions. Third, behaviors once seen as ordinary or as moral "
        "failings - such as persistent sadness or restlessness - were increasingly "
        "defined and treated as medical conditions.\n\n"
        "The team framed each pattern with a different theoretical lens. The coordinated "
        "excusing of the sick was described as an institution maintaining social "
        "stability by managing how illness disrupts roles. The unequal access was "
        "described in terms of groups with different amounts of resources and power "
        "competing for a scarce good. The redefinition of ordinary behaviors as illnesses "
        "was described as a process by which the meaning of 'sickness' is negotiated and "
        "expanded within a society. In interviews, patients described how a formal "
        "diagnosis changed how others treated them, sometimes granting sympathy and "
        "sometimes attaching stigma. The authors noted that the fastest-growing diagnoses "
        "clustered among specific age groups, and that the city's aging population was "
        "projected to raise overall demand for chronic-disease care over the coming "
        "decades."
    ),
    "passage_source": src("Ch. 1, An Introduction to Sociology; Ch. 19, Health and Medicine", SOC),
    "questions": [
        {
            "aamc_category": "9A",
            "subtopic": "Functionalism & the sick role (Parsons)",
            "stem": (
                "Describing medicine as 'an institution maintaining social stability by managing "
                "how illness disrupts roles' reflects which paradigm, and connects to whose "
                "'sick role' concept?"
            ),
            "options": [
                "Conflict theory; Karl Marx",
                "Structural functionalism; Talcott Parsons",
                "Symbolic interactionism; Erving Goffman",
                "Feminist theory; Dorothy Smith",
            ],
            "correct_index": 1,
            "explanation": (
                "Framing an institution by how it preserves social stability is structural "
                "functionalism; Parsons's 'sick role' casts illness as a temporary sanctioned "
                "role with rights (excused duties) and obligations (seek care). Conflict theory "
                "emphasizes power struggles, symbolic interactionism emphasizes meaning, and "
                "feminist theory emphasizes gendered structures."
            ),
            "difficulty": "medium",
            "cognitive_level": "application",
            "subquestions": [
                {
                    "stem": "A view emphasizing how institutions keep society stable and functioning is:",
                    "options": ["conflict theory", "structural functionalism"],
                    "correct_index": 1,
                    "explanation": "Functionalism focuses on stability and the functions institutions serve.",
                },
                {
                    "stem": "The idea that being 'sick' is a temporary social role with rights and duties (from Talcott Parsons) is the:",
                    "options": ["sick role", "looking-glass self"],
                    "correct_index": 0,
                    "explanation": "Parsons described the sick role.",
                },
            ],
        },
        {
            "aamc_category": "9A",
            "subtopic": "Conflict theory",
            "stem": (
                "Explaining unequal access as 'groups with different resources and power "
                "competing for a scarce good' is characteristic of:"
            ),
            "options": [
                "Structural functionalism",
                "Conflict theory",
                "Symbolic interactionism",
                "Exchange/rational-choice theory",
            ],
            "correct_index": 1,
            "explanation": (
                "Conflict theory (rooted in Marx) analyzes society as competition between "
                "groups over scarce resources and power - here, unequal access to care. "
                "Functionalism stresses stability, symbolic interactionism stresses meaning in "
                "interaction, and exchange theory models individual cost-benefit decisions."
            ),
            "difficulty": "medium",
            "cognitive_level": "application",
            "subquestions": [
                {
                    "stem": "A lens focused on competition over scarce resources and power between groups is ___ theory.",
                    "options": ["functionalist", "conflict"],
                    "correct_index": 1,
                    "explanation": "Competition over resources/power is the conflict lens.",
                },
                {
                    "stem": "Conflict theory traces its roots most directly to:",
                    "options": ["Karl Marx", "Emile Durkheim"],
                    "correct_index": 0,
                    "explanation": "Marx is the foundational figure for conflict theory.",
                },
            ],
        },
        {
            "aamc_category": "9A",
            "subtopic": "Symbolic interactionism & medicalization",
            "stem": (
                "Redefining ordinary behaviors as illnesses, framed as negotiating the 'meaning "
                "of sickness,' together with the finding that a diagnosis changed how others "
                "treated patients, reflects:"
            ),
            "options": [
                "Symbolic interactionism and medicalization",
                "Structural functionalism",
                "The demographic transition",
                "Germ theory",
            ],
            "correct_index": 0,
            "explanation": (
                "Symbolic interactionism focuses on how meanings (like 'sick') are created and "
                "negotiated in interaction, and medicalization is the process of defining "
                "non-medical problems as medical ones. Functionalism and germ theory address "
                "different questions, and the demographic transition concerns population "
                "change."
            ),
            "difficulty": "medium",
            "cognitive_level": "application",
            "subquestions": [
                {
                    "stem": "A focus on how meanings (like 'sick') are created and negotiated in interaction is:",
                    "options": ["symbolic interactionism", "conflict theory"],
                    "correct_index": 0,
                    "explanation": "Meaning-in-interaction is the symbolic-interactionist lens.",
                },
                {
                    "stem": "The process of defining non-medical problems as medical ones is:",
                    "options": ["medicalization", "secularization"],
                    "correct_index": 0,
                    "explanation": "That is medicalization.",
                },
            ],
        },
        {
            "aamc_category": "9A",
            "subtopic": "Macro- vs. micro-level analysis",
            "stem": "Which of the three lenses is a MICRO-level (rather than macro-level) approach?",
            "options": [
                "Structural functionalism",
                "Conflict theory",
                "Symbolic interactionism",
                "All three are macro-level",
            ],
            "correct_index": 2,
            "explanation": (
                "Symbolic interactionism analyzes small-scale, everyday interactions and "
                "meanings (micro level). Structural functionalism and conflict theory analyze "
                "large-scale social structures (macro level), so the 'all three are macro' "
                "option is incorrect."
            ),
            "difficulty": "medium",
            "cognitive_level": "comprehension",
            "subquestions": [
                {
                    "stem": "Functionalism and conflict theory analyze society at which level?",
                    "options": ["micro", "macro"],
                    "correct_index": 1,
                    "explanation": "Both are macro-level, big-picture paradigms.",
                },
                {
                    "stem": "Symbolic interactionism analyzes which kind of interactions?",
                    "options": ["large-scale structures", "small-scale, everyday interactions"],
                    "correct_index": 1,
                    "explanation": "It is a micro-level focus on everyday meaning-making.",
                },
            ],
        },
        {
            "aamc_category": "9B",
            "subtopic": "Population aging (demographics)",
            "stem": (
                "The projection that the city's aging population will raise chronic-disease "
                "demand draws on which demographic idea?"
            ),
            "options": [
                "Population aging shifting the age structure",
                "The misinformation effect",
                "Social facilitation",
                "A demographic dividend from high fertility",
            ],
            "correct_index": 0,
            "explanation": (
                "An aging population means a rising share of older people, shifting the age "
                "structure toward higher chronic-disease demand. The misinformation effect and "
                "social facilitation are psychological phenomena, and a demographic dividend "
                "arises from a large working-age share, not aging."
            ),
            "difficulty": "easy",
            "cognitive_level": "data-analysis",
            "subquestions": [
                {
                    "stem": "An 'aging population' means the share of which group is rising?",
                    "options": ["older people", "younger people"],
                    "correct_index": 0,
                    "explanation": "Aging shifts the distribution toward older ages.",
                },
                {
                    "stem": "A tool that displays a population's age-sex structure is a:",
                    "options": ["population pyramid", "scatterplot"],
                    "correct_index": 0,
                    "explanation": "Population pyramids show age-sex structure.",
                },
            ],
        },
    ],
})

# ---------------------------------------------------------------------------
# Passage 10 - Socioeconomic gradient in health, inequality, demography
# ---------------------------------------------------------------------------
PASSAGES.append({
    "passage": (
        "A longitudinal study followed 8,000 adults for 15 years to examine links between "
        "social position and health. Participants were grouped by socioeconomic status "
        "(SES), a composite of income, education, and occupational prestige. Age-adjusted "
        "rates of chronic illness and mortality declined steadily at each higher step of "
        "the SES ladder - not merely a gap between rich and poor, but a graded "
        "relationship across the whole range. The pattern held after controlling for "
        "smoking and diet, and was partly explained by chronic stress, worse neighborhood "
        "conditions, and unequal access to preventive care.\n\n"
        "Participants were also classified by the neighborhood where they lived. "
        "Lower-SES families were concentrated in areas with fewer clinics, more "
        "pollution, and less green space; researchers described these areas as products "
        "of long-standing residential segregation. Children raised in the lowest-SES "
        "neighborhoods were less likely to reach a higher SES than their parents, a "
        "pattern the authors linked to unequal schools and social networks.\n\n"
        "Finally, the study noted a demographic shift: as the population aged and birth "
        "rates fell, the ratio of working-age adults to dependents changed, straining "
        "programs that fund elder care. The authors argued that health follows a social "
        "gradient, that place and inequality shape opportunity across generations, and "
        "that population structure interacts with these inequalities to shape a society's "
        "future needs. They emphasized that individual choices operated within, and were "
        "constrained by, these structural conditions."
    ),
    "passage_source": src("Ch. 9, Social Stratification; Ch. 20, Population, Urbanization, and the Environment", SOC),
    "questions": [
        {
            "aamc_category": "10A",
            "subtopic": "Socioeconomic gradient in health",
            "stem": (
                "The 'graded relationship across the whole range,' not just a rich-poor gap, is "
                "best described as:"
            ),
            "options": [
                "An absolute-poverty threshold effect",
                "The socioeconomic gradient in health",
                "The demographic transition",
                "The sick role",
            ],
            "correct_index": 1,
            "explanation": (
                "A step-by-step improvement in health at each higher SES level is the "
                "socioeconomic (social) gradient in health. A threshold effect would show a "
                "single cutoff, not a gradient; the demographic transition concerns "
                "birth/death rates; and the sick role concerns illness behavior."
            ),
            "difficulty": "medium",
            "cognitive_level": "data-analysis",
            "subquestions": [
                {
                    "stem": "Health improved at which points of the SES ladder?",
                    "options": ["only at the very top", "each higher step"],
                    "correct_index": 1,
                    "explanation": "Improvement occurred at every step, not just the extremes.",
                },
                {
                    "stem": "A continuous, step-by-step relationship across all levels is called a:",
                    "options": ["threshold", "gradient"],
                    "correct_index": 1,
                    "explanation": "That continuous pattern is a gradient.",
                },
            ],
        },
        {
            "aamc_category": "10A",
            "subtopic": "Measuring socioeconomic status",
            "stem": "In this study, SES was measured as a composite of:",
            "options": [
                "income only",
                "income, education, and occupational prestige",
                "age and sex",
                "neighborhood of residence only",
            ],
            "correct_index": 1,
            "explanation": (
                "SES is multidimensional, typically combining income, education, and "
                "occupational prestige - the definition used here. Income alone, age/sex, or "
                "neighborhood alone each capture only part (or none) of SES."
            ),
            "difficulty": "easy",
            "cognitive_level": "comprehension",
            "subquestions": [
                {
                    "stem": "Which is NOT one of the usual components of SES?",
                    "options": ["education", "occupational prestige", "blood type"],
                    "correct_index": 2,
                    "explanation": "Blood type is unrelated to SES.",
                },
                {
                    "stem": "Measuring standing along several dimensions (class, status, power) echoes which theorist?",
                    "options": ["Max Weber", "B. F. Skinner"],
                    "correct_index": 0,
                    "explanation": "Weber described a multidimensional view of stratification.",
                },
            ],
        },
        {
            "aamc_category": "10A",
            "subtopic": "Spatial inequality / environmental injustice",
            "stem": (
                "Concentrating lower-SES families in areas with fewer resources, described as "
                "products of 'residential segregation,' is an example of:"
            ),
            "options": [
                "spatial inequality / environmental injustice",
                "social facilitation",
                "the demographic transition",
                "meritocracy",
            ],
            "correct_index": 0,
            "explanation": (
                "The uneven distribution of resources and environmental burdens across places "
                "is spatial inequality, and poorer neighborhoods bearing more pollution is "
                "environmental injustice. Social facilitation is a group-performance effect, "
                "the demographic transition concerns population change, and meritocracy is an "
                "ideology about earned position."
            ),
            "difficulty": "medium",
            "cognitive_level": "application",
            "subquestions": [
                {
                    "stem": "The unequal distribution of resources across places is ___ inequality.",
                    "options": ["temporal", "spatial"],
                    "correct_index": 1,
                    "explanation": "Inequality tied to place/geography is spatial.",
                },
                {
                    "stem": "Poorer neighborhoods bearing disproportionate pollution reflects environmental:",
                    "options": ["injustice", "adaptation"],
                    "correct_index": 0,
                    "explanation": "That unequal burden is environmental injustice.",
                },
            ],
        },
        {
            "aamc_category": "10A",
            "subtopic": "Social mobility / social reproduction",
            "stem": (
                "Children from the lowest-SES neighborhoods rarely exceeding their parents' SES "
                "illustrates:"
            ),
            "options": [
                "high intergenerational mobility",
                "low intergenerational mobility (social reproduction)",
                "a demographic dividend",
                "absolute upward mobility for everyone",
            ],
            "correct_index": 1,
            "explanation": (
                "When class position persists from parents to children, mobility is low and "
                "advantages/disadvantages are reproduced across generations (social "
                "reproduction). High mobility would mean children readily change SES; a "
                "demographic dividend is a population-age concept; and universal upward "
                "mobility contradicts the data."
            ),
            "difficulty": "medium",
            "cognitive_level": "application",
            "subquestions": [
                {
                    "stem": "Moving to a different SES than one's parents is ___ mobility.",
                    "options": ["intragenerational", "intergenerational"],
                    "correct_index": 1,
                    "explanation": "Across generations = intergenerational mobility.",
                },
                {
                    "stem": "When advantages and disadvantages pass across generations, keeping the class structure stable, sociologists call it social:",
                    "options": ["reproduction", "facilitation"],
                    "correct_index": 0,
                    "explanation": "That persistence is social reproduction.",
                },
            ],
        },
        {
            "aamc_category": "9B",
            "subtopic": "Dependency ratio / demographic transition",
            "stem": (
                "The shift in which an aging population and falling births change the ratio of "
                "workers to dependents concerns the:"
            ),
            "options": [
                "dependency ratio, tied to the demographic transition",
                "misinformation effect",
                "looking-glass self",
                "fundamental attribution error",
            ],
            "correct_index": 0,
            "explanation": (
                "The dependency ratio compares non-working (young + old) to working-age people; "
                "aging plus low fertility (late demographic transition) raises it. The other "
                "options are psychological/social-cognitive concepts unrelated to population "
                "structure."
            ),
            "difficulty": "medium",
            "cognitive_level": "data-analysis",
            "subquestions": [
                {
                    "stem": "Falling birth rates plus longer lifespans are features of the:",
                    "options": ["demographic transition", "sick role"],
                    "correct_index": 0,
                    "explanation": "These are hallmarks of the demographic transition.",
                },
                {
                    "stem": "The ratio of non-working (young + old) to working-age people is the ___ ratio.",
                    "options": ["dependency", "sex"],
                    "correct_index": 0,
                    "explanation": "That is the dependency ratio.",
                },
            ],
        },
        {
            "aamc_category": "9A",
            "subtopic": "Structure vs. agency",
            "stem": (
                "The authors' point that 'individual choices operated within, and were "
                "constrained by, structural conditions' reflects which sociological tension?"
            ),
            "options": [
                "nature vs. nurture",
                "structure vs. agency",
                "reliability vs. validity",
                "primacy vs. recency",
            ],
            "correct_index": 1,
            "explanation": (
                "The interplay between social constraints (structure) and individual choice "
                "(agency) is the structure-agency debate. Nature-nurture concerns genes vs. "
                "environment, reliability-validity concerns measurement, and primacy-recency "
                "concerns memory."
            ),
            "difficulty": "easy",
            "cognitive_level": "comprehension",
            "subquestions": [
                {
                    "stem": "'Structure' refers to which, and 'agency' to which?",
                    "options": ["social constraints; individual choice", "individual choice; social constraints"],
                    "correct_index": 0,
                    "explanation": "Structure = constraints; agency = individual choice.",
                },
                {
                    "stem": "Saying choices are shaped by constraints emphasizes the role of:",
                    "options": ["structure", "agency"],
                    "correct_index": 0,
                    "explanation": "Constraint-focused claims emphasize structure.",
                },
            ],
        },
    ],
})

# ---------------------------------------------------------------------------
# Passage 11 - DISCRETE set A (standalone items; FC 6-7)
# ---------------------------------------------------------------------------
PASSAGES.append({
    "passage": (
        "Discrete questions (no associated passage). Each item below is a standalone "
        "question testing a single concept in the psychological foundations of behavior "
        "(AAMC Foundational Concepts 6-7), mirroring the discrete questions interspersed "
        "between passages on the real P/S exam. Concepts are grounded in OpenStax "
        "Psychology 2e."
    ),
    "passage_source": src("Chs. 5-12 (discrete items)"),
    "questions": [
        {
            "aamc_category": "6A",
            "subtopic": "Sensory transduction (vision)",
            "stem": "Which structures convert light into neural signals in the retina?",
            "options": [
                "Rods and cones",
                "Cochlear hair cells",
                "Olfactory receptor neurons",
                "Pacinian corpuscles",
            ],
            "correct_index": 0,
            "explanation": (
                "Rods and cones are the retinal photoreceptors that transduce light into "
                "neural signals. Hair cells transduce sound in the cochlea, olfactory receptors "
                "transduce smell, and Pacinian corpuscles transduce pressure/vibration."
            ),
            "difficulty": "easy",
            "cognitive_level": "comprehension",
            "subquestions": [
                {
                    "stem": "Transduction is converting a physical stimulus into what?",
                    "options": ["a neural signal", "a hormone"],
                    "correct_index": 0,
                    "explanation": "Transduction yields a neural signal the brain can use.",
                },
                {
                    "stem": "In the eye, the photoreceptors are the:",
                    "options": ["rods and cones", "retinal ganglion cells"],
                    "correct_index": 0,
                    "explanation": "Rods and cones are the light-sensing photoreceptors.",
                },
            ],
        },
        {
            "aamc_category": "6B",
            "subtopic": "Piagetian conservation",
            "stem": (
                "A child who cannot yet grasp that pouring water into a taller, thinner glass "
                "keeps the amount constant lacks:"
            ),
            "options": [
                "object permanence",
                "conservation",
                "formal operational reasoning",
                "a theory of mind",
            ],
            "correct_index": 1,
            "explanation": (
                "Conservation is understanding that quantity stays constant despite changes in "
                "appearance; it is typically absent in Piaget's preoperational stage. Object "
                "permanence (sensorimotor) is knowing objects exist when unseen, formal "
                "operations involve abstract reasoning, and theory of mind is understanding "
                "others' mental states."
            ),
            "difficulty": "medium",
            "cognitive_level": "application",
            "subquestions": [
                {
                    "stem": "Understanding that quantity stays the same despite a change in shape is:",
                    "options": ["conservation", "object permanence"],
                    "correct_index": 0,
                    "explanation": "That is conservation.",
                },
                {
                    "stem": "Conservation is typically acquired in Piaget's ___ stage.",
                    "options": ["sensorimotor", "concrete operational"],
                    "correct_index": 1,
                    "explanation": "Concrete operational children master conservation.",
                },
            ],
        },
        {
            "aamc_category": "6B",
            "subtopic": "Heuristics (representativeness)",
            "stem": (
                "Judging that a shy, detail-oriented person is more likely a librarian than a "
                "salesperson, while ignoring how many more salespeople there are, reflects the:"
            ),
            "options": [
                "availability heuristic",
                "representativeness heuristic",
                "anchoring bias",
                "framing effect",
            ],
            "correct_index": 1,
            "explanation": (
                "The representativeness heuristic judges probability by similarity to a "
                "prototype/stereotype while neglecting base rates. The availability heuristic "
                "uses ease of recall, anchoring fixates on an initial value, and framing "
                "concerns how options are worded."
            ),
            "difficulty": "medium",
            "cognitive_level": "application",
            "subquestions": [
                {
                    "stem": "Judging probability by how well something matches a prototype/stereotype is the ___ heuristic.",
                    "options": ["availability", "representativeness"],
                    "correct_index": 1,
                    "explanation": "Similarity-to-prototype judgments use representativeness.",
                },
                {
                    "stem": "Judging probability by how easily examples come to mind is the ___ heuristic.",
                    "options": ["availability", "representativeness"],
                    "correct_index": 0,
                    "explanation": "Ease-of-recall judgments use availability.",
                },
            ],
        },
        {
            "aamc_category": "6C",
            "subtopic": "Sleep stages (REM)",
            "stem": (
                "Vivid dreaming, rapid eye movements, and an EEG resembling wakefulness most "
                "characterize:"
            ),
            "options": [
                "NREM stage 3 (slow-wave sleep)",
                "REM sleep",
                "NREM stage 1",
                "the hypnagogic state",
            ],
            "correct_index": 1,
            "explanation": (
                "REM sleep features vivid dreaming, rapid eye movements, and a low-voltage, "
                "fast (near-waking) EEG with skeletal-muscle atonia. NREM stage 3 shows slow "
                "delta waves, and stage 1 / the hypnagogic state is the light transition into "
                "sleep."
            ),
            "difficulty": "easy",
            "cognitive_level": "comprehension",
            "subquestions": [
                {
                    "stem": "Deep, slow-wave (delta) sleep is which type?",
                    "options": ["REM", "NREM stage 3"],
                    "correct_index": 1,
                    "explanation": "Slow-wave delta sleep is NREM stage 3.",
                },
                {
                    "stem": "The stage with vivid dreams and paradoxical near-waking brain activity is:",
                    "options": ["REM", "NREM stage 2"],
                    "correct_index": 0,
                    "explanation": "REM is 'paradoxical sleep' with active, waking-like EEG.",
                },
            ],
        },
        {
            "aamc_category": "7A",
            "subtopic": "Operant reinforcement schedules",
            "stem": (
                "A slot machine that pays off after an unpredictable number of plays uses which "
                "schedule, known for high, steady responding that resists extinction?"
            ),
            "options": [
                "fixed-ratio",
                "variable-ratio",
                "fixed-interval",
                "variable-interval",
            ],
            "correct_index": 1,
            "explanation": (
                "A variable-ratio schedule reinforces after an unpredictable number of "
                "responses and produces high, steady, extinction-resistant responding - the "
                "gambling pattern. Fixed-ratio reinforces after a set count, and interval "
                "schedules reinforce based on time elapsed."
            ),
            "difficulty": "medium",
            "cognitive_level": "application",
            "subquestions": [
                {
                    "stem": "Reinforcement after a set NUMBER of responses vs. a varying number is:",
                    "options": ["fixed-ratio vs. variable-ratio", "fixed-interval vs. variable-interval"],
                    "correct_index": 0,
                    "explanation": "Ratio schedules count responses; 'set' = fixed, 'varying' = variable.",
                },
                {
                    "stem": "Which schedule produces the highest, most extinction-resistant responding?",
                    "options": ["fixed-interval", "variable-ratio"],
                    "correct_index": 1,
                    "explanation": "Variable-ratio yields the strongest, most persistent responding.",
                },
            ],
        },
    ],
})

# ---------------------------------------------------------------------------
# Passage 12 - DISCRETE set B (standalone items; FC 7-10)
# ---------------------------------------------------------------------------
PASSAGES.append({
    "passage": (
        "Discrete questions (no associated passage). Each item below is a standalone "
        "question testing a single concept in the social foundations of behavior and "
        "society (AAMC Foundational Concepts 7-10), mirroring the discrete questions on "
        "the real P/S exam. Concepts are grounded in OpenStax Introduction to Sociology "
        "3e and OpenStax Psychology 2e."
    ),
    "passage_source": src("Chs. 1-21 (discrete items)", SOC),
    "questions": [
        {
            "aamc_category": "7B",
            "subtopic": "Obedience to authority (Milgram)",
            "stem": (
                "In studies where participants delivered what they believed were increasingly "
                "severe shocks because an authority instructed them to, most complied. This "
                "demonstrates:"
            ),
            "options": [
                "conformity to peers",
                "obedience to authority",
                "the bystander effect",
                "social loafing",
            ],
            "correct_index": 1,
            "explanation": (
                "Following direct orders from an authority figure is obedience, the focus of "
                "Milgram's studies. Conformity is matching peers without orders, the bystander "
                "effect is reduced helping with more witnesses, and social loafing is reduced "
                "effort in groups."
            ),
            "difficulty": "easy",
            "cognitive_level": "comprehension",
            "subquestions": [
                {
                    "stem": "Following direct orders from an authority is ___; matching peers' behavior is ___.",
                    "options": ["obedience; conformity", "conformity; obedience"],
                    "correct_index": 0,
                    "explanation": "Orders -> obedience; peer matching -> conformity.",
                },
                {
                    "stem": "The classic obedience studies were conducted by:",
                    "options": ["Stanley Milgram", "Solomon Asch"],
                    "correct_index": 0,
                    "explanation": "Milgram ran the obedience experiments; Asch studied conformity.",
                },
            ],
        },
        {
            "aamc_category": "7C",
            "subtopic": "Compliance techniques (foot-in-the-door)",
            "stem": (
                "Agreeing to a small request first makes people more likely to agree to a "
                "larger request later. This persuasion technique is:"
            ),
            "options": [
                "door-in-the-face",
                "foot-in-the-door",
                "lowballing",
                "the reciprocity norm",
            ],
            "correct_index": 1,
            "explanation": (
                "Foot-in-the-door starts with a small request to increase later compliance "
                "with a larger one. Door-in-the-face starts large then retreats to smaller, "
                "lowballing changes the deal after agreement, and the reciprocity norm involves "
                "returning favors."
            ),
            "difficulty": "medium",
            "cognitive_level": "application",
            "subquestions": [
                {
                    "stem": "Starting with a small request to gain later compliance with a bigger one is:",
                    "options": ["foot-in-the-door", "door-in-the-face"],
                    "correct_index": 0,
                    "explanation": "Small-then-large is foot-in-the-door.",
                },
                {
                    "stem": "Starting with a large request, then retreating to a smaller one, is:",
                    "options": ["foot-in-the-door", "door-in-the-face"],
                    "correct_index": 1,
                    "explanation": "Large-then-small is door-in-the-face.",
                },
            ],
        },
        {
            "aamc_category": "8B",
            "subtopic": "Self-serving bias",
            "stem": (
                "A student who credits an A to their intelligence but blames an F on an unfair "
                "professor shows the:"
            ),
            "options": [
                "fundamental attribution error",
                "self-serving bias",
                "just-world hypothesis",
                "actor-observer bias",
            ],
            "correct_index": 1,
            "explanation": (
                "The self-serving bias attributes one's successes to internal factors and "
                "failures to external factors, protecting self-esteem. The fundamental "
                "attribution error and actor-observer bias concern explaining others' vs. one's "
                "own behavior generally, and the just-world hypothesis is believing people get "
                "what they deserve."
            ),
            "difficulty": "medium",
            "cognitive_level": "application",
            "subquestions": [
                {
                    "stem": "Taking credit for successes but blaming failures on outside causes protects:",
                    "options": ["self-esteem", "other people"],
                    "correct_index": 0,
                    "explanation": "The pattern serves and protects the self.",
                },
                {
                    "stem": "This attribution pattern is the ___ bias.",
                    "options": ["self-serving", "halo"],
                    "correct_index": 0,
                    "explanation": "It is the self-serving bias.",
                },
            ],
        },
        {
            "aamc_category": "8C",
            "subtopic": "Attachment (Ainsworth's Strange Situation)",
            "stem": (
                "In the Strange Situation, an infant who explores freely, is distressed at "
                "separation, and is quickly comforted at reunion shows which attachment style?"
            ),
            "options": [
                "avoidant",
                "secure",
                "anxious-ambivalent (resistant)",
                "disorganized",
            ],
            "correct_index": 1,
            "explanation": (
                "Secure attachment is marked by using the caregiver as a base for exploration, "
                "distress at separation, and easy comforting at reunion. Avoidant infants show "
                "little distress or contact-seeking, anxious-ambivalent infants are hard to "
                "soothe, and disorganized infants show contradictory behavior."
            ),
            "difficulty": "medium",
            "cognitive_level": "application",
            "subquestions": [
                {
                    "stem": "The Strange Situation, developed by Mary Ainsworth, measures infant:",
                    "options": ["attachment", "temperament only"],
                    "correct_index": 0,
                    "explanation": "It assesses attachment style.",
                },
                {
                    "stem": "An infant easily soothed by the caregiver at reunion is ___ attached.",
                    "options": ["securely", "avoidantly"],
                    "correct_index": 0,
                    "explanation": "Easy comforting at reunion indicates secure attachment.",
                },
            ],
        },
        {
            "aamc_category": "9A",
            "subtopic": "Anomie (Durkheim) vs. alienation (Marx)",
            "stem": (
                "Emile Durkheim's concept for a breakdown of social norms and the resulting "
                "sense of normlessness is:"
            ),
            "options": [
                "anomie",
                "alienation",
                "the sick role",
                "false consciousness",
            ],
            "correct_index": 0,
            "explanation": (
                "Durkheim's anomie is normlessness arising when social regulation breaks down. "
                "Alienation and false consciousness are Marxian concepts (estrangement from "
                "labor and misperception of one's class interests), and the sick role is "
                "Parsons's illness concept."
            ),
            "difficulty": "medium",
            "cognitive_level": "comprehension",
            "subquestions": [
                {
                    "stem": "Durkheim (a functionalist) coined the term for normlessness:",
                    "options": ["anomie", "alienation"],
                    "correct_index": 0,
                    "explanation": "Normlessness = anomie (Durkheim).",
                },
                {
                    "stem": "Marx's term for workers' estrangement from their labor is:",
                    "options": ["anomie", "alienation"],
                    "correct_index": 1,
                    "explanation": "Estrangement from labor = alienation (Marx).",
                },
            ],
        },
        {
            "aamc_category": "9B",
            "subtopic": "Demographic transition model",
            "stem": "The demographic transition model describes a society shifting from:",
            "options": [
                "high birth and death rates to low birth and death rates",
                "low fertility to permanently high fertility",
                "urban living back to rural living",
                "gesellschaft to gemeinschaft",
            ],
            "correct_index": 0,
            "explanation": (
                "The demographic transition moves from high birth and death rates to low birth "
                "and death rates as societies industrialize, with a middle phase of rapid "
                "growth when death rates fall before birth rates. The other options reverse or "
                "misstate the model."
            ),
            "difficulty": "medium",
            "cognitive_level": "comprehension",
            "subquestions": [
                {
                    "stem": "Early in the transition, death rates fall while birth rates stay high, so the population:",
                    "options": ["grows rapidly", "shrinks"],
                    "correct_index": 0,
                    "explanation": "The gap between high births and falling deaths causes rapid growth.",
                },
                {
                    "stem": "Late in the transition, both birth and death rates are:",
                    "options": ["low", "high"],
                    "correct_index": 0,
                    "explanation": "The end state is low births and low deaths.",
                },
            ],
        },
        {
            "aamc_category": "10A",
            "subtopic": "Meritocracy & social reproduction",
            "stem": (
                "The belief that social positions are earned purely through talent and effort, "
                "independent of inherited advantages, is the ideology of:"
            ),
            "options": [
                "meritocracy",
                "anomie",
                "the demographic transition",
                "social facilitation",
            ],
            "correct_index": 0,
            "explanation": (
                "Meritocracy is the belief that rewards track individual talent and effort. "
                "Evidence of low mobility and social reproduction challenges a pure meritocracy "
                "claim. Anomie is normlessness, and the other options are unrelated population "
                "or group-behavior concepts."
            ),
            "difficulty": "medium",
            "cognitive_level": "application",
            "subquestions": [
                {
                    "stem": "'Meritocracy' claims rewards go to people based on:",
                    "options": ["merit (talent and effort)", "inherited status"],
                    "correct_index": 0,
                    "explanation": "Meritocracy attributes outcomes to individual merit.",
                },
                {
                    "stem": "Evidence of low mobility and social reproduction does what to a pure meritocracy claim?",
                    "options": ["supports it", "challenges it"],
                    "correct_index": 1,
                    "explanation": "Persistent inherited advantage undercuts pure meritocracy.",
                },
            ],
        },
    ],
})

# <<<INSERT_PASSAGES_HERE>>>


def _assign_ids(passages: list[dict]) -> list[dict]:
    """Assign section + stable ids mechanically (psg-ps-N and psg-ps-N-qK)."""
    for i, p in enumerate(passages, start=1):
        p_id = f"psg-ps-{i}"
        # Rebuild each passage dict so key order in the JSON is stable/readable.
        p["id"] = p_id
        p["section"] = "P/S"
        for k, q in enumerate(p.get("questions", []), start=1):
            q["id"] = f"{p_id}-q{k}"
        # Re-order top-level keys: id, section, passage, passage_source, questions.
        ordered = {
            "id": p["id"],
            "section": p["section"],
            "passage": p["passage"],
            "passage_source": p["passage_source"],
            "questions": p["questions"],
        }
        passages[i - 1] = ordered
    return passages


def _coverage(passages: list[dict]) -> None:
    per_cat: collections.Counter[str] = collections.Counter()
    n_q = 0
    n_sub = 0
    for p in passages:
        for q in p["questions"]:
            n_q += 1
            per_cat[q["aamc_category"]] += 1
            n_sub += len(q.get("subquestions", []))
    order = ["6A", "6B", "6C", "7A", "7B", "7C", "8A", "8B", "8C", "9A", "9B", "10A"]
    print(f"Passages: {len(passages)}  Questions: {n_q}  Sub-questions: {n_sub}")
    print("Per AAMC category (FC 6-10):")
    for c in order:
        print(f"  {c:>3}: {per_cat.get(c, 0)}")
    missing = [c for c in order if per_cat.get(c, 0) == 0]
    print(f"Categories covered: {sum(1 for c in order if per_cat.get(c, 0))}/{len(order)}")
    if missing:
        print(f"  MISSING: {missing}")


def main() -> None:
    passages = _assign_ids(PASSAGES)
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(passages, fh, indent=2, ensure_ascii=False)
        fh.write("\n")
    print(f"Wrote {OUT}")
    _coverage(passages)


if __name__ == "__main__":
    main()
