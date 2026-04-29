def parse(s):
    import json

    def parse_value(v):
        v = v.strip()

        # JSON detection (once)
        if (v.startswith("{") and v.endswith("}")) or (v.startswith("[") and v.endswith("]")):
            try:
                return json.loads(v)
            except json.JSONDecodeError:
                pass

        # Dict-style parsing
        if v.startswith("{") and v.endswith("}"):
            inner = v[1:-1].strip()
            if inner == v:  # safety brake
                return v
            return parse_meta(inner)

        # List-style parsing
        if v.startswith("[") and v.endswith("]"):
            inner = v[1:-1]  # STRIP BRACKETS
            if not inner:
                return []

            items = []
            depth_curly = depth_square = 0
            in_string = escape = False
            start = 0

            for i, c in enumerate(inner):
                if escape:
                    escape = False
                elif c == '\\':
                    escape = True
                elif c == '"':
                    in_string = not in_string
                elif not in_string:
                    if c == '{':
                        depth_curly += 1
                    elif c == '}':
                        depth_curly -= 1
                    elif c == '[':
                        depth_square += 1
                    elif c == ']':
                        depth_square -= 1
                    elif c == ',' and depth_curly == 0 and depth_square == 0:
                        part = inner[start:i].strip()
                        if part:
                            items.append(parse_value(part))
                        start = i + 1

            part = inner[start:].strip()
            if part:
                items.append(parse_value(part))

            return items
        return v

    def parse_meta(s):
        result = {}
        depth_curly = depth_square = 0
        in_string = escape = False
        start = 0
        for i, c in enumerate(s):
            if escape:
                escape = False
            elif c == '\\':
                escape = True
            elif c == '"':
                in_string = not in_string
            elif not in_string:
                if c == '{':
                    depth_curly += 1
                elif c == '}':
                    depth_curly -= 1
                elif c == '[':
                    depth_square += 1
                elif c == ']':
                    depth_square -= 1
                elif c == ',' and depth_curly == 0 and depth_square == 0:
                    pair = s[start:i].strip()
                    if '=' in pair:
                        k, v = pair.split('=',1)
                        val = parse_value(v.strip())
                        # handle lore/display-name.extra
                        if k == 'lore' and isinstance(val, str):
                            try:
                                val = json.loads(val)
                            except:
                                pass
                        if k == 'display-name' and isinstance(val, dict) and 'extra' in val:
                            val['extra'] = [json.loads(e) if isinstance(e,str) and e.startswith('[') else e for e in val['extra']]
                        result[k.strip()] = val
                    start = i + 1
        # process last pair
        pair = s[start:].strip()
        if '=' in pair:
            k, v = pair.split('=',1)
            val = parse_value(v.strip())
            if k == 'lore' and isinstance(val, str):
                try:
                    val = json.loads(val)
                except:
                    pass
            if k == 'display-name' and isinstance(val, dict) and 'extra' in val:
                val['extra'] = [json.loads(e) if isinstance(e,str) and e.startswith('[') else e for e in val['extra']]
            result[k.strip()] = val
        return result

    if not s.startswith("ItemStack{") or not s.endswith("}"):
        raise ValueError("Not a valid ItemStack string")

    inner = s[len("ItemStack{"):-1]

    x_idx = inner.find(" x ")
    if x_idx == -1:
        raise ValueError("No ' x ' found in ItemStack")
    item = inner[:x_idx].strip()
    rest = inner[x_idx+3:].strip()

    if ',' not in rest:
        amount = int(rest)
        return {"item": item, "amount": amount, "meta_type": None, "meta": None}

    comma_idx = rest.find(',')
    amount = int(rest[:comma_idx].strip())
    meta_str = rest[comma_idx+1:].strip()

    colon_idx = meta_str.find(':{')
    if colon_idx == -1:
        raise ValueError("Meta block malformed")
    meta_type = meta_str[:colon_idx].strip()
    meta_body = meta_str[colon_idx+1:].strip()

    meta = parse_value(meta_body)

    return {"item": item, "amount": amount, "meta_type": meta_type, "meta": meta}
