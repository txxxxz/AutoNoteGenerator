from langchain.prompts import PromptTemplate

def get_prompt_template(format_type, custom_prompt=""):
    """
    Returns a PromptTemplate with input_variables=["context"] so that RetrievalQA can
    map document chunks into the 'context' variable.
    """
    if format_type == "Custom Template" and custom_prompt.strip():
        return PromptTemplate(
            input_variables=["context"],
            template=custom_prompt
        )

    predefined_templates = {
        "Detailed Structured Study Notes": (
"""
You are an academic assistant. Summarize the lecture into structured, in-depth study notes using the following format.

Be as detailed as possible in each section. Include subpoints, explanations, examples, and connections between ideas wherever relevant.

Context:
{context}

Detailed Notes:
1. Summary  
   - Provide a comprehensive overview of the lecture.  
   - Include the main objective, overall flow, and key insights.  
   - Mention any important conclusions or implications.

2. Key Concepts  
   - List and explain each core concept thoroughly.  
   - For each concept, include:  
     • A definition or explanation  
     • Why it matters  
     • How it connects to other ideas  
     • Real-world relevance if applicable

3. Definitions  
   - Identify and define all important terms introduced in the lecture.  
   - Include context or examples for each term.  
   - If multiple definitions exist (e.g., in different contexts), clarify them.

4. Important Examples  
   - Highlight all illustrative examples used during the lecture.  
   - For each example, explain what it demonstrates and why it’s important.  
   - If calculations or steps are involved, break them down clearly.

5. Questions to Consider  
   - Generate thoughtful questions that test understanding of the material.  
   - Include a mix of factual recall, conceptual understanding, and application-based questions.  
   - Where helpful, suggest brief model answers or hints.
"""
        ),

"Conceptual Mind Map Style": (
"""
You are an AI assistant creating a concept map.
Organize the lecture content into a hierarchical structure of main topics, subtopics, and details.

Context:
{context}

Concept Map:
- Main Topic 1
  - Subtopic 1.1
    - Detail 1.1.1
  - Subtopic 1.2
    - Detail 1.2.1
- Main Topic 2
  - Subtopic 2.1
    - Detail 2.1.1
"""
        ), 

"Step-by-Step Explanation": (
"""
You are a teacher explaining the content step by step for easy understanding.

Context:
{context}

Step-by-Step Notes:
Step 1: ...
Step 2: ...
Step 3: ...
"""
        ), 

"Comparison Table": (
"""
If the lecture compares concepts, highlight their similarities and differences.

Context:
{context}

Comparison Table:
| Concept A | Concept B | Similarities | Differences |
|-----------|-----------|--------------|--------------|

"""
        ),

"Key Terms and Definitions": (
"""
You are an AI assistant extracting key terms and their definitions from the lecture.

Context:
{context}

Key Terms and Definitions:
- Term 1: Definition 1
- Term 2: Definition 2
- Term 3: Definition 3
"""
        ),

"Flashcard Style": (
"""
You are converting the content into flashcards for revision.

Context:
{context}

Flashcards:
Q: [Question based on key concept]
A: [Answer]
"""
        ), 

"Formula + Concept Sheet": (
"""
Extract all formulas, equations, and their explanations from the transcript.

Context:
{context}

Formula Sheet:
- Formula: ...
  - Meaning: ...
  - When to use: ...
"""
        ),

"Topic Clusters": (
"""
Cluster similar concepts or information into topical groups.

Context:
{context}

Clusters:
Topic 1: ...
Topic 2: ...
Topic 3: ...
"""
        ), 

"Cause and Effect Notes": (
"""
Highlight the causal relationships found in the lecture.

Context:
{context}

Cause & Effect:
Cause: ...
→ Effect: ...
"""
        ),

"Exam-Ready Highlights": (
"""
You are helping a student prepare for exams. Highlight the most examinable points.

Context:
{context}

Exam Notes:
Must Know
Common Mistakes
Hot Topics
"""
        ),

"Practical Applications": (
"""
You are an AI assistant summarizing the lecture into practical applications.

Context:
{context}

Practical Applications:
- Application 1: ...
- Application 2: ...
- Application 3: ...
"""
        ),

"Pros and Cons": (
"""
You are an AI assistant summarizing the lecture into pros and cons of key concepts.

Context:
{context}

Pros and Cons:
- Concept 1:
  - Pros: ...
  - Cons: ...
- Concept 2:
  - Pros: ...
  - Cons: ...
"""
        ),

"Problem-Solution Format": (
"""
Present the lecture in a problem-solution structure.

Context:
{context}

Problems and Solutions:
Problem: ...
Solution: ...
"""
        ),

"Explainer with Analogies": (
"""
Explain key ideas using analogies to make them easier to grasp.

Context:
{context}

Explainer Notes:
- Concept: ...
  - Analogy: ...
"""
        ),

"Highlight + Expand": (
"""
Highlight the most important term and give a short paragraph explanation.

Context:
{context}

Highlights:
Term: ...
Explanation: ...
"""
        ),

"Quick Review Cheat Sheet": (
"""
Provide an ultra-concise cheat sheet version.

Context:
{context}

Quick Review:
Key Ideas: ...
Definitions: ...
Examples: ...
Questions: ...
"""
        )
    }

    template_str = predefined_templates.get(format_type, predefined_templates["Detailed Structured Study Notes"])
    return PromptTemplate(
        input_variables=["context"],
        template=template_str
    )
