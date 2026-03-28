import sys
import re
import os
import textwrap

# Simple color formatting for terminal logs
def log_info(msg): print(f"\033[94m[INFO]\033[0m {msg}")
def log_success(msg): print(f"\033[92m[SUCCESS]\033[0m {msg}")
def log_process(msg): print(f"  \033[90m->\033[0m {msg}")

def replace_internal_calls(code, struct_name):
    pattern = re.compile(fr'\b{struct_name}\.([a-zA-Z0-9_]+)\s*\(')
    idx = 0
    while True:
        match = pattern.search(code, idx)
        if not match: break
        
        method_name = match.group(1)
        start_args = match.end()
        brace_count = 1
        end_args = -1
        
        for i in range(start_args, len(code)):
            if code[i] == '(': brace_count += 1
            elif code[i] == ')':
                brace_count -= 1
                if brace_count == 0:
                    end_args = i
                    break
                    
        if end_args != -1:
            args = code[start_args:end_args].strip()
            args = replace_internal_calls(args, struct_name)
            
            replacement = f"{struct_name}_{method_name}(self"
            if args: replacement += f", {args}"
            replacement += ")"
            
            code = code[:match.start()] + replacement + code[end_args+1:]
            idx = match.start()
        else:
            idx = match.end()
    return code

def replace_external_calls(code, var_types):
    pattern = re.compile(r'\b([a-zA-Z0-9_]+)(\.|->)([a-zA-Z0-9_]+)\s*\(')
    idx = 0
    while True:
        match = pattern.search(code, idx)
        if not match: break
            
        var_name, operator, method_name = match.group(1), match.group(2), match.group(3)
        
        if var_name not in var_types:
            idx = match.end()
            continue
            
        start_args = match.end()
        brace_count = 1
        end_args = -1
        
        for i in range(start_args, len(code)):
            if code[i] == '(': brace_count += 1
            elif code[i] == ')':
                brace_count -= 1
                if brace_count == 0:
                    end_args = i
                    break
                    
        if end_args != -1:
            args = code[start_args:end_args].strip()
            args = replace_external_calls(args, var_types)
            
            struct_name = var_types[var_name]
            self_arg = f"&{var_name}" if operator == '.' else var_name
            
            replacement = f"{struct_name}_{method_name}({self_arg}"
            if args: replacement += f", {args}"
            replacement += ")"
            
            code = code[:match.start()] + replacement + code[end_args+1:]
            idx = match.start()
        else:
            idx = match.end()
    return code

def replace_array_element_calls(body, struct_name, struct_fields):
    array_call_pattern = re.compile(
        fr'\b{struct_name}\.([a-zA-Z0-9_]+)(\[[^\]]*\])\.([a-zA-Z0-9_]+)\s*\('
    )
    idx = 0
    while True:
        m = array_call_pattern.search(body, idx)
        if not m:
            break

        field_name = m.group(1)
        index_expr = m.group(2)
        method = m.group(3)

        field_type = struct_fields.get(struct_name, {}).get(field_name)
        if not field_type:
            idx = m.end()
            continue

        start_args = m.end()
        depth = 1
        end_args = -1
        for i in range(start_args, len(body)):
            if body[i] == '(':
                depth += 1
            elif body[i] == ')':
                depth -= 1
                if depth == 0:
                    end_args = i
                    break

        if end_args == -1:
            idx = m.end()
            continue

        args = body[start_args:end_args].strip()
        self_arg = f"&self->{field_name}{index_expr}"

        replacement = f"{field_type}_{method}({self_arg}"
        if args:
            replacement += f", {args}"
        replacement += ")"

        body = body[:m.start()] + replacement + body[end_args + 1:]
        idx = m.start()

    return body

def transpile_grm(input_file, output_file):
    log_info(f"Reading {input_file}...")
    with open(input_file, 'r') as f:
        code = f.read()

    # 1. Normalise `struct Foo { ... };` -> `typedef struct { ... } Foo;`
    #    so all downstream logic only needs to handle the typedef form.
    shorthand_pattern = re.compile(
        r'\bstruct\s+([a-zA-Z0-9_]+)\s*\{([^}]*)\}\s*;'
    )
    def _to_typedef(m):
        name, body = m.group(1), m.group(2)
        return f'typedef struct {{\n{body}}}\n{name};'
    code = shorthand_pattern.sub(_to_typedef, code)

    # 2. Parse structs
    structs = {}
    struct_fields = {}
    struct_pattern = re.compile(
        r'typedef\s+struct(?:\s+[a-zA-Z0-9_]+)?\s*\{([^}]*)\}\s*([a-zA-Z0-9_]+)\s*;'
    )

    log_info("Parsing struct definitions...")
    for match in struct_pattern.finditer(code):
        body, name = match.group(1), match.group(2)
        field_pattern = re.compile(r'\b([a-zA-Z0-9_*]+)\s+\*?([a-zA-Z0-9_]+)\s*(?:\[.*?\])?\s*;')
        fields = {}
        for f in field_pattern.finditer(body):
            fields[f.group(2)] = f.group(1).replace('*', '').strip()
        struct_fields[name] = fields
        structs[name] = list(fields.keys())
        log_process(f"Registered struct: '{name}' with {len(fields)} fields.")

    # 3. Find and transpile `impl` blocks
    impl_pattern = re.compile(r'impl\s+([a-zA-Z0-9_]+)\s*\{')
    
    log_info("Processing 'impl' blocks...")
    while True:
        match = impl_pattern.search(code)
        if not match: break

        struct_name = match.group(1)
        log_process(f"Entering impl block for '{struct_name}'")
        if struct_name not in structs:
            print(f"\033[91mERROR:\033[0m Found 'impl {struct_name}' but no struct definition.")
            sys.exit(1)

        start_idx = match.end() - 1
        brace_count = 0
        end_idx = -1
        for i in range(start_idx, len(code)):
            if code[i] == '{': brace_count += 1
            elif code[i] == '}':
                brace_count -= 1
                if brace_count == 0:
                    end_idx = i
                    break

        impl_body = code[start_idx+1:end_idx]
        transpiled_impl = ""
        idx = 0
        
        func_pattern = re.compile(r'([a-zA-Z0-9_]+\s*\*?)\s+([a-zA-Z0-9_]+)\s*\((.*?)\)\s*\{')
        
        while True:
            f_match = func_pattern.search(impl_body, idx)
            if not f_match: break

            ret_type  = f_match.group(1).strip()
            func_name = f_match.group(2).strip()
            args      = f_match.group(3).strip()
            
            log_process(f"  - Transpiling method: {func_name}() -> {struct_name}_{func_name}")

            f_start_idx = f_match.end() - 1
            f_brace_count = 0
            f_end_idx = -1
            for i in range(f_start_idx, len(impl_body)):
                if impl_body[i] == '{': f_brace_count += 1
                elif impl_body[i] == '}':
                    f_brace_count -= 1
                    if f_brace_count == 0:
                        f_end_idx = i
                        break

            raw_func_body = impl_body[f_start_idx+1:f_end_idx]
            clean_body = textwrap.dedent(raw_func_body).strip()

            clean_body = replace_array_element_calls(clean_body, struct_name, struct_fields)
            clean_body = replace_internal_calls(clean_body, struct_name)

            for field in structs[struct_name]:
                clean_body = re.sub(fr'\b{struct_name}\.{field}\b', f'self->{field}', clean_body)

            indented_body = textwrap.indent(clean_body, '    ')
            c_args = f"{struct_name}* self"
            if args: c_args += f", {args}"
            c_func = f"\n{ret_type} {struct_name}_{func_name}({c_args}) {{\n{indented_body}\n}}\n"
            transpiled_impl += c_func
            idx = f_end_idx + 1

        code = code[:match.start()] + transpiled_impl + code[end_idx+1:]

    # 4. Track variable declarations
    log_info("Mapping variable instances...")
    var_types = {}
    for struct_name in structs.keys():
        var_pattern = re.compile(fr'\b{struct_name}\s+(\**)([a-zA-Z0-9_]+)\b')
        for match in var_pattern.finditer(code):
            v_name = match.group(2)
            var_types[v_name] = struct_name
            log_process(f"Found instance: '{v_name}' of type '{struct_name}'")

    # 5. Handle external method calls
    log_info("Converting external method calls...")
    code = replace_external_calls(code, var_types)

    # Cleanup extra newlines and save
    code = re.sub(r'\n{3,}', '\n\n', code)
    with open(output_file, 'w') as f:
        f.write(code.strip() + '\n')
    
    log_success(f"Transpilation complete! Output: {output_file}")

GRM_MAKE_FILE = "grm-make"

def parse_grm_make():
    """Parse grm-make and return (cc, inputs, inc_paths, lib_paths, libs, out). All fields optional."""
    cc        = "cc"
    inputs    = []
    inc_paths = []
    lib_paths = []
    libs      = []
    out       = "a.out"

    if not os.path.exists(GRM_MAKE_FILE):
        return cc, inputs, inc_paths, lib_paths, libs, out

    log_info(f"Reading '{GRM_MAKE_FILE}'...")
    with open(GRM_MAKE_FILE, 'r') as f:
        for raw in f:
            line = raw.strip()
            if not line or line.startswith('#') or '=' not in line:
                continue
            key, _, value = line.partition('=')
            key   = key.strip()
            value = value.strip()

            if key == "CC":
                cc = value
                log_process(f"Compiler      : {cc}")
            elif key == "IN":
                inputs = value.split()
                log_process(f"Inputs        : {' '.join(inputs)}")
            elif key == "IP":
                inc_paths = value.split()
                log_process(f"Include paths : {' '.join(inc_paths)}")
            elif key == "LP":
                lib_paths = value.split()
                log_process(f"Library paths : {' '.join(lib_paths)}")
            elif key == "L":
                libs = value.split()
                log_process(f"Libraries     : {' '.join(libs)}")
            elif key == "OUT":
                out = value
                log_process(f"Output        : {out}")

    return cc, inputs, inc_paths, lib_paths, libs, out


if __name__ == "__main__":
    import subprocess

    cc, grm_make_inputs, inc_paths, lib_paths, libs, out = parse_grm_make()

    # CLI args override IN from grm-make; if neither provided, bail out
    if sys.argv[1:]:
        grm_files = sys.argv[1:]
    elif grm_make_inputs:
        grm_files = grm_make_inputs
    else:
        print(f"Usage: python grmt.py <file1.grm> [file2.grm ...]")
        print(f"       (or set IN in '{GRM_MAKE_FILE}')")
        sys.exit(1)

    # Transpile every .grm -> .c
    c_files = []
    for grm_file in grm_files:
        c_file = os.path.splitext(grm_file)[0] + ".c"
        transpile_grm(grm_file, c_file)
        c_files.append(c_file)

    # Compile
    inc_flags = [f"-I{p}" for p in inc_paths]
    lib_flags = [f"-L{p}" for p in lib_paths] + [f"-l{lib}" for lib in libs]
    cmd       = [cc] + c_files + inc_flags + lib_flags + ["-o", out]

    log_info(f"Compiling: {' '.join(cmd)}")
    result = subprocess.run(cmd)

    if result.returncode != 0:
        print(f"\033[91m[ERROR]\033[0m Compiler exited with code {result.returncode}.")
        sys.exit(result.returncode)

    for c_file in c_files:
        os.remove(c_file)
        log_process(f"Removed {c_file}")

    log_success(f"Build complete! Binary: {out}")