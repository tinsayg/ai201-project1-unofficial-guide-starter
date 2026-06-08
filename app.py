"""
Milestone 5 — Gradio Web Interface

Run:  python app.py
Then open http://localhost:7860 in your browser.

The UI calls generate.ask() which:
  1. Retrieves the top-5 most relevant review chunks
  2. Sends them to Groq llama-3.3-70b with a grounding-enforced system prompt
  3. Returns a grounded answer + programmatically-built source list
"""

import gradio as gr
from generate import ask, _ensure_loaded

# Pre-load the embedding model and ChromaDB so the first query isn't slow
_ensure_loaded()


def handle_query(question: str):
    question = question.strip()
    if not question:
        return "", ""

    result = ask(question)
    sources_text = "\n".join(f"• {s}" for s in result["sources"])
    return result["answer"], sources_text


EXAMPLE_QUESTIONS = [
    "What are affordable off-campus housing options close to Minnesota State University, Mankato?",
    "What do students say about maintenance at Highland Hills?",
    "What do students say about cleanliness at The Grove?",
    "What do students say about move-in conditions and fees at The Summit?",
    "Is College Station Apartments a good option for students near MNSU?",
]

with gr.Blocks(title="MNSU Off-Campus Housing Guide") as demo:
    gr.Markdown(
        """
        ## MNSU Off-Campus Housing Guide
        Ask questions about student housing near **Minnesota State University, Mankato**.
        Answers are grounded in real student reviews from Reddit, Google, Yelp, and ApartmentRatings.
        """
    )

    with gr.Row():
        with gr.Column(scale=3):
            question_box = gr.Textbox(
                label="Your question",
                placeholder="e.g. What do students say about Highland Hills maintenance?",
                lines=2,
            )
            ask_btn = gr.Button("Ask", variant="primary")
        with gr.Column(scale=1):
            gr.Markdown("**Example questions**")
            example_box = gr.Examples(
                examples=[[q] for q in EXAMPLE_QUESTIONS],
                inputs=question_box,
                label="",
            )

    answer_box = gr.Textbox(label="Answer", lines=8, interactive=False)
    sources_box = gr.Textbox(label="Retrieved from (top-5 chunks)", lines=5, interactive=False)

    ask_btn.click(handle_query, inputs=question_box, outputs=[answer_box, sources_box])
    question_box.submit(handle_query, inputs=question_box, outputs=[answer_box, sources_box])

if __name__ == "__main__":
    demo.launch(theme=gr.themes.Soft())
