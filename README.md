#  Brief overview
> This repository documents my complete journey through building progressively complex RISC-V processors in Chisel, from a basic single-cycle implementation to advanced pipelined designs with interrupt handling and memory-mapped peripherals.

## Project Overview

This project implements a series of RISC-V RV32I processors in Chisel HDL, demonstrating progressive architectural complexity and optimization techniques. Starting from a foundational single-cycle design, the implementations evolve through adding privilege modes, interrupt handling, peripheral integration, and finally, pipelined execution with hazard resolution.

### Implementations Summary

| Project | Architecture | Key Features | Instruction Set | Tests Passed |
|---------|--------------|--------------|-----------------|--------------|
| **0-minimal** | Minimal CPU | 5 instructions, JIT execution | AUIPC, ADDI, LW, SW, JALR | Educational baseline |
| **1-single-cycle** | Single-cycle | Complete RV32I, CPI=1 | 47 instructions | 9/9 unit, 41/41 RISCOF |
| **2-mmio-trap** | Single-cycle + CSR | MMIO peripherals, interrupts | 53 instructions (RV32I + Zicsr) | 9/9 unit, 119/119 RISCOF |
| **3-pipeline** | Pipelined (4 variants) | Hazard handling, forwarding | 53 instructions | 25/25 unit, 119/119 RISCOF |

### Learning Progression

```
0-minimal (Minimal ISA)
    ↓
1-single-cycle (Complete RV32I)
    ↓
2-mmio-trap (Interrupts + CSR + Peripherals)
    ↓
3-pipeline (Performance Optimization)
    ├── ThreeStage (Basic pipeline)
    ├── FiveStageStall (Classic with stalls)
    ├── FiveStageForward (Data forwarding)
    └── FiveStageFinal (Optimized hazard handling)
```

## Repository Structure

```
ca2025-mycpu/
├── 0-minimal/              # Minimal 5-instruction CPU
├── 1-single-cycle/         # Complete RV32I single-cycle CPU
│   ├── CA2025_Exercise.md  # Comprehensive documentation (detailed notes)
│   └── README.md           # Technical specification
├── 2-mmio-trap/            # Extended with CSR, CLINT, peripherals
│   └── README.md           # Implementation details
├── 3-pipeline/             # Four pipelined variants
│   └── README.md           # Pipeline optimization guide
├── common/                 # Shared modules (ALU, RegisterFile, etc.)
├── tests/                  # RISCOF compliance framework
├── scripts/                # Utility scripts
└── build.sbt              # SBT build configuration
```

## Key Achievements

### 1. Complete RV32I Implementation (1-single-cycle)

**Instruction Set Coverage:**
* Arithmetic/Logical: 19 instructions (ADD, SUB, shifts, comparisons)
* Memory Access: 8 instructions (LB, LH, LW, LBU, LHU, SB, SH, SW)
* Control Flow: 8 instructions (branches, JAL, JALR)
* Upper Immediate: 2 instructions (LUI, AUIPC)
* System: 4 instructions (ECALL, EBREAK, FENCE)

**Implementation Highlights:**
* Single-cycle execution with CPI = 1.0
* Harvard architecture with separate I/D memory
* Comprehensive immediate extraction for all instruction types
* Byte-level memory access with proper alignment
* Complete ALU with 11 operations

**Verification:**
* 9/9 ChiselTest unit tests passed
* 41/41 RISCOF architectural compliance tests passed
* Successfully executes Fibonacci and Quicksort programs

### 2. Interrupt-Capable System (2-mmio-trap)

**Extended Features:**
* Zicsr extension: 6 CSR instructions (CSRRW, CSRRS, CSRRC + immediates)
* Machine-mode CSRs: mstatus, mie, mtvec, mepc, mcause, mscratch
* CLINT: Core-Local Interrupt Controller
* MMIO peripherals: Timer, UART, VGA (640×480@72Hz)
* Trap handling: Interrupt entry/exit with atomic CSR updates
* MRET instruction for trap return

**CSR Implementation Details:**
* Atomic read-modify-write semantics
* Write priority: CLINT (trap handling) > CPU (CSR instructions)
* Interrupt state machine: MPIE←MIE, MIE←0 (entry); MIE←MPIE (exit)
* 64-bit cycle counter split into CYCLE/CYCLEH

**Verification:**
- 9/9 ChiselTest unit tests passed
- 119/119 RISCOF compliance tests passed (RV32I + Zicsr + PMP)
- VGA animation demo successfully rendered
- Timer interrupts and trap handling validated

### 3. Pipelined Execution (3-pipeline)

**Four Progressive Implementations:**

| Variant | CPI | Key Optimization |
|---------|-----|------------------|
| ThreeStage | ~2.5 | Simplified 3-stage baseline |
| FiveStageStall | ~1.8 | Classic 5-stage with stalling |
| FiveStageForward | ~1.3 | EX/MEM → EX forwarding |
| FiveStageFinal | ~1.2 | ID-stage branch + full forwarding |

**Hazard Handling Techniques:**
* Load-use hazard detection with 1-cycle stall
* Data forwarding: EX/MEM → EX, MEM/WB → EX
* ID-stage forwarding for early branch resolution
* Jump register dependency detection (JALR)
* Pipeline flush on control flow changes
* Interrupt coordination with pipeline state

**Performance Optimizations:**
* Reduced branch penalty from 2 cycles to 1 cycle (ID-stage resolution)
* Eliminated most RAW hazards through forwarding
* Optimized stall insertion for load-use scenarios
* Maintained trap handling correctness across pipeline stages

**Verification:**
* 25/25 ChiselTest unit tests passed (all 4 variants)
* 119/119 RISCOF compliance tests passed
* Hazard handling validated with hazard.asmbin
* Interrupt handling verified with irqtrap.asmbin

## Technical Implementation

### Instruction Decode

**Immediate Extraction Formats:**
* I-type: 12-bit sign-extended (loads, arithmetic immediates)
* S-type: 12-bit sign-extended split format (stores)
* B-type: 13-bit sign-extended scrambled, LSB=0 (branches)
* U-type: 20-bit upper immediate (LUI, AUIPC)
* J-type: 21-bit sign-extended scrambled, LSB=0 (JAL)

**Control Signal Generation:**
* ALU operand source selection (PC/register, immediate/register)
* Write-back source multiplexing (ALU/Memory/CSR/PC+4)
* Memory access control (read/write enable, byte strobes)

### Execution Stage

**Branch Comparison Logic:**
* Equality: BEQ, BNE
* Signed: BLT, BGE (using `.asSInt` conversion)
* Unsigned: BLTU, BGEU (direct comparison)

**Jump Target Calculation:**
* Branch: PC + immediate
* JAL: PC + immediate
* JALR: (rs1 + immediate) & ~1 (LSB clearing per RISC-V spec)

**CSR Operations:**
* CSRRW: Atomic read/write
* CSRRS: Atomic read and set bits
* CSRRC: Atomic read and clear bits
* Immediate variants with 5-bit zimm

### Memory Access

**Load Operations:**
* LB/LH: Sign extension from bit 7/15
* LBU/LHU: Zero extension
* LW: Full 32-bit word
* Address-based byte/halfword selection using address[1:0]

**Store Operations:**
* SB: 1 byte strobe, shifted by (index × 8) bits
* SH: 2 byte strobes, shifted by 0 or 16 bits
* SW: 4 byte strobes, no shifting
* Proper alignment and write strobe generation

### Interrupt Handling

**Trap Entry Sequence:**
1. CLINT detects interrupt (mstatus.MIE=1, interrupt pending)
2. Atomic CSR updates: MPIE←MIE, MIE←0, MEPC←PC, MCAUSE←cause
3. PC←MTVEC (jump to trap handler)
4. Handler executes (saves context, handles interrupt)

**Trap Exit (MRET):**
1. Restore interrupt enable: MIE←MPIE, MPIE←1
2. Return to saved address: PC←MEPC
3. Resume normal execution

**Priority Handling:**
* PC update priority: Interrupt > Jump/Branch > Sequential
* CSR write priority: CLINT (atomic trap) > CPU (instructions)

### Pipeline Hazard Resolution

**Load-Use Hazards:**
* Detection: Instruction in EX/MEM stage is load, register dependency exists
* Resolution: 1-cycle stall + forwarding from MEM stage on next cycle
* Cannot be eliminated by forwarding alone (data not ready in time)

**Data Forwarding Paths:**
* EX/MEM → EX: Forward ALU results to dependent instructions
* MEM/WB → EX: Forward memory load results
* EX/MEM → ID: Forward for early branch resolution
* MEM/WB → ID: Forward for early branch resolution
* Priority: MEM stage > WB stage when both match

**Control Hazards:**
* FiveStageStall/Forward: EX-stage branch, 2-cycle penalty (flush IF, ID)
* FiveStageFinal: ID-stage branch with forwarding, 1-cycle penalty (flush IF only)
* Jump dependencies: Detect JALR with pending load to jump register

**Stall vs Flush:**
* Stall: Freeze pipeline when data not ready (load-use), insert NOP bubble
* Flush: Clear pipeline on control flow change (branch taken, interrupt)
* Flush values: NOP (0x00000013), EntryAddress, 0.U for interrupt flags

## Development Exercises Completed

### Lab 1: Single-Cycle CPU (Exercises 1-9)
1. Immediate extraction (S-type, B-type, J-type)
2. Control signal generation
3. ALU control logic with funct7 disambiguation
4. Branch comparison (signed/unsigned)
5. Jump target calculation (JALR LSB clearing)
6. Load data extension (sign/zero)
7. Store data alignment (byte strobes)
8. Write-back multiplexer
9. PC update logic

### Lab 2: MMIO and Traps (Exercises 6, 10-15)
6. Control signals with CSR support
10. CSR register lookup table
11. CSR write priority (CLINT > CPU)
12. Load data extension (repeated for MMIO context)
13. Store data alignment (repeated for MMIO context)
13*. Interrupt entry mstatus transition
14. MRET mstatus restoration
15. PC update with interrupt priority

### Lab 3: Pipeline (Exercises 16-21)
16. Complete ALU operations (SLL, SRL, SRA, SLT, SLTU, XOR, OR, AND)
17. EX-stage data forwarding (RAW hazard elimination)
18. ID-stage data forwarding (early branch resolution)
19. Comprehensive hazard detection (load-use, jump dependencies)
20. Pipeline register flush logic
21. Hazard detection analysis (conceptual understanding)

## Verification and Testing

### ChiselTest Unit Tests
* **1-single-cycle**: 9 tests (InstructionFetch, Decode, Execute, Memory, RegisterFile, Fibonacci, Quicksort)
* **2-mmio-trap**: 9 tests (ByteAccess, CLINT, CSR, UART, Timer, Interrupt, Fibonacci, Quicksort)
* **3-pipeline**: 25 tests (4 variants × multiple programs + pipeline register tests)

### RISCOF Architectural Compliance
* **RV32I base**: 41 tests (arithmetic, logic, shifts, comparisons, loads, stores, branches, jumps)
* **Zicsr extension**: 40 tests (CSR instructions, atomic RMW, machine-mode CSRs)
* **PMP registers**: 38 tests (physical memory protection registers)
* **Total**: 119 tests, all passed

### Test Programs
* **hazard.asmbin**: Data hazard scenarios (RAW, WAW), pipeline forwarding validation
* **irqtrap.asmbin**: Interrupt entry/exit, CSR state transitions, trap handling
* **uart.asmbin**: MMIO peripheral access, UART TX/RX operations
* **nyancat.asmbin**: VGA animation with delta frame compression, 12 frames, 8.7KB binary

## Build and Simulation

### Build Commands

```bash
# Navigate to specific project directory
cd 1-single-cycle  # or 2-mmio-trap, 3-pipeline

# Run ChiselTest unit tests
make test

# Generate Verilog and build Verilator simulator
make verilator

# Run simulation with default program
make sim

# Run simulation with specific program
make sim SIM_ARGS="-instruction src/main/resources/fibonacci.asmbin"

# Run RISCOF architectural compliance tests
make compliance

# Format code (Scala + C++)
make indent

# Clean build artifacts
make clean
```

### VGA Animation Demo (2-mmio-trap)

```bash
# Generate compressed animation data (91% reduction)
cd 2-mmio-trap/csrc
python3 ../../scripts/gen-nyancat-data.py --delta --output nyancat-data.h

# Compile nyancat program
make nyancat.asmbin

# Run VGA demo with SDL2 visualization
cd ..
make demo
```

### Waveform Analysis

```bash
# Generate VCD waveform
make sim SIM_VCD=trace.vcd

# View with GTKWave
gtkwave trace.vcd

# Or view with Surfer (modern Rust-based viewer)
surfer trace.vcd
```

## Performance Analysis

### CPI (Cycles Per Instruction) Comparison

| Implementation | CPI | Improvement | Key Technique |
|----------------|-----|-------------|---------------|
| 1-single-cycle | 1.0 | Baseline | Combinational datapath |
| ThreeStage | ~2.5 | -150% | Basic pipeline with stalls |
| FiveStageStall | ~1.8 | -80% | Classic 5-stage with hazard detection |
| FiveStageForward | ~1.3 | -30% | Data forwarding paths |
| FiveStageFinal | ~1.2 | -20% | ID-stage branch + full forwarding |

### Optimization Impact

**Data Forwarding (FiveStageStall → FiveStageForward):**
- Eliminated most RAW hazards
- Reduced hazardX1 value from 46 to 27 (41% reduction in stall cycles)
- CPI improvement: ~0.5 cycles (28% better performance)

**Early Branch Resolution (FiveStageForward → FiveStageFinal):**
- Reduced branch penalty from 2 cycles to 1 cycle
- ID-stage forwarding enables early comparison
- CPI improvement: ~0.1 cycles (8% better performance)

**Load-Use Hazards (Unavoidable):**
- 1-cycle stall required (data not ready in time)
- Forwarding from MEM stage on next cycle
- Cannot be eliminated without speculative execution
