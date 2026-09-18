from django.core.management.base import BaseCommand
from pydantic import BaseModel

from ai import client
from ai.models import AICallLog


class Capital(BaseModel):
    country: str
    capital: str


class Command(BaseCommand):
    help = "Calls the configured AI provider once per capability and prints the results."

    def handle(self, *args, **options):
        self.stdout.write("text: " + client.generate_text(feature="eval", prompt="Reply with the single word: ready"))
        capital = client.generate_structured(feature="eval", prompt="What is the capital of France?", schema=Capital)
        self.stdout.write(f"structured: {capital!r}")
        self.stdout.write(f"embedding dimension: {len(client.embed_query('photosynthesis'))}")
        for log in AICallLog.objects.order_by("-created_at")[:3]:
            self.stdout.write(
                f"  {log.feature} {log.model} {log.status} {log.latency_ms}ms "
                f"in={log.input_tokens} out={log.output_tokens} cost=${log.estimated_cost_usd}"
            )
