#define _POSIX_C_SOURCE 200809L
#include "page_replacement.h"

#include <ctype.h>
#include <errno.h>
#include <inttypes.h>
#include <limits.h>
#include <stdarg.h>
#include <stdlib.h>
#include <string.h>
#include <sys/types.h>
#include <time.h>

static void set_err(char *err, size_t err_size, const char *fmt, ...)
{
    va_list args;
    va_start(args, fmt);
    if (err && err_size > 0) {
        vsnprintf(err, err_size, fmt, args);
    }
    va_end(args);
}

const pr_algorithm_t *const *pr_algorithms(void)
{
    static const pr_algorithm_t *const table[] = {
        &pr_fifo_algorithm,
        &pr_lru_algorithm,
        &pr_clock_algorithm,
        NULL
    };
    return table;
}

const pr_algorithm_t *pr_algorithm_find(const char *name)
{
    if (!name) {
        return NULL;
    }
    for (const pr_algorithm_t *const *it = pr_algorithms(); *it; ++it) {
        if (strcmp((*it)->name, name) == 0) {
            return *it;
        }
    }
    return NULL;
}

int pr_trace_read(const char *path, long **refs, size_t *count,
                  char *err, size_t err_size)
{
    FILE *fp = fopen(path, "r");
    if (!fp) {
        set_err(err, err_size, "cannot open trace '%s': %s", path, strerror(errno));
        return -1;
    }

    long *items = NULL;
    size_t n = 0;
    size_t cap = 0;
    char *line = NULL;
    size_t line_cap = 0;
    ssize_t len;
    unsigned long line_no = 0;
    int status = -1;

    while ((len = getline(&line, &line_cap, fp)) != -1) {
        (void)len;
        ++line_no;
        char *p = line;
        while (isspace((unsigned char)*p)) {
            ++p;
        }
        if (*p == '\0' || *p == '#') {
            continue;
        }

        errno = 0;
        char *end = NULL;
        long value = strtol(p, &end, 10);
        if (errno != 0 || end == p) {
            set_err(err, err_size, "malformed trace '%s' at line %lu", path, line_no);
            goto cleanup;
        }
        while (isspace((unsigned char)*end)) {
            ++end;
        }
        if (*end != '\0' || value < 0) {
            set_err(err, err_size, "invalid page id at line %lu of '%s'", line_no, path);
            goto cleanup;
        }

        if (n == cap) {
            size_t new_cap = cap ? cap * 2 : 128;
            long *tmp = realloc(items, new_cap * sizeof(*items));
            if (!tmp) {
                set_err(err, err_size, "out of memory reading trace '%s'", path);
                goto cleanup;
            }
            items = tmp;
            cap = new_cap;
        }
        items[n++] = value;
    }

    if (ferror(fp)) {
        set_err(err, err_size, "error reading trace '%s'", path);
        goto cleanup;
    }

    *refs = items;
    *count = n;
    status = 0;

cleanup:
    if (status != 0) {
        free(items);
    }
    free(line);
    fclose(fp);
    return status;
}

int pr_state_init(pr_state_t *state, size_t capacity, char *err, size_t err_size)
{
    if (capacity == 0 || capacity > PR_MAX_FRAMES) {
        set_err(err, err_size, "frame capacity must be between 1 and %d", PR_MAX_FRAMES);
        return -1;
    }
    state->frames = calloc(capacity, sizeof(*state->frames));
    if (!state->frames) {
        set_err(err, err_size, "out of memory allocating %zu frames", capacity);
        return -1;
    }
    state->capacity = capacity;
    state->hand = 0;
    state->tick = 0;
    state->hits = 0;
    state->faults = 0;
    return 0;
}

void pr_state_destroy(pr_state_t *state)
{
    free(state->frames);
    state->frames = NULL;
    state->capacity = 0;
}

int pr_simulate(const pr_algorithm_t *algo, const long *refs, size_t count,
                size_t capacity, pr_state_t *out, uint64_t *elapsed_ns,
                char *err, size_t err_size)
{
    if (pr_state_init(out, capacity, err, err_size) != 0) {
        return -1;
    }

    struct timespec start;
    struct timespec end;
    clock_gettime(CLOCK_MONOTONIC, &start);
    for (size_t i = 0; i < count; ++i) {
        algo->reference(out, refs[i]);
    }
    clock_gettime(CLOCK_MONOTONIC, &end);

    uint64_t seconds = (uint64_t)(end.tv_sec - start.tv_sec);
    int64_t nanos = (int64_t)end.tv_nsec - (int64_t)start.tv_nsec;
    if (nanos < 0) {
        --seconds;
        nanos += 1000000000LL;
    }
    *elapsed_ns = seconds * 1000000000ULL + (uint64_t)nanos;
    return 0;
}

static void json_string(FILE *out, const char *s)
{
    fputc('"', out);
    for (; s && *s; ++s) {
        unsigned char c = (unsigned char)*s;
        if (c == '"' || c == '\\') {
            fputc('\\', out);
            fputc(c, out);
        } else if (c < 0x20) {
            fprintf(out, "\\u%04x", c);
        } else {
            fputc(c, out);
        }
    }
    fputc('"', out);
}

int pr_write_result_json(FILE *out, const char *run_id,
                         const pr_algorithm_t *algo, size_t capacity,
                         const char *trace_path, size_t trace_count,
                         const pr_state_t *state, uint64_t elapsed_ns)
{
    double rate = trace_count ? 100.0 * (double)state->faults / (double)trace_count : 0.0;
    double throughput = elapsed_ns ? (double)trace_count * 1e9 / (double)elapsed_ns : 0.0;

    fprintf(out, "{");
    fprintf(out, "\"schema_version\":1,");
    fprintf(out, "\"run_id\":");
    json_string(out, run_id);
    fprintf(out, ",\"algorithm\":");
    json_string(out, algo->name);
    fprintf(out, ",\"frames\":%zu", capacity);
    fprintf(out, ",\"trace_path\":");
    json_string(out, trace_path);
    fprintf(out, ",\"total_references\":%zu", trace_count);
    fprintf(out, ",\"hits\":%" PRIu64, state->hits);
    fprintf(out, ",\"simulated_page_faults\":%" PRIu64, state->faults);
    fprintf(out, ",\"page_fault_rate_percent\":%.6f", rate);
    fprintf(out, ",\"algorithm_time_ns\":%" PRIu64, elapsed_ns);
    fprintf(out, ",\"throughput_refs_per_sec\":%.3f", throughput);
    fprintf(out, ",\"status\":\"ok\"}\n");
    return ferror(out) ? -1 : 0;
}
