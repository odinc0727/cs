// 记录用户每日登录，重复登录不重复计数。
// 统计每日活跃用户数（DAU）。
// 计算指定用户的连续登录天数。
// 计算次日留存率。
// 使用 Redis 事务，保证两份登录 Bitmap 同时更新。
#include <hiredis/hiredis.h>

#include <chrono>
#include <cstddef>
#include <cstdlib>
#include <initializer_list>
#include <iomanip>
#include <iostream>
#include <memory>
#include <sstream>
#include <stdexcept>
#include <vector>

using namespace std::chrono;
using i64 = long long;

struct ContextDeleter {
        void operator()(redisContext* c) const {
                if (c != nullptr) {
                        redisFree(c);
                }
        }
};

struct ReplyDeleter {
        void operator()(redisReply* r) const {
                if (r != nullptr) {
                        freeReplyObject(r);
                }
        }
};

using Reply = std::unique_ptr<redisReply, ReplyDeleter>;

class Redis {
private:
        std::unique_ptr<redisContext, ContextDeleter> context_;

public:
        Redis(const std::string& host, int port) {
                timeval timeout{.tv_sec = 2, .tv_usec = 0};
                context_.reset(redisConnectWithTimeout(host.c_str(), port, timeout));
                if (!context_) {
                        throw std::runtime_error("reidsConnectionWithTimeout returned null");
                }
                if (context_->err) {
                        throw std::runtime_error(context_->errstr);
                }
        }

        Reply command(std::initializer_list<std::string> args) {
                std::vector<const char*> argv;
                std::vector<size_t>      sizes;
                argv.reserve(args.size());
                sizes.reserve(args.size());
                for (const auto& arg : args) {
                        argv.push_back(arg.data());
                        sizes.push_back(arg.size());
                }

                Reply r{static_cast<redisReply*>(
                        redisCommandArgv(context_.get(), static_cast<int>(argv.size()), argv.data(), sizes.data()))};
                if (!r) {
                        throw std::runtime_error(context_->errstr);
                }
                if (r->type == REDIS_REPLY_ERROR) {
                        throw std::runtime_error(r->str ? r->str : "Redis error");
                }
                return r;
        }

        i64 integer(std::initializer_list<std::string> args) {
                Reply r = command(args);
                if (r->type != REDIS_REPLY_INTEGER) {
                        throw std::runtime_error("Expected integer reply");
                }
                return r->integer;
        }
};

// 用户 ID 直接作为每日 Bitmap 的 offset，每个用户再用一个 Bitmap 保存历史登录日期。
//         Key	                             Bit offset	                  用途
// demo:bitmap:v1:dau:2026-10-27	      用户 ID	           统计当天登录人数
// demo:bitmap:v1:login:123	        距离 2026-01-01 的天数       用户 123 的登录历史

static constexpr const char* kPrefix = "demo:bitmap:v1:";
const sys_days               kEpoch{year{2026} / 1 / 1};

sys_days makeDay(int y, unsigned m, unsigned d) {
        const year_month_day ymd{year{y}, month{m}, day{d}};
        if (!ymd.ok()) {
                throw std::invalid_argument("Invalid calendar date");
        }
        return sys_days(ymd);
}

std::string formatDay(sys_days d) {
        const year_month_day ymd{d};
        std::ostringstream   s;
        s << int(ymd.year()) << "-" << std::setfill('0') << std::setw(2) << unsigned(ymd.month()) << "-" << std::setw(2)
          << unsigned(ymd.day());
        return s.str();
}

i64 dayOffset(sys_days d) {
        const auto offset = (d - kEpoch).count();
        if (offset < 0) {
                throw std::invalid_argument("Date is before the bitmap epoch");
        }
        return offset;
}

std::string dailyKey(sys_days d) {
        return std::string{kPrefix} + "dau:" + formatDay(d);
}

std::string historyKey(unsigned userId) {
        return std::string{kPrefix} + "login:" + std::to_string(userId);
}

void recordLogin(Redis& redis, unsigned userId, sys_days date) {
        redis.command({"MULTI"});
        redis.command({"SETBIT", dailyKey(date), std::to_string(userId), "1"});
        redis.command({"SETBIT", historyKey(userId), std::to_string(dayOffset(date)), "1"});
        Reply executed = redis.command({"EXEC"});
        if (executed->type != REDIS_REPLY_ARRAY || executed->elements != 2) {
                throw std::runtime_error("Unexpected EXEC reply");
        }
        for (size_t i = 0; i < executed->elements; ++i) {
                if (executed->element[i]->type == REDIS_REPLY_ERROR) {
                        throw std::runtime_error("SETBIT failed within transaction");
                }
        }
}

i64 dau(Redis& redis, sys_days date) {
        return redis.integer({"BITCOUNT", dailyKey(date)});
}

// streakEnding 每次使用 GETBIT 来验证，可能有大量网络往返。
// 实际可以采用 HASH 记录上一次登录时间和连续天数。
int streakEnding(Redis& redis, unsigned userId, sys_days today) {
        int streak = 0;
        for (i64 offset = dayOffset(today); offset >= 0; offset--) {
                if (redis.integer({"GETBIT", historyKey(userId), std::to_string(offset)}) == 0) {
                        break;
                }
                streak++;
        }
        return streak;
}

struct Retention {
        i64    cohort;
        i64    retained;
        double rate;
};

// nextDayRetention 计算次日留存率
Retention nextDayRetention(Redis& redis, sys_days first, sys_days second) {
        if (second != first + days{1}) {
                throw std::invalid_argument("Expected consecutive days");
        }
        const i64  cohort = dau(redis, first);
        const auto unique = duration_cast<nanoseconds>(steady_clock::now().time_since_epoch()).count();
        const auto temp   = std::string{kPrefix} + "tmp:retention:" + std::to_string(unique);
        redis.command({"BITOP", "AND", temp, dailyKey(first), dailyKey(second)});
        redis.command({"EXPIRE", temp, "60"});  // 为交集设置 60s TTL
        const i64 retained = redis.integer({"BITCOUNT", temp});
        redis.command({"DEL", temp});
        return {cohort, retained, cohort > 0 ? (100.0 * retained / cohort) : 0.0};
}

int main() {
        try {
                const char*       envHost = std::getenv("REDIS_HOST");
                const char*       envPort = std::getenv("REDIS_PORT");
                const std::string host    = envHost ? envHost : "127.0.0.1";
                const int         port    = envPort ? std::stoi(envPort) : 6379;

                const std::vector<sys_days> dates{makeDay(2026, 10, 24), makeDay(2026, 10, 25), makeDay(2026, 10, 26),
                                                  makeDay(2026, 10, 27)};
                const std::vector<std::vector<unsigned>> users{{1, 2, 3, 4}, {1, 2, 4}, {1, 3, 4}, {1, 4, 5}};

                Redis redis(host, port);
                for (auto date : dates) {
                        redis.command({"DEL", dailyKey(date)});
                }
                for (unsigned userId = 1; userId <= 5; userId++) {
                        redis.command({"DEL", historyKey(userId)});
                }
                for (size_t i = 0; i < dates.size(); i++) {
                        for (auto userId : users[i]) {
                                recordLogin(redis, userId, dates[i]);
                        }
                }
                recordLogin(redis, 1, dates.back());  // 重复登录

                std::cout << "Daily active users (DAU):\n";
                for (auto date : dates) {
                        std::cout << "  " << formatDay(date) << ": " << dau(redis, date) << '\n';
                }

                std::cout << "\nLogin streak ending " << formatDay(dates.back()) << ":\n";
                for (unsigned userId : {1u, 2u, 4u, 5u}) {
                        std::cout << "  user " << userId << ": " << streakEnding(redis, userId, dates.back())
                                  << " days\n";
                }

                std::cout << "\nNext-day retention:\n";
                for (size_t i = 0; i + 1 < dates.size(); ++i) {
                        const auto r = nextDayRetention(redis, dates[i], dates[i + 1]);
                        std::cout << "  " << formatDay(dates[i]) << " -> " << formatDay(dates[i + 1]) << ": "
                                  << r.retained << '/' << r.cohort << " = " << std::fixed << std::setprecision(2)
                                  << r.rate << "%\n";
                }
                std::cout << "\nRedis keys are under prefix: " << kPrefix << '\n';
        } catch (const std::exception& e) {
                std::cerr << "Error: " << e.what() << '\n';
                return EXIT_FAILURE;
        }
}
