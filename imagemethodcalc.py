import requests
import pytesseract
import difflib
import os

cwd = os.getcwd()
IMPORTANT_INFO_URL = os.getenv(
    "WFMO_IMPORTANT_INFO_URL",
    "https://s3.us-east-2.amazonaws.com/www.jsourdough.com/ImportantInfo.json",
)
DEFAULT_OCR_LANGUAGE = os.getenv("WFMO_OCR_LANGUAGE", "eng")
OCR_FALLBACK_LANGUAGE = os.getenv("WFMO_OCR_FALLBACK_LANGUAGE", "eng")


importantInfo = {}
warframeParts = ["Chassis", "Systems", "Neuroptics"]
primePartsnames = []
# pytesseract.pytesseract.tesseract_cmd = cwd + "/Tesseract-OCR-V5/tesseract.exe"


def stripPrimeBlueprint(name):
    if any(x in name for x in warframeParts) and name.endswith(" Blueprint"):
        return name.rsplit(" ", 1)[0]
    return name


def normalizeCatalogItem(catalogItem):
    if isinstance(catalogItem, str):
        return {
            "candidate_name": catalogItem,
            "display_name": stripPrimeBlueprint(catalogItem),
            "market_slug": catalogItem,
            "legacy_name": stripPrimeBlueprint(catalogItem),
        }

    displayName = (
        catalogItem.get("display_name")
        or catalogItem.get("localized_name")
        or catalogItem.get("pt")
        or catalogItem.get("name")
        or catalogItem.get("legacy_name")
        or "Failed"
    )
    legacyName = catalogItem.get("legacy_name") or displayName
    candidateName = catalogItem.get("candidate_name") or displayName
    return {
        "candidate_name": candidateName,
        "display_name": stripPrimeBlueprint(displayName),
        "market_slug": catalogItem.get("market_slug") or catalogItem.get("url_name") or legacyName,
        "legacy_name": stripPrimeBlueprint(legacyName),
    }


def buildPrimePartsCatalog():
    global importantInfo
    primeCatalog = []
    for legacyName, marketSlug in importantInfo["itemsNames"].items():
        catalogItem = {
            "display_name": legacyName,
            "market_slug": marketSlug,
            "legacy_name": legacyName,
        }
        if isinstance(marketSlug, dict):
            catalogItem = {
                "display_name": (
                    marketSlug.get("display_name")
                    or marketSlug.get("localized_name")
                    or marketSlug.get("pt")
                    or marketSlug.get("name")
                    or legacyName
                ),
                "market_slug": (
                    marketSlug.get("market_slug")
                    or marketSlug.get("url_name")
                    or marketSlug.get("slug")
                    or legacyName
                ),
                "legacy_name": marketSlug.get("legacy_name", legacyName),
            }
        if any(x in catalogItem["legacy_name"] for x in warframeParts):
            catalogItem["candidate_name"] = catalogItem["display_name"] + " Blueprint"
        else:
            catalogItem["candidate_name"] = catalogItem["display_name"]
        primeCatalog.append(catalogItem)
    return primeCatalog


def getImportantinfo():
    global importantInfo
    global warframeParts
    global primePartsnames
    response = requests.get(IMPORTANT_INFO_URL, timeout=20)
    response.raise_for_status()
    importantInfo = response.json()
    importantInfo["itemsNames"]["Forma Blueprint"] = "Forma"
    importantInfo["itemsNames"]["Failed"] = "Failed"
    importantInfo["itemsDucat"]["Forma Blueprint"] = 0
    importantInfo["itemsDucat"]["Failed"] = 0
    importantInfo["itemsOrdersaverage"]["sell"]["Forma Blueprint"] = 0
    importantInfo["itemsOrdersaverage"]["sell"]["Failed"] = 0
    importantInfo["itemsOrderscheapest"]["sell"]["Forma Blueprint"] = ["None", 0]
    importantInfo["itemsOrderscheapest"]["sell"]["Failed"] = ["None", 0]
    importantInfo["itemsOrdersaverage"]["buy"]["Forma Blueprint"] = 0
    importantInfo["itemsOrdersaverage"]["buy"]["Failed"] = 0
    importantInfo["itemsOrderscheapest"]["buy"]["Forma Blueprint"] = ["None", 0]
    importantInfo["itemsOrderscheapest"]["buy"]["Failed"] = ["None", 0]
    primePartsnames = buildPrimePartsCatalog()
    return (importantInfo, primePartsnames)


def imageTolist(image, language=None):
    if language is None:
        language = DEFAULT_OCR_LANGUAGE
    screenTesseract = []
    try:
        screenTesseractraw = pytesseract.image_to_string(
            image, lang=language, config="--psm 4 --tessdata-dir tessdata"
        ).split("\n")
    except pytesseract.TesseractError:
        if (OCR_FALLBACK_LANGUAGE is None) or (OCR_FALLBACK_LANGUAGE == language):
            raise
        screenTesseractraw = pytesseract.image_to_string(
            image, lang=OCR_FALLBACK_LANGUAGE, config="--psm 4 --tessdata-dir tessdata"
        ).split("\n")
    for i, v in enumerate(screenTesseractraw):
        if not (screenTesseractraw[i] == "" or screenTesseractraw[i].isspace()):
            try:
                int(v.replace(",", ""))
            except ValueError:
                screenTesseract.append(v)
    return screenTesseract


def mappedWordprocessing(itemName, primePartsnames):
    bestMatch = None
    for v in primePartsnames:
        normalizedItem = normalizeCatalogItem(v)
        similarity = int(
            round(
                difflib.SequenceMatcher(a=itemName, b=normalizedItem["candidate_name"]).ratio(),
                2,
            )
            * 100
        )
        if (bestMatch is None) or (similarity > bestMatch[1]):
            bestMatch = (normalizedItem, similarity)
    return bestMatch


def mappedCalc(image, primePartsnames, language=None, return_details=False):
    primePart = imageTolist(image, language=language)
    bestRead = {
        "display_name": "Failed",
        "market_slug": "Failed",
        "legacy_name": "Failed",
        "confidence": 0,
    }
    multiLine = (normalizeCatalogItem("Failed"), 0)
    oneLine = (normalizeCatalogItem("Failed"), 0)
    if primePart != []:
        multiLine = mappedWordprocessing(" ".join(primePart).title(), primePartsnames)
        oneLine = mappedWordprocessing(primePart[-1].title(), primePartsnames)
        if multiLine[1] >= oneLine[1]:
            bestRead = multiLine
        else:
            bestRead = oneLine
        bestRead = {
            "display_name": bestRead[0]["display_name"],
            "market_slug": bestRead[0]["market_slug"],
            "legacy_name": bestRead[0]["legacy_name"],
            "confidence": bestRead[1],
        }
    if return_details:
        return bestRead
    return (bestRead["legacy_name"], str(bestRead["confidence"]))
