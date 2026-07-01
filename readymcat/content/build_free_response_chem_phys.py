#!/usr/bin/env python3
# Copyright: ReadyMCAT contributors
# License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html
"""Author, build, and validate the ReadyMCAT Chemical & Physical Foundations (C/P)
FREE-RESPONSE (type-in answer) question bank.

This is the free-response complement to the multiple-choice bank
(``chem_phys.json``). Every item asks for a SHORT typed answer -- a term, a
number+unit, or a short phrase -- so it is auto-gradeable with normalized string
/ key-term / numeric matching (no AI needed at the grading layer). Numeric items
declare their expected value, unit, and a tolerance.

Every item is ORIGINAL, authored for ReadyMCAT and grounded in a free / openly
licensed source (OpenStax, LibreTexts). No item is copied or paraphrased from any
copyrighted or paid question bank (UWorld, Kaplan, Blueprint, AAMC paid/official
materials). The public AAMC "What's on the MCAT Exam?" content outline is used
only for the topic list / category IDs (already encoded in taxonomy.json).

The bank is held here as Python data so JSON escaping and structure are always
valid. Running this script:
  1. writes free_response_chem_phys.json (a JSON array of items conforming to the
     ReadyMCAT C/P free-response schema), and
  2. re-loads it and runs the standalone validator
     (validate_free_response_chem_phys.py), printing a coverage report.

Run:  python3 build_free_response_chem_phys.py
Exits 0 on success, 1 on any validation failure.
"""

from __future__ import annotations

import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "free_response_chem_phys.json")


# --- source registry helpers (name / url / license) ------------------------
# Each returns a fresh dict so json.dump serializes it inline per item.

def cp2e(chapter: str) -> dict:
    return {"name": f"OpenStax College Physics 2e, {chapter}",
            "url": "https://openstax.org/details/books/college-physics-2e",
            "license": "CC BY 4.0"}


def chem2e(chapter: str) -> dict:
    return {"name": f"OpenStax Chemistry 2e, {chapter}",
            "url": "https://openstax.org/details/books/chemistry-2e",
            "license": "CC BY 4.0"}


def ochem(chapter: str) -> dict:
    return {"name": f"OpenStax Organic Chemistry, {chapter}",
            "url": "https://openstax.org/details/books/organic-chemistry",
            "license": "CC BY 4.0"}


def bio2e(chapter: str) -> dict:
    return {"name": f"OpenStax Biology 2e, {chapter}",
            "url": "https://openstax.org/details/books/biology-2e",
            "license": "CC BY 4.0"}


def ltchem(topic: str) -> dict:
    return {"name": f"LibreTexts Chemistry \u2014 {topic}",
            "url": "https://chem.libretexts.org",
            "license": "CC BY-NC-SA 4.0"}


def ltphys(topic: str) -> dict:
    return {"name": f"LibreTexts Physics \u2014 {topic}",
            "url": "https://phys.libretexts.org",
            "license": "CC BY-NC-SA 4.0"}


# --- item constructors -----------------------------------------------------

def sub(stem: str, accepted: list, explanation: str) -> dict:
    """A guiding teach-on-miss ladder step (a short-answer sub-question)."""
    return {"stem": stem, "answer_type": "free_response",
            "accepted_answers": accepted, "explanation": explanation}


def item(id, cat, subtopic, prompt, accepted, key_terms, model_answer,
         explanation, difficulty, cognitive_level, source, subquestions) -> dict:
    return {
        "id": id,
        "section": "C/P",
        "aamc_category": cat,
        "subtopic": subtopic,
        "answer_type": "free_response",
        "prompt": prompt,
        "accepted_answers": accepted,
        "key_terms": key_terms,
        "model_answer": model_answer,
        "explanation": explanation,
        "difficulty": difficulty,
        "cognitive_level": cognitive_level,
        "source": source,
        "subquestions": subquestions,
    }


# ===========================================================================
#  4A -- Translational motion, forces, work, energy, equilibrium
# ===========================================================================

def _cat_4A() -> list:
    return [
        item("fr-cp-4A-1", "4A", "Kinematics: free fall",
             "A ball is released from rest and falls freely for 3.0 s (g = 10 m/s\u00b2, neglect air resistance). What is its speed just before landing? Give the value with units.",
             ["30 m/s", "30 m s^-1", "30 m/s^1", "v = 30 m/s", "30"],
             ["unit: m/s", "tolerance: \u00b10.5 m/s", "v = g t"],
             "v = v\u2080 + g t = 0 + (10 m/s\u00b2)(3.0 s) = 30 m/s.",
             "From rest v\u2080 = 0, so speed grows linearly as v = g t. The distance fallen (\u00bd g t\u00b2 = 45 m) is a common trap; it is a length, not a speed.",
             "easy", "application", cp2e("Ch. 2: Kinematics"),
             [sub("An object dropped from rest has what initial speed v\u2080 (in m/s)?",
                  ["0", "0 m/s", "zero"],
                  "\"Released from rest\" means v\u2080 = 0."),
              sub("Write the equation for speed after time t for an object falling from rest.",
                  ["v = g t", "v=gt", "gt", "v = at"],
                  "With v\u2080 = 0 and a = g, v = v\u2080 + a t reduces to v = g t."),
              sub("Evaluate v = g t for g = 10 m/s\u00b2 and t = 3.0 s (give m/s).",
                  ["30 m/s", "30"],
                  "(10 m/s\u00b2)(3.0 s) = 30 m/s.")]),

        item("fr-cp-4A-2", "4A", "Kinematics: projectile motion",
             "A marble rolls off a table 1.25 m high with a horizontal speed of 3.0 m/s (g = 10 m/s\u00b2). How far from the base of the table does it land? Give the value with units.",
             ["1.5 m", "1.5 meters", "x = 1.5 m", "1.5"],
             ["unit: m", "tolerance: \u00b10.1 m", "horizontal range"],
             "Fall time from h = \u00bd g t\u00b2: t = \u221a(2h/g) = \u221a(2\u00b71.25/10) = \u221a0.25 = 0.50 s. Range x = v\u2093 t = (3.0)(0.50) = 1.5 m.",
             "Horizontal and vertical motions are independent. The drop height sets the time aloft; the horizontal speed then sets the distance.",
             "medium", "application", cp2e("Ch. 3: Two-Dimensional Kinematics"),
             [sub("With no air resistance, what happens to the horizontal velocity during the flight?",
                  ["stays constant", "constant", "unchanged", "remains 3.0 m/s"],
                  "No horizontal force means a\u2093 = 0, so v\u2093 is constant."),
              sub("How long is the marble airborne? Use h = \u00bd g t\u00b2 with h = 1.25 m, g = 10 m/s\u00b2 (give s).",
                  ["0.50 s", "0.5 s", "0.50"],
                  "t = \u221a(2h/g) = \u221a0.25 = 0.50 s; time aloft depends only on the drop height."),
              sub("Using t = 0.50 s and v\u2093 = 3.0 m/s, find the horizontal distance (give m).",
                  ["1.5 m", "1.5"],
                  "x = v\u2093 t = (3.0)(0.50) = 1.5 m.")]),

        item("fr-cp-4A-3", "4A", "Newton's second law",
             "A constant net force gives a 2.0 kg cart an acceleration of 3.0 m/s\u00b2. What is the magnitude of the net force? Give the value with units.",
             ["6.0 N", "6 N", "F = 6 N", "6"],
             ["unit: N", "tolerance: \u00b10.1 N", "F = m a"],
             "Newton's second law: F_net = m a = (2.0 kg)(3.0 m/s\u00b2) = 6.0 N.",
             "Force equals mass times acceleration; the newton is kg\u00b7m/s\u00b2.",
             "easy", "application", cp2e("Ch. 4: Dynamics: Newton's Laws of Motion"),
             [sub("State Newton's second law relating net force, mass, and acceleration.",
                  ["F = m a", "F=ma", "force = mass x acceleration", "net force = m a"],
                  "F_net = m a."),
              sub("Evaluate (2.0 kg)(3.0 m/s\u00b2) (give N).",
                  ["6.0 N", "6 N", "6"],
                  "2.0 \u00d7 3.0 = 6.0 N."),
              sub("If the same net force acted on a 4.0 kg cart, what acceleration results (m/s\u00b2)?",
                  ["1.5 m/s^2", "1.5 m/s\u00b2", "1.5"],
                  "a = F/m = 6.0/4.0 = 1.5 m/s\u00b2; doubling mass halves acceleration.")]),

        item("fr-cp-4A-4", "4A", "Friction",
             "A 10 kg crate slides across a level floor with coefficient of kinetic friction 0.30 (g = 10 m/s\u00b2). What horizontal force keeps it moving at constant velocity? Give the value with units.",
             ["30 N", "F = 30 N", "30"],
             ["unit: N", "tolerance: \u00b10.5 N", "f = \u03bc_k N"],
             "At constant velocity a = 0, so applied force = kinetic friction. N = mg = (10)(10) = 100 N, so f_k = \u03bc_k N = (0.30)(100) = 30 N.",
             "Kinetic friction is \u03bc_k times the normal force; on a level floor the normal force equals the weight.",
             "medium", "application", cp2e("Ch. 5: Further Applications of Newton's Laws: Friction"),
             [sub("For a crate on a horizontal floor, what does the normal force equal (in N)?",
                  ["100 N", "mg", "m g", "100"],
                  "Vertical equilibrium gives N = mg = (10)(10) = 100 N."),
              sub("Write the equation for kinetic friction in terms of \u03bc_k and N.",
                  ["f = \u03bc_k N", "f = mu_k N", "f=\u03bcN", "friction = coefficient x normal force"],
                  "Kinetic friction equals the coefficient times the normal force."),
              sub("Compute (0.30)(100 N) (give N).",
                  ["30 N", "30"],
                  "f_k = (0.30)(100) = 30 N, which balances the applied force at constant velocity.")]),

        item("fr-cp-4A-5", "4A", "Inclined plane",
             "A block is released from rest on a frictionless incline angled 30\u00b0 above the horizontal (g = 10 m/s\u00b2). What is its acceleration down the incline? Give the value with units.",
             ["5.0 m/s^2", "5.0 m/s\u00b2", "5 m/s^2", "a = 5 m/s^2", "5"],
             ["unit: m/s^2", "tolerance: \u00b10.1 m/s^2", "a = g sin\u03b8"],
             "Along a frictionless incline a = g sin\u03b8 = (10)(sin 30\u00b0) = (10)(0.50) = 5.0 m/s\u00b2.",
             "Only the component of gravity parallel to the surface accelerates the block; that component is g sin\u03b8.",
             "medium", "application", cp2e("Ch. 4-5: Newton's Laws / Inclined planes"),
             [sub("What component of gravitational acceleration acts along a frictionless incline of angle \u03b8?",
                  ["g sin\u03b8", "g sin theta", "gsin\u03b8", "g\u00b7sin\u03b8"],
                  "The parallel component is g sin\u03b8; the perpendicular component g cos\u03b8 is balanced by the normal force."),
              sub("What is sin 30\u00b0?",
                  ["0.5", "0.50", "1/2"],
                  "sin 30\u00b0 = 0.5."),
              sub("Compute g sin\u03b8 = (10 m/s\u00b2)(0.5) (give m/s\u00b2).",
                  ["5.0 m/s^2", "5 m/s^2", "5"],
                  "a = (10)(0.5) = 5.0 m/s\u00b2.")]),

        item("fr-cp-4A-6", "4A", "Torque and static equilibrium",
             "On a seesaw pivoted at its center, a 300 N child sits 1.0 m left of the pivot. How far right of the pivot must a 200 N child sit to balance it? Give the distance with units.",
             ["1.5 m", "d = 1.5 m", "1.5"],
             ["unit: m", "tolerance: \u00b10.05 m", "torque balance"],
             "Balance requires equal and opposite torques: (300 N)(1.0 m) = (200 N)(d) \u2192 d = 300/200 = 1.5 m.",
             "Static equilibrium means net torque = 0. Torque is force \u00d7 lever arm, so the lighter child must sit farther out.",
             "medium", "application", cp2e("Ch. 9: Statics and Torque"),
             [sub("For a balanced seesaw, what must be true of the net torque about the pivot?",
                  ["zero", "net torque = 0", "torques are equal", "0"],
                  "Rotational equilibrium requires the clockwise and counterclockwise torques to be equal (net torque zero)."),
              sub("Write the torque-balance equation for this seesaw.",
                  ["300(1.0) = 200(d)", "300 x 1.0 = 200 x d", "(300)(1.0)=(200)d", "300 = 200 d"],
                  "Torque = force \u00d7 distance on each side: (300)(1.0) = (200)(d)."),
              sub("Solve (300)(1.0) = (200)(d) for d (give m).",
                  ["1.5 m", "1.5"],
                  "d = 300/200 = 1.5 m.")]),

        item("fr-cp-4A-7", "4A", "Work by a constant force",
             "A worker pushes a box 4.0 m across the floor with a constant 25 N force directed along the motion. How much work does the worker do? Give the value with units.",
             ["100 J", "W = 100 J", "100"],
             ["unit: J", "tolerance: \u00b11 J", "W = F d cos\u03b8"],
             "W = F d cos\u03b8 = (25 N)(4.0 m)(cos 0\u00b0) = (25)(4.0)(1) = 100 J.",
             "Work is force times displacement times the cosine of the angle between them; here the force is along the motion (\u03b8 = 0, cos = 1).",
             "easy", "application", cp2e("Ch. 7: Work, Energy, and Energy Resources"),
             [sub("Write the equation for work done by a constant force at angle \u03b8 to the displacement.",
                  ["W = F d cos\u03b8", "W = Fd cos theta", "W=Fdcos\u03b8", "work = F d cos\u03b8"],
                  "W = F d cos\u03b8."),
              sub("What is cos 0\u00b0 (force along the motion)?",
                  ["1", "1.0", "one"],
                  "cos 0\u00b0 = 1, so all of the force does work."),
              sub("Compute (25 N)(4.0 m)(1) (give J).",
                  ["100 J", "100"],
                  "W = 100 J.")]),

        item("fr-cp-4A-8", "4A", "Kinetic energy",
             "What is the kinetic energy of a 2.0 kg object moving at 3.0 m/s? Give the value with units.",
             ["9.0 J", "9 J", "KE = 9 J", "9"],
             ["unit: J", "tolerance: \u00b10.1 J", "KE = 1/2 m v^2"],
             "KE = \u00bd m v\u00b2 = \u00bd (2.0)(3.0)\u00b2 = \u00bd (2.0)(9.0) = 9.0 J.",
             "Kinetic energy scales with the square of speed, so doubling the speed would quadruple KE.",
             "easy", "application", cp2e("Ch. 7: Work, Energy, and Energy Resources"),
             [sub("Write the equation for kinetic energy.",
                  ["KE = 1/2 m v^2", "KE = \u00bd m v\u00b2", "1/2 mv^2", "KE=0.5mv^2"],
                  "KE = \u00bd m v\u00b2."),
              sub("Evaluate v\u00b2 for v = 3.0 m/s (give m\u00b2/s\u00b2).",
                  ["9.0", "9", "9 m^2/s^2"],
                  "(3.0)\u00b2 = 9.0."),
              sub("Compute \u00bd (2.0)(9.0) (give J).",
                  ["9.0 J", "9 J", "9"],
                  "KE = \u00bd(2.0)(9.0) = 9.0 J.")]),

        item("fr-cp-4A-9", "4A", "Conservation of mechanical energy",
             "An object is dropped from rest at a height of 5.0 m (g = 10 m/s\u00b2, no air resistance). What is its speed just before it hits the ground? Give the value with units.",
             ["10 m/s", "v = 10 m/s", "10"],
             ["unit: m/s", "tolerance: \u00b10.5 m/s", "mgh = 1/2 m v^2"],
             "Energy conservation: mgh = \u00bd m v\u00b2 \u2192 v = \u221a(2 g h) = \u221a(2\u00b710\u00b75.0) = \u221a100 = 10 m/s.",
             "Gravitational PE converts entirely to KE; the mass cancels, so speed depends only on height and g.",
             "medium", "application", cp2e("Ch. 7: Work, Energy, and Energy Resources"),
             [sub("As the object falls, gravitational potential energy converts to what form of energy?",
                  ["kinetic energy", "kinetic", "KE"],
                  "PE \u2192 KE with no losses (no friction/air resistance)."),
              sub("Set mgh = \u00bd m v\u00b2 and solve for v.",
                  ["v = sqrt(2gh)", "v = \u221a(2gh)", "sqrt(2gh)", "v=\u221a(2gh)"],
                  "The mass cancels: v = \u221a(2gh)."),
              sub("Compute \u221a(2\u00b710\u00b75.0) (give m/s).",
                  ["10 m/s", "10"],
                  "\u221a100 = 10 m/s.")]),

        item("fr-cp-4A-10", "4A", "Power",
             "A motor does 600 J of work in 4.0 s. What is its average power output? Give the value with units.",
             ["150 W", "P = 150 W", "150"],
             ["unit: W", "tolerance: \u00b11 W", "P = W/t"],
             "P = W/t = 600 J / 4.0 s = 150 W.",
             "Power is the rate of doing work; one watt is one joule per second.",
             "easy", "application", cp2e("Ch. 7: Work, Energy, and Energy Resources"),
             [sub("Write the equation relating power, work, and time.",
                  ["P = W/t", "P=W/t", "power = work/time", "P = W / t"],
                  "Power is work per unit time."),
              sub("Compute 600 J \u00f7 4.0 s (give W).",
                  ["150 W", "150"],
                  "600/4.0 = 150 W."),
              sub("What is the SI unit of power, and what is it equal to?",
                  ["watt", "W", "J/s", "joule per second"],
                  "The watt (W) equals one joule per second.")]),

        item("fr-cp-4A-11", "4A", "Momentum and impulse",
             "A 0.50 kg ball moving at 4.0 m/s is brought to rest. What is the magnitude of the impulse delivered to the ball? Give the value with units.",
             ["2.0 kg\u00b7m/s", "2.0 kg m/s", "2.0 N\u00b7s", "2.0 N s", "2"],
             ["unit: kg\u00b7m/s", "tolerance: \u00b10.1 kg\u00b7m/s", "impulse = change in momentum"],
             "Impulse equals the change in momentum: J = \u0394p = m\u0394v = (0.50)(4.0 \u2212 0) = 2.0 kg\u00b7m/s (equivalently 2.0 N\u00b7s).",
             "Impulse and momentum share units: kg\u00b7m/s = N\u00b7s. Stopping the ball removes all of its momentum.",
             "medium", "application", cp2e("Ch. 8: Linear Momentum and Collisions"),
             [sub("The impulse on an object equals its change in what quantity?",
                  ["momentum", "change in momentum", "\u0394p", "linear momentum"],
                  "Impulse\u2013momentum theorem: J = \u0394p."),
              sub("Write the equation for (linear) momentum.",
                  ["p = m v", "p=mv", "momentum = mass x velocity", "p = mv"],
                  "Momentum p = m v."),
              sub("Compute \u0394p = m\u0394v = (0.50 kg)(4.0 m/s) (give kg\u00b7m/s).",
                  ["2.0 kg\u00b7m/s", "2.0 kg m/s", "2.0 N\u00b7s", "2"],
                  "\u0394p = (0.50)(4.0) = 2.0 kg\u00b7m/s.")]),

        item("fr-cp-4A-12", "4A", "Simple harmonic motion (pendulum)",
             "What is the period of a simple pendulum of length 1.0 m (g = 9.8 m/s\u00b2)? Give the value with units.",
             ["2.0 s", "2.0 seconds", "T = 2.0 s", "2.0"],
             ["unit: s", "tolerance: \u00b10.1 s", "T = 2\u03c0\u221a(L/g)"],
             "T = 2\u03c0\u221a(L/g) = 2\u03c0\u221a(1.0/9.8) = 2\u03c0(0.319) \u2248 2.0 s.",
             "The period of a simple pendulum depends only on length and g (for small angles), not on mass or amplitude.",
             "medium", "application", cp2e("Ch. 16: Oscillatory Motion and Waves"),
             [sub("Write the period formula for a simple pendulum.",
                  ["T = 2\u03c0\u221a(L/g)", "T = 2 pi sqrt(L/g)", "2\u03c0\u221a(L/g)", "T=2\u03c0\u221a(L/g)"],
                  "T = 2\u03c0\u221a(L/g)."),
              sub("Does increasing the bob's mass change the period of a simple pendulum? (yes/no)",
                  ["no", "no change", "does not change", "independent of mass"],
                  "Mass cancels; the period is independent of mass (for small oscillations)."),
              sub("Evaluate 2\u03c0\u221a(1.0/9.8) (give s).",
                  ["2.0 s", "2.0", "2 s"],
                  "\u221a(1.0/9.8) \u2248 0.319, and 2\u03c0(0.319) \u2248 2.0 s.")]),
    ]


# ===========================================================================
#  4B -- Fluids, gases, and gas exchange
# ===========================================================================

def _cat_4B() -> list:
    return [
        item("fr-cp-4B-1", "4B", "Density and specific gravity",
             "An object has a mass of 30 g and a volume of 10 cm\u00b3. What is its density? Give the value with units.",
             ["3.0 g/cm^3", "3.0 g/cm\u00b3", "3 g/cm^3", "3.0 g/mL", "3"],
             ["unit: g/cm^3", "tolerance: \u00b10.1 g/cm^3", "\u03c1 = m/V"],
             "\u03c1 = m/V = 30 g / 10 cm\u00b3 = 3.0 g/cm\u00b3.",
             "Density is mass per unit volume; 1 cm\u00b3 = 1 mL, so 3.0 g/cm\u00b3 = 3.0 g/mL. Its specific gravity (relative to water) is 3.0.",
             "easy", "application", cp2e("Ch. 11: Fluid Statics"),
             [sub("Write the equation for density.",
                  ["\u03c1 = m/V", "rho = m/V", "density = mass/volume", "\u03c1=m/V"],
                  "Density is mass divided by volume."),
              sub("Compute 30 g \u00f7 10 cm\u00b3 (give g/cm\u00b3).",
                  ["3.0 g/cm^3", "3 g/cm^3", "3"],
                  "30/10 = 3.0 g/cm\u00b3."),
              sub("What is this object's specific gravity relative to water (\u03c1_water = 1.0 g/cm\u00b3)?",
                  ["3.0", "3", "3.0 (dimensionless)"],
                  "Specific gravity = \u03c1_object/\u03c1_water = 3.0/1.0 = 3.0 (unitless).")]),

        item("fr-cp-4B-2", "4B", "Buoyancy (Archimedes' principle)",
             "A fully submerged object displaces 2.0 \u00d7 10\u207b\u00b3 m\u00b3 of water (\u03c1 = 1000 kg/m\u00b3, g = 10 m/s\u00b2). What is the buoyant force on it? Give the value with units.",
             ["20 N", "F_b = 20 N", "20"],
             ["unit: N", "tolerance: \u00b10.5 N", "F_b = \u03c1 V g"],
             "F_b = \u03c1_fluid V_displaced g = (1000)(2.0\u00d710\u207b\u00b3)(10) = 20 N.",
             "The buoyant force equals the weight of the displaced fluid (Archimedes' principle).",
             "medium", "application", cp2e("Ch. 11: Fluid Statics \u2014 Archimedes' Principle"),
             [sub("Archimedes' principle: the buoyant force equals the weight of what?",
                  ["displaced fluid", "the fluid displaced", "displaced water", "weight of displaced fluid"],
                  "F_b equals the weight of the fluid displaced by the object."),
              sub("Write the buoyant-force formula in terms of \u03c1, V, and g.",
                  ["F_b = \u03c1 V g", "F = rho V g", "\u03c1Vg", "F_b=\u03c1Vg"],
                  "F_b = \u03c1_fluid V_displaced g."),
              sub("Compute (1000)(2.0\u00d710\u207b\u00b3)(10) (give N).",
                  ["20 N", "20"],
                  "= 20 N.")]),

        item("fr-cp-4B-3", "4B", "Hydrostatic (gauge) pressure",
             "What is the gauge pressure due to the water at a depth of 10 m (\u03c1 = 1000 kg/m\u00b3, g = 10 m/s\u00b2)? Give the value in pascals.",
             ["1.0 \u00d7 10^5 Pa", "100000 Pa", "1.0e5 Pa", "100 kPa", "100000"],
             ["unit: Pa", "tolerance: \u00b12000 Pa", "P = \u03c1 g h"],
             "Gauge pressure P = \u03c1 g h = (1000)(10)(10) = 1.0 \u00d7 10\u2075 Pa (= 100 kPa).",
             "Hydrostatic (gauge) pressure grows linearly with depth; absolute pressure would add atmospheric (\u2248101 kPa).",
             "medium", "application", cp2e("Ch. 11: Fluid Statics \u2014 Pressure"),
             [sub("Write the equation for gauge pressure at depth h in a fluid.",
                  ["P = \u03c1 g h", "P = rho g h", "\u03c1gh", "P=\u03c1gh"],
                  "Gauge pressure P = \u03c1 g h."),
              sub("Compute (1000)(10)(10) (give Pa).",
                  ["100000 Pa", "1.0 x 10^5 Pa", "100 kPa", "100000"],
                  "= 1.0\u00d710\u2075 Pa."),
              sub("Does this depth pressure depend on the cross-sectional area of the water column? (yes/no)",
                  ["no", "no it does not", "independent of area"],
                  "Hydrostatic pressure depends only on \u03c1, g, and depth h \u2014 not on area or total volume.")]),

        item("fr-cp-4B-4", "4B", "Pascal's principle (hydraulics)",
             "In a hydraulic lift, the input piston has area 0.010 m\u00b2 and the output piston has area 0.10 m\u00b2. If 50 N is applied to the input, what force appears at the output? Give the value with units.",
             ["500 N", "F_2 = 500 N", "500"],
             ["unit: N", "tolerance: \u00b15 N", "F2 = F1 A2/A1"],
             "Pascal's principle: pressure is transmitted equally, so F\u2082 = F\u2081(A\u2082/A\u2081) = 50\u00d7(0.10/0.010) = 50\u00d710 = 500 N.",
             "The pressure P = F/A is the same on both pistons, so force scales with area \u2014 the basis of hydraulic force multiplication.",
             "medium", "application", cp2e("Ch. 11: Fluid Statics \u2014 Pascal's Principle"),
             [sub("Pascal's principle: an applied pressure is transmitted how throughout an enclosed fluid?",
                  ["equally", "undiminished", "uniformly", "equally in all directions"],
                  "Pressure is transmitted equally (undiminished) to every part of the fluid."),
              sub("Because pressure is equal on both pistons, write F\u2082 in terms of F\u2081, A\u2081, A\u2082.",
                  ["F2 = F1 A2/A1", "F2 = F1(A2/A1)", "F_2 = F_1 A_2/A_1", "F1 A2/A1"],
                  "Setting F\u2081/A\u2081 = F\u2082/A\u2082 gives F\u2082 = F\u2081(A\u2082/A\u2081)."),
              sub("Compute 50 N \u00d7 (0.10/0.010) (give N).",
                  ["500 N", "500"],
                  "Area ratio = 10, so F\u2082 = 50\u00d710 = 500 N.")]),

        item("fr-cp-4B-5", "4B", "Continuity equation",
             "An incompressible fluid flows at 2.0 m/s through a pipe. Where the pipe's cross-sectional area is half as large, what is the fluid speed? Give the value with units.",
             ["4.0 m/s", "4 m/s", "v_2 = 4 m/s", "4"],
             ["unit: m/s", "tolerance: \u00b10.1 m/s", "A1 v1 = A2 v2"],
             "Continuity: A\u2081v\u2081 = A\u2082v\u2082. With A\u2082 = A\u2081/2, v\u2082 = v\u2081(A\u2081/A\u2082) = 2.0\u00d72 = 4.0 m/s.",
             "For an incompressible fluid the volume flow rate is constant, so narrowing the pipe speeds the fluid up.",
             "medium", "application", cp2e("Ch. 12: Fluid Dynamics \u2014 Flow Rate and Continuity"),
             [sub("Write the continuity equation for an incompressible fluid.",
                  ["A1 v1 = A2 v2", "A\u2081v\u2081 = A\u2082v\u2082", "A1v1=A2v2", "Av = constant"],
                  "The volume flow rate Av is constant: A\u2081v\u2081 = A\u2082v\u2082."),
              sub("If area is halved, how does speed change to keep Av constant?",
                  ["doubles", "speed doubles", "increases by 2", "x2"],
                  "Halving the area doubles the speed."),
              sub("Compute the new speed from v\u2081 = 2.0 m/s (give m/s).",
                  ["4.0 m/s", "4 m/s", "4"],
                  "v\u2082 = 2\u00d72.0 = 4.0 m/s.")]),

        item("fr-cp-4B-6", "4B", "Bernoulli's principle",
             "According to Bernoulli's principle, in a horizontal pipe where the fluid speed increases, how does the fluid's pressure change? Answer in one word.",
             ["lower", "decreases", "it decreases", "drops", "lowers"],
             ["lower", "decreases", "inverse relationship"],
             "It decreases. At constant height, P + \u00bd\u03c1v\u00b2 is constant, so higher speed means lower pressure.",
             "Bernoulli's equation conserves energy per unit volume; faster-moving fluid carries more of its energy as kinetic energy, leaving less as pressure.",
             "medium", "recall", cp2e("Ch. 12: Fluid Dynamics \u2014 Bernoulli's Equation"),
             [sub("Write Bernoulli's equation (name the three terms that sum to a constant).",
                  ["P + 1/2 \u03c1 v^2 + \u03c1 g h", "P + \u00bd\u03c1v\u00b2 + \u03c1gh", "pressure + kinetic + potential", "P+\u00bd\u03c1v\u00b2+\u03c1gh = constant"],
                  "P + \u00bd\u03c1v\u00b2 + \u03c1gh = constant along a streamline."),
              sub("At constant height, if \u00bd\u03c1v\u00b2 (the kinetic term) increases, what must happen to P?",
                  ["decreases", "must decrease", "lower", "goes down"],
                  "The sum is fixed, so P falls as the kinetic term rises."),
              sub("Higher fluid speed therefore corresponds to ____ pressure. (one word)",
                  ["lower", "less", "reduced"],
                  "Higher speed \u2194 lower pressure.")]),

        item("fr-cp-4B-7", "4B", "Viscous flow (Poiseuille's law)",
             "By Poiseuille's law, volume flow rate through a tube is proportional to the fourth power of the radius. If the radius doubles at constant pressure difference, by what factor does the flow rate increase? Give the numeric factor.",
             ["16", "16x", "16 times", "factor of 16"],
             ["dimensionless", "exact", "r^4 dependence"],
             "Q \u221d r\u2074, so doubling r multiplies Q by 2\u2074 = 16.",
             "The steep r\u2074 dependence is why small changes in vessel radius have large effects on blood flow.",
             "medium", "application", cp2e("Ch. 12: Fluid Dynamics \u2014 Viscosity and Poiseuille's Law"),
             [sub("In Poiseuille's law, the flow rate is proportional to the radius raised to what power?",
                  ["4", "fourth", "r^4", "4th"],
                  "Q \u221d r\u2074."),
              sub("Evaluate 2 raised to that power.",
                  ["16", "2^4", "sixteen"],
                  "2\u2074 = 16."),
              sub("So doubling the radius multiplies the flow rate by what factor?",
                  ["16", "16x", "sixteen"],
                  "Flow rate increases 16-fold.")]),

        item("fr-cp-4B-8", "4B", "Ideal gas law",
             "What volume does 2.0 mol of an ideal gas occupy at 1.0 atm and 273 K? Use R = 0.0821 L\u00b7atm/(mol\u00b7K). Give the value in liters.",
             ["44.8 L", "44.8 liters", "45 L", "44.8"],
             ["unit: L", "tolerance: \u00b10.5 L", "V = nRT/P"],
             "V = nRT/P = (2.0)(0.0821)(273)/(1.0) = 44.8 L.",
             "At STP (273 K, 1 atm) one mole of ideal gas occupies 22.4 L, so two moles occupy 44.8 L.",
             "medium", "application", chem2e("Ch. 9: Gases \u2014 The Ideal Gas Law"),
             [sub("Rearrange PV = nRT to solve for volume V.",
                  ["V = nRT/P", "V=nRT/P", "nRT/P"],
                  "V = nRT/P."),
              sub("What volume does 1 mole of ideal gas occupy at STP?",
                  ["22.4 L", "22.4 liters", "22.4"],
                  "The molar volume at STP is 22.4 L."),
              sub("Compute (2.0)(0.0821)(273)/(1.0) (give L).",
                  ["44.8 L", "44.8", "45 L"],
                  "= 44.8 L (\u2248 2 \u00d7 22.4 L).")]),

        item("fr-cp-4B-9", "4B", "Dalton's law of partial pressures",
             "A gas mixture has a total pressure of 1.0 atm. If one component has a mole fraction of 0.25, what is its partial pressure? Give the value with units.",
             ["0.25 atm", "P_A = 0.25 atm", "0.25"],
             ["unit: atm", "tolerance: \u00b10.01 atm", "P_A = X_A P_total"],
             "Partial pressure P_A = X_A \u00b7 P_total = (0.25)(1.0 atm) = 0.25 atm.",
             "Each gas contributes pressure in proportion to its mole fraction; the partial pressures sum to the total (Dalton's law).",
             "easy", "application", chem2e("Ch. 9: Gases \u2014 Dalton's Law"),
             [sub("Write the relationship between a gas's partial pressure, its mole fraction, and the total pressure.",
                  ["P_A = X_A P_total", "P = X P_total", "partial pressure = mole fraction x total", "P_A=X_A\u00b7P"],
                  "P_A = X_A P_total."),
              sub("Compute (0.25)(1.0 atm) (give atm).",
                  ["0.25 atm", "0.25"],
                  "= 0.25 atm."),
              sub("Dalton's law: the partial pressures of all components sum to what?",
                  ["total pressure", "the total pressure", "P_total", "1.0 atm"],
                  "\u03a3 P_i = P_total.")]),

        item("fr-cp-4B-10", "4B", "Kinetic-molecular theory / Graham's law",
             "By Graham's law, how many times faster does hydrogen gas (H\u2082, M = 2 g/mol) effuse compared with oxygen gas (O\u2082, M = 32 g/mol)? Give the numeric factor.",
             ["4", "4x", "4 times", "4:1"],
             ["dimensionless", "exact", "rate \u221d 1/\u221aM"],
             "Rate \u221d 1/\u221aM, so rate_H2/rate_O2 = \u221a(M_O2/M_H2) = \u221a(32/2) = \u221a16 = 4.",
             "Lighter molecules move faster at a given temperature, so they effuse more quickly \u2014 the ratio goes as the square root of the inverse molar-mass ratio.",
             "medium", "application", chem2e("Ch. 9: Gases \u2014 Effusion and Diffusion (Graham's Law)"),
             [sub("In Graham's law, effusion rate is proportional to 1 over the square root of what property?",
                  ["molar mass", "molar mass (M)", "mass", "M"],
                  "Rate \u221d 1/\u221aM."),
              sub("Form the ratio: rate_H2/rate_O2 = \u221a(M_O2/M_H2). Plug in the molar masses.",
                  ["\u221a(32/2)", "sqrt(32/2)", "\u221a16", "sqrt(16)"],
                  "= \u221a(32/2) = \u221a16."),
              sub("Evaluate \u221a16.",
                  ["4", "four"],
                  "\u221a16 = 4, so H\u2082 effuses 4\u00d7 faster.")]),

        item("fr-cp-4B-11", "4B", "Henry's law (gas solubility)",
             "By Henry's law, if the partial pressure of a gas above a liquid triples (temperature constant), by what factor does the dissolved gas concentration change? Give the numeric factor.",
             ["3", "3x", "3 times", "triples"],
             ["dimensionless", "exact", "C = k P"],
             "Henry's law: C = k_H P, so C \u221d P. Tripling the partial pressure triples the dissolved concentration (factor 3).",
             "This linear pressure\u2013solubility relationship underlies gas exchange and, e.g., the fizz when a soda bottle is depressurized.",
             "easy", "application", chem2e("Ch. 11: Solutions and Colloids \u2014 Henry's Law"),
             [sub("Write Henry's law relating dissolved concentration C and partial pressure P.",
                  ["C = k P", "C = k_H P", "C=kP", "concentration = k times pressure"],
                  "C = k_H P (solubility is proportional to partial pressure)."),
              sub("Because C \u221d P, tripling P changes C by what factor?",
                  ["3", "triples", "x3"],
                  "C scales directly with P."),
              sub("If instead the partial pressure were halved, the dissolved concentration would do what?",
                  ["halve", "halves", "decrease by half", "drop to half"],
                  "C \u221d P, so halving P halves C.")]),
    ]


def build_items() -> list:
    items: list = []
    items += _cat_4A()
    items += _cat_4B()
    return items


def main() -> int:
    items = build_items()
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(items, fh, ensure_ascii=False, indent=2)
        fh.write("\n")
    with open(OUT, "r", encoding="utf-8") as fh:
        reloaded = json.load(fh)
    print(f"Wrote {OUT} ({len(reloaded)} items).\n")

    sys.path.insert(0, HERE)
    import validate_free_response_chem_phys as V
    return V.main(["validate", OUT])


if __name__ == "__main__":
    raise SystemExit(main())
