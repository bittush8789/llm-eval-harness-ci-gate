"""Unit tests for the reference RAG application chain."""

import pytest
from app.chains.rag_chain import RAGChain, SuppliedContextRetriever
from app.services.llm_service import MockChatModel


def test_rag_chain_invoke_grounded_answer():
    """Verify RAG chain returns structured response with extracted citations."""
    llm = MockChatModel()
    chain = RAGChain(llm=llm, offline=True)

    question = "What is the mandatory data retention period for audit logs in production?"
    contexts = ["[sec-audit-101] Audit logs in production environments must be retained for 365 days."]

    response = chain.invoke(question=question, contexts=contexts)

    assert response.question == question
    assert "365 days" in response.answer
    assert "sec-audit-101" in response.source_identifiers
    assert response.is_refusal is False
    assert response.prompt_version is not None
    assert response.model_identifier is not None


def test_rag_chain_refusal_on_unanswerable_question():
    """Verify RAG chain flags refusal when question is outside context scope."""
    llm = MockChatModel()
    chain = RAGChain(llm=llm, offline=True)

    question = "What is the planned enterprise price for fiscal year 2027?"
    contexts = ["[fin-pricing-101] The enterprise subscription rate for fiscal year 2024 is $45."]

    response = chain.invoke(question=question, contexts=contexts)

    assert response.is_refusal is True
    assert "unable to answer" in response.answer.lower()
    assert len(response.source_identifiers) == 0


def test_rag_chain_json_fence_parsing():
    """Verify markdown code block stripping during JSON parsing."""
    class CustomMarkdownMock(MockChatModel):
        def _generate(self, messages, **kwargs):
            from langchain_core.messages import AIMessage
            from langchain_core.outputs import ChatGeneration, ChatResult
            content = '```json\n{"answer": "Test answer", "source_identifiers": ["s1"], "refusal": false}\n```'
            return ChatResult(generations=[ChatGeneration(message=AIMessage(content=content))])

    chain = RAGChain(llm=CustomMarkdownMock(), offline=True)
    res = chain.invoke(question="Test?", contexts=["Context [s1]"])

    assert res.answer == "Test answer"
    assert res.source_identifiers == ["s1"]
    assert res.is_refusal is False


def test_supplied_context_retriever():
    """Verify default passthrough retriever interface."""
    retriever = SuppliedContextRetriever()
    contexts = ["[doc-1] Passages 1", "[doc-2] Passages 2"]
    retrieved = retriever.retrieve(query="anything", contexts=contexts)
    assert retrieved == contexts
