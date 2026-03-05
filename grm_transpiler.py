import sys
import re
import os
import textwrap

# --- NEW: Parenthesis-counting parser for internal calls ---
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
            # Recursively handle nested calls inside the arguments
            args = replace_internal_calls(args, struct_name)
            
            replacement = f"{struct_name}_{method_name}(self"
            if args: replacement += f", {args}"
            replacement += ")"
            
            code = code[:match.start()] + replacement + code[end_args+1:]
            idx = match.start()
        else:
            idx = match.end()
    return code

# --- NEW: Parenthesis-counting parser for external calls ---
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
            # Recursively handle nested calls inside the arguments!
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


def compile_grm(input_file, output_file):
    with open(input_file, 'r') as f:
        code = f.read()

    # 1. Parse structs
    structs = {}
    struct_pattern = re.compile(r'typedef\s+struct(?:\s+[a-zA-Z0-9_]+)?\s*\{([^}]*)\}\s*([a-zA-Z0-9_]+)\s*;')
    
    for match in struct_pattern.finditer(code):
        body, name = match.group(1), match.group(2)
        members = re.findall(r'\b([a-zA-Z0-9_]+)\s*(?:\[.*?\])?\s*;', body)
        structs[name] = members

    # 2. Find and replace `impl` blocks
    impl_pattern = re.compile(r'impl\s+([a-zA-Z0-9_]+)\s*\{')
    
    while True:
        match = impl_pattern.search(code)
        if not match: break

        struct_name = match.group(1)
        if struct_name not in structs:
            print(f"ERROR: Found 'impl {struct_name}' but no struct definition.")
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
        translated_impl = ""
        idx = 0
        
        func_pattern = re.compile(r'([a-zA-Z0-9_]+\s*\*?)\s+([a-zA-Z0-9_]+)\s*\((.*?)\)\s*\{')
        
        while True:
            f_match = func_pattern.search(impl_body, idx)
            if not f_match: break

            ret_type, func_name, args = f_match.group(1).strip(), f_match.group(2).strip(), f_match.group(3).strip()
            
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
            
            # --- Handle internal method calls with nested parentheses ---
            clean_body = replace_internal_calls(clean_body, struct_name)

            # Inject `self->` for fields
            for field in structs[struct_name]:
                clean_body = re.sub(fr'\b{struct_name}\.{field}\b', f'self->{field}', clean_body)
            
            indented_body = textwrap.indent(clean_body, '    ')

            c_args = f"{struct_name}* self"
            if args: c_args += f", {args}"
                
            c_func = f"\n{ret_type} {struct_name}_{func_name}({c_args}) {{\n{indented_body}\n}}\n"
            translated_impl += c_func
            idx = f_end_idx + 1

        code = code[:match.start()] + translated_impl + code[end_idx+1:]

    # 3. Track variable declarations
    var_types = {}
    for struct_name in structs.keys():
        var_pattern = re.compile(fr'\b{struct_name}\s+(\**)([a-zA-Z0-9_]+)\b')
        for match in var_pattern.finditer(code):
            var_types[match.group(2)] = struct_name

    # 4. Handle external method calls with nested parentheses
    code = replace_external_calls(code, var_types)

    # Cleanup extra newlines and save
    code = re.sub(r'\n{3,}', '\n\n', code) 
    with open(output_file, 'w') as f:
        f.write(code.strip() + '\n')
    
    print(f"Successfully compiled to {output_file}!")

if __name__ == "__main__":
    if len(sys.argv) < 2: sys.exit(1)
    input_file = sys.argv[1]
    output_file = os.path.splitext(input_file)[0] + ".c"
    compile_grm(input_file, output_file)