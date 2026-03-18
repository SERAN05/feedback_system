import subprocess
from typing import List


def summarize_feedback(category: str, comments: List[str]) -> str:
    if not comments:
        return "No feedback available."

    # Combine all comments into one block of text
    input_text = "\n".join(comments)

    # Create the summarization prompt
    prompt = f"""
    You are analyzing student feedback.
    Category: {category}
    Comments:
    {input_text}

    Task: Generate a concise summary (3–5 sentences). Highlight praises and issues.
    Avoid mentioning names. Keep it professional and actionable.
    """

    # Try running Ollama/Mistral if available, otherwise fall back to a simple summary
    try:
        result = subprocess.run(
            ["ollama", "run", "mistral"],
            input=prompt.encode("utf-8"),
            capture_output=True,
            check=True,
            timeout=15,
        )
        output = result.stdout.decode("utf-8").strip()
        if output:
            return output
    except Exception:
        # Ollama not available or failed; fall back
        pass

    # Simple fallback: combine up to three representative comments
    preview = comments[:3]
    fallback = " \n".join(preview)
    return f"Fallback summary (first {len(preview)} comments):\n{fallback}"
