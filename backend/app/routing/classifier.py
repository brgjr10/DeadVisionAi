"""
Task classification system.
Uses local model (qwen2.5-0.5b-instruct) for classification; 
falls back to heuristics if unavailable.
No external API calls are made during classification.
"""
from __future__ import annotations

import re
import time
from typing import Optional

import httpx

from app.config import get_settings
from app.observability.logging_config import get_logger
from app.routing.schemas import TaskClassification
from app.utils.routing_helper import local_classify, is_classify_available

logger = get_logger(__name__)

# Intent categories supported by the classifier
INTENT_CATEGORIES = [
    "question-answering",
    "code-generation",
    "code-review",
    "summarization",
    "web-search",
    "file-operation",
    "shell-command",
    "memory-retrieval",
    "multi-step-planning",
]

# Keywords that indicate higher complexity
_COMPLEXITY_KEYWORDS = [
    "explain", "analyze", "compare", "design", "architect", "implement",
    "refactor", "optimize", "debug", "why", "how does", "step by step",
    "multiple", "complex", "advanced", "comprehensive", "detailed",
]

# Keywords that indicate need for real-time/current information
_CURRENT_INFO_KEYWORDS = [
    # time / date
    "time", "clock", "date", "today", "now", "current", "live",
    # events / news
    "weather", "stock", "price", "news", "latest", "recent", "update",
    "schedule", "calendar", "event", "holiday", "sunrise", "sunset",
    "deadline",
    # recency / release signals — anything that implies the answer may have
    # changed since the model training cut-off
    "newest", "new", "latest", "recent", "just released", "released",
    "launched", "announced", "debuted", "introduced", "unveiled",
    "coming out", "coming soon", "upcoming", "this year", "this month",
    "current model", "current version", "latest version", "latest build",
    "what's new", "what is new", "what are the latest",
]

# Keywords that indicate multi-step tasks
_MULTI_STEP_KEYWORDS = [
    "then", "after that", "next", "finally", "first", "second", "third",
    "step", "workflow", "pipeline", "sequence", "plan",
]

# Tool-only patterns (no LLM needed)
_TOOL_ONLY_PATTERNS = [
    r"\bread\s+file\b",
    r"\blist\s+(files|directory|dir)\b",
    r"\bgit\s+(status|log|diff|clone)\b",
    r"\bsearch\s+for\b",
    r"\bfind\s+file\b",
    r"\brun\s+command\b",
    r"\bexecute\b",
]

# Local classification prompt
_CLASSIFY_PROMPT = """Classify the following task. Respond with JSON only.

Task: {content}

Respond with this exact JSON structure:
{{
  "intent": "<one of: question-answering, code-generation, code-review, summarization, web-search, file-operation, shell-command, memory-retrieval, multi-step-planning>",
  "complexity_score": <float 0.0-1.0>,
  "estimated_tokens": <integer>,
  "recommended_tools": [<list of tool names>],
  "tool_only_flag": <true|false>,
  "confidence": <float 0.0-1.0>
}}"""


class TaskClassifier:
    """
    Classifies tasks using local Ollama/OpenAI-compatible inference.
    Fallback chain: local model → keyword heuristics (zero external cost).
    """

    def __init__(self) -> None:
        self._settings = get_settings()

    def _heuristic_classify(self, content: str, context: list) -> TaskClassification:
        """
        Fallback heuristic classifier when local model is unavailable.
        Uses keyword matching and content analysis. Zero external API calls.
        """
        lower = content.lower()
        words = lower.split()
        word_count = len(words)

        # Estimate tokens (rough: 1 word ≈ 1.3 tokens)
        estimated_tokens = int(word_count * 1.3) + sum(len(m) for m in context) // 4

        # Detect intent
        intent = "question-answering"
        if any(kw in lower for kw in ["write code", "implement", "create function", "def ", "class "]):
            intent = "code-generation"
        elif any(kw in lower for kw in ["review", "check code", "what's wrong", "bug"]):
            intent = "code-review"
        elif any(kw in lower for kw in ["summarize", "summary", "tldr", "brief"]):
            intent = "summarization"
        elif any(kw in lower for kw in _CURRENT_INFO_KEYWORDS):
            intent = "web-search"
        elif any(kw in lower for kw in ["search", "find online", "look up", "google"]):
            intent = "web-search"
        elif any(kw in lower for kw in ["read file", "write file", "list files", "directory"]):
            intent = "file-operation"
        elif any(kw in lower for kw in ["run", "execute", "command", "shell", "bash", "terminal"]):
            intent = "shell-command"
        elif any(kw in lower for kw in ["remember", "recall", "what did i", "memory"]):
            intent = "memory-retrieval"
        elif any(kw in lower for kw in _MULTI_STEP_KEYWORDS) and word_count > 20:
            intent = "multi-step-planning"

        # Complexity scoring
        complexity = 0.0

        # Length factor (0.0 - 0.3)
        complexity += min(word_count / 200, 0.3)

        # Code presence (0.1)
        if re.search(r"```|def |class |import |function |=>", content):
            complexity += 0.1

        # Multi-step indicators (0.2)
        multi_step_count = sum(1 for kw in _MULTI_STEP_KEYWORDS if kw in lower)
        complexity += min(multi_step_count * 0.05, 0.2)

        # Reasoning keywords (0.2)
        reasoning_count = sum(1 for kw in _COMPLEXITY_KEYWORDS if kw in lower)
        complexity += min(reasoning_count * 0.04, 0.2)

        # Context length factor (0.2)
        if context:
            complexity += min(len(context) * 0.02, 0.2)

        complexity = min(complexity, 1.0)

        # Tool-only detection
        tool_only = any(re.search(pattern, lower) for pattern in _TOOL_ONLY_PATTERNS)
        if tool_only:
            complexity = min(complexity, 0.3)

        # Recommended tools
        recommended_tools: list[str] = []
        if intent in ("file-operation",):
            recommended_tools.append("filesystem")
        if intent in ("shell-command",):
            recommended_tools.append("shell")
        if intent in ("web-search",):
            recommended_tools.append("web_search")
        if "git" in lower:
            recommended_tools.append("git")

        return TaskClassification(
            intent=intent,
            complexity_score=round(complexity, 3),
            estimated_tokens=estimated_tokens,
            recommended_tools=recommended_tools,
            tool_only_flag=tool_only,
            confidence=0.7,  # heuristic confidence is lower
        )

    def _compress_context(self, context: list) -> list:
        """Compress context if it exceeds the token limit."""
        settings = get_settings()
        limit = settings.episodic_token_limit
        total_chars = sum(len(str(m)) for m in context)
        # Rough: 4 chars ≈ 1 token
        if total_chars // 4 <= limit:
            return context
        # Keep most recent messages that fit
        compressed = []
        budget = limit * 4
        for msg in reversed(context):
            msg_len = len(str(msg))
            if budget - msg_len >= 0:
                compressed.insert(0, msg)
                budget -= msg_len
            else:
                break
        logger.debug(
            "context_compressed",
            original=len(context),
            compressed=len(compressed),
        )
        return compressed

    async def _classify_with_local_model(self, content: str) -> Optional[TaskClassification]:
        """
        Attempt classification via the local model helper (qwen2.5-0.5b-instruct).
        Returns None if the available check fails or the call raises.
        """
        if not await is_classify_available():
            logger.info("local_classify_demoted_by_rdocl")
            return None

        try:
            local_result = await local_classify(content)

            # Map local_result category to intent and set complexity score
            category = local_result.get("category", "complex")

            # Mapping from category to intent and complexity score
            if category == "simple":
                intent = "question-answering"
                complexity_score = 0.2
            elif category == "coding":
                intent = "code-generation"
                complexity_score = 0.5
            elif category == "huge_context":
                intent = "web-search"
                complexity_score = 0.9
            else:  # complex or fallback
                intent = "multi-step-planning"
                complexity_score = 0.8

            # Estimate tokens based on content length
            word_count = len(content.split())
            estimated_tokens = int(word_count * 1.3)

            # Determine recommended tools based on intent
            recommended_tools: list[str] = []
            if intent == "file-operation":
                recommended_tools.append("filesystem")
            elif intent == "shell-command":
                recommended_tools.append("shell")
            elif intent == "web-search":
                recommended_tools.append("web_search")
            elif "git" in content.lower():
                recommended_tools.append("git")

            # Post-classify keyword overlay: the local 0.5b model may mis-map
            # recency queries (newest, released, launched, just announced, …)
            # to "complex" or "simple".  A cheap keyword check here catches those
            # before the expensive fallback path is taken.
            _lower = content.lower()
            _current_signals = [
                "newest", "new ", "latest", "recent", "just released", "released",
                "launched", "announced", "debuted", "introduced", "unveiled",
                "coming out", "coming soon", "upcoming", "this year", "this month",
                "current model", "latest model", "current version", "new model",
                "just came out", "is out", "is available",
            ]
            if "web_search" not in recommended_tools and any(
                kw in _lower for kw in _current_signals
            ):
                recommended_tools.append("web_search")

            tool_only_flag = False
            confidence = 0.8

            return TaskClassification(
                intent=intent,
                complexity_score=complexity_score,
                estimated_tokens=estimated_tokens,
                recommended_tools=recommended_tools,
                tool_only_flag=tool_only_flag,
                confidence=confidence,
            )
        except Exception as exc:
            logger.warning("local_model_classification_failed", error=str(exc))
            return None

    async def classify(self, content: str, context: list) -> TaskClassification:
        """
        Classify a task.
        Fallback chain (2 tiers max, zero external API cost):
          1. local_classify via LM Studio (0.5b model ~50 ms)
          2. heuristic_classify — keyword matching, zero latency
        Cloud providers are no longer contacted for classification;
        provider selection is handled by scoring/weighting after classification.
        """
        start = time.perf_counter()
        compressed_context = self._compress_context(context)

        # 1. Local classifier (LM Studio qwen2.5-0.5b-instruct)
        classification = await self._classify_with_local_model(content)
        if classification is not None:
            logger.info(
                "classified_via_local_model",
                intent=classification.intent,
                complexity=classification.complexity_score,
            )
        else:
            # 2. Pure heuristics — zero external calls, zero cost
            classification = self._heuristic_classify(content, compressed_context)
            logger.info(
                "classified_via_heuristic",
                intent=classification.intent,
                complexity=classification.complexity_score,
            )

        elapsed = time.perf_counter() - start
        logger.debug(
            "task_classified",
            intent=classification.intent,
            complexity=classification.complexity_score,
            tool_only=classification.tool_only_flag,
            elapsed_ms=round(elapsed * 1000, 2),
        )
        return classification


_classifier_instance: Optional[TaskClassifier] = None


def get_task_classifier() -> TaskClassifier:
    """Return the singleton TaskClassifier instance."""
    global _classifier_instance
    if _classifier_instance is None:
        _classifier_instance = TaskClassifier()
    return _classifier_instance
