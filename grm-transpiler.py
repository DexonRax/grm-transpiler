import sys
import re
import os
import textwrap



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
    # Added a new group (Group 1) to capture the prefix, e.g., "house." or "ptr->child."
    pattern = re.compile(r'\b((?:[a-zA-Z0-9_]+(?:\[[^\]]*\])*(?:\.|->))*)([a-zA-Z0-9_]+)((?:\[[^\]]*\])*)(\.|->)([a-zA-Z0-9_]+)\s*\(')
    idx = 0
    while True:
        match = pattern.search(code, idx)
        if not match: break
            
        # Unpack all 5 groups
        prefix, base_var, indices, operator, method_name = match.groups()
        
        if base_var not in var_types:
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
            
            struct_name = var_types[base_var]
            
            # Reconstruct the full variable path (e.g., "house." + "residents" + "[0]")
            full_var = prefix + base_var + indices 
            
            self_arg = f"&{full_var}" if operator == '.' else full_var
            
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

            clean_body = replace_internal_calls(clean_body, struct_name)

            for field in structs[struct_name]:
                clean_body = re.sub(fr'\b{struct_name}\.{field}\b', f'self->{field}', clean_body)

            indented_body = textwrap.indent(clean_body, '    ')

            c_args = f"{struct_name}* self"
            if args: c_args += f", {args}"

            c_func = f"\n{ret_type} {struct_name}_{func_name}({c_args}) {{\n{indented_body}\n}}\n"
            translated_impl += c_func
            idx = f_end_idx + 1

        code = code[:match.start()] + translated_impl + code[end_idx+1:]



    # --- UPDATED: 3. Track variable declarations ---
    var_types = {}
    for struct_name in structs.keys():
        # This handles standard vars (Dog my_dog) and pointer vars (Dog* my_ptr, Dog * my_ptr)
        var_pattern = re.compile(fr'\b{struct_name}\s*\*+\s*([a-zA-Z0-9_]+)\b|\b{struct_name}\s+([a-zA-Z0-9_]+)\b')
        for match in var_pattern.finditer(code):
            var_name = match.group(1) if match.group(1) else match.group(2)
            var_types[var_name] = struct_name

    # -----------------------------------------------

    # 4. Replace external OOP method calls
    code = replace_external_calls(code, var_types)

    code = re.sub(r'\n{3,}', '\n\n', code) 
    with open(output_file, 'w') as f:
        f.write(code.strip() + '\n')

    print(f"Successfully compiled to {output_file}!")


if __name__ == "__main__":
    if len(sys.argv) < 2: sys.exit(1)
    input_file = sys.argv[1]
    output_file = os.path.splitext(input_file)[0] + ".c"
    compile_grm(input_file, output_file)