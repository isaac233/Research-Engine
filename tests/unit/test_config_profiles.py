"""Unit tests for the env-var profile expander (``RESEARCH_ENGINE_PROFILE``).

The ``vague`` profile encodes the measured task-53 winning stack (the ``warp``
A/B cell: react path + evidence-grounded scope + WARP writer + dependency-safe
fetchability levers). It is opt-in and uses ``setdefault`` semantics so explicit
env always wins and the default path stays byte-identical.
"""

from __future__ import annotations

from research_engine.config import apply_profile

# Flags the vague profile MUST turn on.
_EXPECTED_ON = {
    "RESEARCH_ENGINE_PLANNER": "react",
    "RESEARCH_ENGINE_RUBRIC_SCAFFOLD": "1",
    "RESEARCH_ENGINE_SCOPING_PASS": "1",
    "RESEARCH_ENGINE_RUBRIC_CRITIC": "1",
    "RESEARCH_ENGINE_WARP_WRITER": "1",
    "RESEARCH_ENGINE_WARP_ROUNDS": "3",
}

# Levers the A/B showed HURT the vague-cohort class — must NOT be set.
_MUST_STAY_UNSET = (
    "RESEARCH_ENGINE_EPHEMERAL_GAP",       # R3: FACT crater 57.6%
    "RESEARCH_ENGINE_REACT_REASONING_LANE",  # R5: worst config, 22.07 RACE
    "RESEARCH_ENGINE_EVIDENCE_RANKER",     # R6: coverage-capping (FACT-first only)
)


def test_vague_profile_sets_winning_flags() -> None:
    env: dict[str, str] = {"RESEARCH_ENGINE_PROFILE": "vague"}
    applied = apply_profile(env)
    assert applied == "vague"
    for key, value in _EXPECTED_ON.items():
        assert env[key] == value, key


def test_vague_profile_excludes_hurtful_levers() -> None:
    env: dict[str, str] = {"RESEARCH_ENGINE_PROFILE": "vague"}
    apply_profile(env)
    for key in _MUST_STAY_UNSET:
        assert key not in env, key


def test_explicit_env_wins_over_profile() -> None:
    env: dict[str, str] = {
        "RESEARCH_ENGINE_PROFILE": "vague",
        "RESEARCH_ENGINE_PLANNER": "linear",  # user override
        "RESEARCH_ENGINE_WARP_ROUNDS": "5",
    }
    apply_profile(env)
    assert env["RESEARCH_ENGINE_PLANNER"] == "linear"
    assert env["RESEARCH_ENGINE_WARP_ROUNDS"] == "5"
    # unset flags still filled by the profile
    assert env["RESEARCH_ENGINE_WARP_WRITER"] == "1"


def test_unset_profile_is_noop() -> None:
    env: dict[str, str] = {}
    assert apply_profile(env) is None
    assert env == {}


def test_unknown_profile_is_noop() -> None:
    env: dict[str, str] = {"RESEARCH_ENGINE_PROFILE": "does-not-exist"}
    assert apply_profile(env) is None
    assert list(env) == ["RESEARCH_ENGINE_PROFILE"]


def test_profile_name_is_normalized() -> None:
    env: dict[str, str] = {"RESEARCH_ENGINE_PROFILE": "  Vague  "}
    assert apply_profile(env) == "vague"
    assert env["RESEARCH_ENGINE_WARP_WRITER"] == "1"
