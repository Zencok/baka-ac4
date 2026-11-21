/* Android ARM64 validation runner for compatible external decoder ABIs.
 * External shared libraries and recordings are local inputs, never linked into
 * the Rust decoder or distributed by this project.
 * Exit 0: nonzero PCM; 1: decoder error/silence; 2: harness/input failure.
 */
#include <dlfcn.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>

int main(int argc, char **argv) {
    if (argc != 4) {
        fprintf(stderr, "usage: reference_probe library.so packets.bin output.s16le\n");
        return 2;
    }
    void *library = dlopen(argv[1], RTLD_NOW);
    if (!library) { fprintf(stderr, "dlopen: %s\n", dlerror()); return 2; }
    int (*open_decoder)(void *, bool) = dlsym(library, "_ZN13DaaAc4Decoder4openEb");
    int (*decode)(void *, char *, unsigned, char *, int, void *) =
        dlsym(library, "_ZN13DaaAc4Decoder6decodeEPcjS0_iPj");
    if (!decode) decode = dlsym(library, "_ZN13DaaAc4Decoder6decodeEPcjS0_iPm");
    void (*close_decoder)(void *) = dlsym(library, "_ZN13DaaAc4DecoderD1Ev");
    int (*channels)(void *) = dlsym(library, "_ZN13DaaAc4Decoder21getOutputChannelCountEv");
    int (*rate)(void *) = dlsym(library, "_ZN13DaaAc4Decoder13getSampleRateEv");
    void *vtable = dlsym(library, "_ZTV13DaaAc4Decoder");
    if (!open_decoder || !decode || !close_decoder || !channels || !rate || !vtable) {
        fprintf(stderr, "unavailable compatible decoder ABI\n"); return 2;
    }
    void *object = calloc(1, 256);
    char *input = malloc(131072);
    int16_t *output = calloc(1, 1048576);
    if (!object || !input || !output) return 2;
    *(void **)object = (char *)vtable + 16;
    int result = open_decoder(object, false);
    if (result) { fprintf(stderr, "decoder open failed: %d\n", result); return 1; }
    FILE *source = fopen(argv[2], "rb"), *dest = fopen(argv[3], "wbx");
    if (!source || !dest) return 2;
    uint64_t frames = 0, bytes = 0;
    unsigned peak = 0;
    for (;;) {
        unsigned char header[4];
        size_t got = fread(header, 1, 4, source);
        if (got == 0 && !ferror(source)) break;
        if (got != 4 || frames >= 1000000) return 2;
        unsigned length = ((unsigned)header[0] << 24) | ((unsigned)header[1] << 16)
            | ((unsigned)header[2] << 8) | header[3];
        if (length == 0 || length > 131072 || fread(input, 1, length, source) != length) return 2;
        // 64-bit storage accommodates either ABI's consumed-byte pointer.
        uint64_t consumed = 0;
        int count = decode(object, input, length, (char *)output, 1048576, &consumed);
        if (count < 0 || consumed != length || count > 1048576 || count % 4) {
            fprintf(stderr, "decode frame %llu: result=%d consumed=%llu\n",
                (unsigned long long)frames, count, (unsigned long long)consumed);
            result = 1; break;
        }
        if (channels(object) != 2 || rate(object) != 48000) {
            fprintf(stderr, "unexpected reference output format\n"); return 2;
        }
        for (int i = 0; i < count / 2; i++) {
            int sample = output[i];
            unsigned magnitude = sample < 0 ? (unsigned)-sample : (unsigned)sample;
            if (magnitude > peak) peak = magnitude;
        }
        if (fwrite(output, 1, (size_t)count, dest) != (size_t)count) return 2;
        frames++; bytes += (unsigned)count;
    }
    if (fclose(source) || fclose(dest) || frames == 0) return 2;
    close_decoder(object); free(object); free(input); free(output); dlclose(library);
    printf("{\"frames\":%llu,\"pcm_bytes\":%llu,\"channels\":2,\"sample_rate\":48000,\"peak\":%.9f,\"signal\":\"%s\"}\n",
        (unsigned long long)frames, (unsigned long long)bytes, peak / 32768.0,
        peak ? "nonzero" : "silence");
    return result ? result : (peak ? 0 : 1);
}
