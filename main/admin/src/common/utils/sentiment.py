"""Sentiment helpers with graceful fallback for lightweight deployments.

If transformers is available, this module uses the pretrained sentiment pipeline.
Otherwise, it falls back to a tiny keyword-based classifier so the feature keeps
working on constrained/free environments.
"""

sentiment_pipeline = None

try:
    from transformers import pipeline  # type: ignore
except Exception:
    pipeline = None


def _get_pipeline():
    global sentiment_pipeline
    if sentiment_pipeline is not None:
        return sentiment_pipeline
    if pipeline is None:
        return None
    try:
        sentiment_pipeline = pipeline(
            "sentiment-analysis",
            model="distilbert-base-uncased-finetuned-sst-2-english"
        )
    except Exception:
        sentiment_pipeline = None
    return sentiment_pipeline


def _fallback_sentiment(text):
    positive_words = {
        "good", "great", "excellent", "helpful", "clear", "nice", "best",
        "love", "improve", "awesome", "satisfied", "positive"
    }
    negative_words = {
        "bad", "poor", "worst", "confusing", "late", "issue", "problem",
        "negative", "unsatisfied", "slow", "difficult", "boring"
    }

    tokens = [t.strip(".,!?;:\"'()[]{}") for t in text.lower().split()]
    pos = sum(1 for t in tokens if t in positive_words)
    neg = sum(1 for t in tokens if t in negative_words)

    if pos > neg:
        return ("Positive", min(0.9, 0.55 + (pos - neg) * 0.08))
    if neg > pos:
        return ("Negative", min(0.9, 0.55 + (neg - pos) * 0.08))
    return ("Neutral", 0.7)

def analyze_sentiment(text):
    """
    Returns: (label, confidence) for the given text
    Label: Positive, Negative, Neutral
    Confidence: float (0-1)
    """
    if not text or not text.strip():
        return ("Neutral", 1.0)

    model = _get_pipeline()
    if model is None:
        return _fallback_sentiment(text)

    result = model(text)[0]
    label = result.get('label', 'Neutral')
    score = float(result.get('score', 0.7))

    # Convert model confidence to 3-class behavior.
    if score < 0.7:
        label = "Neutral"
    if label not in {"Positive", "Negative", "Neutral"}:
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
