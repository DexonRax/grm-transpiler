# GRM Transpiler: Rust-like `impl` blocks for C

**GRM Transpiler** is a lightweight Python preprocessor that brings the elegance of Rust's `impl` blocks and method-style syntax to standard C. Stop writing messy global functions like `Human_set_height(Human* h, int height)` and start organizing your logic where it belongs.

## ✨ Features

* **Scoped Logic**: Group your functions inside `impl` blocks for specific structs.
* **Method Syntax**: Call functions using the dot operator (`object.method()`) or arrow operator (`ptr->method()`).
* **Explicit Member Access**: Use `StructName.member` inside an `impl` block to automatically map to `self->member`, avoiding variable shadowing.
* **Short Struct Syntax**: Define structs with `struct Foo { ... };` instead of the verbose `typedef struct { ... } Foo;`.
* **Auto-Compilation**: Transpiles and compiles in one step — no manual `gcc` invocation needed.
* **Clean Output**: Generates human-readable, perfectly indented C code that follows standard conventions.
* **Zero Overhead**: It's a transpiler, not a runtime. Your code remains as fast as pure C.

## 🚀 How it Works

The transpiler reads `.grm` files, parses your struct definitions and `impl` blocks, rewrites them into valid C, then immediately compiles the result using the settings in your `grm-make` file.

### 1. The Input (`main.grm`)

```rust
struct Human {
    int height;
    float weight;
};

impl Human {
    void printInfo() {
        printf("Height: %d, Weight: %.2f\n", Human.height, Human.weight);
    }
}

int main() {
    Human john = {180, 75.5};
    john.printInfo(); // Method-style call!
    return 0;
}
```

### 2. The Output (`main.c`)

```c
typedef struct {
    int height;
    float weight;
} Human;

void Human_printInfo(Human* self) {
    printf("Height: %d, Weight: %.2f\n", self->height, self->weight);
}

int main() {
    Human john = {180, 75.5};
    Human_printInfo(&john);
    return 0;
}
```

## 🛠 Usage

### Option A — Project build with `grm-make`

Create a `grm-make` file next to your sources:

```
CC  = cc
IN  = main.grm second.grm
IP  = /usr/local/include ./vendor/include
LP  = /usr/local/lib ./vendor/lib
L   = raylib m
OUT = main.exe
```

| Key | Flag | Description |
|-----|------|-------------|
| `CC`  | | Compiler to use (e.g. `gcc`, `clang`, `cc`) |
| `IN`  | | Space-separated list of `.grm` source files |
| `IP`  | `-I` | Space-separated include search paths |
| `LP`  | `-L` | Space-separated library search paths |
| `L`   | `-l` | Space-separated libraries to link (without the `-l` prefix) |
| `OUT` | `-o` | Output binary name |

All keys are optional and whitespace around `=` is ignored. Then just run:

```bash
python grmt.py
```

This transpiles every file listed in `IN`, then compiles them all in one shot:

```bash
cc main.c second.c -I/usr/local/include -I./vendor/include -L/usr/local/lib -L./vendor/lib -lraylib -lm -o main.exe
```

### Option B — Quick one-off compile

Pass files directly on the command line to skip `IN` in `grm-make` (all other settings like `CC`, `IP`, `LP`, `L`, and `OUT` are still read from `grm-make` if present):

```bash
python grmt.py main.grm
```

---

### 💡 Why GRM?

Because C is great, but manually passing pointers and prefixes like `MyVeryLongStructName_my_function_name` is exhausting. GRM Transpiler does the heavy lifting for you so you can focus on building.