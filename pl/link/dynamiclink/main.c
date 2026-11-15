#include <stdio.h>

#ifdef _WIN32
#include <windows.h>
#else
#include <dlfcn.h>
#endif

typedef int (*AddFunc)(int, int);

int main(void) {
#ifdef _WIN32
        HMODULE lib = LoadLibraryA("./math.dll");

        if (!lib) {
                fprintf(stderr, "Failed to load DLL\n");
                return 1;
        }

        AddFunc add = (AddFunc)GetProcAddress(lib, "add");
#else
#ifdef __APPLE__
        const char* path = "./libmath.dylib";
#else
        const char* path = "./libmath.so";
#endif

        void* lib = dlopen(path, RTLD_NOW);

        if (!lib) {
                fprintf(stderr, "%s\n", dlerror());
                return 1;
        }

        AddFunc add = (AddFunc)dlsym(lib, "add");
#endif

        if (!add) {
                fprintf(stderr, "Failed to find add\n");
#ifdef _WIN32
                FreeLibrary(lib);
#else
                dlclose(lib);
#endif
                return 1;
        }

        printf("%d\n", add(10, 20));

#ifdef _WIN32
        FreeLibrary(lib);
#else
        dlclose(lib);
#endif

        return 0;
}
