#include "page_replacement.h"

#include <errno.h>
#include <limits.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

enum {
    EXIT_USAGE = 2,
    EXIT_INPUT = 3,
    EXIT_SIMULATION = 4,
    EXIT_OUTPUT = 5
};

static void usage(FILE *out, const char *prog)
{
    fprintf(out, "Usage: %s --algorithm NAME --frames N --trace FILE [options]\n", prog);
    fprintf(out, "\nOptions:\n");
    fprintf(out, "  --algorithm NAME   one of: fifo, lru, clock\n");
    fprintf(out, "  --frames N         logical frame capacity (1..%d)\n", PR_MAX_FRAMES);
    fprintf(out, "  --trace FILE       trace file: one non-negative page id per line\n");
    fprintf(out, "  --run-id ID        label copied into the result record\n");
    fprintf(out, "  --output FILE      write JSON here instead of stdout\n");
    fprintf(out, "  -h, --help         show this help\n");
    fprintf(out, "\nExits: 0 ok, 2 bad arguments, 3 bad input, 4 simulation error, 5 output error.\n");
}

static int bad_arg(const char *message)
{
    fprintf(stderr, "error: %s (use --help)\n", message);
    return EXIT_USAGE;
}

int main(int argc, char **argv)
{
    const char *algorithm_name = NULL;
    const char *trace_path = NULL;
    const char *run_id = "unassigned";
    const char *output_path = NULL;
    long frames = 0;

    for (int i = 1; i < argc; ++i) {
        const char *arg = argv[i];
        if (strcmp(arg, "-h") == 0 || strcmp(arg, "--help") == 0) {
            usage(stdout, argv[0]);
            return 0;
        }
        if (strcmp(arg, "--algorithm") == 0 || strcmp(arg, "--frames") == 0 ||
            strcmp(arg, "--trace") == 0 || strcmp(arg, "--run-id") == 0 ||
            strcmp(arg, "--output") == 0) {
            if (++i >= argc) {
                return bad_arg("missing value for option");
            }
            if (strcmp(arg, "--algorithm") == 0) {
                algorithm_name = argv[i];
            } else if (strcmp(arg, "--frames") == 0) {
                char *end = NULL;
                errno = 0;
                frames = strtol(argv[i], &end, 10);
                if (errno != 0 || end == argv[i] || *end != '\0' || frames < 1 ||
                    frames > PR_MAX_FRAMES) {
                    return bad_arg("frames must be an integer between 1 and PR_MAX_FRAMES");
                }
            } else if (strcmp(arg, "--trace") == 0) {
                trace_path = argv[i];
            } else if (strcmp(arg, "--run-id") == 0) {
                run_id = argv[i];
            } else {
                output_path = argv[i];
            }
            continue;
        }
        return bad_arg("unknown argument");
    }

    if (!algorithm_name || !trace_path || frames == 0) {
        return bad_arg("--algorithm, --frames and --trace are required");
    }

    const pr_algorithm_t *algorithm = pr_algorithm_find(algorithm_name);
    if (!algorithm) {
        return bad_arg("unknown algorithm name");
    }

    char err[512];
    long *refs = NULL;
    size_t count = 0;
    if (pr_trace_read(trace_path, &refs, &count, err, sizeof(err)) != 0) {
        fprintf(stderr, "error: %s\n", err);
        return EXIT_INPUT;
    }

    pr_state_t state;
    uint64_t elapsed_ns = 0;
    if (pr_simulate(algorithm, refs, count, (size_t)frames, &state, &elapsed_ns,
                    err, sizeof(err)) != 0) {
        fprintf(stderr, "error: %s\n", err);
        free(refs);
        return EXIT_SIMULATION;
    }

    FILE *out = stdout;
    if (output_path) {
        out = fopen(output_path, "w");
        if (!out) {
            fprintf(stderr, "error: cannot open output '%s': %s\n", output_path, strerror(errno));
            pr_state_destroy(&state);
            free(refs);
            return EXIT_OUTPUT;
        }
    }

    int status = pr_write_result_json(out, run_id, algorithm, (size_t)frames,
                                      trace_path, count, &state, elapsed_ns);
    if (status != 0) {
        fprintf(stderr, "error: failed to write result record\n");
        status = EXIT_OUTPUT;
    }

    if (out != stdout) {
        fclose(out);
    }
    pr_state_destroy(&state);
    free(refs);
    return status;
}
