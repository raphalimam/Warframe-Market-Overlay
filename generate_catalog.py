import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import requests


API_URL = "https://api.warframe.market/v2/items"
OUTPUT_FILE = Path(__file__).parent / "catalogs" / "items.pt.json"


def generate_catalog():
    print("Baixando catálogo do Warframe Market...")

    headers = {
        "Accept": "application/json",
        "Language": "pt",
        "User-Agent": "Warframe-Market-Overlay"
    }

    try:
        response = requests.get(
            API_URL,
            headers=headers,
            timeout=30
        )
        response.raise_for_status()
        payload = response.json()

    except requests.RequestException as exc:
        print(f"Erro ao consultar a API: {exc}")
        sys.exit(1)

    except ValueError:
        print("Erro: a API não retornou um JSON válido.")
        sys.exit(1)

    items = payload.get("data")

    if not isinstance(items, list) or not items:
        print("Erro: a resposta não contém uma lista válida de itens.")
        sys.exit(1)

    catalog = []
    missing_pt = 0
    missing_en = 0

    for item in items:
        if not isinstance(item, dict):
            continue

        slug = item.get("slug")
        item_id = item.get("id")
        translations = item.get("i18n") or {}

        if not slug or not item_id:
            continue

        pt_data = translations.get("pt") or {}
        en_data = translations.get("en") or {}

        pt_name = pt_data.get("name")
        en_name = en_data.get("name")

        if not pt_name:
            missing_pt += 1

        if not en_name:
            missing_en += 1

        # Não inventamos traduções ausentes.
        names = {}

        if pt_name:
            names["pt"] = [pt_name]

        if en_name:
            names["en"] = [en_name]

        catalog.append({
            "slug": slug,
            "market_id": item_id,
            "names": names,
            "legacy_name": en_name,
            "aliases": [],
            "tags": item.get("tags", []),
            "ducats": item.get("ducats")
        })

    if not catalog:
        print("Erro: nenhum item válido foi encontrado.")
        sys.exit(1)

    OUTPUT_FILE.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    result = {
        "metadata": {
            "source": API_URL,
            "language": "pt",
            "generated_at": datetime.now(
                timezone.utc
            ).isoformat(),
            "item_count": len(catalog)
        },
        "items": catalog
    }

    OUTPUT_FILE.write_text(
        json.dumps(
            result,
            ensure_ascii=False,
            indent=2
        ) + "\n",
        encoding="utf-8"
    )

    print(f"\nCatálogo gerado: {OUTPUT_FILE}")
    print(f"Total de itens: {len(catalog)}")
    print(f"Sem nome em português: {missing_pt}")
    print(f"Sem nome em inglês: {missing_en}")


if __name__ == "__main__":
    generate_catalog()
