
import difflib
import unicodedata


def normalize_name(value):
    """Normaliza nomes para comparação, sem alterar o nome original."""
    value = unicodedata.normalize("NFKD", value.casefold())
    value = "".join(
        char for char in value
        if not unicodedata.combining(char)
    )
    return " ".join(
        "".join(
            char if char.isalnum() else " "
            for char in value
        ).split()
    )


def find_item(ocr_text, catalog, language="pt", threshold=0.78):
    """
    Retorna (registro, confiança) ou (None, confiança).
    Cada registro deve conter names, aliases e a identidade do item.
    """
    query = normalize_name(ocr_text)
    if not query:
        return None, 0

    candidates = []

    for item in catalog:
        names = item.get("names", {})
        localized_names = names.get(language, [])
        english_names = names.get("en", [])

        if isinstance(localized_names, str):
            localized_names = [localized_names]
        if isinstance(english_names, str):
            english_names = [english_names]

        aliases = item.get("aliases", [])
        all_names = localized_names + english_names + aliases

        for name in all_names:
            normalized = normalize_name(name)
            if not normalized:
                continue

            score = difflib.SequenceMatcher(
                None, query, normalized
            ).ratio()

            if query == normalized:
                score = 1.0

            candidates.append((score, item))

    if not candidates:
        return None, 0

    candidates.sort(key=lambda candidate: candidate[0], reverse=True)
    best_score, best_item = candidates[0]

    # Evita escolher arbitrariamente entre itens muito semelhantes.
    if len(candidates) > 1:
        second_score, second_item = candidates[1]
        if (
            second_item.get("slug") != best_item.get("slug")
            and best_score - second_score < 0.04
        ):
            return None, round(best_score * 100)

    if best_score < threshold:
        return None, round(best_score * 100)

    return best_item, round(best_score * 100)
