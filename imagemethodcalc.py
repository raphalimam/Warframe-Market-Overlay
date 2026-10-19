import requests
import pytesseract
import difflib
import operator
import json
import os
from pathlib import Path

from item_catalog import find_item

cwd = os.getcwd()
IMPORTANT_INFO_URL = os.getenv(
    "WFMO_IMPORTANT_INFO_URL",
    "https://s3.us-east-2.amazonaws.com/www.jsourdough.com/ImportantInfo.json",
)

BASE_DIR = Path(__file__).resolve().parent
CATALOG_PATH = BASE_DIR / "catalogs" / "items.pt.json"

catalog = []

importantInfo = {}
warframeParts = ["Chassis", "Systems", "Neuroptics"]
primePartsnames = []

def load_catalog():
    global catalog

    if catalog:
        return catalog

    if not CATALOG_PATH.is_file():
        raise FileNotFoundError(
            f"Catálogo não encontrado: {CATALOG_PATH}"
        )

    with CATALOG_PATH.open("r", encoding="utf-8") as file:
        data = json.load(file)

    items = data.get("items")

    if not isinstance(items, list) or not items:
        raise ValueError(
            "O catálogo não contém uma lista válida em 'items'."
        )

    catalog = items
    print(f"Catálogo carregado: {len(catalog)} itens.")

    return catalog
# pytesseract.pytesseract.tesseract_cmd = cwd + "/Tesseract-OCR-V5/tesseract.exe"


def generateDictFromMarketItems():
    words = set(" ".join(importantInfo["itemsNames"]).split(" "))
    with open("eng.user-words", "w+") as f:
        f.write("\n".join(words))


def getImportantinfo():
    global importantInfo
    global warframeParts
    global primePartsnames
    response = requests.get(IMPORTANT_INFO_URL, timeout=20)
    response.raise_for_status()
    importantInfo = response.json()

    load_catalog()
    primePartsnames = []
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
    for k, tv in importantInfo["itemsNames"].items():
        if any(x in k for x in warframeParts):
            primePartsnames.append(k + " Blueprint")
        else:
            primePartsnames.append(k)
    generateDictFromMarketItems()
    return (importantInfo, primePartsnames)


def imageTolist(image):
    tessdata_dir = BASE_DIR / "tessdata"

    has_por = (tessdata_dir / "por.traineddata").is_file()
    has_eng = (tessdata_dir / "eng.traineddata").is_file()

    if has_por and has_eng:
        languages = "por+eng"
    elif has_por:
        languages = "por"
    elif has_eng:
        languages = "eng"
        print(
            "Aviso: por.traineddata não encontrado. "
            "O OCR usará inglês e poderá reconhecer pior os nomes em português."
        )
    else:
        raise FileNotFoundError(
            f"Nenhum arquivo de idioma do Tesseract foi encontrado em {tessdata_dir}. "
            "Instale por.traineddata e eng.traineddata."
        )

    config = f'--psm 4 --tessdata-dir "{tessdata_dir}"'

    user_words = BASE_DIR / "eng.user-words"
    if user_words.is_file():
        config += f' --user-words "{user_words}"'

    text = pytesseract.image_to_string(
        image,
        lang=languages,
        config=config
    )

    result = []

    for line in text.splitlines():
        line = line.strip()

        if not line:
            continue

        try:
            int(line.replace(",", ""))
        except ValueError:
            result.append(line)

    return result

def mappedWordprocessing(itemName, primePartsnames):
    global warframeParts
    diffValuesunsorted = {}
    diffValuessorted = []
    for k in primePartsnames:
        diffValuesunsorted[k] = int(
            round(difflib.SequenceMatcher(a=itemName, b=k).ratio(), 2) * 100
        )
        diffValuessorted = list(
            reversed(sorted(diffValuesunsorted.items(), key=operator.itemgetter(1)))
        )
    if any(x in diffValuessorted[0][0] for x in warframeParts):
        diffValuessorted[0] = (diffValuessorted[0][0].rsplit(" ", 1)[0], diffValuessorted[0][1])
    return diffValuessorted[0]


def _resolve_market_name(item, primePartsnames):
    """
    Converte o registro reconhecido no nome esperado pelo sistema antigo.
    Funciona também quando o reconhecimento ocorre em um processo separado.
    """
    if not item:
        return None

    market_names = set(primePartsnames or [])

    names = item.get("names") or {}
    english_names = names.get("en") or []

    if isinstance(english_names, str):
        english_names = [english_names]

    candidates = []

    legacy_name = item.get("legacy_name")
    if isinstance(legacy_name, str) and legacy_name.strip():
        candidates.append(legacy_name.strip())

    candidates.extend(
        name.strip()
        for name in english_names
        if isinstance(name, str) and name.strip()
    )

    # Remove duplicatas sem perder a ordem.
    candidates = list(dict.fromkeys(candidates))
    # Compatibilidade com a entrada especial adicionada ao sistema antigo.
    if "Forma Blueprint" in market_names:
        if any(name.casefold() == "forma" for name in candidates):
            return "Forma Blueprint"
            
    for name in candidates:
        # Peças comuns: o nome inglês já é uma chave de mercado.
        if name in market_names:
            if (
                name.endswith(" Blueprint")
                and any(part in name for part in warframeParts)
            ):
                return name[:-len(" Blueprint")]

            return name

        # O código antigo acrescenta "Blueprint" às peças de Warframe.
        if (
            any(part in name for part in warframeParts)
            and name + " Blueprint" in market_names
        ):
            return name

        # Se o catálogo tiver o sufixo, tenta também o nome sem ele.
        if name.endswith(" Blueprint"):
            base_name = name[:-len(" Blueprint")]

            if base_name in market_names:
                return base_name

    return None


def mappedCalc(image, primePartsnames):
    if not catalog:
        load_catalog()

    lines = imageTolist(image)

    if not lines:
        return ("Failed", "0")

    # Testa o texto completo e as linhas individuais do OCR.
    texts_to_test = [" ".join(lines)]
    texts_to_test.extend(lines)

    best_score = 0
    best_name = None
    best_valid_score = -1

    for text in texts_to_test:
        item, score = find_item(
            text,
            catalog,
            language="pt",
            threshold=0.78
        )

        best_score = max(best_score, score)

        if item is None:
            continue

        market_name = _resolve_market_name(item, primePartsnames)

        if market_name is not None and score > best_valid_score:
            best_name = market_name
            best_valid_score = score

    if best_name is None:
        return ("Failed", str(best_score))

    return (best_name, str(best_valid_score))
