import re
from collections import Counter


CATEGORY_KEYWORDS = {
    "roads": {
        "english": ("pothole", "road", "sidewalk", "pavement", "crosswalk", "street", "traffic", "crack"),
        "hindi": ("सड़क", "गड्ढा", "फुटपाथ", "मार्ग", "ट्रैफिक"),
        "gujarati": ("રસ્તો", "ખાડો", "ફૂટપાથ", "માર્ગ", "ટ્રાફિક"),
    },
    "parks": {
        "english": ("park", "playground", "bench", "garden", "tree", "public space"),
        "hindi": ("पार्क", "बगीचा", "खेल का मैदान", "पेड़", "बेंच"),
        "gujarati": ("બગીચો", "પાર્ક", "રમતનું મેદાન", "વૃક્ષ", "બેન્ચ"),
    },
    "waste": {
        "english": ("garbage", "trash", "waste", "litter", "dump", "bin", "dirty"),
        "hindi": ("कचरा", "गंदगी", "कूड़ा", "सफाई", "डस्टबिन"),
        "gujarati": ("કચરો", "ગંદકી", "સફાઈ", "ડસ્ટબિન", "કચરાપેટી"),
    },
    "water": {
        "english": ("water", "drain", "sewer", "flood", "leak", "pipe", "drainage"),
        "hindi": ("पानी", "नाली", "बाढ़", "रिसाव", "जलभराव", "सीवर"),
        "gujarati": ("પાણી", "ગટર", "પૂર", "લીકેજ", "ભરાવો", "ડ્રેનેજ"),
    },
    "street_lighting": {
        "english": ("streetlight", "street light", "lamp", "lighting", "dark street", "light pole"),
        "hindi": ("स्ट्रीट लाइट", "बत्ती", "लाइट", "अंधेरी सड़क"),
        "gujarati": ("સ્ટ્રીટ લાઇટ", "બત્તી", "લાઇટ", "અંધારો રસ્તો"),
    },
    "public_safety": {
        "english": ("unsafe", "danger", "hazard", "exposed wire", "accident", "broken signal"),
        "hindi": ("खतरा", "असुरक्षित", "दुर्घटना", "बिजली का तार"),
        "gujarati": ("જોખમ", "અસુરક્ષિત", "અકસ્મત", "વીજળીનો તાર"),
    },
}

URGENCY_TERMS = {
    "english": (
        "urgent", "emergency", "dangerous", "life threatening", "exposed wire",
        "electrocution", "fire", "severe flooding", "collapsed", "injured",
    ),
    "hindi": ("आपातकाल", "तत्काल", "खतरनाक", "बिजली का खुला तार", "आग", "गंभीर बाढ़", "दुर्घटना"),
    "gujarati": ("તાત્કાલિક", "કટોકટી", "જોખમી", "ખુલ્લો વીજ તાર", "આગ", "ગંભીર પૂર", "અકસ્મત"),
}

SPAM_TERMS = (
    "buy now", "click here", "crypto", "casino", "free money", "subscribe",
    "visit my website", "promo code", "earn money", "make money",
    "guaranteed returns", "investment opportunity", "limited time offer",
    "claim your prize", "click the link", "join my channel",
    "contact me on whatsapp", "loan approved", "buy followers",
)
IRRELEVANT_TERMS = (
    "this is a test", "not a civic issue", "unrelated to civic", "just checking",
)
STOP_WORDS = {
    "a", "an", "and", "are", "at", "be", "by", "for", "from", "here", "in",
    "is", "it", "near", "of", "on", "the", "there", "this", "to", "was", "with",
    "issue", "problem", "please", "reported",
}
LANGUAGE_NAMES = {"english": "English", "hindi": "Hindi", "gujarati": "Gujarati"}


def detect_language(text):
    devanagari = len(re.findall(r"[\u0900-\u097f]", text))
    gujarati = len(re.findall(r"[\u0a80-\u0aff]", text))
    latin = len(re.findall(r"[A-Za-z]", text))
    total = devanagari + gujarati + latin
    if not total:
        return "unknown", 0.0
    if devanagari > gujarati and devanagari > latin:
        return "hindi", round(devanagari / total, 2)
    if gujarati > devanagari and gujarati > latin:
        return "gujarati", round(gujarati / total, 2)
    if latin > 0:
        return "english", round(latin / total, 2)
    return "unknown", 0.0


def _terms(text):
    return [
        word.casefold()
        for word in re.findall(r"[^\W_]+", text, flags=re.UNICODE)
        if len(word) > 1 and word.casefold() not in STOP_WORDS
    ]


def _category_suggestion(text, language):
    scores = {}
    for category, languages in CATEGORY_KEYWORDS.items():
        keywords = languages.get(language, ())
        matched = [keyword for keyword in keywords if keyword in text.casefold()]
        if matched:
            scores[category] = (len(matched), matched)
    if not scores:
        return "unclassified", 0.0, []
    category, (count, matches) = max(scores.items(), key=lambda item: (item[1][0], item[0]))
    confidence = min(0.95, 0.55 + 0.12 * (count - 1))
    return category, round(confidence, 2), matches


def _summary(text, limit=240):
    sentences = [part.strip() for part in re.split(r"(?<=[.!?।])\s+", text.strip()) if part.strip()]
    summary = sentences[0] if sentences else text.strip()
    if len(summary) > limit:
        summary = summary[:limit - 1].rsplit(" ", 1)[0] + "…"
    return summary


def _entities(description, location):
    found = [{"type": "location", "text": location.strip()}]
    patterns = (
        r"\b(?:near|at|on|opposite|beside|outside)\s+([A-Z][\w'-]*(?:\s+[A-Z][\w'-]*){0,3})",
        r"\b(?:street|road|avenue|lane|market|school|hospital|station)\s+(?:no\.?\s*)?\d*\s*[A-Z][\w'-]*(?:\s+[A-Z][\w'-]*){0,2}",
    )
    candidates = []
    for pattern in patterns:
        candidates.extend(re.findall(pattern, description))
    seen = {location.strip().casefold()}
    for candidate in candidates:
        value = candidate.strip()
        if value and value.casefold() not in seen:
            found.append({"type": "place_hint", "text": value})
            seen.add(value.casefold())
    return found[:6]


def _spam_flags(text):
    normalized = re.sub(r"[^\w]+", " ", text.casefold(), flags=re.UNICODE).strip()
    reasons = []
    spam_matches = [term for term in SPAM_TERMS if term in normalized]
    if spam_matches:
        reasons.append("Promotional/scam wording: " + ", ".join(spam_matches[:3]))
    if any(term in normalized for term in IRRELEVANT_TERMS):
        reasons.append("May not describe a civic service issue")
    if re.search(r"(?:https?://|www\.)\S+", text, flags=re.IGNORECASE):
        reasons.append("Contains a web link")
    words = _terms(normalized)
    if len(words) >= 6 and max(Counter(words).values(), default=0) / len(words) > 0.65:
        reasons.append("Unusually repetitive text")
    if re.search(r"(.)\1{3,}", text, flags=re.IGNORECASE):
        reasons.append("Contains a long repeated character sequence")
    return reasons


def _duplicate_candidates(description, location, category, existing):
    report_terms = set(_terms(description))
    if not report_terms:
        return []
    matches = []
    for candidate in existing:
        other_terms = set(_terms(candidate["description"]))
        union = report_terms | other_terms
        similarity = len(report_terms & other_terms) / len(union) if union else 0
        same_location = location.strip().casefold() == candidate["location"].strip().casefold()
        if same_location:
            similarity = max(similarity, 0.45)
        same_category = category != "unclassified" and category == candidate["category"]
        if similarity >= 0.34 and (same_location or same_category or similarity >= 0.48):
            matches.append({
                "id": candidate["id"],
                "location": candidate["location"],
                "summary": _summary(candidate["description"]),
                "category": candidate["category"],
                "similarity": round(min(similarity, 1.0), 2),
            })
    return sorted(matches, key=lambda match: match["similarity"], reverse=True)[:3]


def analyze_report(description, location, language="auto", existing=()):
    detected_language, language_confidence = detect_language(description)
    if language in LANGUAGE_NAMES:
        detected_language = language
        language_confidence = 1.0
    category, category_confidence, category_matches = _category_suggestion(description, detected_language)
    normalized = description.casefold()
    urgency_matches = [term for term in URGENCY_TERMS.get(detected_language, ()) if term in normalized]
    spam_reasons = _spam_flags(description)
    return {
        "detected_language": detected_language,
        "language_confidence": language_confidence,
        "suggested_category": category,
        "category_confidence": category_confidence,
        "category_matches": category_matches,
        "urgency_flag": bool(urgency_matches),
        "urgency_reasons": urgency_matches,
        "summary": _summary(description),
        "entities": _entities(description, location),
        "spam_flag": bool(spam_reasons),
        "spam_reasons": spam_reasons,
        "duplicate_candidates": _duplicate_candidates(
            description, location, category, existing
        ),
        "model_type": "local_rules",
    }
