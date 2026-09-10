import sys

with open('src/investiq/reporting/report.py', 'r', encoding='utf-8') as f:
    content = f.read()

old = (
    'def _build_evidence_summary(df: pd.DataFrame) -> list[dict[str, Any]]:\n'
    '    """Group evidence by domain for compact presentation.\n'
    '\n'
    '    Each group has a domain label and a list of items.\n'
    '    Full detail (evidence_id, source_url, etc.) is available in each item.\n'
    '    """\n'
    '    if df.empty:\n'
    '        return []\n'
    '    domain_groups: dict[str, list[dict]] = {}\n'
    '    for _, row in df.iterrows():\n'
    '        domain = str(row.get("domain", "Other")).strip() or "Other"\n'
    '        domain_groups.setdefault(domain, []).append({\n'
    '            "evidence_id": row.get("evidence_id", ""),\n'
    '            "tag": row.get("tag"),\n'
    '            "source": row.get("source"),\n'
    '            "source_url": row.get("source_url"),\n'
    '            "label": row.get("label"),\n'
    '            "value": row.get("value"),\n'
    '            "domain": domain,\n'
    '        })\n'
    '    result = []\n'
    '    for domain, items in domain_groups.items():\n'
    '        result.append({"domain": domain, "list": items})\n'
    '    return result'
)

new = (
    'def _build_evidence_summary(df: pd.DataFrame) -> list[dict[str, Any]]:\n'
    '    """Group evidence by domain for compact presentation, deduplicating\n'
    '    calculator-derived duplicates of the same metric.\n'
    '    """\n'
    '    if df.empty:\n'
    '        return []\n'
    '    domain_groups: dict[str, list] = {}\n'
    '    for _, row in df.iterrows():\n'
    '        domain = str(row.get("domain", "Other")).strip() or "Other"\n'
    '        label = row.get("label", "")\n'
    '        value = row.get("value")\n'
    '        source = row.get("source")\n'
    '        tag = row.get("tag")\n'
    '        canonical = _canonicalize_evidence_label(label)\n'
    '        is_calc = _is_calculator_evidence(source, tag)\n'
    '        item = {\n'
    '            "evidence_id": row.get("evidence_id", ""),\n'
    '            "tag": tag, "source": source, "source_url": row.get("source_url"),\n'
    '            "label": label, "value": value, "domain": domain,\n'
    '            "canonical": canonical, "is_calculator": is_calc,\n'
    '        }\n'
    '        domain_groups.setdefault(domain, []).append((canonical, value, is_calc, item))\n'
    '\n'
    '    result = []\n'
    '    for domain, raw_items in domain_groups.items():\n'
    '        primary_map: dict[str, dict] = {}\n'
    '        all_items = []\n'
    '        for (canonical, value, is_calc, item) in raw_items:\n'
    '            all_items.append(item)\n'
    '            if not canonical:\n'
    '                continue\n'
    '            if is_calc:\n'
    '                if canonical not in primary_map:\n'
    '                    primary_map[canonical] = item\n'
    '            else:\n'
    '                primary_map[canonical] = item\n'
    '\n'
    '        seen: set[str] = set()\n'
    '        primary_list = []\n'
    '        for (canonical, value, is_calc, item) in raw_items:\n'
    '            if not canonical:\n'
    '                primary_list.append(item)\n'
    '                continue\n'
    '            if item is primary_map.get(canonical):\n'
    '                key = canonical + "|" + (str(value) if value is not None else "")\n'
    '                if key not in seen:\n'
    '                    seen.add(key)\n'
    '                    primary_list.append(item)\n'
    '\n'
    '        result.append({"domain": domain, "list": primary_list, "all": all_items})\n'
    '    return result'
)

count = content.count(old)
print(f"Found {count} occurrences")
if count == 1:
    content = content.replace(old, new)
    with open('src/investiq/reporting/report.py', 'w', encoding='utf-8') as f:
        f.write(content)
    print("Replaced successfully")
else:
    print("Exact match not found, checking alternatives...")
    idx = content.find('def _build_evidence_summary')
    if idx >= 0:
        print(f"Found at {idx}")
        print(repr(content[idx:idx+500]))