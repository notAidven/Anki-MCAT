#!/usr/bin/env python3
# Copyright: ReadyMCAT contributors
# License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html
"""Builder for the ReadyMCAT B/B free-response (type-in) practice bank.

This script is the authoring SOURCE OF TRUTH for
``free_response_bio_biochem.json``. Items are hand-authored here as plain
Python dicts (organized one function per AAMC content category, mirroring the
"one internal subagent per category" decomposition), then serialized to JSON.
Authoring in Python lets us keep the item text readable (Greek letters, arrows,
apostrophes) and lets ``json.dump`` handle all escaping, so the emitted JSON is
guaranteed valid.

AUTHORING INTEGRITY
  * Every item is ORIGINAL, written for ReadyMCAT and grounded in a FREE /
    openly-licensed source cited per item (see ``SOURCES``). No item is copied
    or closely paraphrased from any copyrighted or paid question bank (UWorld,
    Kaplan, Blueprint, AAMC paid). Facts/concepts are not copyrightable; no
    source's expression is reproduced.
  * Designed for AUTO-GRADING with NO AI at the grading layer: every item and
    every teach-on-miss sub-question has a SHORT, well-defined answer plus
    multiple accepted phrasings (``accepted_answers``) and ``key_terms`` for
    normalized-string / key-term matching.

Run:  python3 free_response_bio_biochem_build.py
      (writes free_response_bio_biochem.json next to this file and prints a
       coverage summary)
"""

from __future__ import annotations

import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
OUT_PATH = os.path.join(HERE, "free_response_bio_biochem.json")

# --- Source registry (free / openly-licensed) -----------------------------
# Each item folds a chapter/location into the emitted source "name".
SOURCES = {
    "bio2e": {
        "name": "OpenStax Biology 2e",
        "url": "https://openstax.org/details/books/biology-2e",
        "license": "CC BY 4.0",
    },
    "ap2e": {
        "name": "OpenStax Anatomy and Physiology 2e",
        "url": "https://openstax.org/details/books/anatomy-and-physiology-2e",
        "license": "CC BY 4.0",
    },
    "micro": {
        "name": "OpenStax Microbiology",
        "url": "https://openstax.org/details/books/microbiology",
        "license": "CC BY 4.0",
    },
    "chem2e": {
        "name": "OpenStax Chemistry 2e",
        "url": "https://openstax.org/details/books/chemistry-2e",
        "license": "CC BY 4.0",
    },
    "libretexts_biochem": {
        "name": "LibreTexts Biochemistry (Fundamentals of Biochemistry)",
        "url": "https://bio.libretexts.org/Bookshelves/Biochemistry",
        "license": "CC BY-NC-SA 4.0",
    },
}


def src(ref: str, loc: str) -> dict:
    base = SOURCES[ref]
    return {
        "name": f"{base['name']} \u2014 {loc}",
        "url": base["url"],
        "license": base["license"],
    }


def sq(stem: str, accepted: list[str], explanation: str) -> dict:
    """One teach-on-miss ladder rung (a guiding short-answer sub-question)."""
    return {
        "stem": stem,
        "answer_type": "free_response",
        "accepted_answers": accepted,
        "explanation": explanation,
    }


def mk(cat, n, subtopic, prompt, accepted, key_terms, model_answer, explanation,
       difficulty, cognitive, src_ref, src_loc, subq):
    return {
        "id": "fr-bb-%s-%02d" % (cat, n),
        "section": "B/B",
        "aamc_category": cat,
        "subtopic": subtopic,
        "answer_type": "free_response",
        "prompt": prompt,
        "accepted_answers": accepted,
        "key_terms": key_terms,
        "model_answer": model_answer,
        "explanation": explanation,
        "difficulty": difficulty,
        "cognitive_level": cognitive,
        "source": src(src_ref, src_loc),
        "subquestions": subq,
    }


# ---------------------------------------------------------------------------
# 1A - Structure and function of proteins and their constituent amino acids
# ---------------------------------------------------------------------------
def cat_1A():
    return [
        mk("1A", 1, "Amino acids: stereochemistry",
           "Which of the 20 standard amino acids is the only one that is achiral (its alpha-carbon is NOT a stereocenter)?",
           ["glycine", "gly", "g"],
           ["glycine"],
           "Glycine",
           "Glycine's side chain is a single hydrogen, so its alpha-carbon bears two identical H substituents and is not a stereocenter; every other standard amino acid is chiral (L-configuration in proteins).",
           "easy", "recall", "libretexts_biochem", "Amino Acids and Proteins",
           [sq("How many DIFFERENT groups must a carbon have to be a chiral center (stereocenter)?",
               ["four", "4", "four different groups"],
               "A stereocenter needs four different substituents."),
            sq("What is the side chain (R group) of glycine?",
               ["hydrogen", "h", "a hydrogen atom", "-h"],
               "Glycine's R group is just a hydrogen atom, so its alpha-carbon has two H's."),
            sq("Because its alpha-carbon has two hydrogens, how many of glycine's four substituents are identical?",
               ["two", "2", "two hydrogens"],
               "Two identical H groups mean the carbon is not a stereocenter, so glycine is achiral.")]),
        mk("1A", 2, "Peptide bond",
           "What is the name of the covalent bond that joins the carboxyl group of one amino acid to the amino group of the next in a polypeptide?",
           ["peptide bond", "peptide", "amide bond", "peptide (amide) bond", "amide linkage"],
           ["peptide"],
           "A peptide bond (an amide linkage)",
           "A peptide bond is an amide bond formed by a condensation (dehydration) reaction between the alpha-carboxyl of one amino acid and the alpha-amino of the next, releasing water.",
           "easy", "recall", "bio2e", "Ch. 3 Biological Macromolecules (Proteins)",
           [sq("What small molecule is released when a peptide bond forms?",
               ["water", "h2o", "h\u2082o"],
               "Peptide-bond formation is a condensation/dehydration reaction that releases one water molecule."),
            sq("Is forming a peptide bond a hydrolysis or a condensation (dehydration) reaction?",
               ["condensation", "dehydration", "dehydration synthesis", "condensation reaction"],
               "Bonds form by condensation; they are broken by hydrolysis (adding water).")]),
        mk("1A", 3, "Amino acids: side chains",
           "Which amino acid has a thiol (-SH) side chain that can form disulfide bonds stabilizing higher-order protein structure?",
           ["cysteine", "cys", "c"],
           ["cysteine"],
           "Cysteine",
           "Two cysteine thiols oxidize to form a disulfide bond (cystine), covalently cross-linking regions of a protein.",
           "easy", "recall", "libretexts_biochem", "Amino Acids and Proteins",
           [sq("When two cysteine -SH groups are oxidized and joined, what covalent linkage forms?",
               ["disulfide bond", "disulfide", "disulfide bridge", "s-s bond"],
               "The two thiols form a disulfide (-S-S-) bond."),
            sq("Which level(s) of protein structure can disulfide bonds stabilize?",
               ["tertiary", "tertiary and quaternary", "tertiary structure", "tertiary/quaternary"],
               "Disulfides cross-link tertiary (within a chain) and quaternary (between chains) structure.")]),
        mk("1A", 4, "Amino acids: proline",
           "Which amino acid's side chain bonds back to its own alpha-amino nitrogen, forming a rigid ring that disrupts alpha-helices?",
           ["proline", "pro", "p"],
           ["proline"],
           "Proline",
           "Proline's cyclic (secondary amine) structure creates a kink and cannot fit an alpha-helix well, so it often breaks secondary structure or appears in turns.",
           "medium", "recall", "libretexts_biochem", "Amino Acids and Proteins",
           [sq("Proline is a SECONDARY amine because its side chain bonds to which backbone atom?",
               ["nitrogen", "the amino nitrogen", "n", "alpha-amino nitrogen"],
               "The ring closes onto the backbone amino nitrogen."),
            sq("Which regular secondary structure does proline tend to break?",
               ["alpha helix", "alpha-helix", "helix", "a-helix"],
               "Proline's rigid ring is poorly accommodated in an alpha-helix.")]),
        mk("1A", 5, "Amino acids: acid-base behavior",
           "If the pH of a solution is BELOW an amino acid's isoelectric point (pI), what is the SIGN of the amino acid's net charge?",
           ["positive", "positively charged", "+", "net positive", "positive charge"],
           ["positive"],
           "Positive (net positive charge)",
           "Below the pI, excess protons keep ionizable groups protonated, so the molecule carries a net positive charge; above the pI it is net negative.",
           "medium", "application", "chem2e", "Acid-base behavior of functional groups",
           [sq("At a pH exactly equal to the pI, what is the average net charge?",
               ["zero", "0", "neutral", "no net charge"],
               "At the pI the net charge is zero (the zwitterion predominates)."),
            sq("Low pH means a HIGH or LOW concentration of H+ (protons)?",
               ["high", "high concentration", "more protons", "high h+"],
               "Low pH = high [H+], which protonates groups and adds positive charge.")]),
        mk("1A", 6, "Amino acids: isoelectric point",
           "What term names the pH at which an amino acid or protein carries NO net electric charge?",
           ["isoelectric point", "pi", "isoelectric ph"],
           ["isoelectric"],
           "The isoelectric point (pI)",
           "At the isoelectric point positive and negative charges balance, giving zero net charge, so the molecule will not migrate in an electric field.",
           "easy", "recall", "chem2e", "Acid-base behavior; titration of amino acids",
           [sq("At its pI, will a protein migrate toward the anode, the cathode, or neither in electrophoresis?",
               ["neither", "it does not migrate", "no migration", "will not move", "does not move"],
               "With zero net charge it does not migrate."),
            sq("A dipolar ion that carries both a + and a - charge but is net-neutral is called a ___?",
               ["zwitterion", "zwitter ion", "dipolar ion"],
               "This species is a zwitterion.")]),
        mk("1A", 7, "Protein structure: secondary",
           "The alpha-helix and beta-pleated sheet are examples of which LEVEL of protein structure, stabilized by hydrogen bonds along the backbone?",
           ["secondary structure", "secondary", "2 structure", "secondary (2)"],
           ["secondary"],
           "Secondary structure",
           "Secondary structure (alpha-helix, beta-sheet) arises from hydrogen bonding between backbone carbonyl O and amide N-H groups, independent of the side chains.",
           "easy", "recall", "bio2e", "Ch. 3 Biological Macromolecules (Protein structure)",
           [sq("Secondary-structure hydrogen bonds form between atoms of the SIDE CHAINS or the BACKBONE?",
               ["backbone", "the backbone", "main chain", "polypeptide backbone"],
               "Backbone C=O and N-H groups hydrogen bond."),
            sq("Name the two most common secondary structures.",
               ["alpha helix and beta sheet", "alpha helix, beta pleated sheet", "helix and sheet", "alpha-helix and beta-sheet"],
               "The alpha-helix and the beta-pleated sheet.")]),
        mk("1A", 8, "Enzyme kinetics: Km",
           "In Michaelis-Menten kinetics, the Michaelis constant Km equals the substrate concentration at what fraction of Vmax?",
           ["half", "one half", "1/2", "0.5", "50%", "half of vmax", "half-maximal velocity"],
           ["half"],
           "The substrate concentration at half of Vmax (half-maximal velocity)",
           "Km is the substrate concentration at which velocity is Vmax/2; a lower Km reflects higher apparent affinity of the enzyme for its substrate.",
           "medium", "recall", "libretexts_biochem", "Enzyme Kinetics (Michaelis-Menten)",
           [sq("When [S] equals Km, the reaction velocity equals what expression in terms of Vmax?",
               ["vmax/2", "one half vmax", "half vmax", "0.5 vmax", "vmax over 2"],
               "v = Vmax/2 when [S] = Km."),
            sq("Does a LOWER Km indicate higher or lower apparent affinity for substrate?",
               ["higher", "higher affinity", "high affinity", "greater affinity"],
               "Lower Km = higher apparent affinity.")]),
        mk("1A", 9, "Enzyme inhibition: competitive",
           "A competitive inhibitor binds the active site. Does it INCREASE, DECREASE, or leave unchanged the apparent Km?",
           ["increase", "increases", "it increases", "increased", "higher", "raises it"],
           ["increase"],
           "It increases the apparent Km",
           "A competitive inhibitor competes with substrate for the active site, so more substrate is needed to reach half-maximal velocity (apparent Km rises); Vmax is unchanged because saturating substrate outcompetes the inhibitor.",
           "medium", "application", "libretexts_biochem", "Enzyme Inhibition",
           [sq("What happens to Vmax with a purely competitive inhibitor at saturating substrate?",
               ["unchanged", "no change", "stays the same", "same", "vmax is unchanged"],
               "Vmax is unchanged; enough substrate outcompetes the inhibitor."),
            sq("Can increasing substrate concentration overcome a competitive inhibitor?",
               ["yes", "yes it can", "yes, it can be overcome"],
               "Yes - high [S] outcompetes a competitive inhibitor.")]),
        mk("1A", 10, "Enzyme inhibition: noncompetitive",
           "A pure noncompetitive inhibitor binds an allosteric site (not the active site). What happens to Vmax?",
           ["decreases", "decrease", "it decreases", "lowered", "reduced", "decreased"],
           ["decrease"],
           "Vmax decreases",
           "A noncompetitive inhibitor lowers Vmax (it inactivates a fraction of enzyme regardless of [S]) while Km is unchanged, because it binds E and ES equally well.",
           "medium", "application", "libretexts_biochem", "Enzyme Inhibition",
           [sq("What happens to Km with a PURE noncompetitive inhibitor?",
               ["unchanged", "no change", "stays the same", "same"],
               "Km is unchanged in pure noncompetitive inhibition."),
            sq("Does a noncompetitive inhibitor bind the active site or a separate (allosteric) site?",
               ["allosteric site", "different site", "allosteric", "a separate site", "not the active site"],
               "It binds a separate, allosteric site.")]),
        mk("1A", 11, "Enzyme classification",
           "Which of the six enzyme classes catalyzes oxidation-reduction (electron-transfer) reactions - e.g., dehydrogenases and oxidases?",
           ["oxidoreductase", "oxidoreductases"],
           ["oxidoreductase"],
           "Oxidoreductases",
           "Oxidoreductases catalyze redox reactions. The six classes are oxidoreductases, transferases, hydrolases, lyases, isomerases, and ligases.",
           "medium", "recall", "libretexts_biochem", "Enzyme Classification (EC)",
           [sq("Which class transfers a functional group between molecules (e.g., kinases transferring phosphate)?",
               ["transferase", "transferases"],
               "Transferases move functional groups; kinases transfer phosphate."),
            sq("Which class breaks bonds using water (e.g., proteases, lipases)?",
               ["hydrolase", "hydrolases"],
               "Hydrolases catalyze hydrolysis.")]),
        mk("1A", 12, "Enzymes and thermodynamics",
           "Enzymes speed reactions by lowering the activation energy. Do they change the reaction's overall delta-G or its equilibrium position? (yes/no)",
           ["no", "no they do not", "no change", "they do not", "no; unchanged"],
           ["no"],
           "No - enzymes do not change delta-G or the equilibrium; they only lower activation energy and increase rate.",
           "A catalyst accelerates the forward and reverse reactions equally, reaching the same equilibrium faster; it cannot alter the thermodynamics (delta-G, Keq).",
           "medium", "application", "bio2e", "Ch. 6 Metabolism (Enzymes)",
           [sq("What quantity do enzymes lower to speed up a reaction?",
               ["activation energy", "ea", "activation energy (ea)", "the activation energy"],
               "Enzymes lower the activation energy (Ea)."),
            sq("A catalyst speeds the forward reaction; what does it do to the reverse reaction rate?",
               ["also speeds it", "speeds it equally", "increases it", "speeds it up too", "same effect"],
               "It speeds the reverse reaction to the same extent, so equilibrium is unchanged.")]),
        mk("1A", 13, "Non-enzymatic proteins: hemoglobin",
           "Which oxygen-transport protein shows a SIGMOIDAL O2-binding curve because of cooperative binding among its four subunits?",
           ["hemoglobin", "hb", "haemoglobin"],
           ["hemoglobin"],
           "Hemoglobin",
           "Hemoglobin's four subunits bind O2 cooperatively, giving a sigmoidal curve; single-subunit myoglobin is hyperbolic.",
           "medium", "application", "bio2e", "Ch. 39 Respiratory System (Hemoglobin)",
           [sq("How many O2-binding subunits does one hemoglobin molecule have?",
               ["four", "4", "four subunits"],
               "Hemoglobin is a tetramer with four subunits."),
            sq("Which related single-subunit protein has a hyperbolic (non-cooperative) O2 curve?",
               ["myoglobin", "mb"],
               "Myoglobin has one subunit and binds O2 non-cooperatively.")]),
        mk("1A", 14, "Non-enzymatic proteins: collagen",
           "What fibrous structural protein, built from a triple helix and rich in glycine and proline, is the most abundant protein in the human body?",
           ["collagen"],
           ["collagen"],
           "Collagen",
           "Collagen forms a triple-helical fiber giving tensile strength to skin, bone, tendon, and connective tissue; its repeating Gly-X-Y sequence allows tight packing.",
           "medium", "recall", "ap2e", "Connective tissue; the extracellular matrix",
           [sq("Collagen's characteristic structure is a helix made of how many polypeptide chains?",
               ["three", "3", "triple helix", "three chains"],
               "Three chains form the triple helix."),
            sq("Which small amino acid appears at every third position, letting the chains pack tightly?",
               ["glycine", "gly"],
               "Glycine's small H side chain fits the crowded helix core.")]),
        mk("1A", 15, "Protein folding: denaturation",
           "What term describes the loss of a protein's 3-D structure (by heat or extreme pH, say) WITHOUT breaking its peptide bonds?",
           ["denaturation", "denaturing", "denature", "denatured"],
           ["denatur"],
           "Denaturation",
           "Denaturation disrupts non-covalent interactions and higher-order structure while leaving the primary sequence (peptide bonds) intact; it often abolishes function.",
           "medium", "recall", "bio2e", "Ch. 3 Biological Macromolecules (Denaturation)",
           [sq("Does denaturation break the peptide (amide) bonds of the PRIMARY structure?",
               ["no", "no it does not", "does not"],
               "Primary structure (peptide bonds) is retained."),
            sq("Name one physical or chemical agent that can denature a protein.",
               ["heat", "high temperature", "extreme ph", "acid", "base", "urea", "detergent", "high salt"],
               "Heat, extreme pH, urea, or detergents can denature proteins.")]),
        mk("1A", 16, "Enzyme regulation: feedback inhibition",
           "What is the term for regulation in which the END PRODUCT of a metabolic pathway inhibits an enzyme earlier in that pathway?",
           ["feedback inhibition", "negative feedback inhibition", "end-product inhibition", "feedback inhibition (negative feedback)"],
           ["feedback"],
           "Feedback inhibition (negative feedback)",
           "The end product allosterically inhibits an early (often committed-step) enzyme, preventing overproduction and conserving resources.",
           "medium", "application", "bio2e", "Ch. 6 Metabolism (Feedback inhibition)",
           [sq("Feedback inhibitors usually bind the active site or an ALLOSTERIC site of the target enzyme?",
               ["allosteric site", "allosteric", "different site"],
               "They typically act at an allosteric site."),
            sq("Does the end product's accumulation speed up or slow down its own production?",
               ["slow down", "slows it", "decreases it", "inhibits it", "slows"],
               "Accumulated product slows its own synthesis.")]),
        mk("1A", 17, "Amino acids: aromatic residues",
           "Proteins absorb ultraviolet light at 280 nm mainly because of which aromatic amino acid (the strongest contributor)?",
           ["tryptophan", "trp", "w"],
           ["tryptophan"],
           "Tryptophan",
           "Aromatic residues (Trp, Tyr, Phe) absorb near 280 nm; tryptophan contributes most, enabling protein quantitation by A280.",
           "medium", "recall", "libretexts_biochem", "Amino Acids (spectroscopic properties)",
           [sq("Name the three aromatic standard amino acids.",
               ["phenylalanine, tyrosine, tryptophan", "phe tyr trp", "tryptophan tyrosine phenylalanine", "trp tyr phe"],
               "Phenylalanine, tyrosine, and tryptophan."),
            sq("Absorbance at 280 nm is commonly used to measure what property of a protein sample?",
               ["concentration", "protein concentration", "amount", "quantity"],
               "A280 estimates protein concentration.")]),
        mk("1A", 18, "Enzyme-substrate binding",
           "What model of enzyme-substrate binding says the active site CHANGES SHAPE to wrap around the substrate on binding (rather than being a rigid, pre-formed complement)?",
           ["induced fit", "induced-fit model", "induced fit model"],
           ["induced fit"],
           "The induced-fit model",
           "Induced fit (Koshland) holds that substrate binding triggers a conformational change that optimizes catalysis, refining the older lock-and-key idea.",
           "hard", "application", "libretexts_biochem", "Enzyme catalysis (induced fit)",
           [sq("What older model describes the active site as a rigid, exact complement to the substrate?",
               ["lock and key", "lock-and-key", "lock and key model"],
               "The lock-and-key model."),
            sq("The region of an enzyme where substrate binds and catalysis occurs is called the ___?",
               ["active site", "the active site"],
               "The active site.")]),
    ]


# ---------------------------------------------------------------------------
# 1B - Transmission of genetic information from the gene to the protein
# ---------------------------------------------------------------------------
def cat_1B():
    return [
        mk("1B", 1, "DNA structure: bases",
           "Name the two PURINE bases found in DNA.",
           ["adenine and guanine", "adenine, guanine", "guanine and adenine", "a and g", "adenine guanine"],
           ["adenine", "guanine"],
           "Adenine and guanine",
           "Purines (adenine, guanine) have a double-ring structure; pyrimidines (cytosine, thymine, uracil) have a single ring.",
           "easy", "recall", "bio2e", "Ch. 14 DNA Structure and Function",
           [sq("Do purines have a single-ring or a double-ring structure?",
               ["double ring", "double-ring", "two rings", "bicyclic", "double"],
               "Purines are double-ringed."),
            sq("Using the mnemonic 'PURe As Gold', which two bases are the purines?",
               ["adenine and guanine", "a and g", "adenine, guanine"],
               "Adenine and Guanine are the purines.")]),
        mk("1B", 2, "Nucleic acids: RNA vs DNA",
           "Which pyrimidine base is found in RNA but NOT in DNA?",
           ["uracil", "u"],
           ["uracil"],
           "Uracil",
           "RNA uses uracil in place of DNA's thymine; both pair with adenine. Cytosine is the pyrimidine common to both.",
           "easy", "recall", "bio2e", "Ch. 14-15 Nucleic acids and RNA",
           [sq("Which pyrimidine does DNA use that RNA replaces with uracil?",
               ["thymine", "t"],
               "DNA uses thymine; RNA uses uracil."),
            sq("Uracil base-pairs with which purine?",
               ["adenine", "a"],
               "U pairs with A.")]),
        mk("1B", 3, "DNA structure: base pairing",
           "In double-stranded DNA, how many hydrogen bonds form between a guanine-cytosine (G-C) base pair?",
           ["three", "3", "three hydrogen bonds"],
           ["three"],
           "Three",
           "G-C pairs share three hydrogen bonds and A-T pairs share two, so GC-rich DNA is more thermally stable (higher melting temperature).",
           "medium", "recall", "bio2e", "Ch. 14 DNA Structure and Function",
           [sq("How many hydrogen bonds are in an A-T base pair?",
               ["two", "2"],
               "A-T pairs have two hydrogen bonds."),
            sq("Which pairing (G-C or A-T) makes DNA more resistant to melting (higher Tm)?",
               ["g-c", "gc", "guanine-cytosine", "gc pairs"],
               "More H-bonds means G-C is more stable.")]),
        mk("1B", 4, "DNA replication: semiconservative",
           "DNA replication is described by what term, because each new double helix keeps one old (parental) strand and one new strand?",
           ["semiconservative", "semi-conservative", "semiconservative replication"],
           ["semiconservative"],
           "Semiconservative",
           "Meselson and Stahl showed replication is semiconservative: each daughter duplex has one parental and one newly synthesized strand.",
           "easy", "recall", "bio2e", "Ch. 14 DNA Replication",
           [sq("In semiconservative replication, how many strands of each daughter duplex are newly made?",
               ["one", "1", "one strand"],
               "One new strand per daughter duplex."),
            sq("Each parental strand serves as a ___ for synthesizing the new complementary strand.",
               ["template", "a template"],
               "Each old strand is a template.")]),
        mk("1B", 5, "DNA replication: polymerase direction",
           "In which direction does DNA polymerase synthesize a new DNA strand?",
           ["5' to 3'", "5'->3'", "5 to 3", "five prime to three prime", "5'-3'", "5 to 3 prime"],
           ["5", "3"],
           "5' to 3' (it adds nucleotides to the 3' end)",
           "DNA polymerase can only extend a free 3'-OH end, so synthesis proceeds 5'->3'; this constraint creates the leading and lagging strands.",
           "medium", "recall", "bio2e", "Ch. 14 DNA Replication (enzymes)",
           [sq("DNA polymerase adds each new nucleotide to which end of the growing strand?",
               ["3' end", "3 prime", "3'", "the 3' end", "3-oh", "3'-oh"],
               "It adds to the free 3'-OH."),
            sq("Reading the template 3'->5', the new strand therefore grows in which direction?",
               ["5' to 3'", "5 to 3", "5'->3'"],
               "The new strand grows 5'->3'.")]),
        mk("1B", 6, "DNA replication: primer",
           "DNA polymerase cannot start from scratch. Which enzyme synthesizes the short RNA primer it needs to begin?",
           ["primase", "rna primase", "dna primase"],
           ["primase"],
           "Primase",
           "Primase lays down a short RNA primer that provides a free 3'-OH for DNA polymerase to extend.",
           "medium", "recall", "bio2e", "Ch. 14 DNA Replication (enzymes)",
           [sq("Is the primer that is laid down made of DNA or RNA?",
               ["rna", "ribonucleic acid"],
               "The primer is RNA."),
            sq("What does the primer provide that DNA polymerase requires to add nucleotides?",
               ["a free 3' hydroxyl", "3'-oh", "free 3' end", "3' oh group", "a 3'-oh"],
               "A free 3'-OH group.")]),
        mk("1B", 7, "DNA replication: lagging strand",
           "What are the short DNA segments synthesized discontinuously on the lagging strand called?",
           ["okazaki fragments", "okazaki fragment", "okazaki"],
           ["okazaki"],
           "Okazaki fragments",
           "Because polymerase only works 5'->3', the lagging strand is built as discontinuous Okazaki fragments, later joined by DNA ligase.",
           "medium", "recall", "bio2e", "Ch. 14 DNA Replication",
           [sq("Are Okazaki fragments made on the leading or the lagging strand?",
               ["lagging", "lagging strand"],
               "On the lagging strand."),
            sq("Which enzyme seals the nicks between adjacent Okazaki fragments?",
               ["dna ligase", "ligase"],
               "DNA ligase joins them.")]),
        mk("1B", 8, "DNA replication: unwinding",
           "Which enzyme unwinds and separates the two strands of the DNA double helix at the replication fork?",
           ["helicase", "dna helicase"],
           ["helicase"],
           "Helicase",
           "Helicase breaks hydrogen bonds to unwind DNA; single-strand binding proteins keep strands apart and topoisomerase relieves supercoiling ahead of the fork.",
           "easy", "recall", "bio2e", "Ch. 14 DNA Replication (enzymes)",
           [sq("Which proteins coat and stabilize the separated single strands to stop them re-annealing?",
               ["single-strand binding proteins", "ssb", "single strand binding proteins", "ssbs"],
               "Single-strand binding proteins (SSBs)."),
            sq("Which enzyme relieves the supercoiling/tension ahead of the replication fork?",
               ["topoisomerase", "dna gyrase", "topoisomerase (gyrase)"],
               "Topoisomerase (gyrase).")]),
        mk("1B", 9, "Translation: start codon",
           "What is the three-nucleotide START codon on mRNA that initiates translation?",
           ["aug", "a-u-g", "5'-aug-3'"],
           ["aug"],
           "AUG",
           "AUG is the start codon and codes for methionine (the initiator Met in eukaryotes).",
           "easy", "recall", "bio2e", "Ch. 15 Genes to Proteins (Translation)",
           [sq("Which amino acid does the start codon AUG code for?",
               ["methionine", "met", "m"],
               "AUG codes for methionine."),
            sq("A codon consists of how many nucleotides?",
               ["three", "3", "three nucleotides"],
               "Three (a triplet).")]),
        mk("1B", 10, "Translation: stop codons",
           "Name the three mRNA STOP (nonsense) codons that terminate translation.",
           ["uaa uag uga", "uaa, uag, uga", "uag uaa uga", "uaa uga uag", "uag, uaa, uga"],
           ["uaa", "uag", "uga"],
           "UAA, UAG, and UGA",
           "These three codons signal release factors to end translation; they do not code for any amino acid.",
           "medium", "recall", "bio2e", "Ch. 15 The Genetic Code",
           [sq("Do stop codons code for an amino acid?",
               ["no", "no they do not", "none"],
               "No - they signal termination."),
            sq("Proteins that recognize stop codons and end translation are called ___?",
               ["release factors", "release factor"],
               "Release factors.")]),
        mk("1B", 11, "Translation: tRNA",
           "The ANTICODON of a tRNA base-pairs with which feature of the mRNA during translation?",
           ["the codon", "codon", "mrna codon", "the mrna codon"],
           ["codon"],
           "The mRNA codon",
           "Each tRNA anticodon pairs antiparallel with a complementary mRNA codon, delivering the correct amino acid.",
           "medium", "recall", "bio2e", "Ch. 15 Translation (tRNA)",
           [sq("Which molecule carries an amino acid to the ribosome and reads the codon?",
               ["trna", "transfer rna", "trna (transfer rna)"],
               "Transfer RNA (tRNA)."),
            sq("Flexible pairing at the third codon position is described by the ___ hypothesis.",
               ["wobble", "wobble hypothesis"],
               "The wobble hypothesis.")]),
        mk("1B", 12, "RNA processing",
           "Name the protective structure added to the 5' end of eukaryotic pre-mRNA during processing.",
           ["5' cap", "5 prime cap", "7-methylguanosine cap", "guanine cap", "5'-cap", "methylguanosine cap", "cap"],
           ["cap"],
           "The 5' cap (7-methylguanosine cap)",
           "Processing adds a 5' 7-methylguanosine cap and a 3' poly-A tail and removes introns by splicing.",
           "medium", "recall", "bio2e", "Ch. 15 Eukaryotic RNA processing",
           [sq("What is added to the 3' end of eukaryotic mRNA during processing?",
               ["poly-a tail", "poly a tail", "polyadenylation", "poly(a) tail", "poly a"],
               "A poly-A tail."),
            sq("Removal of introns and joining of exons is called ___?",
               ["splicing", "rna splicing", "splicing (rna splicing)"],
               "Splicing.")]),
        mk("1B", 13, "Transcription",
           "Which enzyme synthesizes RNA from a DNA template during transcription?",
           ["rna polymerase", "rna pol", "rna polymerase ii", "rnap"],
           ["rna polymerase"],
           "RNA polymerase",
           "RNA polymerase reads the template strand 3'->5' and builds RNA 5'->3'; unlike DNA polymerase it needs no primer.",
           "easy", "recall", "bio2e", "Ch. 15 Transcription",
           [sq("The DNA strand actually read by RNA polymerase is called the ___ strand.",
               ["template strand", "template", "antisense strand", "antisense"],
               "The template (antisense) strand."),
            sq("Does RNA polymerase require a primer to begin, as DNA polymerase does?",
               ["no", "no it does not", "no primer"],
               "No primer needed.")]),
        mk("1B", 14, "The genetic code",
           "What single word describes the property of the genetic code in which most amino acids are specified by MORE THAN ONE codon?",
           ["degenerate", "degeneracy", "redundant", "redundancy"],
           ["degenerate"],
           "Degenerate (redundant)",
           "With 64 codons for 20 amino acids plus stops, most amino acids have several synonymous codons; the code is degenerate but unambiguous (each codon specifies one amino acid).",
           "medium", "recall", "bio2e", "Ch. 15 The Genetic Code",
           [sq("How many possible codons exist (given a 3-nucleotide, 4-base code)?",
               ["64", "sixty-four"],
               "4^3 = 64 codons."),
            sq("Is a single codon ever ambiguous (coding for more than one amino acid)?",
               ["no", "never", "no it is not"],
               "Each codon specifies only one amino acid.")]),
        mk("1B", 15, "Biotechnology: PCR",
           "What lab technique uses repeated cycles of denaturation, annealing, and extension to EXPONENTIALLY amplify a specific DNA sequence?",
           ["pcr", "polymerase chain reaction"],
           ["pcr"],
           "PCR (polymerase chain reaction)",
           "PCR uses a heat-stable DNA polymerase (Taq), primers, and thermal cycling to roughly double the target DNA each cycle.",
           "medium", "application", "bio2e", "Ch. 17 Biotechnology (PCR)",
           [sq("What heat-stable enzyme extends the primers at high temperature in PCR?",
               ["taq polymerase", "taq", "taq dna polymerase"],
               "Taq polymerase (from Thermus aquaticus)."),
            sq("Short synthetic DNA sequences that define the region to be amplified are called ___?",
               ["primers", "primer", "dna primers"],
               "Primers.")]),
        mk("1B", 16, "Biotechnology: reverse transcription",
           "Which enzyme synthesizes DNA from an RNA template (used by retroviruses and to make cDNA)?",
           ["reverse transcriptase", "rt"],
           ["reverse transcriptase"],
           "Reverse transcriptase",
           "Reverse transcriptase makes complementary DNA (cDNA) from RNA, reversing the usual DNA->RNA flow; it is central to retroviruses such as HIV.",
           "medium", "application", "bio2e", "Ch. 17 Biotechnology (cDNA)",
           [sq("DNA made from an mRNA template by reverse transcriptase is called ___ DNA.",
               ["complementary", "cdna", "complementary dna", "c dna"],
               "cDNA (complementary DNA)."),
            sq("Name one virus that uses reverse transcriptase.",
               ["hiv", "retrovirus", "human immunodeficiency virus"],
               "HIV (a retrovirus).")]),
        mk("1B", 17, "Gene regulation: lac operon",
           "In E. coli, the lac operon is turned ON when which molecule (a lactose isomer) binds and inactivates the repressor?",
           ["allolactose", "lactose", "allolactose (lactose isomer)"],
           ["allolactose"],
           "Allolactose",
           "Allolactose, an inducer derived from lactose, binds the lac repressor and releases it from the operator so transcription proceeds - an inducible operon.",
           "medium", "application", "bio2e", "Ch. 16 Gene Regulation (prokaryotic operons)",
           [sq("When lactose/allolactose is ABSENT, is the lac operon ON or OFF?",
               ["off", "off (repressed)", "repressed"],
               "Off - the repressor blocks transcription."),
            sq("The lac repressor binds which DNA sequence to block transcription?",
               ["operator", "the operator", "operator site"],
               "The operator.")]),
        mk("1B", 18, "Mutations: frameshift",
           "Insertion or deletion of a single nucleotide in a coding region causes what type of mutation, altering ALL downstream codons?",
           ["frameshift", "frameshift mutation", "frame shift"],
           ["frameshift"],
           "A frameshift mutation",
           "Because codons are read as non-overlapping triplets, adding or removing one or two nucleotides shifts the reading frame and usually garbles the rest of the protein.",
           "medium", "application", "bio2e", "Ch. 14 Mutations",
           [sq("A single base substitution that changes one amino acid is called a ___ mutation.",
               ["missense", "missense mutation", "point mutation"],
               "A missense (point) mutation."),
            sq("A substitution that creates a premature STOP codon is called a ___ mutation.",
               ["nonsense", "nonsense mutation"],
               "A nonsense mutation.")]),
    ]


def cat_1C():
    return []  # STUB_1C


def cat_1D():
    return []  # STUB_1D


def cat_2A():
    return []  # STUB_2A


def cat_2B():
    return []  # STUB_2B


def cat_2C():
    return []  # STUB_2C


def cat_3A():
    return []  # STUB_3A


def cat_3B():
    return []  # STUB_3B


def build_all():
    items = []
    items += cat_1A()
    items += cat_1B()
    items += cat_1C()
    items += cat_1D()
    items += cat_2A()
    items += cat_2B()
    items += cat_2C()
    items += cat_3A()
    items += cat_3B()
    return items


def main():
    items = build_all()
    with open(OUT_PATH, "w", encoding="utf-8") as fh:
        json.dump(items, fh, ensure_ascii=False, indent=2)
        fh.write("\n")

    # Coverage summary
    from collections import Counter
    per_cat = Counter(it["aamc_category"] for it in items)
    order = ["1A", "1B", "1C", "1D", "2A", "2B", "2C", "3A", "3B"]
    print(f"Wrote {len(items)} items to {OUT_PATH}")
    print("Items per AAMC content category:")
    for c in order:
        print(f"  {c}: {per_cat.get(c, 0)}")
    ladder_rungs = sum(len(it["subquestions"]) for it in items)
    print(f"Total teach-on-miss sub-questions (ladder rungs): {ladder_rungs}")


if __name__ == "__main__":
    main()
