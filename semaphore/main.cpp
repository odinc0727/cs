#include <barrier>
#include <latch>
#include <print>
#include <thread>
#include <vector>

int main() {
        std::vector<std::jthread> workers;
        std::latch                done{3};
        std::barrier              checkpoint{3};

        for (int i = 0; i < 3; ++i) {
                workers.emplace_back([&, i] {
                        std::println("线程 {} 完成阶段 1", i);

                        checkpoint.arrive_and_wait();

                        std::println("线程 {} 完成阶段 2", i);

                        done.count_down();
                });
        }

        done.wait();
        std::println("所有线程执行完成");
}
