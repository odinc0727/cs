#include <cuda_runtime.h>

#include <algorithm>
#include <cmath>
#include <cstddef>
#include <iostream>
#include <random>
#include <stdexcept>
#include <string>
#include <utility>

#define CUDA_CHECK(expr)                                                                                            \
        do {                                                                                                        \
                const cudaError_t error = (expr);                                                                   \
                if (error != cudaSuccess) {                                                                         \
                        throw std::runtime_error(std::string{"CUDA error: "} + cudaGetErrorString(error) + " at " + \
                                                 __FILE__ + ":" + std::to_string(__LINE__));                        \
                }                                                                                                   \
        } while (false)

template <typename T>
class DeviceBuffer {
       private:
        T* data_           = nullptr;
        std::size_t count_ = 0;

       public:
        DeviceBuffer() = default;

        explicit DeviceBuffer(std::size_t count) : count_(count) {
                if (count_ != 0) {
                        CUDA_CHECK(cudaMalloc(reinterpret_cast<void**>(&data_), count_ * sizeof(T)));
                }
        }

        ~DeviceBuffer() {
                if (data_ != nullptr) {
                        cudaFree(data_);
                }
        }

        DeviceBuffer(const DeviceBuffer&) = delete;

        DeviceBuffer& operator=(const DeviceBuffer&) = delete;

        DeviceBuffer(DeviceBuffer&& other) noexcept
            : data_(std::exchange(other.data_, nullptr)), count_(std::exchange(other.count_, 0)) {}

        DeviceBuffer& operator=(DeviceBuffer&& other) noexcept {
                if (this == &other) {
                        return *this;
                }
                if (data_ != nullptr) {
                        cudaFree(data_);
                }

                data_  = std::exchange(other.data_, nullptr);
                count_ = std::exchange(other.count_, 0);

                return *this;
        }

        T* data() {
                return data_;
        }

        const T* data() const {
                return data_;
        }

        std::size_t size() const {
                return count_;
        }

        std::size_t bytes() const {
                return count_ * sizeof(T);
        }
};

template <typename T>
class PinnedBuffer {
       private:
        T* data_           = nullptr;
        std::size_t count_ = 0;

       public:
        PinnedBuffer() = default;

        explicit PinnedBuffer(std::size_t count) : count_{count} {
                if (count_ != 0) {
                        CUDA_CHECK(cudaMallocHost(reinterpret_cast<void**>(&data_), count_ * sizeof(T)));
                }
        }

        ~PinnedBuffer() {
                if (data_ != nullptr) {
                        cudaFreeHost(data_);
                }
        }

        PinnedBuffer(const PinnedBuffer&) = delete;

        PinnedBuffer& operator=(const PinnedBuffer&) = delete;

        PinnedBuffer(PinnedBuffer&& other) noexcept
            : data_{std::exchange(other.data_, nullptr)}, count_{std::exchange(other.count_, 0)} {}

        PinnedBuffer& operator=(PinnedBuffer&& other) noexcept {
                if (this == &other) {
                        return *this;
                }

                if (data_ != nullptr) {
                        cudaFreeHost(data_);
                }

                data_  = std::exchange(other.data_, nullptr);
                count_ = std::exchange(other.count_, 0);

                return *this;
        }

        T& operator[](std::size_t i) {
                return data_[i];
        }

        const T& operator[](std::size_t i) const {
                return data_[i];
        }

        T* data() {
                return data_;
        }

        const T* data() const {
                return data_;
        }

        std::size_t size() const {
                return count_;
        }

        std::size_t bytes() const {
                return count_ * sizeof(T);
        }
};

class CudaStream {
       private:
        cudaStream_t stream_ = nullptr;

       public:
        CudaStream() {
                CUDA_CHECK(cudaStreamCreate(&stream_));
        }

        ~CudaStream() {
                if (stream_ != nullptr) {
                        cudaStreamDestroy(stream_);
                }
        }

        CudaStream(const CudaStream&) = delete;

        CudaStream& operator=(const CudaStream&) = delete;

        cudaStream_t get() const {
                return stream_;
        }

        void synchronize() const {
                CUDA_CHECK(cudaStreamSynchronize(stream_));
        }
};

class CudaEvent {
       private:
        cudaEvent_t event_ = nullptr;

       public:
        CudaEvent() {
                CUDA_CHECK(cudaEventCreate(&event_));
        }

        ~CudaEvent() {
                if (event_ != nullptr) {
                        cudaEventDestroy(event_);
                }
        }

        CudaEvent(const CudaEvent&) = delete;

        CudaEvent& operator=(const CudaEvent&) = delete;

        void record(cudaStream_t stream) {
                CUDA_CHECK(cudaEventRecord(event_, stream));
        }

        float elapsed_from(const CudaEvent& start) const {
                float milliseconds = 0.0F;

                CUDA_CHECK(cudaEventElapsedTime(&milliseconds, start.event_, event_));

                return milliseconds;
        }
};

template <int Tile>
__global__ void matrix_multiply(const float* a, const float* b, float* c, int m, int k, int n) {
        __shared__ float tile_a[Tile][Tile];
        __shared__ float tile_b[Tile][Tile];

        const int row = static_cast<int>(blockIdx.y) * Tile + static_cast<int>(threadIdx.y);

        const int col = static_cast<int>(blockIdx.x) * Tile + static_cast<int>(threadIdx.x);

        float sum = 0.0F;

        const int tile_count = (k + Tile - 1) / Tile;

        for (int tile = 0; tile < tile_count; ++tile) {
                const int a_col = tile * Tile + static_cast<int>(threadIdx.x);

                const int b_row = tile * Tile + static_cast<int>(threadIdx.y);

                if (row < m && a_col < k) {
                        tile_a[threadIdx.y][threadIdx.x] = a[row * k + a_col];
                } else {
                        tile_a[threadIdx.y][threadIdx.x] = 0.0F;
                }

                if (b_row < k && col < n) {
                        tile_b[threadIdx.y][threadIdx.x] = b[b_row * n + col];
                } else {
                        tile_b[threadIdx.y][threadIdx.x] = 0.0F;
                }

                __syncthreads();

#pragma unroll
                for (int i = 0; i < Tile; ++i) {
                        sum += tile_a[threadIdx.y][i] * tile_b[i][threadIdx.x];
                }

                __syncthreads();
        }

        if (row < m && col < n) {
                c[row * n + col] = sum;
        }
}

template <int Tile>
void launch_matrix_multiply(const float* a, const float* b, float* c, int m, int k, int n, cudaStream_t stream) {
        const dim3 block{static_cast<unsigned int>(Tile), static_cast<unsigned int>(Tile)};

        const dim3 grid{static_cast<unsigned int>((n + Tile - 1) / Tile),
                        static_cast<unsigned int>((m + Tile - 1) / Tile)};

        matrix_multiply<Tile><<<grid, block, 0, stream>>>(a, b, c, m, k, n);

        CUDA_CHECK(cudaGetLastError());
}

void fill_random(PinnedBuffer<float>& buffer, std::mt19937& rng) {
        std::uniform_real_distribution<float> dist{-1.0F, 1.0F};

        for (std::size_t i = 0; i < buffer.size(); ++i) {
                buffer[i] = dist(rng);
        }
}

double validate(const PinnedBuffer<float>& a, const PinnedBuffer<float>& b, const PinnedBuffer<float>& c, int m, int k,
                int n) {
        double max_error = 0.0;

        for (int row = 0; row < m; ++row) {
                for (int col = 0; col < n; ++col) {
                        double expected = 0.0;

                        for (int i = 0; i < k; ++i) {
                                expected += static_cast<double>(a[row * k + i]) * static_cast<double>(b[i * n + col]);
                        }

                        const double actual = static_cast<double>(c[row * n + col]);

                        max_error = std::max(max_error, std::abs(expected - actual));
                }
        }

        return max_error;
}

int main() {
        try {
                int device = 0;

                CUDA_CHECK(cudaGetDevice(&device));

                cudaDeviceProp properties{};

                CUDA_CHECK(cudaGetDeviceProperties(&properties, device));

                std::cout << "GPU: " << properties.name << '\n';

                constexpr int M = 256;
                constexpr int K = 256;
                constexpr int N = 256;

                constexpr int Tile = 16;

                const std::size_t size_a = static_cast<std::size_t>(M) * K;

                const std::size_t size_b = static_cast<std::size_t>(K) * N;

                const std::size_t size_c = static_cast<std::size_t>(M) * N;

                PinnedBuffer<float> host_a{size_a};
                PinnedBuffer<float> host_b{size_b};
                PinnedBuffer<float> host_c{size_c};

                std::mt19937 rng{42};

                fill_random(host_a, rng);
                fill_random(host_b, rng);

                DeviceBuffer<float> device_a{size_a};
                DeviceBuffer<float> device_b{size_b};
                DeviceBuffer<float> device_c{size_c};

                CudaStream stream;

                CUDA_CHECK(cudaMemcpyAsync(device_a.data(), host_a.data(), device_a.bytes(), cudaMemcpyHostToDevice,
                                           stream.get()));

                CUDA_CHECK(cudaMemcpyAsync(device_b.data(), host_b.data(), device_b.bytes(), cudaMemcpyHostToDevice,
                                           stream.get()));

                stream.synchronize();

                launch_matrix_multiply<Tile>(device_a.data(), device_b.data(), device_c.data(), M, K, N, stream.get());

                stream.synchronize();

                CudaEvent start;
                CudaEvent stop;

                start.record(stream.get());

                launch_matrix_multiply<Tile>(device_a.data(), device_b.data(), device_c.data(), M, K, N, stream.get());

                stop.record(stream.get());

                CUDA_CHECK(cudaMemcpyAsync(host_c.data(), device_c.data(), device_c.bytes(), cudaMemcpyDeviceToHost,
                                           stream.get()));

                stream.synchronize();

                const float milliseconds = stop.elapsed_from(start);

                const double operations =
                        2.0 * static_cast<double>(M) * static_cast<double>(K) * static_cast<double>(N);

                const double gflops = operations / (static_cast<double>(milliseconds) * 1e6);

                std::cout << "Matrix: " << M << " x " << K << " * " << K << " x " << N << '\n';

                std::cout << "Block: " << Tile << " x " << Tile << '\n';

                std::cout << "Kernel time: " << milliseconds << " ms\n";

                std::cout << "Performance: " << gflops << " GFLOPS\n";

                std::cout << "Validating...\n";

                const double max_error = validate(host_a, host_b, host_c, M, K, N);

                std::cout << "Max error: " << max_error << '\n';

                if (max_error > 1e-3) {
                        std::cerr << "Validation failed\n";

                        return 1;
                }

                std::cout << "Validation passed\n";

                return 0;
        } catch (const std::exception& e) {
                std::cerr << e.what() << '\n';

                return 1;
        }
}
