"""
Ingestion pipeline — runs once to build metadata.csv

Steps:
  1. Collect all files from knowledge_base/
  2. For each file: generate description + tags via LLM (Qwen3 30B)
  3. Normalize all tags across files into a canonical master list
  4. Embed each description (Qwen3 Embedding 0.6B)
  5. Save everything to ../metadata.csv
"""

import json
import csv
import re
import time
import sys
from pathlib import Path

from openai import OpenAI

sys.path.insert(0, str(Path(__file__).parent.parent))
from config import (
    LLM_BASE_URL, LLM_MODEL,
    EMBED_BASE_URL, EMBED_MODEL,
    KB_PATH, METADATA_CSV, MASTER_TAGS_JSON, MANIFEST_PATH,
    SKIP_FILES, SUPPORTED_EXTENSIONS, MAX_CONTENT_CHARS,
)

llm = OpenAI(base_url=LLM_BASE_URL, api_key="dummy")
embedder = OpenAI(base_url=EMBED_BASE_URL, api_key="dummy")


def parse_json(content: str) -> dict:
    """Parse JSON with fallback: try direct parse, then extract first {...} block."""
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        match = re.search(r'\{.*\}', content, re.DOTALL)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                pass
        raise


# ─── File loading ────────────────────────────────────────────────────────────

def load_manifest() -> dict:
    if not MANIFEST_PATH.exists():
        return {}
    with open(MANIFEST_PATH, encoding="utf-8") as f:
        return {row["file_path"]: row for row in csv.DictReader(f)}


def prepare_content(filepath: Path) -> str:
    suffix = filepath.suffix.lower()

    if suffix == ".json":
        try:
            data = json.loads(filepath.read_text(encoding="utf-8"))
            if isinstance(data, list):
                lines = []
                for msg in data:
                    ts = msg.get("timestamp", "")[:16]
                    user = msg.get("user", "unknown")
                    channel = msg.get("channel", "")
                    text = msg.get("text", "")
                    lines.append(f"[{ts}] #{channel} {user}: {text}")
                return "\n".join(lines)
        except Exception:
            pass

    if suffix == ".pdf":
        try:
            import pypdf
            reader = pypdf.PdfReader(str(filepath))
            return "\n".join(page.extract_text() or "" for page in reader.pages)
        except Exception as e:
            return f"[PDF could not be parsed: {e}]"

    try:
        return filepath.read_text(encoding="utf-8")
    except Exception as e:
        return f"[Could not read file: {e}]"


def collect_files() -> list[Path]:
    files = []
    for path in sorted(KB_PATH.rglob("*")):
        if (
            path.is_file()
            and path.name not in SKIP_FILES
            and path.suffix.lower() in SUPPORTED_EXTENSIONS
        ):
            files.append(path)
    return files


# ─── LLM calls ───────────────────────────────────────────────────────────────

def generate_description_and_tags(filepath: Path, content: str, manifest_row: dict) -> dict:
    truncated = content[:MAX_CONTENT_CHARS]
    if len(content) > MAX_CONTENT_CHARS:
        truncated += "\n\n[... content truncated ...]"

    meta_hint = ""
    if manifest_row:
        meta_hint = (
            f"Manifest metadata: title='{manifest_row.get('title', '')}', "
            f"author='{manifest_row.get('author', '')}', "
            f"last_modified='{manifest_row.get('last_modified', '')}', "
            f"status='{manifest_row.get('status', '')}'.\n\n"
        )

    prompt = f"""{meta_hint}Analyze this internal document from Meridian Technologies and respond with JSON only.

Filename: {filepath.name}
Path: {filepath.relative_to(KB_PATH)}

Content:
---
{truncated}
---

Generate:
1. "description": EXACTLY 3-4 sentences, MAX 120 words. Cover: what the document is about, \
the most important specific facts (numbers, dates, names, limits), document status \
(current/outdated/draft/superseded), and any notable issues (contradictions, deprecated info).

2. "tags": 10-20 lowercase keyword tags. Include topic areas, system/service names, \
team names, tool names, document type, key policy terms, specific identifiers \
(e.g. "pto", "incident-response", "kafka", "aurora", "adr-003").

JSON format:
{{
  "description": "...",
  "tags": ["tag1", "tag2", ...]
}}"""

    response = llm.chat.completions.create(
        model=LLM_MODEL,
        messages=[
            {"role": "system", "content": "/no_think"},
            {"role": "user", "content": prompt},
        ],
        temperature=0.1,
        max_tokens=4000,
        response_format={"type": "json_object"},
    )
    return parse_json(response.choices[0].message.content)


def normalize_tags(all_tags_per_file: dict) -> dict:
    raw_tags = set()
    for tags in all_tags_per_file.values():
        raw_tags.update(tags)

    prompt = f"""You are a taxonomy expert normalizing keyword tags from internal company documents.

Rules:
- Merge obvious synonyms (e.g. "pto" + "paid-time-off" → "pto", "postgres" + "postgresql" → "postgresql")
- Normalize to lowercase, use hyphens instead of spaces
- Keep specific proper nouns as-is (service names, tool names, ticket IDs)
- Remove pure duplicates
- Do NOT over-merge — "deploy-process" and "deployment" can stay separate if they have different meanings

Raw tags ({len(raw_tags)} total), comma-separated:
{", ".join(sorted(raw_tags))}

Return a JSON object mapping every raw tag to its canonical form:
{{"raw_tag": "canonical_tag", ...}}"""

    response = llm.chat.completions.create(
        model=LLM_MODEL,
        messages=[
            {"role": "system", "content": "/no_think"},
            {"role": "user", "content": prompt},
        ],
        temperature=0.0,
        max_tokens=6000,
        response_format={"type": "json_object"},
    )
    return parse_json(response.choices[0].message.content)


# ─── Embedding ───────────────────────────────────────────────────────────────

def embed_text(text: str) -> list[float]:
    response = embedder.embeddings.create(
        model=EMBED_MODEL,
        input=text,
    )
    return response.data[0].embedding


# ─── Main ────────────────────────────────────────────────────────────────────

def main():
    print("=" * 60)
    print("Step 1: Collecting files")
    print("=" * 60)
    files = collect_files()
    manifest = load_manifest()
    print(f"Found {len(files)} files (skipping: {SKIP_FILES})\n")

    print("=" * 60)
    print("Step 2: Generating descriptions + tags")
    print("=" * 60)
    records = []
    all_tags_per_file = {}

    for i, filepath in enumerate(files):
        rel_path = filepath.relative_to(KB_PATH).as_posix()
        print(f"[{i+1:02d}/{len(files)}] {rel_path} ... ", end="", flush=True)

        content = prepare_content(filepath)
        manifest_row = manifest.get(rel_path, {})

        try:
            result = generate_description_and_tags(filepath, content, manifest_row)
        except Exception as e:
            print(f"ERROR: {e}")
            result = {"description": f"Could not process file: {e}", "tags": []}

        record = {
            "filepath":      rel_path,
            "filename":      filepath.name,
            "filetype":      filepath.suffix.lstrip("."),
            "description":   result["description"],
            "raw_tags":      result.get("tags", []),
            "last_modified": manifest_row.get("last_modified", ""),
            "status":        manifest_row.get("status", "unknown"),
            "department":    manifest_row.get("department", ""),
            "author":        manifest_row.get("author", ""),
            "in_manifest":   rel_path in manifest,
        }
        records.append(record)
        all_tags_per_file[rel_path] = result.get("tags", [])
        print("ok")
        time.sleep(0.1)

    print("\n" + "=" * 60)
    print("Step 3: Normalizing tags")
    print("=" * 60)
    tag_mapping = normalize_tags(all_tags_per_file)
    MASTER_TAGS_JSON.write_text(json.dumps(tag_mapping, indent=2, ensure_ascii=False))
    master_tags = sorted(set(tag_mapping.values()))
    print(f"Unique canonical tags: {len(master_tags)}")
    print(", ".join(master_tags))

    print("\n" + "=" * 60)
    print("Step 4: Embedding descriptions")
    print("=" * 60)
    for i, record in enumerate(records):
        print(f"[{i+1:02d}/{len(records)}] {record['filename']} ... ", end="", flush=True)

        canonical_tags = sorted(set(
            tag_mapping.get(t, t.lower().replace(" ", "-"))
            for t in record["raw_tags"]
        ))

        try:
            embedding = embed_text(record["description"])
        except Exception as e:
            print(f"ERROR: {e}")
            embedding = []

        record["tags"] = "|".join(canonical_tags)
        record["embedding"] = json.dumps(embedding)
        del record["raw_tags"]
        print(f"dim={len(embedding)}")

    print("\n" + "=" * 60)
    print("Step 5: Saving metadata.csv")
    print("=" * 60)
    fieldnames = [
        "filepath", "filename", "filetype",
        "description", "tags",
        "last_modified", "status", "department", "author",
        "in_manifest", "embedding",
    ]
    with open(METADATA_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(records)

    print(f"Saved {len(records)} records → {METADATA_CSV}")
    print(f"Master tags          → {MASTER_TAGS_JSON}")
    print("\nDone!")


if __name__ == "__main__":
    main()
