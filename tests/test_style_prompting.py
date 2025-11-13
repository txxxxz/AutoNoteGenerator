import sys
import types
import unittest

# Lightweight stubs so tests can import NoteGenerator without real LangChain.
if "langchain_core.documents" not in sys.modules:
    langchain_core = types.ModuleType("langchain_core")
    sys.modules["langchain_core"] = langchain_core

    documents_module = types.ModuleType("langchain_core.documents")

    class _Document:
        def __init__(self, page_content: str = "", metadata=None):
            self.page_content = page_content
            self.metadata = metadata or {}

    documents_module.Document = _Document
    sys.modules["langchain_core.documents"] = documents_module
    setattr(langchain_core, "documents", documents_module)

    messages_module = types.ModuleType("langchain_core.messages")

    class _Message:
        def __init__(self, content: str):
            self.content = content

    messages_module.HumanMessage = _Message
    messages_module.SystemMessage = _Message
    sys.modules["langchain_core.messages"] = messages_module
    setattr(langchain_core, "messages", messages_module)

if "dotenv" not in sys.modules:
    dotenv_module = types.ModuleType("dotenv")

    def _load_dotenv(*_args, **_kwargs):
        return None

    dotenv_module.load_dotenv = _load_dotenv
    sys.modules["dotenv"] = dotenv_module

if "pydantic" not in sys.modules:
    pydantic_module = types.ModuleType("pydantic")

    class _BaseModel:
        def __init__(self, **data):
            for key, value in data.items():
                setattr(self, key, value)

        @classmethod
        def model_rebuild(cls):
            return None

    def _field(default=None, default_factory=None, **_kwargs):
        if default_factory is not None:
            return default_factory()
        return default

    pydantic_module.BaseModel = _BaseModel
    pydantic_module.Field = _field
    sys.modules["pydantic"] = pydantic_module

if "langchain_community.vectorstores" not in sys.modules:
    community_module = types.ModuleType("langchain_community")
    sys.modules["langchain_community"] = community_module

    vectorstores_module = types.ModuleType("langchain_community.vectorstores")

    class _FakeFaiss:
        @classmethod
        def load_local(cls, *_args, **_kwargs):
            return cls()

        @classmethod
        def from_documents(cls, *_args, **_kwargs):
            return cls()

        def save_local(self, *_args, **_kwargs):
            return None

    vectorstores_module.FAISS = _FakeFaiss
    sys.modules["langchain_community.vectorstores"] = vectorstores_module
    setattr(community_module, "vectorstores", vectorstores_module)

from app.modules.note.generator import NoteGenerator
from app.modules.note.style_policies import build_style_profile
from app.schemas.common import AnchorRef, OutlineNode


def _sample_section() -> OutlineNode:
    return OutlineNode(
        section_id="sec_test",
        title="自注意力机制",
        summary="说明每一页如何拆解注意力。",
        anchors=[AnchorRef(page=1, ref="p1"), AnchorRef(page=2, ref="p2")],
        children=[],
        level=1,
        pages=[1, 2],
        page_start=1,
        page_end=2,
    )


class StylePromptingTests(unittest.TestCase):
    def test_brief_simple_vs_detailed_academic_prompts(self) -> None:
        """
        Ensures prompts (and thus downstream markdown) diverge when style settings change.
        """
        generator = NoteGenerator()
        section = _sample_section()
        brief_profile = build_style_profile("brief", "simple", "zh")
        detailed_profile = build_style_profile("detailed", "academic", "zh")

        brief_prompt = generator._build_prompt(section, brief_profile, "mock context")
        detailed_prompt = generator._build_prompt(section, detailed_profile, "mock context")

        self.assertIn("打个比方", brief_prompt)
        self.assertNotIn("| 对比项 |", brief_prompt)

        self.assertIn("| 对比项 |", detailed_prompt)
        self.assertIn("> **章节洞察", detailed_prompt)

        self.assertGreater(len(detailed_prompt), len(brief_prompt))


if __name__ == "__main__":
    unittest.main()
