#include "page_replacement.h"

static pr_frame_t *find_frame(pr_state_t *state, long page)
{
    for (size_t i = 0; i < state->capacity; ++i) {
        if (state->frames[i].occupied && state->frames[i].page_id == page) {
            return &state->frames[i];
        }
    }
    return NULL;
}

static void clock_reference(pr_state_t *state, long page)
{
    pr_frame_t *frame = find_frame(state, page);
    if (frame) {
        ++state->hits;
        frame->referenced = true;
        frame->last_used = ++state->tick;
        return;
    }

    ++state->faults;

    bool has_free = false;
    for (size_t i = 0; i < state->capacity; ++i) {
        if (!state->frames[i].occupied) {
            has_free = true;
            break;
        }
    }

    if (has_free) {
        while (state->frames[state->hand].occupied) {
            state->hand = (state->hand + 1) % state->capacity;
        }
    } else {
        /* Second chance: clear reference bits until an unreferenced frame is found. */
        while (state->frames[state->hand].referenced) {
            state->frames[state->hand].referenced = false;
            state->hand = (state->hand + 1) % state->capacity;
        }
    }

    frame = &state->frames[state->hand];
    state->hand = (state->hand + 1) % state->capacity;

    frame->occupied = true;
    frame->page_id = page;
    frame->referenced = true;
    frame->insertion_seq = ++state->tick;
    frame->last_used = state->tick;
}

const pr_algorithm_t pr_clock_algorithm = {"clock", clock_reference};
