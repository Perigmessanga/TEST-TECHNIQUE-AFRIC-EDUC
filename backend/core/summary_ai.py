import json
import os
import re
import urllib.error
import urllib.request
from collections import Counter
from decimal import Decimal

from django.conf import settings
from django.utils import timezone

from .models import AICall


def fallback_text(counts):
    return (
        f"{counts['eleves']} élèves inscrits, {counts['present']} présents, "
        f"{counts['retards']} retards et {counts['sorties_hors_plage']} sorties hors plage."
    )


def _numbers_match(text, counts):
    expected = Counter(str(counts[key]) for key in ('eleves', 'present', 'retards', 'sorties_hors_plage'))
    return Counter(re.findall(r'\d+', text)) == expected


def _daily_cost():
    today = timezone.localdate()
    return sum(
        (call.cost for call in AICall.objects.filter(at__date=today)),
        Decimal('0'),
    )


def _estimate_cost(input_tokens, output_tokens):
    return (
        Decimal(input_tokens) * Decimal(os.getenv('AI_INPUT_USD_PER_MILLION', '0.15'))
        + Decimal(output_tokens) * Decimal(os.getenv('AI_OUTPUT_USD_PER_MILLION', '0.60'))
    ) / Decimal(1_000_000)


def generate_summary_text(counts):
    api_key = os.getenv('OPENAI_API_KEY', '').strip()
    if not api_key:
        return fallback_text(counts), 'gabarit'

    daily_limit = Decimal(str(getattr(settings, 'AI_DAILY_COST_LIMIT', '0.10')))
    model = os.getenv('OPENAI_MODEL', 'gpt-4o-mini')
    prompt = (
        'Rédige une phrase française courte à partir de ces quatre nombres dans cet ordre: '
        'élèves inscrits, présents, retards, sorties hors plage. Ne modifie, ne calcule et '
        'n’ajoute aucun nombre. Réponds uniquement en JSON {"text":"..."}. Données: '
        + json.dumps(counts, ensure_ascii=False)
    )

    for _ in range(2):
        input_tokens = max(1, len(prompt) // 4)
        estimated_output_tokens = 128
        estimated_cost = _estimate_cost(input_tokens, estimated_output_tokens)
        if _daily_cost() + estimated_cost > daily_limit:
            return fallback_text(counts), 'gabarit_plafond'
        call = AICall.objects.create(
            model=model,
            input_tokens=input_tokens,
            output_tokens=estimated_output_tokens,
            cost=estimated_cost,
            status='pending',
        )
        body = {
            'model': model,
            'temperature': 0,
            'response_format': {'type': 'json_object'},
            'messages': [{'role': 'user', 'content': prompt}],
        }
        request = urllib.request.Request(
            os.getenv('OPENAI_BASE_URL', 'https://api.openai.com/v1/chat/completions'),
            data=json.dumps(body).encode('utf-8'),
            headers={'Authorization': f'Bearer {api_key}', 'Content-Type': 'application/json'},
            method='POST',
        )
        try:
            with urllib.request.urlopen(request, timeout=8) as response:
                payload = json.loads(response.read().decode('utf-8'))
            content = payload['choices'][0]['message']['content']
            parsed = json.loads(content)
            text = parsed.get('text')
            valid = isinstance(text, str) and 10 <= len(text) <= 500 and _numbers_match(text, counts)
            usage = payload.get('usage', {})
            in_tokens = int(usage.get('prompt_tokens', input_tokens))
            out_tokens = int(usage.get('completion_tokens', max(1, len(str(content)) // 4)))
            call.input_tokens = in_tokens
            call.output_tokens = out_tokens
            call.cost = _estimate_cost(in_tokens, out_tokens)
            call.status = 'success' if valid else 'invalid_output'
            call.save(update_fields=['input_tokens', 'output_tokens', 'cost', 'status'])
            if valid:
                return text.strip(), 'modele'
        except (urllib.error.URLError, TimeoutError, ValueError, KeyError, TypeError, json.JSONDecodeError) as error:
            call.status = f'error:{type(error).__name__}'[:20]
            call.save(update_fields=['status'])

    return fallback_text(counts), 'gabarit_erreur_modele'
