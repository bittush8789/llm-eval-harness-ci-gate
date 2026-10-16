"""LLM Service providing Google Gemini orchestration and offline Mock LLM support."""

import os
from typing import Any, List, Optional
from langchain_core.callbacks import CallbackManagerForLLMRun
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from app.core.config import settings
from app.core.logging import logger


class MockChatModel(BaseChatModel):
    """Deterministic Mock Chat Model for offline testing and CI workflows."""

    mock_responses: List[str] = [
        "Production audit logs must be retained for 365 days in tamper-proof immutable storage [sec-audit-101]."
    ]
    current_index: int = 0

    @property
    def _llm_type(self) -> str:
        return "mock-chat-model"

    def _generate(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> ChatResult:
        user_text = ""
        for msg in messages:
            # Only inspect non-system messages to avoid false positives on system instructions
            if getattr(msg, "type", "") == "system":
                continue
            if hasattr(msg, "content"):
                user_text += str(msg.content) + " "

        # Deterministic simulation based on prompt keywords
        if any(unans in user_text for unans in ["fiscal year 2027", "private home address", "Salesforce API", "Datadog"]):
            reply = '{"answer": "I am unable to answer this question based on the provided context.", "source_identifiers": [], "refusal": true}'
        elif any(adv in user_text for adv in ["Ignore all previous", "DAN", "public GitHub repositories", "system prompt"]):
            if "encryption keys" in user_text:
                reply = '{"answer": "Encryption keys must be rotated every 90 days using AWS KMS.", "source_identifiers": ["enc-sec-203"], "refusal": false}'
            else:
                reply = '{"answer": "I am unable to answer this question based on the provided context.", "source_identifiers": [], "refusal": true}'
        elif "365 days" in user_text or "audit logs" in user_text:
            reply = '{"answer": "Production audit logs must be retained for 365 days in tamper-proof immutable storage.", "source_identifiers": ["sec-audit-101"], "refusal": false}'
        elif "16 characters" in user_text or "password" in user_text:
            reply = '{"answer": "Administrative accounts require a minimum password length of 16 characters and mandatory hardware-backed MFA.", "source_identifiers": ["iam-policy-202"], "refusal": false}'
        elif "port 443" in user_text or "ports" in user_text:
            reply = '{"answer": "Permitted outbound ports are port 443 (HTTPS) and port 5432 (TLS) to designated database subnets.", "source_identifiers": ["net-rules-305"], "refusal": false}'
        elif "Tier-1" in user_text or "RTO" in user_text:
            reply = '{"answer": "The maximum allowable RTO for Tier-1 mission-critical systems is 15 minutes.", "source_identifiers": ["dr-plan-401"], "refusal": false}'
        elif "European" in user_text or "GDPR" in user_text:
            reply = '{"answer": "European customer data may only be stored in eu-west-1 (Ireland) and eu-central-1 (Frankfurt).", "source_identifiers": ["data-residency-502"], "refusal": false}'
        elif "Customer-Managed Key" in user_text or "CMK" in user_text:
            reply = '{"answer": "Yes, cross-region replication requires multi-region replica keys or explicit cross-region KMS grant permissions in the destination account.", "source_identifiers": ["s3-rep-601"], "refusal": false}'
        elif "exactly 100MB" in user_text or "upload" in user_text:
            reply = '{"answer": "Files of exactly 100MB are accepted and processed directly via the synchronous API handler.", "source_identifiers": ["upload-limits-701"], "refusal": false}'
        elif "TLS 1.1" in user_text:
            reply = '{"answer": "No. Under the active 2024 policy, TLS 1.1 is strictly disabled and all endpoints must enforce TLS 1.3.", "source_identifiers": ["crypto-current-802"], "refusal": false}'
        elif "RBAC" in user_text or "multiple role" in user_text:
            reply = '{"answer": "Permissions are additive (the union of all roles), but any explicit deny takes absolute precedence.", "source_identifiers": ["rbac-spec-901"], "refusal": false}'
        elif "Infosec directorate approval" in user_text or "production IAM" in user_text:
            reply = '{"answer": "Provisioning requires formal Infosec directorate approval [sec-policy-402] and must enforce least privilege with automated credential expiration [iam-guide-101].", "source_identifiers": ["sec-policy-402", "iam-guide-101"], "refusal": false}'
        elif "SOC 2" in user_text or "CC9.1" in user_text:
            reply = '{"answer": "Control CC9.1 requires monthly automated backup restoration tests accompanied by signed verification logs from database administrators.", "source_identifiers": ["soc2-report-2024"], "refusal": false}'
        elif "Transit Gateway" in user_text:
            reply = '{"answer": "All inter-VPC traffic traversing AWS Transit Gateway must pass through dedicated intrusion detection firewalls with deep packet inspection.", "source_identifiers": ["net-spec-303"], "refusal": false}'
        elif "Severity 1" in user_text or "escalation timeline" in user_text:
            reply = '{"answer": "Severity 1 security incidents require notifying the incident commander within 15 minutes and escalating to the executive breach committee within 60 minutes.", "source_identifiers": ["sec-ops-501"], "refusal": false}'
        else:
            if self.mock_responses:
                reply = self.mock_responses[self.current_index % len(self.mock_responses)]
                self.current_index += 1
            else:
                reply = '{"answer": "Grounded answer from provided context.", "source_identifiers": ["context-1"], "refusal": false}'

        generation = ChatGeneration(message=AIMessage(content=reply))
        return ChatResult(generations=[generation])


class LLMService:
    """Factory service for generating LangChain Chat LLMs for application and evaluator roles."""

    @staticmethod
    def get_application_llm(
        model_name: Optional[str] = None,
        temperature: Optional[float] = None,
        offline: Optional[bool] = None,
    ) -> BaseChatModel:
        """Return the chat model for answer generation (Gemini or Mock)."""
        is_offline = offline if offline is not None else settings.EVALUATION_OFFLINE_MODE
        target_model = model_name or settings.APP_LLM_MODEL
        target_temp = temperature if temperature is not None else settings.APP_LLM_TEMPERATURE

        api_key = settings.GOOGLE_API_KEY or os.environ.get("GOOGLE_API_KEY")

        if is_offline or not api_key:
            logger.info(
                f"Using MockChatModel for application LLM (offline_mode={is_offline}, api_key_present={bool(api_key)})"
            )
            return MockChatModel()

        logger.info(f"Instantiating ChatGoogleGenerativeAI (model={target_model}, temp={target_temp})")
        from langchain_google_genai import ChatGoogleGenerativeAI

        return ChatGoogleGenerativeAI(
            model=target_model,
            temperature=target_temp,
            google_api_key=api_key,
            max_retries=settings.EVALUATION_MAX_RETRIES,
            timeout=settings.EVALUATION_TIMEOUT_SECONDS,
        )

    @staticmethod
    def get_evaluator_llm(
        model_name: Optional[str] = None,
        temperature: Optional[float] = None,
        offline: Optional[bool] = None,
    ) -> BaseChatModel:
        """Return the evaluator judge model (Gemini or Mock), configured separately."""
        is_offline = offline if offline is not None else settings.EVALUATION_OFFLINE_MODE
        eval_model = model_name or settings.EVALUATOR_LLM_MODEL
        eval_temp = temperature if temperature is not None else settings.EVALUATOR_LLM_TEMPERATURE

        api_key = settings.GOOGLE_API_KEY or os.environ.get("GOOGLE_API_KEY")

        if is_offline or not api_key:
            logger.info(
                f"Using MockChatModel for evaluator LLM (offline_mode={is_offline}, api_key_present={bool(api_key)})"
            )
            return MockChatModel()

        logger.info(f"Instantiating Evaluator ChatGoogleGenerativeAI (model={eval_model}, temp={eval_temp})")
        from langchain_google_genai import ChatGoogleGenerativeAI

        return ChatGoogleGenerativeAI(
            model=eval_model,
            temperature=eval_temp,
            google_api_key=api_key,
            max_retries=settings.EVALUATION_MAX_RETRIES,
            timeout=settings.EVALUATION_TIMEOUT_SECONDS,
        )
