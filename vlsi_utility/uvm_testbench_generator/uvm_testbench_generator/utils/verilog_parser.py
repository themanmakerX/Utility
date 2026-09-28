import re

def extract_parameters(file_path):
    with open(file_path, "r") as file:
        content = file.read()

    # Extract all parameter and localparam values
    param_pattern = re.compile(r'(parameter|localparam)\s+(\w+)\s*=\s*([^,;\n]+)', re.IGNORECASE)
    parameters = {}
    for match in param_pattern.findall(content):
        name = match[1].strip()
        value = match[2].strip().split("//")[0].strip()  # Remove inline comments
        parameters[name] = value

    return parameters


def extract_signals(file_path):
    with open(file_path, "r") as file:
        content = file.read()

    parameters = extract_parameters(file_path)

    # Signal declaration regex
    signal_pattern = re.compile(r'(input|output|inout)\s+(?:logic|reg|wire)?\s*(\[[^\[\]]+\])?\s*(\w+)', re.IGNORECASE)
    signals = []

    for match in signal_pattern.findall(content):
        direction = match[0].strip()
        raw_width = match[1].strip() if match[1] else "1"
        name = match[2].strip()
        width = resolve_width(raw_width, parameters)
        signals.append({
            "direction": direction,
            "name": name,
            "width": width,
            "raw": raw_width
        })

    return signals


def resolve_width(raw_width, parameters):
    if raw_width == "1":
        return "1"

    try:
        # Extract expression from [X:Y]
        match = re.match(r'\[\s*([\w\d\-+*/()]+)\s*:\s*([\w\d\-+*/()]+)\s*\]', raw_width)
        if not match:
            return raw_width  # fallback to raw if not parsable

        msb, lsb = match.group(1), match.group(2)
        expr = f"({msb}) - ({lsb}) + 1"

        # Replace parameter names with their values
        for param, value in parameters.items():
            expr = re.sub(rf'\b{param}\b', f'({value})', expr)

        width_val = eval(expr)
        return str(width_val)
    except Exception:
        return raw_width  # fallback to raw if evaluation fails


def extract_module_info(file_path):
    with open(file_path, "r") as file:
        content = file.read()

    # Extract module name
    module_match = re.search(r'\bmodule\s+(\w+)', content)
    module_name = module_match.group(1) if module_match else "unknown_module"

    parameters = extract_parameters(file_path)
    signals = extract_signals(file_path)

    return {
        "module_name": module_name,
        "parameters": parameters,
        "signals": signals
    }
