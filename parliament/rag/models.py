"""RAG-related Django models."""

from django.contrib.postgres.indexes import GinIndex
from django.contrib.postgres.search import SearchVectorField
from django.db import models


class KnowledgeSource(models.TextChoices):
    BILL = "bill", "Bill"
    DEBATE = "debate", "Debate"
    COMMITTEE = "committee", "Committee"
    MEMBER = "member", "Member"
    VOTE = "vote", "Vote"


class KnowledgeChunk(models.Model):
    """Embedding chunks sourced from parliamentary content."""

    source_type = models.CharField(
        max_length=32, choices=KnowledgeSource.choices)
    source_identifier = models.CharField(max_length=128)
    jurisdiction = models.CharField(max_length=32)
    language = models.CharField(max_length=8, default="en")
    title = models.CharField(max_length=255)
    content = models.TextField()
    search_document = SearchVectorField(null=True)
    embedding = models.JSONField(default=list, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["jurisdiction", "language",
                         "source_type"], name="rag_chunk_scope_idx"),
            GinIndex(fields=["search_document"], name="rag_chunk_search_idx"),
        ]
        unique_together = ("source_type", "source_identifier",
                           "language", "jurisdiction", "title")

    def __str__(self) -> str:  # pragma: no cover - debug helper
        return f"{self.source_type}:{self.source_identifier} ({self.language})"
