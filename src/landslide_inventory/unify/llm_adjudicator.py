"""LLM adjudication for the judgement calls that rules handle badly.

Why an LLM, and why only here
-----------------------------
Measured on the locked test set (n=362, precision 0.801 / recall 0.413), the
140 errors split three ways:

**Definitional (~24).** Rows excluded by the operator's road-obstruction policy.
An annotator asked "did a landslide happen?" says yes; the pipeline excludes
them by design. No model can fix a definition.

**Mechanical (~28).** The rules already extracted the district, the date and the
event correctly, and a downstream gate discarded the row anyway. These are code
bugs. An LLM would be an expensive way to avoid fixing them.

**Judgement (~88, the majority).** "Is this a first report, a follow-up, a risk
warning, or a running total?" over bilingual prose. Substring rules are poor at
this -- ``followup`` alone accounts for 19 misses, ``context_only`` 18,
``risk_only`` 13, and 20 of the 24 false positives are roundups. This is a
reading-comprehension task, and it is the one place a pretrained model has a
real edge over 200 hand-written patterns.

So the LLM adjudicates category three and nothing else.

Reproducibility, which this project actually cares about
--------------------------------------------------------
The pipeline's determinism was designed in (``stable_hash``, sorted iteration,
seeded sampling) and the paper claims reproducibility. A hosted model threatens
that: versions are retired, and the same prompt can drift between runs. Three
things keep the claim honest:

1. **Every response is cached on disk**, keyed by a hash of
   (model, prompt version, article text). A re-run reads the cache and makes no
   network call, so a result is reproducible from the cache alone -- which is
   what should be archived alongside the dataset.
2. **The model id and prompt version are recorded per row.** "We used an LLM"
   is not a method; "claude-sonnet-4-5 with prompt v1, cache checksum X" is.
3. **The rules remain the fallback.** With no API key, no cache entry and no
   network, the pipeline runs exactly as it does today. The LLM is an
   improvement path, never a dependency.

**Selective adjudication.** Only rows the rules are *uncertain* about are sent.
Roughly a quarter of the corpus, so most rows keep a fully deterministic path
and cost stays bounded.

Whether it is actually better is an empirical question, not an assumption --
``validation/benchmark_adjudicator.py`` scores it against the same labelled
rows the rules were scored on. Do not adopt it because it is an LLM; adopt it
if it wins on that comparison, and report both numbers either way.
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from ..utils import ensure_directory, stable_hash

LOGGER = logging.getLogger(__name__)

PROMPT_VERSION = 'v1'
DEFAULT_MODEL = 'claude-sonnet-4-5'

# The vocabularies the model must answer in -- identical to
# validation/locked_test_set.TRUTH_VOCABULARIES, so model output, annotator
# labels and pipeline output are all directly comparable.
ARTICLE_ROLES = ('first_report', 'follow_up', 'retrospective', 'forecast_or_risk',
                 'metaphor_or_nonevent', 'unclear')
GRANULARITIES = ('single', 'multi', 'roundup', 'not_applicable', 'unclear')
HAZARDS = ('landslide', 'debris_flow', 'rockfall', 'avalanche', 'flood',
           'other_hazard', 'not_a_hazard', 'unclear')

SYSTEM_PROMPT = """You classify Nepali and English news articles for a landslide event inventory.

You answer four questions about the article you are given. You are not asked to \
be helpful, tactful, or generous — only accurate. "unclear" is a valid answer \
and is strongly preferred over a guess.

1. is_landslide_event — did a landslide actually occur, as reported fact?
   yes / no / unclear
   A forecast, a warning, a risk assessment or a political metaphor is "no".

2. hazard_type — which hazard does the article describe?
   landslide / debris_flow / rockfall / avalanche / flood / other_hazard / \
not_a_hazard / unclear
   CRITICAL: in Nepali an avalanche is हिमपहिरो or हिउँपहिरो, literally \
"snow-landslide". It contains the word पहिरो (landslide) but IS NOT ONE. \
Everest and Manaslu snow events are avalanches. बाढी alone is a flood.

3. event_granularity — what does the article count?
   single    one identifiable landslide at one place
   multi     several distinct landslides in one article
   roundup   a running total over a period or region, not an event
             ("Floods, landslides claim 1000 lives in five years";
              "134 dead since the monsoon began")
   not_applicable / unclear
   A single event whose toll is stated ("death toll in the Gumthang landslide \
reaches 11") is SINGLE, not a roundup. The distinction is whether the number is \
scoped to a period or region beyond the event itself.

4. article_role — what kind of article is it?
   first_report / follow_up / retrospective / forecast_or_risk / \
metaphor_or_nonevent / unclear
   A relief-distribution or government-response piece about a real past event is \
follow_up.

Reply with JSON only, no prose:
{"is_landslide_event": "...", "hazard_type": "...", "event_granularity": "...", \
"article_role": "...", "confidence": 0.0-1.0, "reason": "one short sentence"}"""


@dataclass(frozen=True)
class Adjudication:
    """One model verdict, plus the provenance needed to reproduce it."""

    is_landslide_event: str
    hazard_type: str
    event_granularity: str
    article_role: str
    confidence: float
    reason: str
    model: str
    prompt_version: str
    from_cache: bool = False

    @property
    def is_headline_event(self) -> bool:
        """Apply the same headline definition the scorer uses."""

        return (
            self.is_landslide_event == 'yes'
            and self.hazard_type in {'landslide', 'debris_flow', 'rockfall'}
            and self.event_granularity in {'single', 'multi'}
        )


# Rows where the rules are confident are not worth a network call. These are the
# reasons that the locked-set error analysis showed the rules getting wrong.
AMBIGUOUS_REASONS = frozenset({
    'followup', 'context_only', 'risk_only', 'roundup', 'insufficient_signal',
    'damage_only', 'event_specific',
})


def needs_adjudication(specificity_reason: str | None, specificity_score: float | None) -> bool:
    """Whether the rules are uncertain enough to be worth a second opinion.

    ``event_specific`` is included deliberately: 20 of 24 false positives were
    rows the rules confidently kept. Confidence and correctness are not the same
    thing, and the errors cluster at both ends.
    """

    reason = (specificity_reason or '').strip()
    if reason in {'out_of_country', 'no_location_signal'}:
        return False  # the rules are reliable here; do not spend a call
    return reason in AMBIGUOUS_REASONS


class ResponseCache:
    """On-disk cache keyed by (model, prompt version, article text).

    This is what makes an LLM stage reproducible. Archive the cache with the
    dataset and the run replays exactly, with no network and no model access --
    including after the model version is retired.
    """

    def __init__(self, path: Path) -> None:
        self.path = path
        ensure_directory(path.parent)
        self._data: dict[str, dict[str, Any]] = {}
        if path.exists():
            try:
                self._data = json.loads(path.read_text(encoding='utf-8'))
            except json.JSONDecodeError:
                LOGGER.warning('Cache at %s is corrupt; starting empty', path)

    @staticmethod
    def key(model: str, title: str | None, text: str | None) -> str:
        return stable_hash('llm_adjudicator', PROMPT_VERSION, model,
                           (title or '')[:500], (text or '')[:6000])

    def get(self, key: str) -> dict[str, Any] | None:
        return self._data.get(key)

    def put(self, key: str, value: Mapping[str, Any]) -> None:
        self._data[key] = dict(value)

    def save(self) -> None:
        self.path.write_text(
            json.dumps(self._data, ensure_ascii=False, indent=0, sort_keys=True) + '\n',
            encoding='utf-8',
        )

    def __len__(self) -> int:
        return len(self._data)


def build_user_prompt(title: str | None, text: str | None, max_chars: int = 6000) -> str:
    return (
        f'TITLE: {(title or "").strip()}\n\n'
        f'ARTICLE:\n{(text or "").strip()[:max_chars]}'
    )


def parse_response(payload: str) -> dict[str, Any] | None:
    """Parse the model's JSON, tolerating a code fence, and reject bad values.

    An out-of-vocabulary answer is dropped rather than coerced -- silently
    mapping a wrong label to a plausible one is how the ``unkown`` truth class
    happened (review section 5.4).
    """

    text = (payload or '').strip()
    if text.startswith('```'):
        text = text.split('\n', 1)[-1].rsplit('```', 1)[0]
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return None
    if not isinstance(data, dict):
        return None
    checks = (
        ('is_landslide_event', ('yes', 'no', 'unclear')),
        ('hazard_type', HAZARDS),
        ('event_granularity', GRANULARITIES),
        ('article_role', ARTICLE_ROLES),
    )
    for field_name, allowed in checks:
        if data.get(field_name) not in allowed:
            LOGGER.warning('Model returned %s=%r, not in vocabulary', field_name, data.get(field_name))
            return None
    return data


def adjudicate(
    title: str | None,
    text: str | None,
    *,
    cache: ResponseCache,
    call_model: Callable[[str, str], str] | None = None,
    model: str = DEFAULT_MODEL,
) -> Adjudication | None:
    """Return the model's verdict, from cache when possible.

    ``call_model`` is injected so this module has no hard dependency on any SDK
    and can be unit-tested with a stub. Returns None when there is no cached
    answer and no way to make a call -- callers fall back to the rules.
    """

    key = cache.key(model, title, text)
    hit = cache.get(key)
    if hit is not None:
        return Adjudication(**{**hit, 'from_cache': True})

    if call_model is None:
        return None

    raw = call_model(SYSTEM_PROMPT, build_user_prompt(title, text))
    parsed = parse_response(raw)
    if parsed is None:
        return None

    record = {
        'is_landslide_event': parsed['is_landslide_event'],
        'hazard_type': parsed['hazard_type'],
        'event_granularity': parsed['event_granularity'],
        'article_role': parsed['article_role'],
        'confidence': float(parsed.get('confidence') or 0.0),
        'reason': str(parsed.get('reason') or '')[:200],
        'model': model,
        'prompt_version': PROMPT_VERSION,
    }
    cache.put(key, record)
    return Adjudication(**record, from_cache=False)


def ollama_caller(
    model: str = 'qwen2.5:7b',
    host: str = 'http://localhost:11434',
) -> Callable[[str, str], str] | None:
    """Build a caller backed by a LOCAL model served by Ollama.

    For this project a local model is not a budget compromise -- it is the
    better choice on the merits.

    **Reproducibility.** The paper claims a reproducible pipeline. A hosted API
    is a moving target: versions are retired, and the same prompt can drift
    between runs. A local model is a pinned artefact. Record the model tag and
    its digest and the classification step replays years later, offline, with no
    account and no vendor.

    **Cost and rate limits.** 4,453 articles, of which only the ~25% ambiguous
    ones are sent. No key, no quota, no per-token cost, so re-running after a
    prompt change is free rather than a decision.

    **Data handling.** Article text never leaves the machine, which some
    institutional data agreements require.

    The trade is quality: a 7B local model is weaker than a frontier API model
    at nuanced judgement. That is exactly what --stage benchmark_adjudicator is
    for. Measure both against the labelled rows and take whichever wins; if the
    local model matches the rules it is already worth having, because it costs
    nothing to re-run.

    Setup:
        # https://ollama.com  -- one install, no account
        ollama pull qwen2.5:7b       # good multilingual, handles Devanagari
        ollama serve

    Model suggestions, best multilingual first:
        qwen2.5:7b     strong Nepali/Devanagari, ~5 GB
        qwen2.5:14b    better judgement if you have ~10 GB of RAM to spare
        gemma2:9b      solid alternative
        llama3.1:8b    weaker on Devanagari; fine for the English half
    """

    import json as _json
    import urllib.error
    import urllib.request

    endpoint = f'{host.rstrip("/")}/api/chat'
    try:
        with urllib.request.urlopen(f'{host.rstrip("/")}/api/tags', timeout=3) as response:
            available = {m.get('name', '') for m in _json.loads(response.read()).get('models', [])}
    except (urllib.error.URLError, TimeoutError, OSError):
        LOGGER.info('No Ollama server at %s; LLM adjudication disabled, using rules', host)
        return None
    if model not in available and available:
        LOGGER.warning('Model %r not pulled. Available: %s. Run: ollama pull %s',
                       model, sorted(available), model)
        return None

    def _call(system: str, user: str) -> str:
        payload = _json.dumps({
            'model': model,
            'messages': [{'role': 'system', 'content': system},
                         {'role': 'user', 'content': user}],
            'stream': False,
            # Greedy decoding: the same input gives the same output, which is
            # what makes the cached run defensible as a method.
            'options': {'temperature': 0, 'seed': 20260807},
            'format': 'json',
        }).encode('utf-8')
        request = urllib.request.Request(
            endpoint, data=payload, headers={'Content-Type': 'application/json'})
        with urllib.request.urlopen(request, timeout=120) as response:
            body = _json.loads(response.read())
        return body.get('message', {}).get('content', '')

    LOGGER.info('Using local model %s via Ollama at %s', model, host)
    return _call


def build_caller(
    prefer: str = 'ollama',
    model: str | None = None,
) -> tuple[Callable[[str, str], str] | None, str]:
    """Pick a caller, preferring the local model. Returns (caller, model_id).

    Order is deliberate: local first because it is free and reproducible, hosted
    only as a fallback, and rules if neither is available. Nothing here ever
    raises -- an absent model must degrade, not break the pipeline.
    """

    if prefer == 'ollama':
        chosen = model or 'qwen2.5:7b'
        caller = ollama_caller(model=chosen)
        if caller is not None:
            return caller, f'ollama/{chosen}'
        caller = anthropic_caller(model=model or DEFAULT_MODEL)
        return caller, (model or DEFAULT_MODEL) if caller else 'rules-only'
    chosen = model or DEFAULT_MODEL
    caller = anthropic_caller(model=chosen)
    if caller is not None:
        return caller, chosen
    caller = ollama_caller()
    return caller, 'ollama/qwen2.5:7b' if caller else 'rules-only'


def anthropic_caller(api_key: str | None = None, model: str = DEFAULT_MODEL) -> Callable[[str, str], str] | None:
    """Build a caller backed by the Anthropic SDK, or None if unavailable.

    Deliberately returns None rather than raising: an absent key must degrade to
    the rule-based path, never break the pipeline.
    """

    key = api_key or os.environ.get('ANTHROPIC_API_KEY')
    if not key:
        LOGGER.info('No ANTHROPIC_API_KEY; LLM adjudication disabled, using rules')
        return None
    try:
        import anthropic  # noqa: PLC0415 - optional dependency by design
    except ImportError:
        LOGGER.info('anthropic package not installed; LLM adjudication disabled')
        return None

    client = anthropic.Anthropic(api_key=key)

    def _call(system: str, user: str) -> str:
        response = client.messages.create(
            model=model,
            max_tokens=400,
            temperature=0,  # determinism, as far as the API allows
            system=system,
            messages=[{'role': 'user', 'content': user}],
        )
        return ''.join(block.text for block in response.content if hasattr(block, 'text'))

    return _call
