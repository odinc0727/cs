#include <cuda_runtime.h>

#include <cstdio>

__global__ void hello() {
        printf("Hello CUDA, thread %d\n", threadIdx.x);
}

__global__ void add(const int* a, const int* b, int* c, int n) {
        int i = blockIdx.x * blockDim.x + threadIdx.x;
        if (i < n) {
                c[i] = a[i] + b[i];
        }
}

int main() {
        printf("Hello?\n");

        int n = 1000;

        int* a = new int[n];
        int* b = new int[n];
        int* c = new int[n];

        for (int i = 0; i < n; i++) {
                a[i] = i;
                b[i] = i * 2;
        }

        int* da;
        int* db;
        int* dc;

        cudaMalloc(&da, n * sizeof(int));
        cudaMalloc(&db, n * sizeof(int));
        cudaMalloc(&dc, n * sizeof(int));

        cudaMemcpy(da, a, n * sizeof(int), cudaMemcpyHostToDevice);
        cudaMemcpy(db, b, n * sizeof(int), cudaMemcpyHostToDevice);

        int blockSize = 256;
        int gridSize  = (n + blockSize - 1) / blockSize;

        add<<<gridSize, blockSize>>>(da, db, dc, n);

        cudaDeviceSynchronize();

        cudaMemcpy(c, dc, n * sizeof(int), cudaMemcpyDeviceToHost);

        for (int i = 0; i < 10; i++) {
                printf("%d + %d = %d\n", a[i], b[i], c[i]);
        }

        cudaFree(da);
        cudaFree(db);
        cudaFree(dc);

        delete[] a;
        delete[] b;
        delete[] c;
}
