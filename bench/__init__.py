"""DeepResearch Bench port — the apples-to-apples scoreboard for the engine.

Runs the Research Engine over the 100 official DeepResearch Bench tasks and
scores its reports with RACE (report quality vs a reference report) and FACT
(citation trustworthiness), so the engine can be compared head-to-head against
the published Opus / Gemini / Kimi leaderboard. Model-agnostic judge.

Upstream: github.com/Ayanami0730/deep_research_bench (Apache-2.0). See
``bench/data/LICENSE`` for provenance and attribution.
"""
