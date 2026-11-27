#ifndef PAGE_REPLACEMENT_H
#define PAGE_REPLACEMENT_H

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#include <stdio.h>

#define PR_MAX_FRAMES 4096

typedef struct {
    long page_id;
    uint64_t insertion_seq;
    uint64_t last_used;
    bool referenced;
    bool occupied;
} pr_frame_t;

typedef struct {
    pr_frame_t *frames;
    size_t capacity;
    size_t hand;
    uint64_t tick;
    uint64_t hits;
    uint64_t faults;
} pr_state_t;

typedef void (*pr_policy_fn)(pr_state_t *state, long page_id);

typedef struct {
    const char *name;
    pr_policy_fn reference;
} pr_algorithm_t;

extern const pr_algorithm_t pr_fifo_algorithm;
extern const pr_algorithm_t pr_lru_algorithm;
extern const pr_algorithm_t pr_clock_algorithm;

const pr_algorithm_t *const *pr_algorithms(void);
const pr_algorithm_t *pr_algorithm_find(const char *name);

/* Reads one non-negative page id per line; blanks and #-comments ignored. */
int pr_trace_read(const char *path, long **refs, size_t *count,
                  char *err, size_t err_size);

int pr_state_init(pr_state_t *state, size_t capacity, char *err, size_t err_size);
void pr_state_destroy(pr_state_t *state);

/* Times only the policy loop: parsing and file I/O are excluded. */
int pr_simulate(const pr_algorithm_t *algo, const long *refs, size_t count,
                size_t capacity, pr_state_t *out, uint64_t *elapsed_ns,
                char *err, size_t err_size);

int pr_write_result_json(FILE *out, const char *run_id,
                         const pr_algorithm_t *algo, size_t capacity,
                         const char *trace_path, size_t trace_count,
                         const pr_state_t *state, uint64_t elapsed_ns);

#endif
