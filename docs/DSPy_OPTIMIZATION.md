# DSPy Optimization Guide

This guide explains how the fixed pipeline agent design uses [DSPy](https://dspy.ai/) to learn from your behavior and improve over time.

## Overview

The fixed pipeline agent uses DSPy modules for structured-output tasks like evaluating job fit and generating search queries. Initially, these modules rely on instructions alone (zero-shot). As you use the app, it passively collects training data from your actions and can optimize the modules with few-shot examples so they better match your preferences.

**Two modules are currently optimizable:**

| Module | What it does | What it learns |
|--------|-------------|----------------|
| **Evaluator** | Rates job fit (0-5 stars) during job searches | Which jobs you actually add to your tracker vs. ignore, and when you correct fit ratings |
| **Query Generator** | Creates optimized search queries from your criteria | Which query strategies produce results you like (measured by tracker adds) |

## How Feedback Collection Works

### Automatic Recording (Passive)

Every time you run a job search through the AI assistant, the app records:

1. **Evaluator examples** — The profile/resume context and job results (inputs) plus the fit ratings and reasons the evaluator produced (output)
2. **Query generator examples** — Your search criteria and profile (inputs) plus the queries generated (output)

These are saved to the `dspy_examples` database table with `score = NULL` (unscored).

### Automatic Scoring (From Your Actions)

Examples get scored automatically when you interact with search results:

**When you add a search result to your tracker:**
- The app looks at all search results in that conversation
- **Evaluator score**: Measures how well the evaluator's ratings predicted your choices. High-rated jobs (4-5 stars) that you added = good. Low-rated jobs (1-2 stars) that you skipped = good. Mismatches lower the score.
- **Query generator score**: `tracker_adds / total_results` — what fraction of results were good enough to add.
- Scores are recalculated on each add, refining as more data accumulates.

**When you edit a job's fit rating in the tracker:**
- If you change the fit rating on a job that came from a search result, the evaluator score is penalized proportionally to how far off the original rating was.
- Example: If the evaluator rated a job 5 stars but you change it to 2, that's a big penalty. A 4→3 change is a small penalty.

### What Gets Stored

Each training example contains:

| Field | Description |
|-------|-------------|
| `module_name` | Which module produced it (`evaluator` or `query_generator`) |
| `inputs_json` | The inputs sent to the module (profile, criteria, job data, etc.) |
| `output_json` | The module's output (ratings, queries, etc.) |
| `score` | 0.0–1.0 quality score (NULL until scored by user actions) |
| `metadata_json` | Conversation ID linking back to the search session |

## Checking Optimization Readiness

### Via API

```bash
curl http://localhost:5000/api/optimize/status
```

Returns per-module status:

```json
[
  {
    "module_name": "evaluator",
    "scored_count": 12,
    "unscored_count": 3,
    "min_required": 10,
    "ready": true,
    "has_optimized_module": false,
    "last_optimized": null
  },
  {
    "module_name": "query_generator",
    "scored_count": 8,
    "unscored_count": 3,
    "min_required": 10,
    "ready": false,
    "has_optimized_module": false,
    "last_optimized": null
  }
]
```

- `scored_count`: Examples with user feedback (score != NULL)
- `ready`: True when `scored_count >= min_required` (currently 10)
- `has_optimized_module`: Whether a previously compiled module exists on disk

### How Many Examples Do I Need?

**Minimum: 10 scored examples per module.** In practice, this means:

- Run ~3-5 job searches (each search creates 1 evaluator + 1 query generator example)
- Add at least some results to your tracker after each search (this triggers scoring)
- Optionally edit fit ratings on tracked jobs for even better evaluator signal

More examples = better optimization. 20-30 scored examples will give noticeably better results than the minimum 10.

## Running Optimization

Once you have enough scored examples:

```bash
curl -X POST http://localhost:5000/api/optimize
```

This runs DSPy's **BootstrapFewShot** optimizer, which:

1. Takes your scored training examples
2. Selects the best examples as few-shot demonstrations
3. Compiles them into the module's prompt (up to 4 bootstrapped + 8 labeled demos)
4. Saves the compiled module to disk

**Response:**

```json
{
  "status": "success",
  "modules_optimized": ["evaluator"],
  "examples_used": {"evaluator": 15},
  "errors": {"query_generator": "Insufficient examples: 8/10"}
}
```

- Only modules with enough scored examples are optimized
- Modules without enough data are skipped (not an error — just not ready yet)

### Using a Teacher Model (Advanced)

For better optimization results, you can use a more powerful model as a "teacher" to generate the bootstrapped demos:

```bash
curl -X POST http://localhost:5000/api/optimize \
  -H "Content-Type: application/json" \
  -d '{
    "teacher_model": {
      "provider": "anthropic",
      "api_key": "sk-ant-...",
      "model": "claude-sonnet-4-5-20250929"
    }
  }'
```

This is optional — by default, the optimizer uses your configured main LLM.

## What Happens After Optimization

### Automatic Loading

Optimized modules are saved as JSON files in `dspy_modules/` under your data directory:

```
dspy_modules/
├── evaluator.json
└── query_generator.json
```

On every app restart, the EvaluatorModule and QueryGeneratorModule check for these files and load the optimized state automatically. You'll see log messages like:

```
Loaded optimized module 'evaluator' from /path/to/dspy_modules/evaluator.json
```

### What Changes

Before optimization, the modules use only their instruction prompt (zero-shot). After optimization, they include few-shot demonstrations — real examples of good inputs → outputs from your usage history. This helps the LLM:

- **Evaluator**: Better predict which jobs match your actual preferences (not just your stated profile)
- **Query Generator**: Generate search queries in patterns that previously produced results you liked

### Re-optimization

You can run `POST /api/optimize` again at any time. New examples accumulate as you keep using the app, and re-optimizing incorporates the latest feedback. The previous compiled module is overwritten.

### Resetting

To reset to zero-shot (remove optimizations), delete the JSON files:

```bash
rm dspy_modules/evaluator.json dspy_modules/query_generator.json
```

Or, if using a custom data directory:

```bash
rm $DATA_DIR/dspy_modules/*.json
```

The modules will revert to instruction-only mode on the next app restart (or next instantiation during a pipeline run).

## Architecture Details

### File Map

| File | Purpose |
|------|---------|
| `backend/models/dspy_example.py` | `DspyExample` SQLAlchemy model |
| `backend/agent/fixed_pipeline/feedback.py` | Recording functions (`record_evaluator_example`, `record_query_generator_example`), scoring functions (`score_from_tracker_add`, `score_from_job_edit`), and metric functions for BootstrapFewShot |
| `backend/agent/fixed_pipeline/module_store.py` | `save_module()`, `load_module_state()`, `has_optimized_module()` — persists compiled modules as JSON |
| `backend/agent/fixed_pipeline/dspy_modules.py` | DSPy Module classes — `EvaluatorModule` and `QueryGeneratorModule` call `load_module_state()` in `__init__()` |
| `backend/routes/optimize.py` | `POST /api/optimize` and `GET /api/optimize/status` endpoints |

### Data Flow

```
User runs job search
  └─► Pipeline calls EvaluatorAgent / QueryGeneratorAgent
       └─► Inputs + outputs recorded as DspyExample (score=NULL)

User adds result to tracker (or edits job_fit)
  └─► Scoring functions compute quality score (0.0–1.0)
       └─► DspyExample.score updated

Developer/user calls POST /api/optimize
  └─► BootstrapFewShot selects best examples as demos
       └─► Compiled module saved to dspy_modules/*.json

App restarts (or next pipeline run)
  └─► Module loads optimized state from disk
       └─► Future LLM calls include few-shot demos in prompt
```

### Scoring Algorithm Detail

**Evaluator scoring** (triggered on each tracker add):
- For all search results in the conversation with `job_fit >= 4`: what fraction were `added_to_tracker`?
- For all search results with `job_fit <= 2`: what fraction were NOT added?
- Score = average of these two fractions (0.5 default if no results in a bucket)

**Query generator scoring**:
- Score = `tracker_adds / total_search_results` for the conversation

**Job edit penalty** (blended into evaluator score):
- `edit_penalty = max(0.0, 1.0 - (|new_fit - original_fit| / 5.0))`
- Final score = `0.7 * tracker_score + 0.3 * edit_penalty`

### Safety

- All feedback collection is wrapped in try/except — failures never break the main pipeline
- Scoring uses lazy imports so the feedback module is only loaded when the fixed_pipeline design is active
- The optimize endpoint validates minimum example counts before running
- BootstrapFewShot failures for individual modules don't block others
