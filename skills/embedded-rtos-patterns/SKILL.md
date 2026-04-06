---
name: embedded-rtos-patterns
description: Bare-metal C patterns, ISR design, memory-mapped registers, FreeRTOS/Zephyr task architecture, queues, semaphores, timing, multicore SMP, power management, telemetry, and off-target testing. Use when writing, reviewing, or designing embedded firmware and RTOS applications.
---

# Embedded & RTOS Patterns

Patterns and best practices for bare-metal C, interrupt-driven firmware, and RTOS-based embedded systems (FreeRTOS, Zephyr). Covers architectural decoupling, memory allocation, hardware-enforced safety, multicore SMP, ISR design, task architecture, synchronization, hardware interaction, state machines, deterministic timing, power management, watchdog supervision, and crash telemetry.

## When to Use

- Writing or reviewing embedded C/C++ firmware
- Designing FreeRTOS or Zephyr task architectures
- Implementing ISR handlers and deferred processing
- Working with memory-mapped registers and peripherals
- Debugging timing, starvation, or priority inversion issues
- Structuring producer-consumer or sensor-processing pipelines
- Designing multicore (SMP) firmware on dual-core MCUs (e.g., RP2040)
- Implementing low-power modes and tickless idle
- Designing watchdog supervision and crash persistence strategies
- Planning off-target testing and architectural decoupling

### When NOT to Use

- General-purpose application development (use `cpp-coding-standards` or `rust-patterns`)
- Linux userspace applications (embedded patterns assume bare-metal or RTOS constraints)

## How It Works

This skill provides concrete patterns organized by domain: architectural decoupling, static memory, hardware-enforced safety, multicore SMP, ISR design, RTOS task architecture, synchronization primitives, hardware register access, state machines, timing, DMA, power management, watchdog supervision, telemetry, and defensive programming. Each pattern includes a rationale, a BAD/GOOD code example, and guidance on when to apply it.

---

## 1. Architectural Decoupling & Off-Target Testing

Decouple application logic from hardware and RTOS to enable portable, testable firmware.

### OS Abstraction Layer (OSAL)

Prevent vendor lock-in and enable hardware-agnostic host-side simulation by abstracting RTOS APIs behind a portable interface (e.g., CMSIS-RTOSv2).

```c
// BAD: Direct FreeRTOS calls scattered through application code
void vAppTask(void *pvParameters) {
    xSemaphoreTake(xMutex, portMAX_DELAY);
    // ... application logic ...
    xSemaphoreGive(xMutex);
}

// GOOD: OSAL abstraction -- swap RTOS without touching app code
#include "osal.h"

void vAppTask(void *pvParameters) {
    osal_mutex_lock(&app_mutex, OSAL_WAIT_FOREVER);
    // ... application logic ...
    osal_mutex_unlock(&app_mutex);
}
```

### Configuration Tables

Centralize peripheral initialization parameters into `static const` ROM tables to make hardware drivers highly reusable and decoupled from specific application implementations.

```c
// BAD: Hard-coded peripheral setup mixed into driver logic
void uart_init(void) {
    USART1->BRR = 0x0683;  // Magic baud rate
    USART1->CR1 = USART_CR1_TE | USART_CR1_RE | USART_CR1_UE;
}

// GOOD: Configuration table -- driver is reusable across products
typedef struct {
    USART_TypeDef *periph;
    uint32_t       baud;
    uint32_t       flags;
} UartConfig_t;

static const UartConfig_t uart_configs[] = {
    { USART1, 115200, USART_CR1_TE | USART_CR1_RE | USART_CR1_UE },
    { USART2,   9600, USART_CR1_TE | USART_CR1_RE | USART_CR1_UE },
};

void uart_init(const UartConfig_t *cfg) {
    cfg->periph->BRR = compute_brr(cfg->baud);
    cfg->periph->CR1 = cfg->flags;
}
```

### Data Encapsulation (Opaque Pointer Pattern)

Use the Opaque Pointer pattern in C to hide struct memory layouts from client code, enforcing state protection without the overhead of C++.

```c
// sensor.h -- public API, struct internals hidden
typedef struct Sensor Sensor_t;  // Opaque forward declaration

Sensor_t *sensor_create(uint8_t channel);
int32_t   sensor_read(const Sensor_t *self);
void      sensor_destroy(Sensor_t *self);

// sensor.c -- private implementation
struct Sensor {
    uint8_t  channel;
    int32_t  last_reading;
    uint32_t calibration;
};
```

### Test-Driven Development (Off-Target)

Compile and verify logic off-target on a host PC using mocking frameworks (CMock, Unity, fff) to achieve full execution path coverage without the bottleneck of physical hardware.

```c
// test_sensor_filter.c -- runs on host PC, no hardware needed
#include "unity.h"
#include "mock_adc_driver.h"  // CMock-generated mock
#include "sensor_filter.h"

void test_moving_average_filters_noise(void) {
    adc_read_raw_ExpectAndReturn(1024);
    adc_read_raw_ExpectAndReturn(1028);
    adc_read_raw_ExpectAndReturn(1020);

    int32_t avg = sensor_filter_update();
    TEST_ASSERT_INT32_WITHIN(2, 1024, avg);
}
```

---

## 2. Memory Management & Hardware-Enforced Safety

### Static Memory Allocation

All memory must be statically allocated at compile time. Dynamic allocation (`malloc`, `free`, `new`, `delete`, `pvPortMalloc`, `vPortFree`) causes fragmentation and non-deterministic behavior.

```c
// BAD: Dynamic allocation at runtime
void vTask(void *pvParameters) {
    uint8_t *buf = malloc(512); // Fragmentation risk, may fail silently
    // ...
    free(buf);
}

// GOOD: Static allocation -- deterministic, no fragmentation
static uint8_t rx_buffer[512];
static uint8_t tx_buffer[256];

void vTask(void *pvParameters) {
    memset(rx_buffer, 0, sizeof(rx_buffer));
}
```

### Static RTOS Objects

```c
// GOOD: Statically allocated FreeRTOS objects
static StaticTask_t xTaskBuffer;
static StackType_t xTaskStack[configMINIMAL_STACK_SIZE];

static StaticQueue_t xQueueBuffer;
static uint8_t xQueueStorage[QUEUE_LENGTH * ITEM_SIZE];

void vCreateInfrastructure(void) {
    xTaskCreateStatic(vWorkerTask, "Worker", configMINIMAL_STACK_SIZE,
                      NULL, WORKER_PRIORITY, xTaskStack, &xTaskBuffer);

    xQueueCreateStatic(QUEUE_LENGTH, ITEM_SIZE, xQueueStorage, &xQueueBuffer);
}
```

### Hardware Stack Protection

Software watermarks (`uxTaskGetStackHighWaterMark`) are insufficient for safety-critical systems. Use the Memory Protection Unit (MPU) or ARM stack limit registers (e.g., `PSPLIM`) to enforce strict mathematical boundaries that trigger instantaneous hardware faults on stack overflow.

```c
// INSUFFICIENT: Software watermark -- detects overflow after the fact
#if configCHECK_FOR_STACK_OVERFLOW
UBaseType_t hwm = uxTaskGetStackHighWaterMark(NULL);
configASSERT(hwm > 32);
#endif

// BETTER: MPU-enforced stack guard region -- hardware fault on overflow
// FreeRTOS v10.6+ with configENABLE_MPU = 1
// The kernel automatically configures MPU regions around task stacks
// when using xTaskCreateRestricted() or xTaskCreateRestrictedStatic()
static const TaskParameters_t xWorkerParams = {
    .pvTaskCode    = vWorkerTask,
    .pcName        = "Worker",
    .usStackDepth  = WORKER_STACK_SIZE,
    .uxPriority    = WORKER_PRIORITY | portPRIVILEGE_BIT,
    .puxStackBuffer = xWorkerStack,
    // MPU regions configured automatically for stack guard
};

xTaskCreateRestricted(&xWorkerParams, &xWorkerHandle);
```

### Stack Discipline

Keep local variables small. Large arrays on the stack risk overflow in tasks with limited stack space.

```c
// BAD: Large local buffer threatens task stack
void vProcessTask(void *pvParameters) {
    uint8_t frame[2048]; // 2KB on a task stack that may only be 1KB!
    // ...
}

// GOOD: File-scope static buffer
static uint8_t frame[2048];

void vProcessTask(void *pvParameters) {
    memset(frame, 0, sizeof(frame));
    // ...
}
```

### Struct Padding Minimization

Order struct members strictly by size (largest to smallest) to minimize padding waste during queue copies or DMA transfers.

```c
// BAD: Compiler inserts 7 bytes of padding (24 bytes total on 32-bit)
typedef struct {
    uint8_t  status;     // 1 byte + 3 padding
    uint32_t timestamp;  // 4 bytes
    uint8_t  channel;    // 1 byte + 3 padding
    uint32_t value;      // 4 bytes
} PaddedSample_t;        // 16 bytes with 6 wasted

// GOOD: Ordered by size -- minimal padding (12 bytes, 0 wasted)
typedef struct {
    uint32_t timestamp;  // 4 bytes
    uint32_t value;      // 4 bytes
    uint8_t  status;     // 1 byte
    uint8_t  channel;    // 1 byte + 2 padding (end only)
} PackedSample_t;        // 12 bytes

_Static_assert(sizeof(PackedSample_t) == 12, "unexpected struct padding");
```

---

## 3. Multicore (SMP) Paradigms

For dual-core architectures (like the RP2040), tasks cannot assume single-core preemption rules. SMP-aware scheduling and inter-core communication primitives are required.

### Core Affinity

Pin hardware-dependent tasks to dedicated cores to prevent migration and ensure deterministic peripheral access.

```c
// GOOD: Pin time-critical sensor task to core 0, comms to core 1
TaskHandle_t xSensorTask, xCommsTask;

xTaskCreate(vSensorTask, "Sensor", SENSOR_STACK, NULL, 3, &xSensorTask);
xTaskCreate(vCommsTask,  "Comms",  COMMS_STACK,  NULL, 2, &xCommsTask);

// FreeRTOS SMP API
vTaskCoreAffinitySet(xSensorTask, (1 << 0));  // Core 0 only
vTaskCoreAffinitySet(xCommsTask,  (1 << 1));  // Core 1 only
```

### Inter-Core Communication

Use Stream Buffers and Message Buffers for lock-free, lightweight data transfer across cores instead of relying solely on standard queues (which may require cross-core mutex contention).

```c
// GOOD: Stream buffer for lock-free cross-core byte stream
static StreamBufferHandle_t xCrossCoreBuf;

// Core 0: Producer
void vSensorTask(void *pvParameters) {
    uint8_t sample[16];
    while (1) {
        read_sensor(sample, sizeof(sample));
        xStreamBufferSend(xCrossCoreBuf, sample, sizeof(sample),
                          pdMS_TO_TICKS(10));
    }
}

// Core 1: Consumer
void vCommsTask(void *pvParameters) {
    uint8_t rx[16];
    while (1) {
        size_t n = xStreamBufferReceive(xCrossCoreBuf, rx, sizeof(rx),
                                         portMAX_DELAY);
        if (n > 0) transmit_data(rx, n);
    }
}
```

> **Note:** Stream/Message Buffers are single-writer, single-reader only. For multi-writer or multi-reader scenarios, use queues with appropriate synchronization.

---

## 4. Task Decomposition & Scheduling

### Rate Monotonic Scheduling (RMS)

Use RMS principles to mathematically verify that all periodic tasks will meet their execution deadlines based on their worst-case execution times and frequencies.

```c
// RMS schedulability check: sum of (WCET_i / Period_i) <= n * (2^(1/n) - 1)
// For 3 tasks: utilization bound = 3 * (2^(1/3) - 1) ≈ 0.780
//
// Task         WCET    Period    Utilization
// Sensor       1ms     10ms      0.100
// Filter       2ms     20ms      0.100
// Transmit     5ms     50ms      0.100
// Total:                         0.300 <= 0.780  ✓ Schedulable

// Assign priorities: shorter period = higher priority (RMS rule)
#define SENSOR_PRIORITY    (tskIDLE_PRIORITY + 3)  // 10ms period
#define FILTER_PRIORITY    (tskIDLE_PRIORITY + 2)  // 20ms period
#define TRANSMIT_PRIORITY  (tskIDLE_PRIORITY + 1)  // 50ms period
```

### Active Object Pattern

Transition from monolithic switch-based FSMs and deadlock-prone mutexes to Active Objects that encapsulate their own threads and communicate exclusively via lock-free, asynchronous message queues.

```c
// BAD: Shared state protected by mutex -- deadlock-prone
static Mutex_t gStateMutex;
static SystemState_t gState;

void vTask1(void *p) {
    xSemaphoreTake(gStateMutex, portMAX_DELAY);
    gState = process_event(gState, evt);  // Holding mutex during compute
    xSemaphoreGive(gStateMutex);
}

// GOOD: Active Object -- private state, message-driven
typedef struct {
    TaskHandle_t  task;
    QueueHandle_t mailbox;
    SystemState_t state;  // Private, never shared
} ActiveObject_t;

static void vActiveObjectRun(void *pvParameters) {
    ActiveObject_t *ao = (ActiveObject_t *)pvParameters;
    Event_t evt;
    while (1) {
        xQueueReceive(ao->mailbox, &evt, portMAX_DELAY);
        ao->state = process_event(ao->state, &evt);  // No mutex needed
    }
}

// External callers post events, never touch state directly
void active_object_post(ActiveObject_t *ao, const Event_t *evt) {
    xQueueSend(ao->mailbox, evt, pdMS_TO_TICKS(10));
}
```

### Priority-Based Pipeline (Task Chaining)

Chain chronological tasks with strictly descending priorities to enable sequential data processing without race conditions.

```c
// Sensor (highest) -> FFT (middle) -> Output (lowest)
#define SENSOR_TASK_PRIORITY  (tskIDLE_PRIORITY + 3)
#define FFT_TASK_PRIORITY     (tskIDLE_PRIORITY + 2)
#define OUTPUT_TASK_PRIORITY  (tskIDLE_PRIORITY + 1)

static QueueHandle_t xRawQueue;   // Sensor -> FFT
static QueueHandle_t xResultQueue; // FFT -> Output

void vSensorTask(void *pvParameters) {
    SensorData_t sample;
    while (1) {
        ulTaskNotifyTake(pdTRUE, portMAX_DELAY); // Wait for ISR trigger
        sample = read_sensor();
        xQueueSend(xRawQueue, &sample, portMAX_DELAY); // Hand off, then block
    }
}

void vFFTTask(void *pvParameters) {
    SensorData_t sample;
    FFTResult_t result;
    while (1) {
        xQueueReceive(xRawQueue, &sample, portMAX_DELAY);
        result = compute_fft(&sample);
        xQueueSend(xResultQueue, &result, portMAX_DELAY);
    }
}

void vOutputTask(void *pvParameters) {
    FFTResult_t result;
    while (1) {
        xQueueReceive(xResultQueue, &result, portMAX_DELAY);
        transmit_result(&result);
    }
}
```

### Event-Driven Tasks (Never Poll)

```c
// BAD: Polling wastes CPU, introduces latency, starves lower tasks
void vBadTask(void *pvParameters) {
    while (1) {
        if (check_flag()) {
            do_work();
        }
        vTaskDelay(pdMS_TO_TICKS(10)); // Arbitrary delay -- misses events
    }
}

// GOOD: Block on a synchronization primitive
void vGoodTask(void *pvParameters) {
    while (1) {
        xQueueReceive(xEventQueue, &event, portMAX_DELAY);
        handle_event(&event);
    }
}
```

### Stack Sizing

Always document stack size rationale. Use `uxTaskGetStackHighWaterMark()` during development to verify headroom.

```c
// BAD: Magic number
xTaskCreate(vWorkerTask, "Worker", 256, NULL, 2, NULL);

// GOOD: Named constant with rationale
// Stack: 128 baseline + 64 for printf + 64 headroom = 256 words
#define WORKER_STACK_SIZE  256
xTaskCreate(vWorkerTask, "Worker", WORKER_STACK_SIZE, NULL, 2, NULL);
```

---

## 5. ISR Design & Hardware Interaction

ISRs must be short, non-blocking, and defer all heavy work to tasks. The ISR captures the event and hands it off.

### Deferred Processing (ISR-to-Task Handoff)

Keep ISRs absolutely minimal. Clear the hardware flag and immediately hand off processing to an RTOS task using `vTaskNotifyGiveFromISR` or queues.

```c
static TaskHandle_t xProcessingTask = NULL;

// ISR: Capture event, notify task, exit fast
void EXTI0_IRQHandler(void) {
    BaseType_t xHigherPriorityTaskWoken = pdFALSE;

    HAL_GPIO_EXTI_IRQHandler(GPIO_PIN_0);

    vTaskNotifyGiveFromISR(xProcessingTask, &xHigherPriorityTaskWoken);
    portYIELD_FROM_ISR(xHigherPriorityTaskWoken);
}

// Task: Do the heavy lifting
void vProcessingTask(void *pvParameters) {
    while (1) {
        ulTaskNotifyTake(pdTRUE, portMAX_DELAY); // Block until ISR signals
        perform_expensive_computation();
    }
}
```

### ISR Data Handoff via Queue

When the ISR produces data (not just a signal), use a queue:

```c
static QueueHandle_t xUartQueue;

void USART1_IRQHandler(void) {
    BaseType_t xHigherPriorityTaskWoken = pdFALSE;
    uint8_t byte = USART1->DR;

    xQueueSendFromISR(xUartQueue, &byte, &xHigherPriorityTaskWoken);
    portYIELD_FROM_ISR(xHigherPriorityTaskWoken);
}

void vUartTask(void *pvParameters) {
    uint8_t byte;
    while (1) {
        if (xQueueReceive(xUartQueue, &byte, portMAX_DELAY) == pdPASS) {
            process_byte(byte);
        }
    }
}
```

### Mandatory Yielding

Always evaluate context switches at the end of an ISR (`portYIELD_FROM_ISR`) to guarantee the immediate execution of any high-priority task unblocked by the interrupt.

### ISR API Rules

| Context | Use This | Never This |
|---------|----------|------------|
| ISR | `xQueueSendFromISR()` | `xQueueSend()` |
| ISR | `xSemaphoreGiveFromISR()` | `xSemaphoreGive()` |
| ISR | `vTaskNotifyGiveFromISR()` | `xTaskNotifyGive()` |
| ISR | `xTimerStartFromISR()` | `xTimerStart()` |
| ISR exit | `portYIELD_FROM_ISR()` | (don't omit) |

### ISR Identification

Recognize ISR code by these naming patterns:
- `*_IRQHandler` (STM32 HAL / CMSIS)
- `ISR(TIMER1_COMPA_vect)` (AVR)
- `IRAM_ATTR` functions (ESP-IDF)
- `__attribute__((interrupt))` annotations
- Files named `*_it.c`, `*_isr.c`

### Volatile for Memory-Mapped Registers

All hardware register access must go through `volatile` pointers. Without `volatile`, the compiler may optimize away reads/writes.

```c
// Typical memory-mapped register definition
#define GPIOA_BASE  0x40020000UL
#define GPIOA_ODR   (*(volatile uint32_t *)(GPIOA_BASE + 0x14))
#define GPIOA_IDR   (*(volatile uint32_t *)(GPIOA_BASE + 0x10))

// GOOD: Atomic read-modify-write in critical section
void gpio_set_pin(uint32_t pin) {
    taskENTER_CRITICAL();
    GPIOA_ODR |= (1UL << pin);
    taskEXIT_CRITICAL();
}
```

### Critical Sections for Read-Modify-Write

Any read-modify-write on a hardware register must be protected. An interrupt between the read and write corrupts the register.

```c
// BAD: Unprotected read-modify-write
void config_peripheral(void) {
    PERIPH->CR |= ENABLE_BIT;  // Interrupt here corrupts CR
}

// GOOD: Protected
void config_peripheral(void) {
    taskENTER_CRITICAL();       // Disables interrupts
    PERIPH->CR |= ENABLE_BIT;
    taskEXIT_CRITICAL();
}
```

### Keep Critical Sections Minimal

```c
// BAD: Heavy work inside critical section blocks all interrupts
taskENTER_CRITICAL();
compute_checksum(large_buffer, 4096);  // Long computation!
PERIPH->DR = result;
taskEXIT_CRITICAL();

// GOOD: Compute outside, protect only the register write
uint32_t result = compute_checksum(large_buffer, 4096);
taskENTER_CRITICAL();
PERIPH->DR = result;
taskEXIT_CRITICAL();
```

### DMA Offloading

Prefer Direct Memory Access (DMA) over CPU-driven loops for all bulk data transfers (SPI, UART, ADC) to maximize CPU availability.

> **Note:** Not all MCUs have DMA controllers, and available DMA channels may be limited. Treat this as a strong recommendation, not a universal rule. Verify DMA availability for your target before refactoring.

#### SPI Transfer

```c
// BAD: CPU-driven -- blocks task for entire transfer
void vSendFrame(const uint8_t *buf, size_t len) {
    for (size_t i = 0; i < len; i++) {
        while (!(SPI1->SR & SPI_SR_TXE)) {}  // Spin per byte
        SPI1->DR = buf[i];
    }
    while (SPI1->SR & SPI_SR_BSY) {}  // Wait for completion
}

// GOOD: DMA -- CPU is free during transfer, task blocks on notification
static TaskHandle_t xSpiTaskHandle;

void vSendFrame(const uint8_t *buf, size_t len) {
    HAL_SPI_Transmit_DMA(&hspi1, buf, len);
    ulTaskNotifyTake(pdTRUE, pdMS_TO_TICKS(100)); // Block until DMA complete
}

void HAL_SPI_TxCpltCallback(SPI_HandleTypeDef *hspi) {
    BaseType_t xWoken = pdFALSE;
    vTaskNotifyGiveFromISR(xSpiTaskHandle, &xWoken);
    portYIELD_FROM_ISR(xWoken);
}
```

#### ADC Scan Sequence

```c
// BAD: CPU polls each channel sequentially
uint16_t adc_values[4];
for (int ch = 0; ch < 4; ch++) {
    HAL_ADC_Start(&hadc1);
    HAL_ADC_PollForConversion(&hadc1, 100);
    adc_values[ch] = HAL_ADC_GetValue(&hadc1);
}

// GOOD: DMA fills buffer in hardware, ISR signals task when done
static uint16_t adc_dma_buffer[4];

void vStartADCScan(void) {
    HAL_ADC_Start_DMA(&hadc1, (uint32_t *)adc_dma_buffer, 4);
}

void HAL_ADC_ConvCpltCallback(ADC_HandleTypeDef *hadc) {
    BaseType_t xWoken = pdFALSE;
    vTaskNotifyGiveFromISR(xAdcTaskHandle, &xWoken);
    portYIELD_FROM_ISR(xWoken);
}
```

#### When to Keep CPU-Driven Transfers

- Single-byte control registers or configuration writes (DMA setup overhead not justified)
- MCUs without a DMA controller (e.g. some Cortex-M0 parts)
- All DMA channels already allocated to higher-priority peripherals

---

## 6. Synchronization Primitives

### When to Use What

| Primitive | Use Case | Notes |
|-----------|----------|-------|
| **Task Notification** | Unblocking a single known task | Fastest, zero RAM overhead. Replace binary semaphores with these. |
| **Queue** | Passing data between tasks or ISR-to-task | Copies data. Size queues for worst-case burst. |
| **Mutex** | Mutual exclusion (shared resource) | Has priority inheritance. Never use in ISRs. |
| **Binary Semaphore** | ISR-to-task signaling (legacy) | Prefer task notifications instead. No priority inheritance -- never use for mutual exclusion. |
| **Counting Semaphore** | Resource pools, event counting | When multiple identical resources exist. |
| **Event Group** | Waiting for multiple conditions | `xEventGroupWaitBits` for AND/OR of flags. |
| **Stream/Message Buffer** | Variable-length byte/message streams | Single-reader, single-writer only. Ideal for inter-core communication. |

### Task Notifications Over Semaphores

```c
// BAD: Binary semaphore for simple ISR-to-task signaling
static SemaphoreHandle_t xSemaphore;

void ISR_Handler(void) {
    BaseType_t xWoken = pdFALSE;
    xSemaphoreGiveFromISR(xSemaphore, &xWoken);
    portYIELD_FROM_ISR(xWoken);
}

void vTask(void *pvParameters) {
    while (1) {
        xSemaphoreTake(xSemaphore, portMAX_DELAY);
        do_work();
    }
}

// GOOD: Task notification -- faster, no RAM allocation
void ISR_Handler(void) {
    BaseType_t xWoken = pdFALSE;
    vTaskNotifyGiveFromISR(xTaskHandle, &xWoken);
    portYIELD_FROM_ISR(xWoken);
}

void vTask(void *pvParameters) {
    while (1) {
        ulTaskNotifyTake(pdTRUE, portMAX_DELAY);
        do_work();
    }
}
```

### Mutex for Shared Resources (Not Binary Semaphore)

```c
// BAD: Binary semaphore for mutual exclusion -- no priority inheritance
static SemaphoreHandle_t xBinSem = xSemaphoreCreateBinary();

// GOOD: Mutex -- supports priority inheritance, prevents priority inversion
static SemaphoreHandle_t xMutex = xSemaphoreCreateMutex();

void vAccessSharedResource(void) {
    if (xSemaphoreTake(xMutex, pdMS_TO_TICKS(100)) == pdPASS) {
        update_shared_state();
        xSemaphoreGive(xMutex);
    } else {
        handle_timeout();
    }
}
```

---

## 7. State Machines

State machines are the backbone of embedded control logic. They must be explicit, exhaustive, and safe. For complex systems, consider the Active Object pattern (Section 4) as an evolution of monolithic FSMs.

### Explicit State Enum with Default Handler

```c
typedef enum {
    STATE_IDLE,
    STATE_SAMPLING,
    STATE_PROCESSING,
    STATE_TRANSMITTING,
    STATE_ERROR,
} SystemState_t;

static SystemState_t state = STATE_IDLE;

void vControlTask(void *pvParameters) {
    while (1) {
        switch (state) {
        case STATE_IDLE:
            if (start_requested()) state = STATE_SAMPLING;
            break;
        case STATE_SAMPLING:
            if (sample_complete()) state = STATE_PROCESSING;
            break;
        case STATE_PROCESSING:
            if (process_complete()) state = STATE_TRANSMITTING;
            if (process_failed())   state = STATE_ERROR;
            break;
        case STATE_TRANSMITTING:
            if (transmit_complete()) state = STATE_IDLE;
            break;
        case STATE_ERROR:
            log_error();
            state = STATE_IDLE; // Recovery transition
            break;
        default:
            // Corrupted state -- recover to known safe state
            configASSERT(0); // Trap in debug
            state = STATE_ERROR;
            break;
        }

        ulTaskNotifyTake(pdTRUE, pdMS_TO_TICKS(CONTROL_PERIOD_MS));
    }
}
```

### Bitwise vs. Logical Operators for Register Masks

```c
// BAD: Logical operator -- evaluates to true/false, not a bitmask
if (status_reg && ERROR_MASK) {  // Always true if status_reg != 0!
    handle_error();
}

// GOOD: Bitwise AND tests specific bits
if (status_reg & ERROR_MASK) {
    handle_error();
}
```

---

## 8. Timing and Tick Safety

### Tick Overflow-Safe Comparisons

The RTOS tick counter wraps around. Use interval subtraction, which is safe due to unsigned integer arithmetic.

```c
// BAD: Direct comparison -- breaks on tick rollover
TickType_t deadline = xTaskGetTickCount() + pdMS_TO_TICKS(500);
while (xTaskGetTickCount() < deadline) {
    // If tick rolls over, this exits immediately
}

// GOOD: Interval subtraction -- safe from rollover
TickType_t start = xTaskGetTickCount();
while ((xTaskGetTickCount() - start) < pdMS_TO_TICKS(500)) {
    vTaskDelay(1); // Yield between checks
}

// BEST: Use vTaskDelayUntil for periodic tasks
void vPeriodicTask(void *pvParameters) {
    TickType_t xLastWakeTime = xTaskGetTickCount();
    while (1) {
        vTaskDelayUntil(&xLastWakeTime, pdMS_TO_TICKS(PERIOD_MS));
        do_periodic_work();
    }
}
```

### Bounded Hardware Waits

Never spin indefinitely waiting for hardware. Always use a timeout.

```c
// BAD: Infinite wait if hardware hangs
while (!(SPI->SR & SPI_SR_TXE)) { /* spin forever */ }

// GOOD: Bounded wait with timeout
uint32_t timeout = 10000;
while (!(SPI->SR & SPI_SR_TXE)) {
    if (--timeout == 0) {
        handle_spi_timeout();
        return ERROR_TIMEOUT;
    }
}
```

---

## 9. System Reliability & Power Management

### Task Watchdog Supervisor

Abstract the physical hardware watchdog behind a high-priority software manager task. Critical threads must periodically check in; if any thread deadlocks on a mutex, the supervisor intentionally starves the hardware watchdog to force a safe system reset.

```c
#define NUM_MONITORED_TASKS  3
#define WDT_CHECKIN_PERIOD   pdMS_TO_TICKS(500)
#define WDT_SUPERVISOR_PERIOD pdMS_TO_TICKS(250)

static volatile uint32_t checkin_flags = 0;

// Each monitored task checks in periodically
void vTask_CheckIn(uint32_t task_id) {
    taskENTER_CRITICAL();
    checkin_flags |= (1UL << task_id);
    taskEXIT_CRITICAL();
}

// Supervisor: highest priority, feeds HW watchdog only if all tasks checked in
void vWatchdogSupervisor(void *pvParameters) {
    const uint32_t all_flags = (1UL << NUM_MONITORED_TASKS) - 1;
    while (1) {
        vTaskDelay(WDT_SUPERVISOR_PERIOD);

        taskENTER_CRITICAL();
        uint32_t flags = checkin_flags;
        checkin_flags = 0;  // Reset for next period
        taskEXIT_CRITICAL();

        if (flags == all_flags) {
            HAL_IWDG_Refresh(&hiwdg);  // All tasks alive -- feed HW WDT
        }
        // else: deliberately starve HW WDT -> system reset
    }
}
```

### Tickless Idle (Low-Power)

For low-power constraints, implement Tickless Idle to dynamically suppress the periodic RTOS tick, allowing the CPU to remain in deep sleep for calculated durations.

```c
// FreeRTOSConfig.h
#define configUSE_TICKLESS_IDLE          2  // Custom tickless implementation
#define configEXPECTED_IDLE_TIME_BEFORE_SLEEP  2  // Min ticks before sleeping

// portSUPPRESS_TICKS_AND_SLEEP implementation (port-specific)
void vPortSuppressTicksAndSleep(TickType_t xExpectedIdleTime) {
    // 1. Stop SysTick
    // 2. Configure low-power timer (LPTIM/RTC) for xExpectedIdleTime ticks
    // 3. Enter STOP/STANDBY mode
    // 4. On wake: compensate tick count, restart SysTick
    uint32_t ulCompleteTickPeriods = calculate_elapsed_ticks();
    vTaskStepTick(ulCompleteTickPeriods);
}
```

---

## 10. Advanced Telemetry & Crash Persistence

### Zero-Overhead Assertions

Redefine `configASSERT()` to capture the Program Counter (PC) and Link Register (LR) via compiler intrinsics instead of storing massive `__FILE__` ASCII strings, shifting string resolution to the host PC.

```c
// BAD: Default configASSERT stores __FILE__ strings -- wastes flash
#define configASSERT(x) if (!(x)) { printf("%s:%d\n", __FILE__, __LINE__); while(1); }

// GOOD: Capture PC/LR -- resolve file:line on host via addr2line
typedef struct {
    uint32_t pc;
    uint32_t lr;
    uint32_t magic;
} AssertInfo_t;

static AssertInfo_t __attribute__((section(".noinit"))) assert_info;

#define configASSERT(x) do { \
    if (!(x)) { \
        assert_info.pc = (uint32_t)__builtin_return_address(0); \
        assert_info.lr = (uint32_t)__builtin_return_address(1); \
        assert_info.magic = 0xDEADC0DE; \
        NVIC_SystemReset(); \
    } \
} while(0)

// Host-side: arm-none-eabi-addr2line -e firmware.elf 0x0800ABCD
```

### Crash Context Persistence (.noinit Region)

Carve out a `.noinit` (NOLOAD) memory region in the SRAM linker script, protected by a "magic number", to persist crash logs, fault registers, and thread states across watchdog resets.

```c
// Linker script addition:
// .noinit (NOLOAD) : { *(.noinit) } > RAM

typedef struct {
    uint32_t magic;          // 0xCRASH001 if valid
    uint32_t reset_reason;
    uint32_t fault_pc;
    uint32_t fault_lr;
    uint32_t cfsr;           // Configurable Fault Status Register
    uint32_t hfsr;           // HardFault Status Register
    char     task_name[16];
    uint32_t uptime_ms;
} CrashLog_t;

static CrashLog_t __attribute__((section(".noinit"))) crash_log;

// On boot: check for previous crash
void vCheckCrashLog(void) {
    if (crash_log.magic == 0xCRA50001) {
        // Transmit crash_log over UART/telemetry before clearing
        report_crash(&crash_log);
        crash_log.magic = 0;
    }
}

// In HardFault handler: populate crash_log
void HardFault_Handler(void) {
    crash_log.magic  = 0xCRA50001;
    crash_log.cfsr   = SCB->CFSR;
    crash_log.hfsr   = SCB->HFSR;
    crash_log.fault_pc = __get_PSP();  // Approximate
    // ... fill remaining fields ...
    NVIC_SystemReset();
}
```

### Deferred Binary Logging (TRICE / RTT)

Remove ASCII string formatting from the target entirely. Use tools like TRICE to compile format strings into numeric IDs, flushing highly compressed raw binary payloads over UART or RTT to eliminate CPU blocking and timing "Heisenbugs".

```c
// BAD: printf in real-time path -- 100+ us per call, alters timing
void vSensorTask(void *pvParameters) {
    while (1) {
        int32_t val = read_sensor();
        printf("Sensor: %d mV at tick %lu\n", val, xTaskGetTickCount());
        // ^ blocking UART, mutexes, heap allocation for format buffer
    }
}

// GOOD: TRICE -- format string compiled to ID, ~100 ns per call
// Host resolves ID -> format string from the ELF
#include "trice.h"

void vSensorTask(void *pvParameters) {
    while (1) {
        int32_t val = read_sensor();
        TRICE32("Sensor: %d mV at tick %u\n", val, xTaskGetTickCount());
        // ^ writes 8-12 bytes to ring buffer, no formatting on target
    }
}
```

---

## 11. Defensive Programming

### Assertions for Development

```c
// Use configASSERT liberally during development
void vEnqueueData(QueueHandle_t queue, const void *data) {
    configASSERT(queue != NULL);
    configASSERT(data != NULL);

    BaseType_t result = xQueueSend(queue, data, pdMS_TO_TICKS(100));
    configASSERT(result == pdPASS); // Catch queue-full during dev
}
```

### Return Value Checking

```c
// BAD: Ignoring return values
xQueueSend(xQueue, &data, 0);
HAL_SPI_Transmit(&hspi1, buf, len, 100);

// GOOD: Check and handle
if (xQueueSend(xQueue, &data, pdMS_TO_TICKS(10)) != pdPASS) {
    increment_error_counter(ERR_QUEUE_FULL);
}

if (HAL_SPI_Transmit(&hspi1, buf, len, 100) != HAL_OK) {
    handle_spi_error();
}
```

### File-Local Scope

```c
// BAD: Global linkage for a helper -- pollutes symbol table
void process_sample(int32_t raw) { /* ... */ }

// GOOD: static restricts to this translation unit
static void process_sample(int32_t raw) { /* ... */ }
```

---

## Quick Reference

| Pattern | Rule |
|---------|------|
| Architecture | OSAL for portability. Config tables for reusable drivers. Opaque pointers for encapsulation. |
| Off-Target Testing | Mock hardware via CMock/Unity/fff. Test logic on host PC. |
| Memory | All static. No malloc/free at runtime. Use `xTaskCreateStatic`. |
| Stack Protection | MPU/PSPLIM for safety-critical. Software watermarks for development only. |
| Multicore (SMP) | Pin tasks to cores via `vTaskCoreAffinitySet`. Stream Buffers for cross-core data. |
| Schedulability | RMS analysis: sum(WCET/Period) <= bound. Shorter period = higher priority. |
| Active Objects | Private state + message queue. No shared mutexes. |
| ISR | Short, non-blocking, use `...FromISR()`, always `portYIELD_FROM_ISR`. |
| Tasks | Event-driven. Never poll. Never use arbitrary delays for sync. |
| Sync | Task notifications > semaphores. Mutexes for exclusion (never binary sems). |
| Registers | Always `volatile`. Protect read-modify-write with critical sections. |
| State machines | Explicit enum, exhaustive switch, always handle `default`. |
| Timing | Interval subtraction for tick math. Bounded waits on hardware. |
| Structs | Order by size. Verify with `_Static_assert`. |
| DMA | Prefer DMA for bulk transfers. CPU-driven only for single-byte ops or when DMA unavailable. |
| Watchdog | Software supervisor task. All critical tasks check in. Starve HW WDT on failure. |
| Power | Tickless Idle for low-power. Suppress SysTick during deep sleep. |
| Assertions | Zero-overhead: capture PC/LR, not `__FILE__`. Resolve on host. |
| Crash Logs | `.noinit` SRAM region with magic number. Persist across resets. |
| Logging | Binary logging (TRICE/RTT). No printf in real-time paths. |
| Scope | `static` on file-local functions. `const` on read-only data. |
