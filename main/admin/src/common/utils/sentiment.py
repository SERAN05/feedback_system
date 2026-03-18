from transformers import pipeline

# Load once at module level for efficiency
sentiment_pipeline = pipeline("sentiment-analysis", model="distilbert-base-uncased-finetuned-sst-2-english")

def analyze_sentiment(text):
    """
    Returns: (label, confidence) for the given text
    Label: Positive, Negative, Neutral
    Confidence: float (0-1)
    """
    if not text or not text.strip():
        return ("Neutral", 1.0)
    result = sentiment_pipeline(text)[0]
    label = result['label']
    score = float(result['score'])
    # Convert to 3-class
    if score < 0.7:
        label = "Neutral"
    return (label, score)

def batch_analyze(feedback_list):
    """
    feedback_list: list of strings
    Returns: list of dicts: {text, label, score}
    """
    results = []
    for text in feedback_list:
        label, score = analyze_sentiment(text)
        results.append({"text": text, "label": label, "score": round(score, 2)})
    return results
