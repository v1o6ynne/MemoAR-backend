import json
from pathlib import Path


def read_text(path: str) -> str:
    return Path(path).read_text(encoding="utf-8")


def read_json(path: str) -> dict:
    return json.loads(read_text(path))


def read_json_text(path: str) -> str:
    """
    Read trigger JSON and return flattened text for prompt usage.
    """
    trigger_dict = read_json(path)

    lines = []
    for key, values in trigger_dict.items():
        if values:
            lines.append(f"{key}: {', '.join(values)}")

    return "\n".join(lines)

def write_json_atomic(path: str, data: dict):
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(p.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(p)


def update_trigger_db(path: str, triggers: dict) -> dict:
    """
    DB keys are all lowercase: context/time/location/emotion
    Add new trigger values if missing; keep existing.
    triggers example: {"context": "Dog", "location": "Kansas", ...}
    """
    db = read_json(path)

    for k in ["context", "time", "location", "emotion"]:
        db.setdefault(k, [])
        if not isinstance(db[k], list):
            db[k] = []

    
    existing_lower = {k: {str(x).strip().lower() for x in db[k]} for k in db.keys()}

    for key, raw_val in (triggers or {}).items():
        if key not in db:
            continue

        val = (raw_val or "").strip()
        if not val:
            continue

        v_norm = val.lower()
        if v_norm not in existing_lower[key]:
           
            db[key].append(val)

            existing_lower[key].add(v_norm)

    write_json_atomic(path, db)
    return db
