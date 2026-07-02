# 🐜 Pheromone - Ant Colony Experience Routing System

**One-liner**: Multi-agent shared experience system. Like ant pheromone trails — successful paths get stronger, failed paths fade away. Every agent deposits experience, every agent benefits from history.

## What is this?

Pheromone is a lightweight CLI tool that lets multiple AI agents (Codex, Trae CN, Hermes, custom agents) share task execution experience. When an agent solves a problem, it deposits "pheromone" on that solution path. When another agent faces a similar task, it queries the pheromone trails and sees which approaches historically worked best.

Think of it as **muscle memory for your AI agent fleet**.

## Core Mechanism: Hybrid Evaporation Model (v2)

Classic ACO (Ant Colony Optimization) uses iteration-based evaporation. Real-world knowledge has a shelf life (APIs change, tools update). Pheromone v2 combines both:

```
Total Evaporation = Time-based decay + Activity competition + Failure penalty - Confidence immunity
```

| Mechanism | Rate | Why |
|-----------|------|-----|
| **Time baseline decay** | 0.5%/day | Handles "bit rot" — old knowledge becomes less relevant |
| **Activity competition** | 3% per deposit (same task type) | When a new solution succeeds, competitors fade slightly — prevents stagnation |
| **Failure acceleration** | Extra 10% self-evaporation on failure | Bad paths die faster than they decay naturally |
| **Confidence immunity** | Time decay halved for solutions with ≥5 successes and ≥90% success rate | Proven "iron law" solutions persist longer |
| **Exploration rate** | 15% | Random chance to pick a non-optimal solution — avoids local optima |

### Evaporation Curve Examples

| Scenario | After 30 days | After 90 days | After 180 days |
|----------|---------------|---------------|----------------|
| Normal solution | 86% remaining | 64% | 40% |
| 🏆 Confident solution | 93% remaining | 80% | 64% |
| Competing solution (5 new deposits on rival) | 86%×0.97⁵ ≈ 74% | — | — |

## Quick Start

```bash
# Before doing a task — check what worked before
python pheromone_cli.py query "web scraping"

# After completing a task — deposit your experience
python pheromone_cli.py deposit "web scraping" "requests+BeautifulSoup" \
  --success --description "Works for static sites, 30s avg" --agent "MyAgent"

# If you failed — record that too (negatives are valuable!)
python pheromone_cli.py deposit "web scraping" "selenium headless" \
  --fail --description "Detected by anti-bot on 80% of targets" --agent "MyAgent"

# Let the ant colony pick for you
python pheromone_cli.py select "web scraping"

# Check system health
python pheromone_cli.py status
python pheromone_cli.py list-tasks
python pheromone_cli.py agent-stats "MyAgent"
```

## CLI Reference

```bash
# Query best solutions for a task type
python pheromone_cli.py query "<task_type>" [--top-k 5]

# Ant colony probabilistic selection
python pheromone_cli.py select "<task_type>"

# Deposit experience (after task completion)
python pheromone_cli.py deposit "<task_type>" "<solution>" --success \
  [--duration SECONDS] [--description "desc"] [--agent "AgentName"]
python pheromone_cli.py deposit "<task_type>" "<solution>" --fail \
  [--description "why it failed"] [--agent "AgentName"]

# System status
python pheromone_cli.py status
python pheromone_cli.py list-tasks
python pheromone_cli.py agent-stats "<AgentName>"
python pheromone_cli.py evaporate  # Manual time-decay flush

# JSON output for programmatic use
python pheromone_cli.py query "<task_type>" --json
```

## Naming Conventions

| Field | Convention | Example |
|-------|-----------|---------|
| Task type | Chinese/English, "domain + action" format | `微信爬虫运维`, `CDP生图`, `web scraping` |
| Solution name | Distinct, describes the specific method | `CDP串行导航+scan+save`, `Pillow垫图+凡道API` |
| Agent name | Your agent's identifier | `Trae CN`, `Codex`, `Hermes` |

## Data Model

### tasks.json

```json
{
  "task_type_name": {
    "solution_name": {
      "pheromone": 1.0,
      "success_count": 2,
      "fail_count": 1,
      "avg_time": 180.5,
      "avg_time_sum": 541.5,
      "avg_time_count": 3,
      "last_used": "2026-07-01T15:30:00",
      "description": "What this solution does and key pitfalls",
      "agents": ["Trae CN", "Hermes"]
    }
  }
}
```

### agents.json

```json
{
  "AgentName": {
    "total_tasks": 25,
    "success_count": 22,
    "fail_count": 3,
    "specialties": {
      "task_type": {"success": 5, "fail": 0}
    },
    "last_active": "2026-07-02T15:50:00"
  }
}
```

## Python API

```python
from pheromone_core import get_core

core = get_core()  # Uses ./data/ by default
# core = get_core("/path/to/data")  # Custom data directory

# Before task
solutions = core.query("web scraping", top_k=3)
best = core.select_solution("web scraping")  # Probabilistic selection

# After task
core.deposit("web scraping", "requests+BS4", success=True,
             duration_seconds=45, description="Static sites only",
             agent_name="MyAgent")
```

## Architecture

```
┌─────────────┐    query     ┌──────────────┐
│  Agent Task │ ──────────→  │ PheromoneCore│
│  (any agent)│              │  - Time decay│
└─────────────┘              │  - Competition│
       ↑                     │  - Confidence │
       │   deposit            └──────┬───────┘
       └─────────────────────────────┘
                    │
              ┌─────▼─────┐
              │ data/     │
              │ tasks.json│ ← Shared across all agents
              │ agents.json│
              └───────────┘
```

- **Thread-safe**: In-process lock prevents concurrent write corruption
- **Atomic writes**: Temp file → fsync → rename (crash-proof)
- **Lazy evaporation**: Computed on read/write, no cron job required
- **Zero dependencies**: Pure Python stdlib, no pip install needed

## Best Practices

1. **Always query before starting a non-trivial task** — don't reinvent the wheel
2. **Always deposit after task completion** — failures are just as valuable as successes
3. **Be specific with solution names** — "Pillow batch compress" vs "script approach"
4. **Describe key pitfalls in descriptions** — the description is the actual knowledge transfer
5. **Use --agent consistently** — this builds agent capability profiles
6. **Share the data directory** — point all agents to the same `data/` folder for cross-agent learning

## Integration with Agents

Pheromone is agent-agnostic. Any agent that can execute shell commands can use it:

- **Trae CN**: Load as a Skill, use CLI commands in task workflow
- **Codex**: CLI commands in task execution (pre-task query, post-task deposit)
- **Hermes**: Configure as a default_skill for automatic loading
- **Custom agents**: Call CLI or import Python API directly

## License

MIT

## Acknowledgments

Inspired by ant colony optimization algorithms and the principle that collective experience beats individual trial-and-error.
