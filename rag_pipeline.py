import os
from functools import lru_cache

from dotenv import load_dotenv
from langchain.chains import RetrievalQA
from langchain.schema import HumanMessage, SystemMessage
from langchain.text_splitter import TokenTextSplitter
from langchain.vectorstores import FAISS
from langchain_core.documents import Document

# Provider-specific imports (optional depending on configuration)
try:
    from langchain_google_genai import ChatGoogleGenerativeAI, GoogleGenerativeAIEmbeddings
except ImportError:
    ChatGoogleGenerativeAI = None  # type: ignore
    GoogleGenerativeAIEmbeddings = None  # type: ignore

try:
    from langchain_openai import ChatOpenAI, OpenAIEmbeddings
except ImportError:
    ChatOpenAI = None  # type: ignore
    OpenAIEmbeddings = None  # type: ignore

# Load environment variables from .env.txt file if present
load_dotenv(dotenv_path=".env.txt")

_default_provider = "google"
if os.getenv("OPENAI_API_KEY") and not os.getenv("GOOGLE_API_KEY"):
    _default_provider = "openai"

LLM_PROVIDER = os.getenv("LLM_PROVIDER", _default_provider).strip().lower()


def _require_env(value: str | None, var_name: str, provider: str) -> str:
    """Ensure provider-specific environment variables are available."""
    if value:
        return value
    raise ValueError(
        f"{var_name} must be set when LLM_PROVIDER='{provider}'. "
        "Update your environment variables (e.g. .env.txt)."
    )


@lru_cache(maxsize=1)
def get_embedding_model():
    """Return an embedding model instance for the configured provider."""
    if LLM_PROVIDER == "openai":
        if OpenAIEmbeddings is None:
            raise ImportError(
                "langchain-openai is required when LLM_PROVIDER='openai'. "
                "Install it with `pip install langchain-openai openai`."
            )
        api_key = _require_env(os.getenv("OPENAI_API_KEY"), "OPENAI_API_KEY", "openai")
        base_url = os.getenv("OPENAI_API_BASE")
        embedding_model_name = os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-large")
        kwargs = {"model": embedding_model_name, "openai_api_key": api_key}
        if base_url:
            kwargs["openai_api_base"] = base_url.rstrip("/")
        return OpenAIEmbeddings(**kwargs)

    if GoogleGenerativeAIEmbeddings is None:
        raise ImportError(
            "langchain-google-genai is required when LLM_PROVIDER='google'. "
            "Install it with `pip install langchain-google-genai google-generativeai`."
        )
    api_key = _require_env(os.getenv("GOOGLE_API_KEY"), "GOOGLE_API_KEY", "google")
    embedding_model_name = os.getenv("GOOGLE_EMBEDDING_MODEL", "models/embedding-001")
    return GoogleGenerativeAIEmbeddings(model=embedding_model_name, google_api_key=api_key)


def get_llm(temperature=0.7):
    """Instantiate the chat model for the configured provider."""
    if LLM_PROVIDER == "openai":
        if ChatOpenAI is None:
            raise ImportError(
                "langchain-openai is required when LLM_PROVIDER='openai'. "
                "Install it with `pip install langchain-openai openai`."
            )
        api_key = _require_env(os.getenv("OPENAI_API_KEY"), "OPENAI_API_KEY", "openai")
        base_url = os.getenv("OPENAI_API_BASE")
        llm_model_name = os.getenv("OPENAI_LLM_MODEL", "gpt-4o-mini")
        kwargs = {
            "model": llm_model_name,
            "temperature": temperature,
            "openai_api_key": api_key,
        }
        if base_url:
            kwargs["openai_api_base"] = base_url.rstrip("/")
        return ChatOpenAI(**kwargs)

    if ChatGoogleGenerativeAI is None:
        raise ImportError(
            "langchain-google-genai is required when LLM_PROVIDER='google'. "
            "Install it with `pip install langchain-google-genai google-generativeai`."
        )
    llm_model_name = os.getenv("GOOGLE_LLM_MODEL", "gemini-1.5-flash-latest")
    return ChatGoogleGenerativeAI(
        model=llm_model_name,
        convert_system_message_to_human=True,
        temperature=temperature,
    )

# Text chunking function
def chunk_text(text, chunk_size=1000, chunk_overlap=200):
    splitter = TokenTextSplitter(chunk_size=chunk_size, chunk_overlap=chunk_overlap)
    return splitter.split_documents([Document(page_content=text)])

def get_vectorstore(docs):
    vectorstore = FAISS.from_documents(docs, embedding=get_embedding_model())
    return vectorstore

# Main RAG pipeline function to generate notes
def generate_notes(transcript_text, prompt_template, chunk_size=1000, chunk_overlap=200, retriever_k=5, llm_temperature=0.7):
    chunks = chunk_text(transcript_text, chunk_size=chunk_size, chunk_overlap=chunk_overlap)
    vectordb = get_vectorstore(chunks)
    retriever = vectordb.as_retriever(search_kwargs={"k": retriever_k})

    qa_chain = RetrievalQA.from_chain_type(
        llm=get_llm(temperature=llm_temperature),
        retriever=retriever,
        chain_type="stuff",
        return_source_documents=False,
        chain_type_kwargs={"prompt": prompt_template}
    )

    # Use prompt to ask for notes
    response = qa_chain.run("Generate lecture notes based on the above transcript.")
    return response, retriever

# Chat interface to ask questions based on the same transcript
# Add a chat history parameter and notes context
def chat_with_transcript(user_query, retriever, chat_history=None, notes_context=None):
    llm = get_llm()
    if chat_history is None:
        chat_history = []
    messages = []

    # Add notes context as a system message if available
    if notes_context:
        messages.append(SystemMessage(content=f"Lecture notes context:\n{notes_context}"))

    # Add previous chat history
    messages.extend(chat_history)
    # Add current user query
    messages.append(HumanMessage(content=user_query))

    qa_chain = RetrievalQA.from_chain_type(
        llm=llm,
        retriever=retriever,
        chain_type="stuff",
        return_source_documents=False
    )
    response = qa_chain.run(user_query)

    keywords = ["does not consist", "doesn't contain information", "not found", "absent", "missing", "does not explain", "not present", "not mentioned", "not included", "not discussed", "not covered", "not addressed", "not specified", "not detailed", "not elaborated", "not described", "not explained", "not contain", "not provided", "not available", "no information on", "no details on", "does not, however, provide a direct answer", "don't know", "cannot answer", "unable to answer", "no information available", "no relevant information found", "no details provided", "no context available", "not applicable", "not relevant", "not related", "not pertinent", "not useful", "not helpful", "not informative", "not insightful", "not conclusive", "not definitive", "not satisfactory", "can't answer", "can't provide", "can't find", "can't locate", "can't retrieve", "can't access", "can't obtain", "can't discover", "can't identify", "can't determine", "can't clarify", "can't explain", "can't elaborate", "can't detail", "can't describe", "can't specify", "can't mention", "can't cover", "can't address", "not applicable to the question"]
    if any(keyword in response.lower() for keyword in keywords):
        general_chatbot_response = llm.invoke(messages)
        content = general_chatbot_response[0] if isinstance(general_chatbot_response, list) else general_chatbot_response.content
        return f"\nNote: The requested information was not found in the provided document. Hence, the general chatbot was used.\n\n{content}\n", messages

    # Add the assistant's response to chat history
    messages.append(SystemMessage(content=response))
    return response, messages
