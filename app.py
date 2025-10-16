import streamlit as st
from transcript_loader import load_transcript
from prompts import get_prompt_template
from rag_pipeline import generate_notes, chat_with_transcript
from dotenv import load_dotenv
from markdown_pdf import MarkdownPdf, Section
import os

st.set_page_config(page_title="RAG-Powered Lecture Summaries", layout="centered")

# Load environment variables
load_dotenv()

st.title("📚 Lec2Notes: Smarter Notes. Powered by RAG.")

# Sidebar introduction
with st.sidebar:
    st.header("📘 About This Project")
    st.markdown("""
    Welcome to **Lec2Notes**! 🎓  
    Your smart academic assistant for transforming raw transcripts into organized, readable, and exportable study material — all **powered by RAG (Retrieval-Augmented Generation)**.

    ---

    ### 🚀 What Can Lec2Notes Do?

    - 📝 **Auto-generate structured notes** from your lecture transcripts (TXT, PDF, or SRT).
    - 💬 **Chat with your lecture content** using a Q&A interface.
    - 🧠 **Choose your preferred format** like Mind Maps, Flashcards, Tables, Exam Highlights, or your own custom template!
    - 📤 **Export your notes** to Markdown or PDF in one click.
    - ⚙️ **Tune hyperparameters** like chunk size, top-K retrieval, and temperature for optimal results.

    ---

    ### 🧠 Why RAG?

    RAG combines **document retrieval** with **language generation**, so your notes aren't just guesses — they're built on actual lecture content. When information isn’t found, Lec2Notes gracefully switches to general LLM responses for a complete answer.

    ---

    🎯 **Built with:**
    - `LangChain` for RAG pipeline
    - `Gemini API` for language generation
    - `Chroma` for vector storage
    - `Streamlit` for interactive UI
    """)

    # Collapsible Hyperparameters Section
    with st.expander("⚙️ Adjust Hyperparameters", expanded=False):
        st.markdown("Fine-tune the settings for better results:")
        chunk_size = st.number_input("Chunk Size", min_value=100, max_value=5000, value=1000, step=100, help="Size of each text chunk for processing.")
        chunk_overlap = st.number_input("Chunk Overlap", min_value=0, max_value=1000, value=200, step=50, help="Overlap between chunks to ensure context continuity.")
        retriever_k = st.number_input("Retriever Top-K", min_value=1, max_value=20, value=5, step=1, help="Number of top documents retrieved for context.")
        llm_temperature = st.slider("LLM Temperature", min_value=0.0, max_value=1.0, value=0.7, step=0.1, help="Controls randomness in the language model's output.")

    # Additional Resources Section
    st.markdown("### 📚 Resources")
    st.markdown("""
    - [Streamlit Documentation](https://docs.streamlit.io/)
    - [Learn About RAG](https://python.langchain.com/docs/tutorials/rag/)
    - [GitHub Repository](https://github.com/AdityaZala3919/Lec2Notes-RAG)
    """)

    # Feedback Section
    st.markdown("### 💬 Feedback")
    feedback = st.text_area("Have suggestions or found a bug? Let us know!", placeholder="Type your feedback here...")
    if st.button("Submit Feedback"):
        st.success("Thank you for your feedback!")

# Session state init
if 'notes' not in st.session_state:
    st.session_state.notes = ""
if 'retriever' not in st.session_state:
    st.session_state.retriever = None
if 'chat_history' not in st.session_state:
    st.session_state.chat_history = []

# Upload transcript
uploaded_file = st.file_uploader("Upload your lecture transcript (TXT, PDF, or SRT)", type=["txt", "pdf", "srt"])

# Notes format selection
notes_format = st.selectbox("Choose your notes format:", [
    "Detailed Structured Study Notes",
    "Conceptual Mind Map Style",
    "Step-by-Step Explanation",
    "Comparison Table",
    "Key Terms and Definitions",
    "Flashcard Style",
    "Formula + Concept Sheet",
    "Topic Clusters",
    "Cause and Effect Notes",
    "Exam-Ready Highlights",
    "Practical Applications",
    "Pros and Cons",
    "Problem-Solution Format",
    "Explainer with Analogies",
    "Highlight + Expand",
    "Quick Review Cheat Sheet",
    "Custom Template"
])

custom_prompt = ""
if notes_format == "Custom Template":
    custom_prompt = st.text_area("Enter your custom prompt template:", height=200)

# Generate button
if uploaded_file and st.button("✍️ Generate Notes"):
    with st.spinner("Loading and processing transcript..."):
        transcript_text = load_transcript(uploaded_file)
        prompt_template = get_prompt_template(notes_format, custom_prompt)

        # Pass hyperparameters to the pipeline
        notes, retriever = generate_notes(
            transcript_text,
            prompt_template,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            retriever_k=retriever_k,
            llm_temperature=llm_temperature
        )

        st.session_state.notes = notes
        st.session_state.retriever = retriever
        st.session_state.chat_history = []  # reset chat on new upload

    st.success("Notes generated successfully!")

# Display Notes
if st.session_state.notes:
    st.markdown("### 📄 Generated Notes:")
    st.markdown(st.session_state.notes)

    st.download_button(
        "⬇️ Download as Markdown",
        data=st.session_state.notes.strip(),
        file_name="notes.md"
    )
    
    markdown_content = st.session_state.notes.strip()
    pdf = MarkdownPdf()
    pdf.add_section(Section(markdown_content))

    pdf.save("temp.pdf")
    with open("temp.pdf", "rb") as f:
        pdf_bytes = f.read()
        
    st.download_button(
        "⬇️ Download as PDF",
        data=pdf_bytes,
        file_name="notes.pdf"
    )

# Chat Interface
if st.session_state.retriever:
    st.markdown("---")
    st.markdown("### 💬 Ask Questions About the Transcript")

    for chat in st.session_state.chat_history:
        with st.chat_message("user"):
            st.markdown(chat["user"])
        with st.chat_message("assistant"):
            st.markdown(chat["bot"])

    user_input = st.chat_input("Ask a question...")
    if user_input:
        with st.chat_message("user"):
            st.markdown(user_input)
        with st.spinner("Thinking..."):
            # Pass chat_history and notes context to chat_with_transcript
            response, updated_history = chat_with_transcript(
                user_input,
                st.session_state.retriever,
                chat_history=st.session_state.get("raw_chat_history", []),
                notes_context=st.session_state.notes
            )
        # Store formatted response for display, and raw history for context
        st.session_state.chat_history.append({"user": user_input, "bot": response})
        st.session_state.raw_chat_history = updated_history
        with st.chat_message("assistant"):
            st.markdown(response)
