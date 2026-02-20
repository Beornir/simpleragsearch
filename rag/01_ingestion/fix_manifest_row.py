"""
Fixes the document_manifest.csv row in metadata.csv.
The CSV is a catalog file — needs a special short prompt, not a full-content analysis.
Run this once after ingest.py if the manifest row has an empty description.
"""

import csv
import json
import re
import sys
from pathlib import Path
from openai import OpenAI

sys.path.insert(0, str(Path(__file__).parent.parent))
from config import LLM_BASE_URL, LLM_MODEL, EMBED_BASE_URL, EMBED_MODEL, KB_PATH, METADATA_CSV

llm = OpenAI(base_url=LLM_BASE_URL, api_key="dummy")
embedder = OpenAI(base_url=EMBED_BASE_URL, api_key="dummy")

MANIFEST_PATH = KB_PATH / "meta" / "document_manifest.csv"
TARGET_FILEPATH = "meta/document_manifest.csv"


def describe_manifest() -> dict:
    with open(MANIFEST_PATH, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    total = len(rows)
    statuses = {}
    departments = {}
    missing_author = 0
    missing_modified = 0

    for r in rows:
        s = r.get("status", "").strip()
        statuses[s] = statuses.get(s, 0) + 1
        d = r.get("department", "").strip()
        departments[d] = departments.get(d, 0) + 1
        if not r.get("author", "").strip():
            missing_author += 1
        if not r.get("last_modified", "").strip():
            missing_modified += 1

    # files in manifest but not on disk
    missing_files = [
        r["file_path"] for r in rows
        if not (KB_PATH / r["file_path"]).exists()
    ]

    summary = f"""This file is the document manifest/catalog for the Meridian Technologies knowledge base.
It lists {total} documents with columns: file_path, title, author, last_modified, department, status.
Status breakdown: {dict(statuses)}.
Departments covered: {list(departments.keys())}.
Data quality issues: {missing_author} entries missing author, {missing_modified} entries missing last_modified date.
Files listed in manifest but NOT present on disk (broken references): {missing_files if missing_files else 'none detected'}.
Note: some files on disk are NOT in this manifest (e.g. grandmas_lasagna_recipe.md, expense_policy_DRAFT.md)."""

    prompt = f"""Analyze this document catalog/index and write a description for it.

{summary}

Write a 3-4 sentence description for use in a search index. Focus on: what this file is, \
what metadata it contains, known data quality issues, and its usefulness for finding documents.

Return JSON: {{"description": "...", "tags": ["tag1", "tag2", ...]}}
Include 8-12 tags like: manifest, catalog, metadata, document-index, knowledge-base, etc."""

    response = llm.chat.completions.create(
        model=LLM_MODEL,
        messages=[
            {"role": "system", "content": "/no_think"},
            {"role": "user", "content": prompt},
        ],
        temperature=0.1,
        max_tokens=800,
        response_format={"type": "json_object"},
    )
    raw = response.choices[0].message.content
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        m = re.search(r'\{.*\}', raw, re.DOTALL)
        if m:
            return json.loads(m.group())
        raise


def main():
    print(f"Generating description for {TARGET_FILEPATH}...")
    result = describe_manifest()
    description = result["description"]
    tags = "|".join(sorted(set(result.get("tags", []))))
    print(f"Description: {description}")
    print(f"Tags: {tags}")

    print("Embedding description...")
    emb_resp = embedder.embeddings.create(model=EMBED_MODEL, input=description)
    embedding = json.dumps(emb_resp.data[0].embedding)

    print(f"Updating {METADATA_CSV}...")
    rows = []
    with open(METADATA_CSV, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        for row in reader:
            if row["filepath"] == TARGET_FILEPATH:
                row["description"] = description
                row["tags"] = tags
                row["embedding"] = embedding
                print(f"  Updated row for {TARGET_FILEPATH}")
            rows.append(row)

    with open(METADATA_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print("Done.")


if __name__ == "__main__":
    main()
