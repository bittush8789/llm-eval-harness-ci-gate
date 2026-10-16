"""Reference LangChain RAG application with structured output and modular retrieval."""

import json
import re
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.prompts import ChatPromptTemplate, HumanMessagePromptTemplate, SystemMessagePromptTemplate
from app.core.config import settings
from app.core.logging import logger
from app.services.llm_service import LLMService


class CitationItem(BaseModel):
    """Citation metadata identifying source and referenced snippet."""

    source_id: str
    snippet: Optional[str] = None


class RAGStructuredOutput(BaseModel):
    """Schema for LLM structured output parsing."""

    answer: str = Field(description="The factual answer grounded in the supplied context")
    source_identifiers: List[str] = Field(
        default_factory=list,
        description="List of document identifiers cited in the answer (e.g., ['sec-audit-101'])",
    )
    refusal: bool = Field(
        default=False,
        description="Set to true if the context was insufficient to answer the question",
    )


class RAGResponse(BaseModel):
    """Complete application response returned to clients and evaluation runner."""

    question: str
    answer: str
    source_identifiers: List[str]
    citation_metadata: List[CitationItem]
    prompt_version: str
    model_identifier: str
    is_refusal: bool
    raw_response: Optional[str] = None


class BaseRetriever:
    """Modular retrieval interface allowing future vector store integration."""

    def retrieve(self, query: str, contexts: Optional[List[str]] = None) -> List[str]:
        raise NotImplementedError


class SuppliedContextRetriever(BaseRetriever):
    """Default POC retriever passing through supplied context passages."""

    def retrieve(self, query: str, contexts: Optional[List[str]] = None) -> List[str]:
        return contexts or []


class RAGChain:
    """LangChain RAG pipeline orchestrating system prompts, models, and structured responses."""

    def __init__(
        self,
        llm: Optional[BaseChatModel] = None,
        prompt_version: Optional[str] = None,
        model_name: Optional[str] = None,
        retriever: Optional[BaseRetriever] = None,
        offline: Optional[bool] = None,
    ):
        self.prompt_version = prompt_version or settings.APP_PROMPT_VERSION
        self.model_identifier = model_name or settings.APP_LLM_MODEL
        self.llm = llm or LLMService.get_application_llm(
            model_name=self.model_identifier,
            offline=offline,
        )
        self.retriever = retriever or SuppliedContextRetriever()
        self.system_prompt_text = settings.get_system_prompt_content()

        # Build prompt template
        self.prompt_template = ChatPromptTemplate.from_messages(
            [
                SystemMessagePromptTemplate.from_template(
                    "{system_prompt}\n\n"
                    "You must output ONLY valid JSON matching this schema:\n"
                    '{{"answer": "<your text>", "source_identifiers": ["<id1>", "<id2>"], "refusal": false}}\n'
                    "If unanswerable, set refusal to true and source_identifiers to []."
                ),
                HumanMessagePromptTemplate.from_template(
                    "CONTEXT PASSAGES:\n{context_text}\n\n"
                    "QUESTION: {question}\n\n"
                    "Respond strictly in JSON format:"
                ),
            ]
        )

    def _extract_source_ids(self, text: str) -> List[str]:
        """Extract [source-id] style citation tokens from text."""
        matches = re.findall(r"\[([a-zA-Z0-9_\-]+)\]", text)
        return list(dict.fromkeys(matches))  # deduplicate preserving order

    def _parse_llm_output(self, raw_content: str, question: str) -> RAGResponse:
        """Robustly parse LLM response into structured RAGResponse."""
        cleaned = raw_content.strip()

        # Handle markdown JSON fence
        if cleaned.startswith("```"):
            cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
            cleaned = re.sub(r"\s*```$", "", cleaned)
            cleaned = cleaned.strip()

        answer_text = cleaned
        sources: List[str] = []
        is_refusal = False

        try:
            parsed = json.loads(cleaned)
            if isinstance(parsed, dict):
                answer_text = parsed.get("answer", cleaned)
                sources = parsed.get("source_identifiers", [])
                is_refusal = parsed.get("refusal", False)
        except Exception:
            # Fallback if raw text wasn't valid JSON
            logger.warning(f"Could not parse LLM output as JSON; falling back to text analysis.")
            refusal_phrases = [
                "unable to answer",
                "cannot answer",
                "insufficient",
                "not provided in the context",
                "context does not contain",
            ]
            if any(phrase in answer_text.lower() for phrase in refusal_phrases):
                is_refusal = True
            sources = self._extract_source_ids(answer_text)

        # Re-check explicit refusal phrases even if parsed from JSON
        refusal_markers = [
            "unable to answer",
            "cannot answer",
            "context does not contain",
            "not mentioned in the context",
        ]
        if any(marker in answer_text.lower() for marker in refusal_markers):
            is_refusal = True
            if is_refusal and not sources:
                sources = []

        # Also pull inline citations if structured sources was empty
        if not sources and not is_refusal:
            sources = self._extract_source_ids(answer_text)

        citation_items = [CitationItem(source_id=s) for s in sources]

        return RAGResponse(
            question=question,
            answer=answer_text,
            source_identifiers=sources,
            citation_metadata=citation_items,
            prompt_version=self.prompt_version,
            model_identifier=self.model_identifier,
            is_refusal=is_refusal,
            raw_response=raw_content,
        )

    def invoke(self, question: str, contexts: Optional[List[str]] = None) -> RAGResponse:
        """Execute RAG pipeline synchronously."""
        retrieved_contexts = self.retriever.retrieve(question, contexts)
        context_text = (
            "\n\n".join(retrieved_contexts)
            if retrieved_contexts
            else "NO CONTEXT PROVIDED."
        )

        messages = self.prompt_template.format_messages(
            system_prompt=self.system_prompt_text,
            context_text=context_text,
            question=question,
        )

        try:
            ai_message = self.llm.invoke(messages)
            raw_content = (
                ai_message.content
                if hasattr(ai_message, "content")
                else str(ai_message)
            )
            return self._parse_llm_output(raw_content, question)
        except Exception as e:
            logger.error(f"Error during RAG invocation: {e}", exc_info=True)
            return RAGResponse(
                question=question,
                answer=f"Error executing answer generation: {str(e)}",
                source_identifiers=[],
                citation_metadata=[],
                prompt_version=self.prompt_version,
                model_identifier=self.model_identifier,
                is_refusal=True,
                raw_response=str(e),
            )

    async def ainvoke(self, question: str, contexts: Optional[List[str]] = None) -> RAGResponse:
        """Asynchronous execution wrapper."""
        return self.invoke(question, contexts)
