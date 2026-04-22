# commentgen harness

Shared project harness for evaluating agent quality in a repeatable way.

## Layout

```text
harness/
  cases/
    comment_reply/
      *.json
  report/
  runner.py
```

## Case format

Each case is a JSON file:

```json
{
  "name": "supportive_short_basic",
  "agent_name": "comment_reply",
  "request": {
    "source_post_text": "We just launched a lightweight analytics plugin for WordPress.",
    "intent": "supportive",
    "tone": "professional",
    "length": "short",
    "variants": 3
  },
  "checks": {
    "min_comments": 3,
    "forbid_any": ["buy now", "click here"],
    "must_include_any": ["great", "nice", "strong", "love"]
  }
}
```

## Run

```bash
python harness/runner.py --base-url http://127.0.0.1:8010
```

Filter to one agent:

```bash
python harness/runner.py --agent comment_reply
```

Sample shortcut script:

```bash
bash harness/sample_run.sh http://127.0.0.1:8010
```

## Included sample case

- `harness/cases/comment_reply/sample_single_reply.json`
- Good starter for the current one-input/one-reply flow

## Output

- Writes a report JSON file under `harness/report/`.
- Prints pass/fail summary in terminal.
