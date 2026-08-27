"""Translation engine contract and registry."""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from app.core.config import settings
from app.integrations.docutranslate import DocuTranslateClient, DocuTranslateError
from app.integrations.mineru import MinerUClient, MinerUError
from app.integrations.ollama import OllamaClient, OllamaError

logger = logging.getLogger(__name__)


class TranslationEngineError(RuntimeError):
    pass


@dataclass
class TranslationPageRequest:
    document_id: str
    page_id: str
    page_no: int
    source_file_id: str
    file_version_id: str
    target_lang: str
    source_text: str | None = None
    source_bytes: bytes | None = None
    source_filename: str = "source.pdf"


@dataclass
class TranslationPageResult:
    content: str
    meta: dict[str, Any] = field(default_factory=dict)


@dataclass
class TranslationProgress:
    status: str
    progress: int
    message: str | None = None


class TranslationEngine(ABC):
    @abstractmethod
    async def translate_page(self, request: TranslationPageRequest) -> TranslationPageResult:
        raise NotImplementedError

    @abstractmethod
    async def translate_document(self, request: TranslationPageRequest) -> TranslationPageResult:
        raise NotImplementedError

    @abstractmethod
    async def get_progress(self, document_id: str) -> TranslationProgress:
        raise NotImplementedError

    @abstractmethod
    async def cancel(self, document_id: str) -> None:
        raise NotImplementedError

    @abstractmethod
    async def aclose(self) -> None:
        raise NotImplementedError


class DocuTranslateEngine(TranslationEngine):
    """DocuTranslate adapter orchestrating MinerU extraction and Ollama inference."""

    def __init__(
        self,
        *,
        docutranslate: DocuTranslateClient | None = None,
        mineru: MinerUClient | None = None,
        ollama: OllamaClient | None = None,
    ):
        self._docutranslate = docutranslate or DocuTranslateClient()
        self._mineru = mineru or MinerUClient()
        self._ollama = ollama or OllamaClient()
        self._owns_docutranslate = docutranslate is None
        self._owns_mineru = mineru is None
        self._owns_ollama = ollama is None
        self._progress: dict[str, TranslationProgress] = {}

    async def aclose(self) -> None:
        if self._owns_docutranslate:
            await self._docutranslate.aclose()
        if self._owns_mineru:
            await self._mineru.aclose()
        if self._owns_ollama:
            await self._ollama.aclose()

    async def _resolve_source_text(self, request: TranslationPageRequest) -> str:
        if request.source_text:
            return request.source_text
        if request.source_bytes:
            try:
                return await self._mineru.extract_page_text(
                    file_bytes=request.source_bytes,
                    filename=request.source_filename,
                    page_no=request.page_no,
                )
            except MinerUError as exc:
                raise TranslationEngineError(f"mineru_unavailable: {exc}") from exc
        raise TranslationEngineError("missing_source_content")

    async def translate_page(self, request: TranslationPageRequest) -> TranslationPageResult:
        self._progress[request.document_id] = TranslationProgress(
            status="running",
            progress=10,
            message="extracting",
        )
        source_text = await self._resolve_source_text(request)
        self._progress[request.document_id] = TranslationProgress(
            status="running",
            progress=50,
            message="translating",
        )
        try:
            translated = await self._docutranslate.translate_page(
                source_text=source_text,
                target_lang=request.target_lang,
                page_no=request.page_no,
            )
            engine = "docutranslate"
        except DocuTranslateError as exc:
            logger.warning("DocuTranslate failed, falling back to Ollama: %s", exc)
            try:
                translated = await self._ollama.translate(
                    text=source_text,
                    target_lang=request.target_lang,
                )
                engine = "ollama_fallback"
            except OllamaError as ollama_exc:
                raise TranslationEngineError(f"translation_unavailable: {ollama_exc}") from ollama_exc
        self._progress[request.document_id] = TranslationProgress(
            status="completed",
            progress=100,
            message="done",
        )
        return TranslationPageResult(
            content=translated,
            meta={"engine": engine, "page_no": request.page_no},
        )

    async def translate_document(self, request: TranslationPageRequest) -> TranslationPageResult:
        return await self.translate_page(request)

    async def get_progress(self, document_id: str) -> TranslationProgress:
        return self._progress.get(
            document_id,
            TranslationProgress(status="unknown", progress=0),
        )

    async def cancel(self, document_id: str) -> None:
        self._progress[document_id] = TranslationProgress(
            status="cancelled",
            progress=0,
            message="cancelled",
        )


_ENGINE_REGISTRY: dict[str, type[TranslationEngine]] = {
    "docutranslate": DocuTranslateEngine,
}


def register_translation_engine(name: str, engine_cls: type[TranslationEngine]) -> None:
    _ENGINE_REGISTRY[name] = engine_cls


def get_translation_engine(name: str | None = None, **kwargs: Any) -> TranslationEngine:
    engine_name = (name or settings.KNOWLEDGE_TRANSLATION_ENGINE or "docutranslate").strip().lower()
    engine_cls = _ENGINE_REGISTRY.get(engine_name)
    if engine_cls is None:
        raise TranslationEngineError(f"unknown_translation_engine: {engine_name}")
    return engine_cls(**kwargs)
