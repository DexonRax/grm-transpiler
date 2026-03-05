# GRM Transpiler: Rust-like `impl` blocks for C

**GRM Transpiler** is a lightweight Python preprocessor that brings the elegance of Rust's `impl` blocks and method-style syntax to standard C. Stop writing messy global functions like `Human_set_height(Human* h, int height)` and start organizing your logic where it belongs.

## ✨ Features

* **Scoped Logic**: Group your functions inside `impl` blocks for specific structs.
* **Method Syntax**: Call functions using the dot operator (`object.method()`) or arrow operator (`ptr->method()`).
* **Explicit Member Access**: Use `StructName.member` inside an `impl` block to automatically map to `self->member`, avoiding variable shadowing.
* **Clean Output**: Generates human-readable, perfectly indented C code that follows standard conventions.
* **Zero Overhead**: It’s a transpiler, not a runtime. Your code remains as fast as pure C.

## 🚀 How it Works

The transpiler reads a `.grm` file, parses your struct definitions and `impl` blocks, and rewrites them into valid C code.

### 1. The Input (`main.grm`)

```rust
typedef struct {
    int height;
    float weight;
} Human;

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

1. Clone the repo.
2. Write your code in a `.grm` file.
3. Run the transpiler:
```bash
python grm_transpiler.py your_file.grm

```


4. Compile the generated `.c` file with your favorite compiler:
```bash
gcc your_file.c -o your_program

```



---

### 💡 Why GRM?

Because C is great, but manually passing pointers and prefixes like `MyVeryLongStructName_my_function_name` is exhausting. GRM Transpiler does the heavy lifting for you so you can focus on building.

---
