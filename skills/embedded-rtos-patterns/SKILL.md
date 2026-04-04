---
name: embedded-rtos-patterns
description: Bare-metal C patterns, ISR design, memory-mapped registers, FreeRTOS/Zephyr task architecture, queues, semaphores, and timing. Use when writing, reviewing, or designing embedded firmware and RTOS applications.
---

# Embedded & RTOS Patterns

Patterns and best practices for bare-metal C, interrupt-driven firmware, and RTOS-based embedded systems (FreeRTOS, Zephyr). Covers memory allocation, ISR design, task architecture, synchronization, hardware interaction, and deterministic timing.

## When to Use

- Writing or reviewing embedded C/C++ firmware
- Designing FreeRTOS or Zephyr task architectures
- Implementing ISR handlers and deferred processing
- Working with memory-mapped registers and peripherals
- Debugging timing, starvation, or priority inversion issues
- Structuring producer-consumer or sensor-processing pipelines

### When NOT to Use

- General-purpose application development (use `cpp-coding-standards` or `rust-patterns`)
- Linux userspace applications (embedded patterns assume bare-metal or RTOS constraints)

## How It Works

This skill provides concrete patterns organized by domain: static memory, ISR design, RTOS task architecture, synchronization primitives, hardware register access, state machines, and timing. Each pattern includes a rationale, a BAD/GOOD code example, and guidance on when to apply it.

---

## 1. Static Memory Allocation

All memory must be statically allocated at compile time. Dynamic allocation (`malloc`, `free`, `new`, `delete`, `pvPortMalloc`, `vPortFree`) causes fragmentation and non-deterministic behavior and introduces instability in embedded systems.

### Static Buffers

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
    // Use static buffers directly
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

---

## 2. ISR Design Patterns

ISRs must be short, non-blocking, and defer all heavy work to tasks. The ISR captures the event and hands it off.

### Deferred Processing (ISR-to-Task Handoff)

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

---

## 3. RTOS Task Architecture

### Task Chaining (Priority-Based Pipeline)

Assign strictly descending priorities so each stage completes before the next begins. The higher-priority task **must block** after handing off data.

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
        xQueueReceive(xRawQueue, &sample, portMAX_DELAY); // Block until data
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

// Development: Check high water mark
void vWorkerTask(void *pvParameters) {
    while (1) {
        // ... work ...
        #if configCHECK_FOR_STACK_OVERFLOW
        UBaseType_t hwm = uxTaskGetStackHighWaterMark(NULL);
        configASSERT(hwm > 32); // At least 32 words headroom
        #endif
    }
}
```

---

## 4. Synchronization Primitives

### When to Use What

| Primitive | Use Case | Notes |
|-----------|----------|-------|
| **Task Notification** | Unblocking a single known task | Fastest, zero RAM overhead. Replace binary semaphores with these. |
| **Queue** | Passing data between tasks or ISR-to-task | Copies data. Size queues for worst-case burst. |
| **Mutex** | Mutual exclusion (shared resource) | Has priority inheritance. Never use in ISRs. |
| **Binary Semaphore** | ISR-to-task signaling (legacy) | Prefer task notifications instead. No priority inheritance -- never use for mutual exclusion. |
| **Counting Semaphore** | Resource pools, event counting | When multiple identical resources exist. |
| **Event Group** | Waiting for multiple conditions | `xEventGroupWaitBits` for AND/OR of flags. |
| **Stream/Message Buffer** | Variable-length byte/message streams | Single-reader, single-writer only. |

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
        // Critical resource access
        update_shared_state();
        xSemaphoreGive(xMutex);
    } else {
        handle_timeout();
    }
}
```

---

## 5. Hardware Register Access

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

---

## 6. State Machines

State machines are the backbone of embedded control logic. They must be explicit, exhaustive, and safe.

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

## 7. Timing and Tick Safety

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
        // Automatically handles tick overflow
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

## 8. Struct Layout for Queues and DMA

Order struct members by size (largest first) to minimize padding. This matters when structs are copied through queues or DMA'd over a bus.

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

## 9. DMA Over CPU-Driven Peripheral Access

Prefer DMA for bulk data transfers (SPI, UART, I2C, ADC scan sequences, display framebuffers). DMA frees the CPU to run other tasks or sleep, reducing power consumption and improving throughput.

> **Note:** Not all MCUs have DMA controllers, and available DMA channels may be limited. Treat this as a strong recommendation, not a universal rule. Verify DMA availability for your target before refactoring.

### SPI Transfer

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

### ADC Scan Sequence

```c
// BAD: CPU polls each channel sequentially
uint16_t adc_values[4];
for (int ch = 0; ch < 4; ch++) {
    HAL_ADC_Start(&hadc1);
    HAL_ADC_PollForConversion(&hadc1, 100); // Blocks per channel
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

### When to Keep CPU-Driven Transfers

- Single-byte control registers or configuration writes (DMA setup overhead not justified)
- MCUs without a DMA controller (e.g. some Cortex-M0 parts)
- All DMA channels already allocated to higher-priority peripherals

---

## 10. Defensive Programming

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
| Memory | All static. No malloc/free at runtime. |
| ISR | Short, non-blocking, use `...FromISR()`, always `portYIELD_FROM_ISR`. |
| Tasks | Event-driven. Never poll. Never use arbitrary delays for sync. |
| Sync | Task notifications > semaphores. Mutexes for exclusion (never binary sems). |
| Registers | Always `volatile`. Protect read-modify-write with critical sections. |
| State machines | Explicit enum, exhaustive switch, always handle `default`. |
| Timing | Interval subtraction for tick math. Bounded waits on hardware. |
| Structs | Order by size. Verify with `_Static_assert`. |
| DMA | Prefer DMA for bulk transfers. CPU-driven only for single-byte ops or when DMA unavailable. |
| Scope | `static` on file-local functions. `const` on read-only data. |
| Assertions | `configASSERT()` liberally in development. Check all return values. |
