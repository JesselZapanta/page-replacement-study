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

static pr_frame_t *free_frame(pr_state_t *state)
{
    for (size_t i = 0; i < state->capacity; ++i) {
        if (!state->frames[i].occupied) {
            return &state->frames[i];
        }
    }
    return NULL;
}

static void lru_reference(pr_state_t *state, long page)
{
    pr_frame_t *frame = find_frame(state, page);
    if (frame) {
        ++state->hits;
        frame->last_used = ++state->tick;
        return;
    }

    ++state->faults;
    frame = free_frame(state);
    if (!frame) {
        frame = state->frames;
        for (size_t i = 1; i < state->capacity; ++i) {
            if (state->frames[i].last_used < frame->last_used) {
                frame = &state->frames[i];
            }
        }
    }

    frame->occupied = true;
    frame->page_id = page;
    frame->insertion_seq = ++state->tick;
    frame->last_used = state->tick;
    frame->referenced = true;
}

const pr_algorithm_t pr_lru_algorithm = {"lru", lru_reference};
