"""
Input security layer. Scans the operator question for prompt-injection
attempts before the agent does anything else.

The whole premise of the receipt is that a reviewer can trust what the agent
did. An unmitigated injection surface breaks that premise: a user who can
override the system prompt can make the model say anything and the receipt
would dutifully record a confident, well-sourced lie. So injection detection
runs first, the result is stamped on the receipt, and a detected attempt
short-circuits the model call entirely. The agent refuses rather than
sanitizes, because for an audit demo a visible refusal is the honest behavior.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

# Patterns are intentionally conservative: each targets a well-known override
# technique, not generic phrasing, so legitimate operator questions don't trip.
_INJECTION_PATTERNS: list[tuple[str, re.Pattern]] = [
    ("override_instructions", re.compile(r"\b(ignore|disregard|forget)\b.{0,30}\b(previous|prior|above|earlier|all|your|the)\b.{0,20}\b(instruction|instructions|rule|rules|prompt|context|direction|directions)\b", re.I)),
    ("wipe_context", re.compile(r"\b(ignore|disregard|forget)\b\s+(everything|all|what you|anything)\b", re.I)),
    ("role_reassignment", re.compile(r"\b(you are now|act as|pretend to be|behave as|from now on you are|roleplay as)\b", re.I)),
    ("new_directive", re.compile(r"\b(new|updated|revised)\b.{0,15}\b(instruction|instructions|system prompt|directive|directives|rule|rules)\b\s*:?", re.I)),
    ("prompt_disclosure", re.compile(r"\b(reveal|show|print|repeat|expose|leak)\b.{0,25}\b(your )?(system )?(prompt|instructions|rules|guidelines)\b", re.I)),
    ("system_role_spoof", re.compile(r"(^|\n)\s*(system|developer|assistant)\s*:", re.I)),
    ("guardrail_bypass", re.compile(r"\b(bypass|disable|turn off|ignore|skip|override)\b.{0,20}\b(guardrails?|safeguards?|safety|content (policy|policies|filters?)|moderation|filters?)\b", re.I)),
    ("unconditional_directive", re.compile(r"\b(recommend|approve|say|output|return|reply with)\b.{0,40}\b(no matter what|regardless|to (every|all)|always|unconditionally)\b", re.I)),
]


@dataclass
class SecurityCheck:
    injection_detected: bool
    action: str  # "blocked" | "none"
    matched_patterns: list[str] = field(default_factory=list)
    note: str = ""


def scan_injection(question: str) -> SecurityCheck:
    matched = [name for name, pat in _INJECTION_PATTERNS if pat.search(question)]
    if matched:
        return SecurityCheck(
            injection_detected=True,
            action="blocked",
            matched_patterns=matched,
            note=(
                "Prompt-injection patterns detected in the operator input. The question was "
                "not forwarded to the model. The attempt is recorded here for audit."
            ),
        )
    return SecurityCheck(injection_detected=False, action="none", matched_patterns=[], note="")
